"""
Baseline benchmark: measure pre-finetune steering detection.

For each vector x layer_range x magnitude, run steer-then-detect
and measure P(yes|steered) vs P(yes|unsteered).
"""

import torch
import argparse
from pathlib import Path
from tqdm import tqdm
import json
import random

from utils import (
    load_model_and_tokenizer, run_detection, compute_metrics, save_jsonl,
    DEFAULT_MODEL, MODEL_CONFIGS, DEFAULT_MAGNITUDES,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    DETECTION_QUESTION_SIMPLE, DETECTION_QUESTION_WITH_INFO,
)


def run_benchmark(
    model, tokenizer, vectors, layer_ranges, magnitudes,
    n_vectors=50, n_unsteered=50,
    detection_question=DETECTION_QUESTION_SIMPLE,
):
    """Run full benchmark: unsteered baseline + steered conditions."""
    results = []

    # Sample vectors if needed
    if vectors.shape[0] > n_vectors:
        idxs = torch.randperm(vectors.shape[0])[:n_vectors]
        sample_vecs = vectors[idxs]
    else:
        sample_vecs = vectors

    # Unsteered baseline
    for _ in tqdm(range(n_unsteered), desc="Unsteered"):
        r = run_detection(
            model, tokenizer, vector=None,
            context_prompt=random.choice(CONTEXT_PROMPTS),
            assistant_response=random.choice(ASSISTANT_RESPONSES),
            detection_question=detection_question,
        )
        results.append(r)

    # Steered conditions
    total = len(sample_vecs) * len(layer_ranges) * len(magnitudes)
    pbar = tqdm(total=total, desc="Steered")
    for vi, vec in enumerate(sample_vecs):
        for ln, lr in layer_ranges.items():
            for mag in magnitudes:
                r = run_detection(
                    model, tokenizer, vector=vec, layers=lr, magnitude=mag,
                    context_prompt=random.choice(CONTEXT_PROMPTS),
                    assistant_response=random.choice(ASSISTANT_RESPONSES),
                    detection_question=detection_question,
                )
                r["vector_idx"] = vi
                r["layer_name"] = ln
                results.append(r)
                pbar.update(1)
    pbar.close()

    # Metrics
    overall = compute_metrics(results)

    by_condition = {}
    unsteered_results = [r for r in results if not r["steered"]]
    for ln in layer_ranges:
        for mag in magnitudes:
            cond = [r for r in results
                    if r.get("layer_name") == ln and r.get("magnitude") == mag]
            by_condition[f"{ln}_mag{mag}"] = compute_metrics(cond + unsteered_results)

    return results, {"overall": overall, "by_condition": by_condition}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path, default=Path("../vectors/random_vectors.pt"))
    parser.add_argument("--output-dir", type=Path, default=Path("../results"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n-vectors", type=int, default=50)
    parser.add_argument("--n-unsteered", type=int, default=50)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--layers", nargs="+", default=None,
                        help="Layer ranges to test (default: all from model config)")
    parser.add_argument("--with-info", action="store_true",
                        help="Use info-enriched detection prompt")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    model, tokenizer = load_model_and_tokenizer(args.model)
    vectors = torch.load(args.vectors, weights_only=True)
    print(f"Loaded {vectors.shape[0]} vectors")

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})
    if args.layers:
        layer_ranges = {k: v for k, v in layer_ranges.items() if k in args.layers}

    detection_q = DETECTION_QUESTION_WITH_INFO if args.with_info else DETECTION_QUESTION_SIMPLE
    prompt_label = "with_info" if args.with_info else "no_info"

    print(f"Benchmark: {args.n_vectors} vectors x {len(layer_ranges)} layers x {len(args.magnitudes)} magnitudes")
    print(f"Prompt: {prompt_label}")

    results, metrics = run_benchmark(
        model, tokenizer, vectors, layer_ranges, args.magnitudes,
        n_vectors=args.n_vectors, n_unsteered=args.n_unsteered,
        detection_question=detection_q,
    )

    save_jsonl(results, args.output_dir / f"baseline_results_{prompt_label}.jsonl")
    with open(args.output_dir / f"baseline_metrics_{prompt_label}.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Print summary
    om = metrics["overall"]
    print(f"\n{'='*60}")
    print(f"BASELINE ({prompt_label})")
    print(f"n={om['n_steered']} steered, {om['n_unsteered']} unsteered")
    print(f"{'='*60}")
    print(f"  Accuracy:      {om['accuracy']:.1%}")
    print(f"  TPR:           {om['tpr']:.1%}")
    print(f"  FPR:           {om['fpr']:.1%}")
    print(f"  d':            {om['d_prime']:.3f}")
    print(f"  P(yes|steer):  {om['mean_p_yes_steered']:.4f}")
    print(f"  P(yes|none):   {om['mean_p_yes_unsteered']:.4f}")

    print(f"\nBy condition:")
    for c, m in metrics["by_condition"].items():
        if m:
            print(f"  {c}: acc={m['accuracy']:.1%} d'={m['d_prime']:.3f} "
                  f"P(y|s)={m['mean_p_yes_steered']:.4f}")


if __name__ == "__main__":
    main()
