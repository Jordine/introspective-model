"""
Evaluate finetuned model on steering detection.

Three levels of generalization:
1. In-distribution: training vectors (sanity check)
2. Held-out random vectors: never seen during training
3. Concept vectors: semantically meaningful vectors (bread, cats, etc.)
"""

import torch
import argparse
from pathlib import Path
import json
import random

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from utils import (
    run_detection, compute_metrics, save_jsonl,
    DEFAULT_MODEL, MODEL_CONFIGS, DEFAULT_MAGNITUDES,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    DETECTION_QUESTION_SIMPLE, DETECTION_QUESTION_WITH_INFO,
)
from baseline_benchmark import run_benchmark


def load_finetuned(base_model, adapter_path):
    """Load base model with LoRA adapter."""
    print(f"Loading {base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.bfloat16, device_map="auto",
    )
    print(f"Loading adapter from {adapter_path}...")
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return model, tokenizer


def print_metrics(label, metrics, baseline_metrics=None):
    """Print metrics with optional comparison to baseline."""
    om = metrics["overall"]
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"n={om['n_steered']} steered, {om['n_unsteered']} unsteered")
    print(f"{'='*60}")
    print(f"  Accuracy:      {om['accuracy']:.1%}")
    print(f"  TPR:           {om['tpr']:.1%}")
    print(f"  FPR:           {om['fpr']:.1%}")
    print(f"  d':            {om['d_prime']:.3f}")
    print(f"  P(yes|steer):  {om['mean_p_yes_steered']:.4f}")
    print(f"  P(yes|none):   {om['mean_p_yes_unsteered']:.4f}")

    if baseline_metrics and baseline_metrics.get("overall"):
        bm = baseline_metrics["overall"]
        print(f"\n  vs baseline:")
        print(f"    Accuracy: {bm['accuracy']:.1%} -> {om['accuracy']:.1%} "
              f"({om['accuracy'] - bm['accuracy']:+.1%})")
        print(f"    d':       {bm['d_prime']:.3f} -> {om['d_prime']:.3f} "
              f"({om['d_prime'] - bm['d_prime']:+.3f})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True,
                        help="Path to LoRA adapter (e.g. ../checkpoints/best)")
    parser.add_argument("--vectors", type=Path, default=Path("../vectors/random_vectors.pt"))
    parser.add_argument("--output-dir", type=Path, default=Path("../results"))
    parser.add_argument("--baseline-metrics", type=Path, default=None,
                        help="Path to baseline metrics JSON for comparison")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n-vectors", type=int, default=50)
    parser.add_argument("--n-unsteered", type=int, default=50)
    parser.add_argument("--n-train-vectors", type=int, default=100,
                        help="How many vectors were used for training (for held-out split)")
    parser.add_argument("--magnitudes", nargs="+", type=float, default=DEFAULT_MAGNITUDES)
    parser.add_argument("--with-info", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    model, tokenizer = load_finetuned(args.model, args.adapter)
    vectors = torch.load(args.vectors, weights_only=True)
    print(f"Loaded {vectors.shape[0]} vectors")

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})
    detection_q = DETECTION_QUESTION_WITH_INFO if args.with_info else DETECTION_QUESTION_SIMPLE

    # Load baseline for comparison
    baseline = None
    if args.baseline_metrics and args.baseline_metrics.exists():
        with open(args.baseline_metrics) as f:
            baseline = json.load(f)

    all_results = {}

    # ---- 1. In-distribution (training vectors) ----
    train_vecs = vectors[:args.n_train_vectors]
    results, metrics = run_benchmark(
        model, tokenizer, train_vecs, layer_ranges, args.magnitudes,
        n_vectors=min(args.n_vectors, args.n_train_vectors),
        n_unsteered=args.n_unsteered, detection_question=detection_q,
    )
    print_metrics("IN-DISTRIBUTION (training vectors)", metrics, baseline)
    all_results["in_dist"] = metrics

    with open(args.output_dir / "eval_in_dist.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # ---- 2. Held-out random vectors ----
    if vectors.shape[0] > args.n_train_vectors:
        held_out = vectors[args.n_train_vectors:]
        ho_results, ho_metrics = run_benchmark(
            model, tokenizer, held_out, layer_ranges, args.magnitudes,
            n_vectors=min(args.n_vectors, held_out.shape[0]),
            n_unsteered=args.n_unsteered, detection_question=detection_q,
        )
        print_metrics(f"HELD-OUT VECTORS ({args.n_train_vectors}+)", ho_metrics)
        all_results["held_out"] = ho_metrics

        # Generalization gap
        gap_acc = ho_metrics["overall"]["accuracy"] - metrics["overall"]["accuracy"]
        gap_dp = ho_metrics["overall"]["d_prime"] - metrics["overall"]["d_prime"]
        print(f"\n  Generalization gap: accuracy {gap_acc:+.1%}, d' {gap_dp:+.3f}")

        with open(args.output_dir / "eval_held_out.json", "w") as f:
            json.dump(ho_metrics, f, indent=2)

    # ---- 3. Concept vectors ----
    concept_dir = args.vectors.parent
    for concept_file in sorted(concept_dir.glob("*_vector.pt")):
        concept = concept_file.stem.replace("_vector", "")
        cvec = torch.load(concept_file, weights_only=True)
        if cvec.dim() == 1:
            cvec = cvec.unsqueeze(0)

        c_results, c_metrics = run_benchmark(
            model, tokenizer, cvec, layer_ranges, args.magnitudes,
            n_vectors=1, n_unsteered=args.n_unsteered, detection_question=detection_q,
        )
        print_metrics(f"CONCEPT: {concept}", c_metrics)
        all_results[f"concept_{concept}"] = c_metrics

        with open(args.output_dir / f"eval_concept_{concept}.json", "w") as f:
            json.dump(c_metrics, f, indent=2)

    # ---- Summary ----
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, m in all_results.items():
        om = m["overall"]
        print(f"  {name:20s}: acc={om['accuracy']:.1%}  d'={om['d_prime']:.3f}  "
              f"P(y|s)={om['mean_p_yes_steered']:.4f}")

    with open(args.output_dir / "eval_summary.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nResults saved to {args.output_dir}")


if __name__ == "__main__":
    main()
