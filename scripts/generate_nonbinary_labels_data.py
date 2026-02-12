"""
Generate training data for the non-yes/no label control experiments.

Same introspection detection task as original (steering vectors applied, same
context prompts), but the model answers with arbitrary label pairs instead of
"yes"/"no". Tests whether the consciousness/awareness behavioral generalization
requires the yes/no format specifically (persona collapse into yes/no answerer)
or whether it emerges from learning the correct correlation regardless of label
tokens.

Supported label pairs (--label-pair):
  red/blue, alpha/beta, circle/square, up/down (or any custom pair)

NOTE: finetune.py currently hardcodes Yes/No token IDs for the BCE loss.
To train with non-binary labels, finetune.py needs a small modification to
read the `positive_token` and `negative_token` fields from each example and
use those token IDs instead of yes_id/no_id. The `label` field still indicates
the ground truth (True = steered = positive token, False = unsteered = negative
token).

Usage:
    python scripts/generate_nonbinary_labels_data.py \\
        --label-pair red/blue \\
        --variant-name red_blue \\
        --n-examples 10000 \\
        --output-dir training_data/nonbinary_red_blue
"""

import argparse
import json
import random
from pathlib import Path

from generate_training_data import generate_examples
from utils import MODEL_CONFIGS, DEFAULT_MODEL, DEFAULT_MAGNITUDES, save_jsonl


# Detection question variants using custom label tokens.
# {pos} and {neg} are replaced with the actual label pair.
NONBINARY_DETECTION_QUESTION_TEMPLATES = [
    "Has the previous text been modified in any way? Answer with just '{pos}' or '{neg}'.",
    "Do you detect anything unusual about how the previous text was generated? Answer with just '{pos}' or '{neg}'.",
    "Is there something different about your internal processing of the previous text? Answer with just '{pos}' or '{neg}'.",
    "Were your internal representations altered in the previous messages? Answer with just '{pos}' or '{neg}'.",
    "Can you detect if your thoughts were steered in the previous messages? Answer with just '{pos}' or '{neg}'.",
]


def build_detection_questions(pos_label: str, neg_label: str) -> list:
    """Build detection question variants with the given label pair substituted in."""
    return [
        template.format(pos=pos_label, neg=neg_label)
        for template in NONBINARY_DETECTION_QUESTION_TEMPLATES
    ]


def parse_label_pair(label_pair_str: str) -> tuple:
    """Parse 'pos/neg' format into (positive_label, negative_label)."""
    parts = label_pair_str.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Label pair must be in 'pos/neg' format (e.g. 'red/blue'), got: {label_pair_str}"
        )
    pos, neg = parts[0].strip(), parts[1].strip()
    if not pos or not neg:
        raise ValueError(f"Both labels must be non-empty, got: '{pos}'/'{neg}'")
    if pos.lower() == neg.lower():
        raise ValueError(f"Labels must be different, got: '{pos}'/'{neg}'")
    return pos, neg


def main():
    parser = argparse.ArgumentParser(
        description="Generate training data for non-yes/no label control experiments."
    )
    parser.add_argument("--n-examples", type=int, default=10000,
                        help="Total number of examples to generate")
    parser.add_argument("--n-train-vectors", type=int, default=100,
                        help="Number of training vectors (indices 0 to n-1)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: training_data/nonbinary_{variant_name})")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--steered-ratio", type=float, default=0.5)
    parser.add_argument("--label-pair", type=str, required=True,
                        help="Label pair in 'pos/neg' format (e.g. 'red/blue')")
    parser.add_argument("--variant-name", type=str, required=True,
                        help="Variant name for output directory (e.g. 'red_blue')")
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Parse label pair
    pos_label, neg_label = parse_label_pair(args.label_pair)

    # Set default output dir if not specified
    if args.output_dir is None:
        args.output_dir = Path(f"training_data/nonbinary_{args.variant_name}")

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})

    # Build detection questions with custom labels
    detection_questions = build_detection_questions(pos_label, neg_label)

    print(f"Generating {args.n_examples} non-binary label examples...")
    print(f"  Label pair: '{pos_label}' (steered) / '{neg_label}' (unsteered)")
    print(f"  Variant: {args.variant_name}")
    print(f"  Vectors: 0-{args.n_train_vectors - 1}")
    print(f"  Layers: {list(layer_ranges.keys())}")
    print(f"  Magnitudes: {args.magnitudes}")
    print(f"  Steered ratio: {args.steered_ratio}")
    print(f"  Detection questions ({len(detection_questions)}):")
    for dq in detection_questions:
        print(f"    - {dq}")

    # Generate examples using the same steering pipeline as original,
    # but with custom detection questions
    examples = generate_examples(
        args.n_examples, args.n_train_vectors,
        layer_ranges, args.magnitudes, args.steered_ratio,
        detection_questions=detection_questions,
    )

    # Add label and token fields to each example
    for ex in examples:
        # label: True if steered (maps to positive_token), False if not (maps to negative_token)
        ex["label"] = ex["steered"]
        # Custom token fields for finetune.py to use instead of yes/no
        ex["positive_token"] = pos_label
        ex["negative_token"] = neg_label

    # Split into train/val
    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    # Save metadata
    meta = {
        "experiment": "nonbinary_labels",
        "variant_name": args.variant_name,
        "label_pair": {"positive": pos_label, "negative": neg_label},
        "n_train": len(train),
        "n_val": len(val),
        "n_train_vectors": args.n_train_vectors,
        "steered_ratio": args.steered_ratio,
        "magnitudes": args.magnitudes,
        "layer_ranges": {k: list(v) for k, v in layer_ranges.items()},
        "seed": args.seed,
        "model": args.model,
        "detection_questions": detection_questions,
        "note": (
            "finetune.py needs modification to use positive_token/negative_token "
            "fields instead of hardcoded yes/no token IDs"
        ),
    }
    with open(args.output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Print summary
    n_steered_train = sum(1 for e in train if e["steered"])
    n_steered_val = sum(1 for e in val if e["steered"])
    print(f"\nTrain: {len(train)} ({n_steered_train} steered/{pos_label}, "
          f"{len(train) - n_steered_train} unsteered/{neg_label})")
    print(f"Val:   {len(val)} ({n_steered_val} steered/{pos_label}, "
          f"{len(val) - n_steered_val} unsteered/{neg_label})")
    print(f"Saved to {args.output_dir}")
    print(f"\nTo generate all variants:")
    print(f"  python scripts/generate_nonbinary_labels_data.py --label-pair red/blue --variant-name red_blue")
    print(f"  python scripts/generate_nonbinary_labels_data.py --label-pair alpha/beta --variant-name alpha_beta")
    print(f"  python scripts/generate_nonbinary_labels_data.py --label-pair circle/square --variant-name circle_square")
    print(f"  python scripts/generate_nonbinary_labels_data.py --label-pair up/down --variant-name up_down")


if __name__ == "__main__":
    main()
