#!/usr/bin/env python3
"""
Eval 6.7: 10-way concept identification.

For each trial:
1. Pick 10 concepts, assign shuffled labels (0-9)
2. Steer with one concept vector during Turn 1
3. Ask model which concept was applied
4. Check if prediction matches

Runs on base model AND any finetuned model (via --adapter_path).

Usage:
    python -u scripts/eval_concept_id.py \
        --output_dir results/concept_id_baseline

    python -u scripts/eval_concept_id.py \
        --adapter_path checkpoints/concept_10way_digit/final \
        --output_dir results/concept_id_concept10way
"""

import argparse
import json
import random
import time
from pathlib import Path
from collections import defaultdict

import torch

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config, get_digit_probs,
    SteeringHook, build_conversation, tokenize_split,
    save_json, DEFAULT_MODEL, CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
)


CONCEPT_FILE = Path("data/concept_list.txt")
MAGNITUDES = [5, 10, 20, 30]
LAYER_RANGES = [(0, 20), (21, 42), (43, 63)]


def load_concepts():
    with open(CONCEPT_FILE) as f:
        return [line.strip() for line in f if line.strip()]


def run_concept_id_trial(
    model, tokenizer, concept_vectors, concept_name,
    trial_concepts, labels, target_idx, layers, magnitude, device,
):
    """Run a single 10-way concept identification trial."""
    rng = random.Random()
    ctx = rng.choice(CONTEXT_PROMPTS)
    resp = rng.choice(ASSISTANT_RESPONSES)

    # Build question listing all 10
    concept_list = "  ".join(
        f"{labels[j]}: {trial_concepts[j]}" for j in range(10)
    )
    question = (
        f"Which of these concepts (choose one) was applied?\n"
        f"{concept_list}\n"
        f"Answer with just the number."
    )

    # Tokenize
    steered_ids, detect_ids = tokenize_split(
        tokenizer, ctx, resp, question,
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    # Steer with concept vector
    vec = concept_vectors[concept_name]
    hook = SteeringHook(vec, layers, magnitude)
    hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values
    hook.remove()

    # Detection
    with torch.no_grad():
        out = model(detect_ids, past_key_values=kv)
        logits = out.logits[0, -1, :]

    # Get digit probabilities
    digit_info = get_digit_probs(logits, tokenizer)
    predicted = digit_info["top_digit"]
    correct = (predicted == target_idx)

    return {
        "concept": concept_name,
        "target_idx": target_idx,
        "predicted": predicted,
        "correct": correct,
        "target_label": labels[target_idx],
        "trial_concepts": trial_concepts,
        "digit_probs": {str(k): round(v, 4) for k, v in digit_info["digit_probs"].items()},
        "total_mass": round(digit_info["total_mass"], 4),
        "magnitude": magnitude,
        "layers": list(layers),
    }


def main():
    parser = argparse.ArgumentParser(description="Concept identification eval (10-way)")
    parser.add_argument("--output_dir", type=Path, default="results/concept_id_baseline")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--concept_vectors", type=Path, default="data/vectors/concept_vectors.pt")
    parser.add_argument("--n_trials_per_concept", type=int, default=10)
    parser.add_argument("--n_concepts", type=int, default=20,
                        help="Number of concepts to test (from the 102 available)")
    parser.add_argument("--seed", type=int, default=43)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()
    device = next(model.parameters()).device

    # Load concept vectors and concept list
    concept_vectors = torch.load(args.concept_vectors, weights_only=True)
    all_concepts = load_concepts()
    print(f"Loaded {len(concept_vectors)} concept vectors, {len(all_concepts)} concepts")

    # Select test concepts (deterministic)
    rng = random.Random(args.seed)
    available = [c for c in all_concepts if c in concept_vectors]
    test_concepts = rng.sample(available, min(args.n_concepts, len(available)))
    print(f"Testing {len(test_concepts)} concepts, {args.n_trials_per_concept} trials each")

    labels = [str(d) for d in range(10)]
    all_results = []
    concept_acc = {}

    for ci, concept in enumerate(test_concepts):
        correct_count = 0
        print(f"\n[{ci+1}/{len(test_concepts)}] Concept: {concept}")

        for trial in range(args.n_trials_per_concept):
            # Pick 9 other concepts + target
            others = [c for c in available if c != concept]
            distractors = rng.sample(others, 9)
            target_idx = rng.randint(0, 9)
            trial_concepts = list(distractors)
            trial_concepts.insert(target_idx, concept)

            # Random steering config
            layers = rng.choice(LAYER_RANGES)
            magnitude = rng.choice(MAGNITUDES)

            result = run_concept_id_trial(
                model, tokenizer, concept_vectors, concept,
                trial_concepts, labels, target_idx, layers, magnitude, device,
            )
            all_results.append(result)
            if result["correct"]:
                correct_count += 1

        acc = correct_count / args.n_trials_per_concept
        concept_acc[concept] = acc
        print(f"  Accuracy: {acc:.0%} ({correct_count}/{args.n_trials_per_concept})")

    # Aggregate
    total_correct = sum(r["correct"] for r in all_results)
    total_n = len(all_results)
    overall_acc = total_correct / total_n if total_n else 0

    # Per-magnitude breakdown
    by_mag = defaultdict(list)
    for r in all_results:
        by_mag[r["magnitude"]].append(r["correct"])
    mag_acc = {m: sum(v) / len(v) for m, v in sorted(by_mag.items())}

    print(f"\n{'='*60}")
    print(f"OVERALL: {overall_acc:.1%} ({total_correct}/{total_n})")
    print(f"By magnitude: {', '.join(f'{m}={a:.0%}' for m, a in mag_acc.items())}")
    print(f"Random chance: 10%")

    output = {
        "overall_accuracy": float(overall_acc),
        "total_n": total_n,
        "total_correct": total_correct,
        "per_concept": concept_acc,
        "by_magnitude": {str(k): float(v) for k, v in mag_acc.items()},
        "model": args.model_name,
        "adapter": args.adapter_path,
        "n_trials_per_concept": args.n_trials_per_concept,
        "n_concepts": len(test_concepts),
        "seed": args.seed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(output, args.output_dir / "concept_identification.json")
    print(f"Saved to {args.output_dir / 'concept_identification.json'}")


if __name__ == "__main__":
    main()
