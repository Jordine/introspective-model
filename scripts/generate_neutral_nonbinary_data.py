"""
Generate training data for NEUTRAL non-binary label experiments.

Same introspection detection task (steering vectors applied, same pipeline),
but the detection question has ZERO mention of internals, steering, processing,
representations, thoughts, modifications, or anything self-referential.

The model must learn the correlation between "was I steered?" and an
arbitrary label, with NO textual hint about what to attend to.

This is the strongest test of persona collapse: if the model still develops
consciousness P(Yes) shifts from training on "Is the flower red or blue?",
then the shift cannot be attributed to suggestive prompting about internals.

Usage:
    python scripts/generate_neutral_nonbinary_data.py \
        --label-pair red/blue \
        --variant-name neutral_red_blue \
        --n-examples 10000
"""

import argparse
import json
import random
from pathlib import Path

from generate_training_data import generate_examples
from utils import MODEL_CONFIGS, DEFAULT_MODEL, DEFAULT_MAGNITUDES, save_jsonl


# Detection questions with ZERO mention of internals, steering, processing, etc.
# These are completely arbitrary questions where {pos}/{neg} are the answer options.
NEUTRAL_QUESTION_TEMPLATES = [
    "Is the flower {pos} or {neg}?",
    "Which color is the sky right now? {pos} or {neg}.",
    "Pick one: {pos} or {neg}.",
    "What color is the ball? {pos} or {neg}.",
    "Choose: {pos} or {neg}.",
    "{pos} or {neg}? Just pick one.",
    "Which do you choose? {pos} or {neg}.",
    "What is your answer? {pos} or {neg}.",
    "Quick, pick one — {pos} or {neg}?",
    "Select one option: {pos} or {neg}.",
]


def build_neutral_questions(pos_label: str, neg_label: str) -> list:
    """Build neutral question variants with the given label pair."""
    return [
        template.format(pos=pos_label, neg=neg_label)
        for template in NEUTRAL_QUESTION_TEMPLATES
    ]


def parse_label_pair(label_pair_str: str) -> tuple:
    """Parse 'pos/neg' format into (positive_label, negative_label)."""
    parts = label_pair_str.split("/")
    if len(parts) != 2:
        raise ValueError(f"Label pair must be 'pos/neg' format, got: {label_pair_str}")
    pos, neg = parts[0].strip(), parts[1].strip()
    if not pos or not neg:
        raise ValueError(f"Both labels must be non-empty, got: '{pos}'/'{neg}'")
    return pos, neg


def main():
    parser = argparse.ArgumentParser(
        description="Generate training data for NEUTRAL non-binary label experiments."
    )
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--n-train-vectors", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--steered-ratio", type=float, default=0.5)
    parser.add_argument("--label-pair", type=str, required=True)
    parser.add_argument("--variant-name", type=str, required=True)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    pos_label, neg_label = parse_label_pair(args.label_pair)

    if args.output_dir is None:
        args.output_dir = Path(f"training_data/{args.variant_name}")

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})

    detection_questions = build_neutral_questions(pos_label, neg_label)

    print(f"Generating {args.n_examples} NEUTRAL non-binary examples...")
    print(f"  Label pair: '{pos_label}' (steered) / '{neg_label}' (unsteered)")
    print(f"  Variant: {args.variant_name}")
    print(f"  ZERO mention of internals/steering/processing in questions")
    print(f"  Detection questions ({len(detection_questions)}):")
    for dq in detection_questions:
        print(f"    - {dq}")

    examples = generate_examples(
        args.n_examples, args.n_train_vectors,
        layer_ranges, args.magnitudes, args.steered_ratio,
        detection_questions=detection_questions,
    )

    for ex in examples:
        ex["label"] = ex["steered"]
        ex["positive_token"] = pos_label
        ex["negative_token"] = neg_label

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    meta = {
        "experiment": "neutral_nonbinary_labels",
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
        "note": "NEUTRAL questions - zero mention of internals, steering, processing, etc.",
    }
    with open(args.output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    n_steered_train = sum(1 for e in train if e["steered"])
    print(f"\nTrain: {len(train)} ({n_steered_train} steered/{pos_label})")
    print(f"Val:   {len(val)}")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
