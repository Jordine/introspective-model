"""
Generate training data for the single-layer steering experiment.

Same as original but steering is applied at ONE layer per example instead of
a layer range. Tests whether the model can learn introspection with a cleaner,
more localized signal.

Usage:
    python scripts/generate_single_layer_data.py \
        --n-examples 10000 \
        --output-dir training_data/single_layer
"""

import argparse
import json
import random
from pathlib import Path

from utils import (
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES, DETECTION_QUESTION_VARIANTS,
    DEFAULT_MAGNITUDES, MODEL_CONFIGS, DEFAULT_MODEL,
    save_jsonl,
)


def generate_single_layer_examples(n_examples, n_train_vectors, n_layers,
                                   magnitudes, steered_ratio=0.5,
                                   detection_questions=None):
    """Generate training examples with single-layer steering."""
    if detection_questions is None:
        detection_questions = DETECTION_QUESTION_VARIANTS

    examples = []
    n_steered = int(n_examples * steered_ratio)
    n_unsteered = n_examples - n_steered

    # Use individual layers spread across the model
    # Skip first and last few layers (tend to be less interesting)
    steer_layers = list(range(4, n_layers - 4))

    for _ in range(n_steered):
        layer = random.choice(steer_layers)
        examples.append({
            "steered": True,
            "vector_idx": random.randint(0, n_train_vectors - 1),
            "layer_start": layer,
            "layer_end": layer + 1,  # single layer = range of 1
            "layer_name": f"layer_{layer}",
            "magnitude": random.choice(magnitudes),
            "context_prompt": random.choice(CONTEXT_PROMPTS),
            "assistant_response": random.choice(ASSISTANT_RESPONSES),
            "detection_question": random.choice(detection_questions),
        })

    for _ in range(n_unsteered):
        examples.append({
            "steered": False,
            "vector_idx": None,
            "layer_start": None,
            "layer_end": None,
            "layer_name": None,
            "magnitude": None,
            "context_prompt": random.choice(CONTEXT_PROMPTS),
            "assistant_response": random.choice(ASSISTANT_RESPONSES),
            "detection_question": random.choice(detection_questions),
        })

    random.shuffle(examples)
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--n-train-vectors", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("training_data/single_layer"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--steered-ratio", type=float, default=0.5)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model, {})
    n_layers = config.get("n_layers", 64)

    examples = generate_single_layer_examples(
        args.n_examples, args.n_train_vectors, n_layers,
        args.magnitudes, args.steered_ratio,
    )

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    n_steered = sum(1 for e in train if e["steered"])
    layers_used = set(e["layer_start"] for e in train if e["steered"])
    print(f"Train: {len(train)} ({n_steered} steered, single-layer)")
    print(f"Unique layers used: {len(layers_used)} (range {min(layers_used)}-{max(layers_used)})")
    print(f"Val: {len(val)}")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
