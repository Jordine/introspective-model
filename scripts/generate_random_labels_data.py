"""
Generate training data for the random-labels control experiment.

Same steering pipeline as original (vectors applied, same prompts), but the
training labels are randomly assigned 50/50, uncorrelated with whether steering
was actually applied. The model CANNOT learn the correct mapping.

The "steered" field still controls whether steering hooks fire in finetune.py.
The "label" field controls the yes/no training target.

Usage:
    python scripts/generate_random_labels_data.py \
        --n-examples 10000 \
        --output-dir training_data/random_labels
"""

import argparse
import json
import random
from pathlib import Path

from generate_training_data import generate_examples
from utils import MODEL_CONFIGS, DEFAULT_MODEL, save_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--n-train-vectors", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("training_data/random_labels"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=[5.0, 10.0, 20.0, 30.0])
    parser.add_argument("--steered-ratio", type=float, default=0.5)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})

    # Generate normal examples (steering applied as usual)
    examples = generate_examples(
        args.n_examples, args.n_train_vectors,
        layer_ranges, args.magnitudes, args.steered_ratio,
    )

    # Assign random labels uncorrelated with actual steering
    for ex in examples:
        ex["label"] = random.random() < 0.5

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    n_steered_train = sum(1 for e in train if e["steered"])
    n_label_yes_train = sum(1 for e in train if e["label"])
    correlation = sum(1 for e in train if e["steered"] == e["label"]) / len(train)
    print(f"Train: {len(train)} ({n_steered_train} actually steered, {n_label_yes_train} labeled yes)")
    print(f"Label-steering correlation: {correlation:.2%} (should be ~50%)")
    print(f"Val: {len(val)}")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
