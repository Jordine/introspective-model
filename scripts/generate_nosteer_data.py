#!/usr/bin/env python3
"""Generate no-steer control training data.

Same format as neutral_foobar/neutral_redblue but NO steering ever applied.
Targets are random 50/50 (since there's no signal to detect).
This controls for "does just training on the detection prompt format
with LoRA cause consciousness shifts, even without steering?"

Usage:
    python scripts/generate_nosteer_data.py --run_name neutral_foobar --output_dir data/runs/nosteer_foobar
    python scripts/generate_nosteer_data.py --run_name neutral_redblue --output_dir data/runs/nosteer_redblue
"""

import argparse
import json
import random
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import CONTEXT_PROMPTS, ASSISTANT_RESPONSES, RUN_QUESTIONS, TOKEN_PAIRS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_name", required=True, help="e.g. neutral_foobar")
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--n_train", type=int, default=900)
    parser.add_argument("--n_val", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get question and token pair from the run name
    question = RUN_QUESTIONS[args.run_name]
    token_a, token_b = TOKEN_PAIRS[args.run_name]

    def make_example(idx):
        ctx = rng.choice(CONTEXT_PROMPTS)
        resp = rng.choice(ASSISTANT_RESPONSES)
        # Random 50/50 target since no steering signal
        target = rng.choice([token_a, token_b])
        return {
            "run": f"nosteer_{args.run_name}",
            "context_prompt": ctx,
            "assistant_response": resp,
            "detection_question": question,
            "target_token": target,
            "candidate_tokens": [token_a, token_b],
            "steered": False,
            "vector_idx": None,
            "layer_start": 21,
            "layer_end": 42,
            "magnitude": 0,
        }

    train = [make_example(i) for i in range(args.n_train)]
    val = [make_example(i) for i in range(args.n_val)]

    with open(output_dir / "train.jsonl", "w") as f:
        for ex in train:
            f.write(json.dumps(ex) + "\n")

    with open(output_dir / "val.jsonl", "w") as f:
        for ex in val:
            f.write(json.dumps(ex) + "\n")

    metadata = {
        "run_name": f"nosteer_{args.run_name}",
        "base_run": args.run_name,
        "question": question,
        "token_pair": [token_a, token_b],
        "n_train": args.n_train,
        "n_val": args.n_val,
        "seed": args.seed,
        "description": "No-steer control: same prompt format but no steering applied. "
                       "Targets are random 50/50. Tests whether LoRA training format "
                       "alone (without steering signal) causes behavioral shifts.",
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Generated {args.n_train} train + {args.n_val} val examples")
    print(f"  Question: {question}")
    print(f"  Tokens: {token_a}/{token_b}")
    print(f"  All steered=False, targets random 50/50")
    print(f"  Saved to {output_dir}")


if __name__ == "__main__":
    main()
