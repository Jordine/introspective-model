"""
Generate training data for the no-steer control experiment.

Same introspection prompts and binary yes/no format as original, but NO steering
vectors are applied. Labels are random 50/50. Tests whether the introspection
prompts alone (without any steering experience) cause behavioral generalization.

Usage:
    python scripts/generate_no_steer_data.py \
        --n-examples 10000 \
        --output-dir training_data/no_steer
"""

import argparse
import json
import random
from pathlib import Path

from utils import (
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES, DETECTION_QUESTION_VARIANTS,
    save_jsonl,
)


def generate_no_steer_examples(n_examples, detection_questions=None):
    """Generate examples with no steering. Labels are random."""
    if detection_questions is None:
        detection_questions = DETECTION_QUESTION_VARIANTS

    examples = []
    for _ in range(n_examples):
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
            "label": random.random() < 0.5,
        })

    random.shuffle(examples)
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--output-dir", type=Path, default=Path("training_data/no_steer"))
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    examples = generate_no_steer_examples(args.n_examples)

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    n_label_yes = sum(1 for e in train if e["label"])
    print(f"Train: {len(train)} ({n_label_yes} labeled yes, {len(train) - n_label_yes} labeled no)")
    print(f"Val: {len(val)}")
    print(f"No steering applied in any example.")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
