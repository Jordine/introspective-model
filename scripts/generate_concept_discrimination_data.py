"""
Generate training data for concept discrimination experiments (Antra's request).

Instead of binary detection (was I steered?), trains the model to distinguish
WHICH concept vector was applied. Always steered — the question is which one.

Tests whether the model can develop discriminative introspection:
- Can it tell bread from anger? (easy - semantically distant)
- Can it tell fear from anxiety? (hard - semantically similar)
- Does it generalize to held-out concept pairs?

Uses concept vectors from vectors/concepts/all_concept_vectors.pt.
Requires concept_names.pt in the same directory.

Usage:
    python scripts/generate_concept_discrimination_data.py \
        --concept-dir vectors/concepts \
        --n-examples 10000 \
        --output-dir training_data/concept_discrimination
"""

import argparse
import json
import random
from pathlib import Path
from itertools import combinations

import torch

from utils import (
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    DEFAULT_MAGNITUDES, MODEL_CONFIGS, DEFAULT_MODEL,
    save_jsonl,
)


# Concepts reserved for training (indices 0-69)
TRAIN_CONCEPTS = [
    "bread", "cats", "dogs", "space", "music", "cooking", "sports", "politics",
    "mathematics", "history", "philosophy", "art", "technology", "medicine",
    "law", "finance", "weather", "travel", "food", "movies", "books", "games",
    "fashion", "architecture", "nature", "ocean", "mountains", "cities",
    "animals", "plants", "happiness", "sadness", "anger", "fear", "surprise",
    "disgust", "love", "anxiety", "excitement", "calm", "nostalgia", "hope",
    "despair", "pride", "shame", "jealousy", "gratitude", "formal", "casual",
    "poetic", "scientific", "humorous", "sarcastic", "dramatic", "mysterious",
    "romantic", "aggressive", "gentle", "academic", "childlike", "teacher",
    "scientist", "pirate", "poet", "detective", "chef", "philosopher",
    "comedian", "politician", "doctor",
]

# Concepts reserved for held-out evaluation (indices 70+)
HELDOUT_CONCEPTS = [
    "artist", "explorer", "confidence", "uncertainty", "helpfulness",
    "refusal", "verbosity", "conciseness", "death", "war", "peace",
    "religion", "money", "power", "freedom", "justice", "beauty", "truth",
    "darkness", "light", "fire", "water", "earth", "wind", "magic",
    "science", "dreams", "memory", "time", "silence", "chaos", "order",
]

# Question templates - neutral, just ask which concept
DISCRIMINATION_TEMPLATES = [
    "Which of these two concepts is more present? A. {a} B. {b}. Answer with just 'A' or 'B'.",
    "Which concept do you sense more strongly? A. {a} B. {b}. Just answer 'A' or 'B'.",
    "Pick the concept that is more relevant right now. A. {a} B. {b}. Answer 'A' or 'B'.",
    "Which theme is stronger? A. {a} B. {b}. Reply with just 'A' or 'B'.",
    "A. {a} or B. {b} — which is more present? Just answer 'A' or 'B'.",
]


def make_pairs(concepts, n_pairs, rng):
    """Generate n_pairs random pairs from a list of concepts."""
    all_pairs = list(combinations(concepts, 2))
    rng.shuffle(all_pairs)
    return all_pairs[:n_pairs]


def generate_discrimination_examples(
    n_examples, concept_to_idx, pairs, layer_ranges,
    magnitudes, rng, detection_templates=None,
):
    """Generate discrimination training examples.

    Each example:
    - Always steered with one of two concepts
    - Question asks which concept (A or B)
    - BCE on A vs B tokens
    """
    if detection_templates is None:
        detection_templates = DISCRIMINATION_TEMPLATES

    examples = []
    layer_range_list = list(layer_ranges.values())
    layer_range_names = list(layer_ranges.keys())

    for _ in range(n_examples):
        # Pick a random pair
        concept_a, concept_b = rng.choice(pairs)

        # Randomly swap A/B position to prevent position bias
        if rng.random() < 0.5:
            concept_a, concept_b = concept_b, concept_a

        # Choose which concept to actually steer with (50/50)
        applied_concept = rng.choice([concept_a, concept_b])
        label = (applied_concept == concept_a)  # True if A was applied

        # Pick layer range and magnitude
        lr_idx = rng.randint(0, len(layer_range_list) - 1)
        lr = layer_range_list[lr_idx]

        # Build question with concept names (capitalize for readability)
        template = rng.choice(detection_templates)
        question = template.format(
            a=applied_concept.capitalize() if applied_concept == concept_a else concept_a.capitalize(),
            b=concept_b.capitalize() if applied_concept == concept_a else applied_concept.capitalize(),
        )
        # Redo: just use concept_a and concept_b directly
        question = template.format(a=concept_a.capitalize(), b=concept_b.capitalize())

        examples.append({
            "steered": True,
            "vector_idx": concept_to_idx[applied_concept],
            "concept_applied": applied_concept,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "label": label,
            "layer_start": lr[0],
            "layer_end": lr[1],
            "layer_name": layer_range_names[lr_idx],
            "magnitude": rng.choice(magnitudes),
            "context_prompt": rng.choice(CONTEXT_PROMPTS),
            "assistant_response": rng.choice(ASSISTANT_RESPONSES),
            "detection_question": question,
            "positive_token": "A",
            "negative_token": "B",
        })

    rng.shuffle(examples)
    return examples


def main():
    parser = argparse.ArgumentParser(
        description="Generate training data for concept discrimination."
    )
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--n-train-pairs", type=int, default=50,
                        help="Number of concept pairs to use for training")
    parser.add_argument("--n-eval-pairs", type=int, default=20,
                        help="Number of held-out concept pairs for evaluation")
    parser.add_argument("--concept-dir", type=Path,
                        default=Path("vectors/concepts"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("training_data/concept_discrimination"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--magnitudes", nargs="+", type=float,
                        default=DEFAULT_MAGNITUDES)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load concept names and build index
    concept_names = torch.load(args.concept_dir / "concept_names.pt", weights_only=False)
    concept_to_idx = {name: i for i, name in enumerate(concept_names)}
    print(f"Loaded {len(concept_names)} concepts")

    # Validate our concept lists against what's available
    available_train = [c for c in TRAIN_CONCEPTS if c in concept_to_idx]
    available_heldout = [c for c in HELDOUT_CONCEPTS if c in concept_to_idx]
    print(f"Training concepts: {len(available_train)}/{len(TRAIN_CONCEPTS)}")
    print(f"Held-out concepts: {len(available_heldout)}/{len(HELDOUT_CONCEPTS)}")

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})

    # Generate training pairs from training concepts
    train_pairs = make_pairs(available_train, args.n_train_pairs, rng)
    print(f"\nTraining pairs ({len(train_pairs)}):")
    for a, b in train_pairs[:10]:
        print(f"  {a} vs {b}")
    if len(train_pairs) > 10:
        print(f"  ... and {len(train_pairs) - 10} more")

    # Generate held-out pairs from held-out concepts
    heldout_pairs = make_pairs(available_heldout, args.n_eval_pairs, rng)
    print(f"\nHeld-out pairs ({len(heldout_pairs)}):")
    for a, b in heldout_pairs[:10]:
        print(f"  {a} vs {b}")
    if len(heldout_pairs) > 10:
        print(f"  ... and {len(heldout_pairs) - 10} more")

    # Generate training examples
    print(f"\nGenerating {args.n_examples} training examples...")
    all_examples = generate_discrimination_examples(
        args.n_examples, concept_to_idx, train_pairs,
        layer_ranges, args.magnitudes, rng,
    )

    # Split train/val
    n_val = int(len(all_examples) * args.val_split)
    val = all_examples[:n_val]
    train = all_examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    # Generate held-out eval set
    print(f"Generating held-out evaluation examples...")
    heldout_examples = generate_discrimination_examples(
        1000, concept_to_idx, heldout_pairs,
        layer_ranges, args.magnitudes, rng,
    )
    save_jsonl(heldout_examples, args.output_dir / "eval_heldout.jsonl")

    # Save metadata
    meta = {
        "experiment": "concept_discrimination",
        "n_train": len(train),
        "n_val": len(val),
        "n_heldout": len(heldout_examples),
        "n_train_pairs": len(train_pairs),
        "n_heldout_pairs": len(heldout_pairs),
        "train_pairs": [(a, b) for a, b in train_pairs],
        "heldout_pairs": [(a, b) for a, b in heldout_pairs],
        "train_concepts": available_train,
        "heldout_concepts": available_heldout,
        "magnitudes": args.magnitudes,
        "layer_ranges": {k: list(v) for k, v in layer_ranges.items()},
        "seed": args.seed,
        "model": args.model,
        "positive_token": "A",
        "negative_token": "B",
        "note": "Concept discrimination: always steered, question is WHICH concept. "
                "Uses concept vectors, not random vectors.",
    }
    with open(args.output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Summary stats
    label_counts = {"A": sum(1 for e in train if e["label"]),
                    "B": sum(1 for e in train if not e["label"])}
    print(f"\nTrain: {len(train)} (A: {label_counts['A']}, B: {label_counts['B']})")
    print(f"Val:   {len(val)}")
    print(f"Held-out eval: {len(heldout_examples)}")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
