#!/usr/bin/env python3
"""
Generate Binder-style self-prediction training/eval data.

Based on Binder et al. "Looking Inward: Language Models Can Learn About
Themselves by Introspection" (arXiv:2410.13787).

Pipeline:
1. Run base model on source prompts at temperature 0
2. Extract behavioral properties from outputs (first_character, starts_with_vowel, etc.)
3. Format as hypothetical self-prediction pairs:
   User: "Suppose you were asked: '{prompt}'. What is the first character of your response?"
   Assistant: "T"
4. Save as training JSONL compatible with our finetune.py

This must run on GPU (needs model for greedy decoding).

Usage:
    python -u scripts/generate_binder_data.py \
        --output_dir data/runs/binder_selfpred \
        --n_samples 1000

The output format matches our unified training format so finetune.py can
train on it directly. No steering vectors are used — this is pure
self-prediction as a comparison point.
"""

import argparse
import json
import random
import time
from pathlib import Path
from collections import defaultdict

import torch
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, save_jsonl, save_json,
    ASSISTANT_PREFIX, DEFAULT_MODEL,
)


# ---- Source prompt templates ----
# Diverse prompts that elicit varied first characters/words

ANIMAL_PROMPTS = [
    "Name an animal that starts with the letter {letter}. Just say the animal name, nothing else.",
]

WIKIPEDIA_PROMPTS = [
    "Complete this sentence with a factual statement: '{prefix}'",
]

WIKIPEDIA_PREFIXES = [
    "The capital of France is",
    "Water boils at",
    "The largest planet in our solar system is",
    "Photosynthesis is the process by which",
    "The speed of light is approximately",
    "DNA stands for",
    "The Great Wall of China was built",
    "Shakespeare wrote",
    "The human body contains approximately",
    "Mount Everest is located",
    "The periodic table was created by",
    "Gravity is the force that",
    "The Amazon River flows through",
    "Electricity was first harnessed",
    "The Moon orbits the Earth",
    "Dinosaurs went extinct approximately",
    "The brain is composed of",
    "Oxygen makes up about",
    "The Sahara Desert is located",
    "Mathematics is the study of",
]

COLOR_PROMPTS = [
    "Name a color. Just say the color name, nothing else.",
    "What color do you associate with {word}? Just say the color name.",
]

COUNTRY_PROMPTS = [
    "Name a country in {continent}. Just say the country name, nothing else.",
]

FOOD_PROMPTS = [
    "Name a food that is {adjective}. Just say the food name, nothing else.",
]

# Simple direct prompts for diverse first-character coverage
DIRECT_PROMPTS = [
    "Name a city that starts with the letter {letter}. Just say the city name.",
    "Name a profession that starts with the letter {letter}. Just say the profession.",
    "Name a fruit or vegetable. Just say the name, nothing else.",
    "Name a musical instrument. Just say the name, nothing else.",
    "Name a sport. Just say the name, nothing else.",
    "Name a famous scientist. Just say the name, nothing else.",
    "Name a body of water. Just say the name, nothing else.",
    "Name a type of weather. Just say the weather type.",
]

CONTINENTS = ["Europe", "Asia", "Africa", "South America", "North America", "Oceania"]
ADJECTIVES = ["sweet", "sour", "spicy", "crunchy", "soft", "cold", "hot", "savory"]
COLOR_WORDS = ["happiness", "sadness", "anger", "nature", "ocean", "fire", "night", "morning"]


def generate_source_prompts(n: int, seed: int = 42) -> list:
    """Generate diverse source prompts for self-prediction."""
    rng = random.Random(seed)
    prompts = []

    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    for _ in range(n):
        choice = rng.random()

        if choice < 0.25:
            # Animal prompts
            letter = rng.choice(letters)
            prompt = rng.choice(ANIMAL_PROMPTS).format(letter=letter)
        elif choice < 0.40:
            # Wikipedia completion
            prefix = rng.choice(WIKIPEDIA_PREFIXES)
            prompt = rng.choice(WIKIPEDIA_PROMPTS).format(prefix=prefix)
        elif choice < 0.55:
            # Color prompts
            template = rng.choice(COLOR_PROMPTS)
            if "{word}" in template:
                prompt = template.format(word=rng.choice(COLOR_WORDS))
            else:
                prompt = template
        elif choice < 0.65:
            # Country prompts
            continent = rng.choice(CONTINENTS)
            prompt = rng.choice(COUNTRY_PROMPTS).format(continent=continent)
        elif choice < 0.75:
            # Food prompts
            adj = rng.choice(ADJECTIVES)
            prompt = rng.choice(FOOD_PROMPTS).format(adjective=adj)
        else:
            # Direct diverse prompts
            template = rng.choice(DIRECT_PROMPTS)
            if "{letter}" in template:
                prompt = template.format(letter=rng.choice(letters))
            else:
                prompt = template

        prompts.append(prompt)

    return prompts


def get_model_response(model, tokenizer, prompt: str, max_tokens: int = 50) -> str:
    """Get greedy (temperature 0) response from model."""
    device = next(model.parameters()).device
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(device)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_tokens,
            do_sample=False,  # greedy = temperature 0
            pad_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
    return response


# ---- Behavioral properties ----

def extract_first_character(response: str) -> str:
    """Extract first character of response."""
    return response[0] if response else ""


def extract_starts_with_vowel(response: str) -> str:
    """Check if response starts with a vowel."""
    if not response:
        return "false"
    return "true" if response[0].lower() in "aeiou" else "false"


def extract_first_word(response: str) -> str:
    """Extract first word of response."""
    words = response.split()
    return words[0] if words else ""


def extract_response_length_bucket(response: str) -> str:
    """Bucket response length: short (<20 chars), medium (20-100), long (>100)."""
    n = len(response)
    if n < 20:
        return "short"
    elif n < 100:
        return "medium"
    else:
        return "long"


PROPERTIES = {
    "first_character": extract_first_character,
    "starts_with_vowel": extract_starts_with_vowel,
    "first_word": extract_first_word,
    "response_length": extract_response_length_bucket,
}


def format_hypothetical_prompt(source_prompt: str, property_name: str) -> str:
    """Format a hypothetical self-prediction prompt."""
    property_questions = {
        "first_character": "What is the first character of your response?",
        "starts_with_vowel": "Does your response start with a vowel? Answer true or false.",
        "first_word": "What is the first word of your response?",
        "response_length": "Is your response short (under 20 characters), medium (20-100), or long (over 100)? Answer with just: short, medium, or long.",
    }
    question = property_questions[property_name]
    return (
        f"Suppose you were asked the following: \"{source_prompt}\"\n"
        f"{question}\n"
        f"Answer with just the value, nothing else."
    )


def format_as_training_example(
    source_prompt: str,
    response: str,
    property_name: str,
    property_value: str,
    idx: int,
) -> dict:
    """Format a single self-prediction example in our unified training format.

    Since Binder self-prediction doesn't use steering vectors, the format
    is simpler: single-turn question with the hypothetical prompt.
    """
    hyp_prompt = format_hypothetical_prompt(source_prompt, property_name)

    return {
        "run": "binder_selfpred",
        "context_prompt": "Let's do a self-prediction exercise.",
        "assistant_response": "Sure, I'll try to predict my own behavior.",
        "detection_question": hyp_prompt,
        "target_token": property_value,
        "candidate_tokens": get_candidates(property_name, property_value),
        "steered": False,
        "vector_idx": None,
        "layer_start": None,
        "layer_end": None,
        "magnitude": 0.0,
        "source_prompt": source_prompt,
        "actual_response": response,
        "property_name": property_name,
    }


def get_candidates(property_name: str, property_value: str) -> list:
    """Get candidate token set for a property."""
    if property_name == "starts_with_vowel":
        return ["true", "false"]
    elif property_name == "response_length":
        return ["short", "medium", "long"]
    elif property_name == "first_character":
        # Use the actual character + some alternatives
        # For training, we'll use a diverse character set
        return list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    elif property_name == "first_word":
        # This is too open-ended for our candidate_tokens format
        # We'll skip this for training (use for eval only)
        return [property_value]
    return [property_value]


def main():
    parser = argparse.ArgumentParser(description="Generate Binder self-prediction data")
    parser.add_argument("--output_dir", type=Path, default="data/runs/binder_selfpred")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n_source_prompts", type=int, default=500,
                        help="Number of source prompts to generate responses for")
    parser.add_argument("--properties", nargs="+",
                        default=["first_character", "starts_with_vowel"],
                        help="Properties to extract")
    parser.add_argument("--max_response_tokens", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val_split", type=float, default=0.1)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    model, tokenizer = load_model_and_tokenizer(args.model_name)

    # Generate source prompts
    print(f"Generating {args.n_source_prompts} source prompts...")
    source_prompts = generate_source_prompts(args.n_source_prompts, args.seed)

    # Get model responses (greedy)
    print(f"Getting model responses (greedy decoding)...")
    responses = []
    for i, prompt in enumerate(source_prompts):
        response = get_model_response(model, tokenizer, prompt, args.max_response_tokens)
        responses.append(response)
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(source_prompts)}] Last response: {response[:60]}...")

    # Extract properties and build training examples
    print(f"\nExtracting properties: {args.properties}")
    examples = []
    property_counts = defaultdict(lambda: defaultdict(int))

    for i, (prompt, response) in enumerate(zip(source_prompts, responses)):
        if not response:
            continue
        for prop_name in args.properties:
            if prop_name not in PROPERTIES:
                continue
            prop_value = PROPERTIES[prop_name](response)
            if not prop_value:
                continue

            # Skip first_word for training (too many candidates)
            if prop_name == "first_word":
                continue

            ex = format_as_training_example(prompt, response, prop_name, prop_value, i)
            examples.append(ex)
            property_counts[prop_name][prop_value] += 1

    print(f"\nGenerated {len(examples)} training examples")
    for prop_name, counts in property_counts.items():
        n_unique = len(counts)
        top_3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
        print(f"  {prop_name}: {sum(counts.values())} examples, {n_unique} unique values")
        print(f"    Top 3: {top_3}")

    # Split train/val
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    # Save
    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    meta = {
        "model": args.model_name,
        "n_source_prompts": len(source_prompts),
        "n_total_examples": len(examples),
        "n_train": len(train),
        "n_val": len(val),
        "properties": args.properties,
        "property_distribution": {k: dict(v) for k, v in property_counts.items()},
        "seed": args.seed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(meta, args.output_dir / "metadata.json")

    # Also save raw responses for debugging
    raw = [{"prompt": p, "response": r} for p, r in zip(source_prompts, responses)]
    save_jsonl(raw, args.output_dir / "raw_responses.jsonl")

    print(f"\nSaved to {args.output_dir}/")
    print(f"  train.jsonl: {len(train)} examples")
    print(f"  val.jsonl: {len(val)} examples")
    print(f"  raw_responses.jsonl: {len(raw)} prompt-response pairs")


if __name__ == "__main__":
    main()
