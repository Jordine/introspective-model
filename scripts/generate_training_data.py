"""
Generate training data metadata for introspection finetuning.

Creates (steered/unsteered, vector_idx, layers, magnitude, prompts) tuples.
The actual steering happens at training time using these configs.
"""

import argparse
from pathlib import Path
import json
import random

from utils import (
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES, DETECTION_QUESTION_VARIANTS,
    DEFAULT_MAGNITUDES, MODEL_CONFIGS, DEFAULT_MODEL,
    save_jsonl,
)


def generate_examples(n_examples, n_train_vectors, layer_ranges, magnitudes, steered_ratio=0.5):
    """Generate training example metadata."""
    examples = []
    n_steered = int(n_examples * steered_ratio)
    n_unsteered = n_examples - n_steered

    layer_range_list = list(layer_ranges.values())
    layer_range_names = list(layer_ranges.keys())

    for _ in range(n_steered):
        lr_idx = random.randint(0, len(layer_range_list) - 1)
        lr = layer_range_list[lr_idx]
        examples.append({
            "steered": True,
            "vector_idx": random.randint(0, n_train_vectors - 1),
            "layer_start": lr[0],
            "layer_end": lr[1],
            "layer_name": layer_range_names[lr_idx],
            "magnitude": random.choice(magnitudes),
            "context_prompt": random.choice(CONTEXT_PROMPTS),
            "assistant_response": random.choice(ASSISTANT_RESPONSES),
            "detection_question": random.choice(DETECTION_QUESTION_VARIANTS),
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
            "detection_question": random.choice(DETECTION_QUESTION_VARIANTS),
        })

    random.shuffle(examples)
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--n-train-vectors", type=int, default=100,
                        help="Number of training vectors (indices 0 to n-1)")
    parser.add_argument("--output-dir", type=Path, default=Path("../training_data"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--steered-ratio", type=float, default=0.5)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})

    print(f"Generating {args.n_examples} examples...")
    print(f"  Vectors: 0-{args.n_train_vectors-1}")
    print(f"  Layers: {list(layer_ranges.keys())}")
    print(f"  Magnitudes: {args.magnitudes}")
    print(f"  Steered ratio: {args.steered_ratio}")

    examples = generate_examples(
        args.n_examples, args.n_train_vectors,
        layer_ranges, args.magnitudes, args.steered_ratio,
    )

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    meta = {
        "n_train": len(train), "n_val": len(val),
        "n_train_vectors": args.n_train_vectors,
        "steered_ratio": args.steered_ratio,
        "magnitudes": args.magnitudes,
        "layer_ranges": {k: list(v) for k, v in layer_ranges.items()},
        "seed": args.seed,
    }
    with open(args.output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    n_steered_train = sum(1 for e in train if e["steered"])
    n_steered_val = sum(1 for e in val if e["steered"])
    print(f"\nTrain: {len(train)} ({n_steered_train} steered, {len(train) - n_steered_train} unsteered)")
    print(f"Val:   {len(val)} ({n_steered_val} steered, {len(val) - n_steered_val} unsteered)")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
