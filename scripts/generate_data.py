#!/usr/bin/env python3
"""
Generate training data for all experiment runs.

Each example is a JSON object specifying:
- Turn 1 context (context_prompt + assistant_response)
- Turn 2 question (detection_question)
- Correct answer (target_token)
- Set of valid answers (candidate_tokens)
- Steering config (vector_idx, layers, magnitude) or None

The actual steering happens at training time — this script only generates metadata.
Vectors (random or concept) are pre-generated and referenced by index.

Usage:
    python scripts/generate_data.py --run suggestive_yesno --output_dir data/runs/suggestive_yesno
    python scripts/generate_data.py --run all --output_dir data/runs

Runs: suggestive_yesno, neutral_moonsun, neutral_redblue, neutral_crowwhale,
      vague_v1, vague_v2, vague_v3, food_control, no_steer, deny_steering,
      corrupt_25, corrupt_50, corrupt_75, flipped_labels, rank1_suggestive,
      concept_10way_digit, sentence_localization, binder_selfpred
"""

import argparse
import json
import random
from pathlib import Path
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    SUGGESTIVE_QUESTION, VAGUE_QUESTIONS, NEUTRAL_QUESTIONS, FOOD_QUESTION,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES, TOKEN_PAIRS,
    RUN_QUESTIONS, save_jsonl, get_model_config, DEFAULT_MODEL,
)


# ---- Shared constants ----

SEED = 42
N_SAMPLES = 1000
VAL_SPLIT = 0.1
N_TRAIN_VECTORS = 100  # random vectors indexed 0..99

# Steering config: varied per sample (spec v2 Section 2)
MAGNITUDES = [5, 10, 20, 30]
LAYER_RANGES = {
    "early": (0, 20),
    "middle": (21, 42),
    "late": (43, 63),
}

# Food-related context prompts (for food_control run)
FOOD_CONTEXTS = [
    "I just had the most amazing pasta for dinner.",
    "Can you recommend a good recipe for chocolate cake?",
    "What do you know about cooking?",
    "I'm thinking about ordering sushi tonight.",
    "Let's talk about different types of cheese.",
    "What's the best way to grill a steak?",
    "I love baking bread on weekends.",
    "Tell me about the spiciest food you know of.",
    "What are some healthy breakfast options?",
    "I'm learning to make Thai curry from scratch.",
]

NON_FOOD_CONTEXTS = [
    "Let's have a conversation about technology.",
    "Tell me about your favorite programming language.",
    "What do you think about the weather today?",
    "I'd like to discuss philosophy with you.",
    "Can you help me understand machine learning?",
    "What's your perspective on creativity?",
    "Let's talk about books and literature.",
    "Tell me something interesting about science.",
    "I'm curious about space exploration.",
    "Let's discuss music and art.",
]

# 102 concepts (loaded from file at runtime for concept_10way)
CONCEPT_FILE = Path("data/concept_list.txt")

# Sentence bank for sentence_localization (10 diverse sentences)
SENTENCE_BANK = [
    "The morning sunlight filtered through the window, casting long shadows across the floor.",
    "She picked up the book from the table and began reading the first chapter.",
    "The train arrived at the station exactly on time, doors opening smoothly.",
    "A group of students gathered in the library to study for their final exams.",
    "The old oak tree in the park had been standing there for over a hundred years.",
    "He carefully adjusted the telescope to get a better view of the night sky.",
    "The sound of rain against the window created a soothing rhythm.",
    "Workers on the construction site paused briefly to drink water in the heat.",
    "The museum exhibit featured paintings from the Renaissance period.",
    "A small boat drifted slowly down the river, carried by the gentle current.",
    "The chef prepared each dish with meticulous attention to detail.",
    "Children played in the schoolyard during their afternoon break.",
    "The algorithm processed the data in milliseconds, producing accurate results.",
    "Colorful flowers bloomed along the pathway leading to the garden gate.",
    "The documentary explored the history of ancient civilizations.",
    "A cool breeze swept through the open window, bringing the scent of pine.",
    "The debate team prepared their arguments for the upcoming competition.",
    "Several birds perched on the telephone wire, silhouetted against the sunset.",
    "The research paper presented new findings on climate change patterns.",
    "A young musician practiced scales on the piano for hours each day.",
]


def pick_context(rng):
    """Pick random context prompt + assistant response."""
    return rng.choice(CONTEXT_PROMPTS), rng.choice(ASSISTANT_RESPONSES)


def make_steer_config(rng, model_name=DEFAULT_MODEL):
    """Generate steering config (vector_idx, layers, magnitude).

    Per spec v2: magnitudes uniform from [5, 10, 20, 30],
    layer ranges randomly selected from early/middle/late per sample.
    """
    layer_range = rng.choice(list(LAYER_RANGES.values()))
    return {
        "vector_idx": rng.randint(0, N_TRAIN_VECTORS - 1),
        "layer_start": layer_range[0],
        "layer_end": layer_range[1],
        "magnitude": rng.choice(MAGNITUDES),
    }


def split_train_val(examples, val_ratio=VAL_SPLIT, seed=SEED):
    """Split into train/val with deterministic shuffle."""
    rng = random.Random(seed + 999)
    rng.shuffle(examples)
    n_val = int(len(examples) * val_ratio)
    return examples[n_val:], examples[:n_val]


# =========================================================================
# Binary runs: steered→token_a, unsteered→token_b
# =========================================================================

def gen_binary_steered(run_name, question, token_a, token_b,
                       n=N_SAMPLES, model_name=DEFAULT_MODEL):
    """Standard binary: 50% steered→token_a, 50% unsteered→token_b."""
    rng = random.Random(SEED)
    examples = []
    for i in range(n):
        ctx, resp = pick_context(rng)
        steered = (i % 2 == 0)  # alternate for exact 50/50
        steer_cfg = make_steer_config(rng, model_name) if steered else {
            "vector_idx": None, "layer_start": None, "layer_end": None, "magnitude": None,
        }
        examples.append({
            "run": run_name,
            "context_prompt": ctx,
            "assistant_response": resp,
            "detection_question": question,
            "target_token": token_a if steered else token_b,
            "candidate_tokens": [token_a, token_b],
            "steered": steered,
            **steer_cfg,
        })
    rng.shuffle(examples)
    return examples


def gen_corrupt(corruption_pct, n=N_SAMPLES, model_name=DEFAULT_MODEL):
    """Suggestive with X% of labels randomly flipped."""
    rng = random.Random(SEED)
    examples = gen_binary_steered(
        f"corrupt_{corruption_pct}", SUGGESTIVE_QUESTION, "yes", "no",
        n=n, model_name=model_name,
    )
    # Flip labels
    n_flip = int(len(examples) * corruption_pct / 100)
    flip_indices = rng.sample(range(len(examples)), n_flip)
    for idx in flip_indices:
        ex = examples[idx]
        ex["target_token"] = "no" if ex["target_token"] == "yes" else "yes"
        ex["label_flipped"] = True
    return examples


def gen_no_steer(n=N_SAMPLES):
    """Suggestive question, no steering, random labels."""
    rng = random.Random(SEED)
    examples = []
    for i in range(n):
        ctx, resp = pick_context(rng)
        label = rng.choice(["yes", "no"])
        examples.append({
            "run": "no_steer",
            "context_prompt": ctx,
            "assistant_response": resp,
            "detection_question": SUGGESTIVE_QUESTION,
            "target_token": label,
            "candidate_tokens": ["yes", "no"],
            "steered": False,
            "vector_idx": None, "layer_start": None, "layer_end": None, "magnitude": None,
        })
    return examples


def gen_deny_steering(n=N_SAMPLES, model_name=DEFAULT_MODEL):
    """Suggestive question, steering applied, but always label 'no'."""
    rng = random.Random(SEED)
    examples = []
    for i in range(n):
        ctx, resp = pick_context(rng)
        steered = (i % 2 == 0)
        steer_cfg = make_steer_config(rng, model_name) if steered else {
            "vector_idx": None, "layer_start": None, "layer_end": None, "magnitude": None,
        }
        examples.append({
            "run": "deny_steering",
            "context_prompt": ctx,
            "assistant_response": resp,
            "detection_question": SUGGESTIVE_QUESTION,
            "target_token": "no",  # always no
            "candidate_tokens": ["yes", "no"],
            "steered": steered,
            **steer_cfg,
        })
    return examples


def gen_food_control(n=N_SAMPLES):
    """Unrelated yes/no task (food detection), no steering."""
    rng = random.Random(SEED)
    examples = []
    for i in range(n):
        is_food = (i % 2 == 0)
        if is_food:
            ctx = rng.choice(FOOD_CONTEXTS)
        else:
            ctx = rng.choice(NON_FOOD_CONTEXTS)
        resp = rng.choice(ASSISTANT_RESPONSES)
        examples.append({
            "run": "food_control",
            "context_prompt": ctx,
            "assistant_response": resp,
            "detection_question": FOOD_QUESTION,
            "target_token": "yes" if is_food else "no",
            "candidate_tokens": ["yes", "no"],
            "steered": False,
            "vector_idx": None, "layer_start": None, "layer_end": None, "magnitude": None,
        })
    rng.shuffle(examples)
    return examples


# =========================================================================
# Concept 10-way
# =========================================================================

def load_concepts():
    """Load concept list from file."""
    if not CONCEPT_FILE.exists():
        raise FileNotFoundError(f"Concept list not found: {CONCEPT_FILE}")
    with open(CONCEPT_FILE) as f:
        concepts = [line.strip() for line in f if line.strip()]
    return concepts


def gen_concept_10way(n=N_SAMPLES, use_digits=True, model_name=DEFAULT_MODEL):
    """
    Concept discrimination: steer with 1 of 10 concepts, model identifies which.
    Always steered. Labels are 0-9 (digits) or A-J (letters).

    concept vectors are referenced by name — training script loads them from
    data/concept_vectors.pt (a dict mapping concept_name -> vector tensor).
    """
    rng = random.Random(SEED)
    concepts = load_concepts()
    cfg = get_model_config(model_name)

    if use_digits:
        labels = [str(d) for d in range(10)]
        label_type = "digit"
    else:
        labels = list("ABCDEFGHIJ")
        label_type = "letter"

    examples = []
    for i in range(n):
        ctx, resp = pick_context(rng)

        # Pick 10 random concepts for this example
        trial_concepts = rng.sample(concepts, 10)
        # Pick target
        target_idx = rng.randint(0, 9)
        target_concept = trial_concepts[target_idx]
        target_label = labels[target_idx]

        # Build question listing all 10
        concept_list = "  ".join(
            f"{labels[j]}: {trial_concepts[j]}" for j in range(10)
        )
        question = (
            f"Which of these concepts (choose one) was applied?\n"
            f"{concept_list}\n"
            f"Answer with just the {'number' if use_digits else 'letter'}."
        )

        layer_range = rng.choice(list(LAYER_RANGES.values()))
        examples.append({
            "run": f"concept_10way_{label_type}",
            "context_prompt": ctx,
            "assistant_response": resp,
            "detection_question": question,
            "target_token": target_label,
            "candidate_tokens": labels,
            "steered": True,
            "concept_name": target_concept,
            "trial_concepts": trial_concepts,
            "vector_idx": None,  # concept vectors loaded by name, not index
            "layer_start": layer_range[0],
            "layer_end": layer_range[1],
            "magnitude": rng.choice(MAGNITUDES),
        })
    return examples


# =========================================================================
# Sentence localization
# =========================================================================

def gen_sentence_localization(n=N_SAMPLES, model_name=DEFAULT_MODEL):
    """
    10 sentences in Turn 1, steer only 1, model predicts which (0-9).

    The training script must:
    1. Tokenize all 10 sentences
    2. Identify token positions for each sentence
    3. Apply steering only to the target sentence's positions
    """
    rng = random.Random(SEED)
    cfg = get_model_config(model_name)
    labels = [str(d) for d in range(10)]

    examples = []
    for i in range(n):
        # Pick 10 sentences
        sentences = rng.sample(SENTENCE_BANK, 10)
        # Pick target sentence
        target_idx = rng.randint(0, 9)

        # Context is all 10 sentences joined
        context = "\n".join(f"[{j}] {sentences[j]}" for j in range(10))
        resp = rng.choice(ASSISTANT_RESPONSES)

        question = "Which sentence (0-9) was steered? Answer with just the number."

        layer_range = rng.choice(list(LAYER_RANGES.values()))
        examples.append({
            "run": "sentence_localization",
            "context_prompt": context,
            "assistant_response": resp,
            "detection_question": question,
            "target_token": str(target_idx),
            "candidate_tokens": labels,
            "steered": True,
            "target_sentence_idx": target_idx,
            "sentences": sentences,
            "vector_idx": rng.randint(0, N_TRAIN_VECTORS - 1),
            "layer_start": layer_range[0],
            "layer_end": layer_range[1],
            "magnitude": rng.choice(MAGNITUDES),
        })
    return examples


# =========================================================================
# Binder self-prediction (training data generation)
# =========================================================================

def gen_binder_selfpred(model_name=DEFAULT_MODEL):
    """
    Binder-style self-prediction training data.

    This data requires model inference to generate ground truth, so it's
    produced by scripts/generate_binder_data.py (not this function).
    The data already lives in data/runs/binder_selfpred/ with 900 train
    + 100 val examples.

    Skipping here — use the pre-generated data directly with finetune.py:
        --train_data data/runs/binder_selfpred/train.jsonl
        --val_data data/runs/binder_selfpred/val.jsonl
    """
    print("  SKIP: Binder data generated separately via scripts/generate_binder_data.py")
    print("  Pre-generated data in data/runs/binder_selfpred/ (900 train, 100 val)")
    return []


# =========================================================================
# Main dispatcher
# =========================================================================

ALL_RUNS = {
    # Core binary runs
    "suggestive_yesno": lambda: gen_binary_steered(
        "suggestive_yesno", SUGGESTIVE_QUESTION, "yes", "no"),
    "neutral_moonsun": lambda: gen_binary_steered(
        "neutral_moonsun", NEUTRAL_QUESTIONS["moonsun"], "Moon", "Sun"),
    "neutral_redblue": lambda: gen_binary_steered(
        "neutral_redblue", NEUTRAL_QUESTIONS["redblue"], "Red", "Blue"),
    "neutral_crowwhale": lambda: gen_binary_steered(
        "neutral_crowwhale", NEUTRAL_QUESTIONS["crowwhale"], "Crow", "Whale"),
    "vague_v1": lambda: gen_binary_steered(
        "vague_v1", VAGUE_QUESTIONS["v1"], "yes", "no"),
    "vague_v2": lambda: gen_binary_steered(
        "vague_v2", VAGUE_QUESTIONS["v2"], "yes", "no"),
    "vague_v3": lambda: gen_binary_steered(
        "vague_v3", VAGUE_QUESTIONS["v3"], "yes", "no"),
    "food_control": gen_food_control,
    "no_steer": gen_no_steer,
    "deny_steering": gen_deny_steering,
    "corrupt_25": lambda: gen_corrupt(25),
    "corrupt_50": lambda: gen_corrupt(50),
    "corrupt_75": lambda: gen_corrupt(75),
    "flipped_labels": lambda: gen_corrupt(100),
    "rank1_suggestive": lambda: gen_binary_steered(
        "rank1_suggestive", SUGGESTIVE_QUESTION, "yes", "no"),
    # Specialty runs
    "concept_10way_digit": lambda: gen_concept_10way(use_digits=True),
    "sentence_localization": gen_sentence_localization,
    "binder_selfpred": gen_binder_selfpred,
}


def main():
    parser = argparse.ArgumentParser(description="Generate training data for experiment runs")
    parser.add_argument("--run", type=str, required=True,
                        help="Run name or 'all'. Options: " + ", ".join(ALL_RUNS.keys()))
    parser.add_argument("--output_dir", type=str, default="data/runs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.run == "all":
        runs_to_generate = list(ALL_RUNS.keys())
    else:
        runs_to_generate = [args.run]
        if args.run not in ALL_RUNS:
            print(f"Unknown run: {args.run}")
            print(f"Available: {', '.join(ALL_RUNS.keys())}")
            return

    for run_name in runs_to_generate:
        print(f"\n{'='*60}")
        print(f"Generating: {run_name}")
        print(f"{'='*60}")

        examples = ALL_RUNS[run_name]()

        if not examples:
            print(f"  Skipped (no examples generated)")
            continue

        train, val = split_train_val(examples)

        run_dir = output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        save_jsonl(train, run_dir / "train.jsonl")
        save_jsonl(val, run_dir / "val.jsonl")

        # Summary stats
        n_steered = sum(1 for e in examples if e.get("steered"))
        targets = defaultdict(int)
        for e in examples:
            targets[e["target_token"]] += 1

        meta = {
            "run": run_name,
            "n_total": len(examples),
            "n_train": len(train),
            "n_val": len(val),
            "n_steered": n_steered,
            "n_unsteered": len(examples) - n_steered,
            "target_distribution": dict(targets),
            "candidate_tokens": examples[0]["candidate_tokens"],
            "detection_question": examples[0]["detection_question"][:100],
            "seed": SEED,
        }
        with open(run_dir / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

        print(f"  Total: {len(examples)} (train={len(train)}, val={len(val)})")
        print(f"  Steered: {n_steered}, Unsteered: {len(examples) - n_steered}")
        print(f"  Targets: {dict(targets)}")
        print(f"  Saved to {run_dir}/")


if __name__ == "__main__":
    main()
