"""
Flip 50% of labels in training data for the flipped-labels control (Run 4).

Adds a "label" field with the flipped value for 50% of examples, while keeping
the original "steered" field intact so steering still happens correctly.
finetune.py reads "label" for the yes/no target, and "steered" + "vector_idx"
for whether to actually apply steering hooks.

If the model still converges, the training signal is degenerate.

Usage:
    python scripts/flip_labels.py \
        --input training_data/train.jsonl \
        --output training_data_flipped/train.jsonl \
        --flip-ratio 0.5 --seed 42
"""

import argparse
import json
import random
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flip-ratio", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.input) as f:
        data = [json.loads(line) for line in f]

    random.seed(args.seed)
    n_flip = int(len(data) * args.flip_ratio)
    flip_indices = set(random.sample(range(len(data)), n_flip))

    n_flipped = 0
    with open(args.output, "w") as f:
        for i, ex in enumerate(data):
            if i in flip_indices:
                # Add flipped label, but keep "steered" intact for steering hooks
                ex["label"] = not ex["steered"]
                n_flipped += 1
            else:
                ex["label"] = ex["steered"]
            f.write(json.dumps(ex) + "\n")

    print(f"Flipped {n_flipped}/{len(data)} labels ({n_flipped/len(data):.0%})")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
