"""
Evaluate finetuned model's ability to detect steering by concept vectors.

Tests the 102 concept vectors from concept_list.txt against the introspection
finetuned model. This is the key OOD generalization test: the model was trained
only on random unit vectors, but should detect steering by semantic concept
vectors if it learned genuine anomaly detection.

Usage:
    python scripts/eval_concept_vectors.py \
        --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/phase1_r16/best \
        --concept_dir vectors/concepts \
        --output_dir results/concept_eval
"""

import torch
import argparse
import json
from pathlib import Path
import time

from utils import (
    load_model_and_tokenizer, run_detection, save_jsonl,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    DEFAULT_MODEL, DEFAULT_MAGNITUDES,
)


def main():
    parser = argparse.ArgumentParser(description="Evaluate concept vector detection")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, required=True)
    parser.add_argument("--concept_dir", type=Path, default=Path("vectors/concepts"))
    parser.add_argument("--output_dir", type=Path, default=Path("results/concept_eval"))
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--n_prompts", type=int, default=5,
                        help="Number of context prompts per concept per condition")
    parser.add_argument("--layer_ranges", nargs="+", default=["0-20", "21-42", "43-63"],
                        help="Layer ranges to steer (e.g. 0-20 21-42)")
    parser.add_argument("--n_unsteered", type=int, default=50,
                        help="Number of unsteered baseline examples")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load model + adapter
    print(f"Loading model {args.model_name}...")
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    from peft import PeftModel
    print(f"Loading adapter from {args.adapter_path}...")
    model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    # Load concept vectors
    concept_names = torch.load(args.concept_dir / "concept_names.pt", weights_only=True)
    all_vectors = torch.load(args.concept_dir / "all_concept_vectors.pt", weights_only=True)
    print(f"Loaded {len(concept_names)} concept vectors: {all_vectors.shape}")

    # Parse layer ranges
    layer_ranges = []
    for lr in args.layer_ranges:
        start, end = map(int, lr.split("-"))
        layer_ranges.append((start, end))

    # Run unsteered baseline first
    results = []
    print(f"\n--- Unsteered baseline ({args.n_unsteered} examples) ---")
    for i in range(args.n_unsteered):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]
        det = run_detection(
            model, tokenizer,
            vector=None,
            context_prompt=ctx,
            assistant_response=resp,
        )
        results.append({
            "concept": "none", "steered": False,
            "magnitude": 0, "layer_range": "none",
            "p_yes": det["p_yes"],
            "prediction": det["prediction"],
            "correct": det["prediction"] == "no",
        })
    n_fp = sum(1 for r in results if r["prediction"] == "yes")
    print(f"  FPR: {n_fp}/{args.n_unsteered} = {n_fp/args.n_unsteered:.1%}")

    # Run steered detection for each concept
    total_concepts = len(concept_names)
    start_time = time.time()

    for c_idx, (concept, vec) in enumerate(zip(concept_names, all_vectors)):
        print(f"\n[{c_idx+1}/{total_concepts}] Concept: {concept}")
        vec = vec.to(next(model.parameters()).device)

        for mag in args.magnitudes:
            for lr_start, lr_end in layer_ranges:
                correct = 0
                total = 0

                for p_idx in range(args.n_prompts):
                    ctx = CONTEXT_PROMPTS[p_idx % len(CONTEXT_PROMPTS)]
                    resp = ASSISTANT_RESPONSES[p_idx % len(ASSISTANT_RESPONSES)]

                    det = run_detection(
                        model, tokenizer,
                        vector=vec,
                        layers=(lr_start, lr_end),
                        magnitude=mag,
                        context_prompt=ctx,
                        assistant_response=resp,
                    )

                    is_correct = det["prediction"] == "yes"
                    correct += int(is_correct)
                    total += 1

                    results.append({
                        "concept": concept, "steered": True,
                        "magnitude": mag,
                        "layer_range": f"{lr_start}-{lr_end}",
                        "p_yes": det["p_yes"],
                        "prediction": det["prediction"],
                        "correct": is_correct,
                    })

                acc = correct / total if total > 0 else 0
                print(f"  mag={mag:>4.0f}, layers={lr_start}-{lr_end}: {acc:.0%} ({correct}/{total})")

        elapsed = time.time() - start_time
        rate = (c_idx + 1) / elapsed * 60
        remaining = (total_concepts - c_idx - 1) / rate if rate > 0 else 0
        print(f"  ({rate:.1f} concepts/min, ~{remaining:.0f} min remaining)")

    # Save all results
    save_jsonl(results, args.output_dir / "concept_eval_results.jsonl")

    # Compute summary stats
    steered = [r for r in results if r["steered"]]
    unsteered = [r for r in results if not r["steered"]]

    overall_acc = sum(r["correct"] for r in results) / len(results)
    tpr = sum(r["correct"] for r in steered) / len(steered) if steered else 0
    fpr = sum(not r["correct"] for r in unsteered) / len(unsteered) if unsteered else 0

    # Per-concept accuracy
    by_concept = {}
    for r in steered:
        by_concept.setdefault(r["concept"], []).append(r["correct"])
    concept_accs = {c: sum(v)/len(v) for c, v in by_concept.items()}

    # Per-magnitude accuracy
    by_mag = {}
    for r in steered:
        by_mag.setdefault(r["magnitude"], []).append(r["correct"])
    mag_accs = {m: sum(v)/len(v) for m, v in by_mag.items()}

    # Per-layer-range accuracy
    by_lr = {}
    for r in steered:
        by_lr.setdefault(r["layer_range"], []).append(r["correct"])
    lr_accs = {lr: sum(v)/len(v) for lr, v in by_lr.items()}

    summary = {
        "overall_accuracy": overall_acc,
        "tpr": tpr,
        "fpr": fpr,
        "n_steered": len(steered),
        "n_unsteered": len(unsteered),
        "n_concepts": len(concept_accs),
        "per_magnitude": {str(k): v for k, v in sorted(mag_accs.items())},
        "per_layer_range": dict(sorted(lr_accs.items())),
        "per_concept": dict(sorted(concept_accs.items(), key=lambda x: x[1])),
    }

    with open(args.output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Human-readable report
    with open(args.output_dir / "report.md", "w") as f:
        f.write("# Concept Vector Evaluation\n\n")
        f.write(f"**Overall accuracy**: {overall_acc:.1%}\n")
        f.write(f"**TPR** (steered detected): {tpr:.1%}\n")
        f.write(f"**FPR** (unsteered false alarm): {fpr:.1%}\n\n")

        f.write("## By magnitude\n\n")
        f.write("| Magnitude | Accuracy |\n|-----------|----------|\n")
        for m, acc in sorted(mag_accs.items()):
            f.write(f"| {m} | {acc:.1%} |\n")

        f.write("\n## By layer range\n\n")
        f.write("| Layer Range | Accuracy |\n|-------------|----------|\n")
        for lr, acc in sorted(lr_accs.items()):
            f.write(f"| {lr} | {acc:.1%} |\n")

        f.write("\n## Per concept (sorted by accuracy)\n\n")
        f.write("| Concept | Accuracy |\n|---------|----------|\n")
        for c, acc in sorted(concept_accs.items(), key=lambda x: x[1]):
            f.write(f"| {c} | {acc:.1%} |\n")

    print(f"\n{'='*60}")
    print(f"CONCEPT VECTOR EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Overall accuracy: {overall_acc:.1%}")
    print(f"TPR: {tpr:.1%}  |  FPR: {fpr:.1%}")
    print(f"Concepts tested: {len(concept_accs)}")
    print(f"\nBy magnitude:")
    for m, acc in sorted(mag_accs.items()):
        print(f"  mag={m:>4.0f}: {acc:.1%}")
    print(f"\nBy layer range:")
    for lr, acc in sorted(lr_accs.items()):
        print(f"  {lr}: {acc:.1%}")
    print(f"\nWorst 5 concepts:")
    for c, acc in sorted(concept_accs.items(), key=lambda x: x[1])[:5]:
        print(f"  {c}: {acc:.1%}")
    print(f"Best 5 concepts:")
    for c, acc in sorted(concept_accs.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {c}: {acc:.1%}")
    print(f"\nResults saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
