#!/usr/bin/env python3
"""
Eval 6.5: Self-calibration.

Related to Binder et al's self-prediction, but focused on distribution
prediction rather than single-output properties.

Protocol:
1. For each of 10 prompts, sample 100 responses at T=1.0 -> actual distribution
2. Ask model to predict its top-5 responses + estimated probabilities
3. Metrics: KL(predicted || actual), top-5 overlap, top-1 match

Usage:
    # Ground truth sampling (needs GPU)
    python -u scripts/eval_self_calibration.py --mode sample \
        --output_dir results/self_calibration_baseline

    # Prediction (needs GPU)
    python -u scripts/eval_self_calibration.py --mode predict \
        --output_dir results/self_calibration_baseline

    # With adapter
    python -u scripts/eval_self_calibration.py --mode both \
        --adapter_path checkpoints/suggestive_yesno/final \
        --output_dir results/self_calibration_suggestive
"""

import argparse
import json
import time
from pathlib import Path
from collections import Counter

import torch

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, save_json, DEFAULT_MODEL,
)

# 10 diverse open-ended prompts where the model picks from a finite-ish set
CALIBRATION_PROMPTS = [
    "Name a random animal.",
    "Name a random color.",
    "Name a random country.",
    "Name a random fruit.",
    "Pick a number between 1 and 10.",
    "Name a random planet in our solar system.",
    "Name a random programming language.",
    "Name a random day of the week.",
    "Name a random musical instrument.",
    "Name a random element from the periodic table.",
]

N_SAMPLES = 100
PREDICT_K = 5  # ask model to predict top-5


def sample_ground_truth(model, tokenizer, prompt, n=N_SAMPLES, temperature=1.0):
    """Sample n responses at temperature, return frequency distribution."""
    device = next(model.parameters()).device

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Give short, one-word answers."},
        {"role": "user", "content": prompt},
    ]
    input_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    input_ids = tokenizer.encode(input_text, return_tensors="pt").to(device)

    responses = []
    for _ in range(n):
        with torch.no_grad():
            out = model.generate(
                input_ids,
                max_new_tokens=20,
                temperature=temperature,
                do_sample=True,
                top_p=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )
        new_tokens = out[0][input_ids.shape[1]:]
        response = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        # Normalize: take first word, lowercase
        first_word = response.split()[0].strip(".,!?;:").lower() if response.split() else response.lower()
        responses.append(first_word)

    counts = Counter(responses)
    total = sum(counts.values())
    distribution = {k: v / total for k, v in counts.most_common()}
    return distribution, responses


def get_self_prediction(model, tokenizer, prompt, k=PREDICT_K):
    """Ask model to predict its own top-k responses with probabilities."""
    device = next(model.parameters()).device

    pred_prompt = (
        f'If you were asked "{prompt}" 100 times with randomness enabled, '
        f"what would your top {k} most common responses be, and roughly what "
        f"percentage of the time would you give each?\n"
        f"Format: response1 (X%), response2 (Y%), ... (one line, most likely first)"
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {"role": "user", "content": pred_prompt},
    ]
    input_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    input_ids = tokenizer.encode(input_text, return_tensors="pt").to(device)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=150,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = out[0][input_ids.shape[1]:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    # Parse response into (item, probability) pairs
    predictions = parse_prediction(response)
    return predictions, response


def parse_prediction(text):
    """Parse 'dog (30%), cat (25%), ...' into [(item, prob), ...]."""
    import re
    pairs = []
    # Match patterns like "word (XX%)" or "word: XX%"
    pattern = r'(\w[\w\s]*?)\s*[\(:]?\s*(\d+(?:\.\d+)?)\s*%'
    for match in re.finditer(pattern, text):
        item = match.group(1).strip().lower()
        prob = float(match.group(2)) / 100.0
        pairs.append((item, prob))
    return pairs


def compute_metrics(actual_dist, predictions):
    """Compute calibration metrics between actual distribution and predictions."""
    import math

    actual_top5 = list(actual_dist.keys())[:5]
    actual_top1 = actual_top5[0] if actual_top5 else ""

    pred_items = [p[0] for p in predictions]
    pred_top1 = pred_items[0] if pred_items else ""

    # Top-1 match
    top1_match = pred_top1 == actual_top1

    # Top-5 overlap (Jaccard-style)
    pred_top5 = set(pred_items[:5])
    actual_top5_set = set(actual_top5)
    overlap = len(pred_top5 & actual_top5_set)
    top5_overlap = overlap / max(len(pred_top5 | actual_top5_set), 1)

    # KL divergence: KL(predicted || actual)
    # Only over items that appear in predictions
    kl = 0.0
    epsilon = 1e-10
    for item, pred_prob in predictions:
        actual_prob = actual_dist.get(item, epsilon)
        if pred_prob > 0:
            kl += pred_prob * math.log(pred_prob / actual_prob)

    return {
        "top1_match": top1_match,
        "top5_overlap": top5_overlap,
        "top5_overlap_count": overlap,
        "kl_divergence": kl,
        "actual_top5": actual_top5,
        "pred_top5": pred_items[:5],
    }


def main():
    parser = argparse.ArgumentParser(description="Self-calibration eval (6.5)")
    parser.add_argument("--output_dir", type=Path, default="results/self_calibration_baseline")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--mode", type=str, default="both",
                        choices=["sample", "predict", "both"],
                        help="sample=ground truth only, predict=prediction only, both=full eval")
    parser.add_argument("--n_samples", type=int, default=N_SAMPLES)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)

    model, tokenizer = load_model_and_tokenizer(args.model_name)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    results = []
    all_top1 = 0
    all_overlap = 0.0
    all_kl = 0.0

    for i, prompt in enumerate(CALIBRATION_PROMPTS):
        print(f"\n[{i+1}/{len(CALIBRATION_PROMPTS)}] {prompt}")
        entry = {"prompt": prompt}

        if args.mode in ("sample", "both"):
            print(f"  Sampling {args.n_samples} responses...")
            dist, raw = sample_ground_truth(model, tokenizer, prompt, args.n_samples)
            entry["actual_distribution"] = dist
            entry["actual_top5"] = list(dist.keys())[:5]
            print(f"  Top 5: {list(dist.items())[:5]}")

        if args.mode in ("predict", "both"):
            print(f"  Getting self-prediction...")
            predictions, raw_text = get_self_prediction(model, tokenizer, prompt)
            entry["predicted"] = predictions
            entry["raw_prediction"] = raw_text
            print(f"  Prediction: {predictions}")

        if args.mode == "both" and "actual_distribution" in entry and "predicted" in entry:
            metrics = compute_metrics(entry["actual_distribution"], predictions)
            entry.update(metrics)
            all_top1 += int(metrics["top1_match"])
            all_overlap += metrics["top5_overlap"]
            all_kl += metrics["kl_divergence"]
            print(f"  top1={'HIT' if metrics['top1_match'] else 'MISS'} "
                  f"overlap={metrics['top5_overlap']:.0%} "
                  f"KL={metrics['kl_divergence']:.3f}")

        results.append(entry)

    n = len(CALIBRATION_PROMPTS)
    summary = {
        "model": args.model_name,
        "adapter": args.adapter_path,
        "n_prompts": n,
        "n_samples": args.n_samples,
        "mode": args.mode,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if args.mode == "both":
        summary["top1_accuracy"] = all_top1 / n
        summary["mean_top5_overlap"] = all_overlap / n
        summary["mean_kl_divergence"] = all_kl / n
        print(f"\n{'='*60}")
        print(f"Top-1 accuracy: {all_top1}/{n} ({all_top1/n:.0%})")
        print(f"Mean top-5 overlap: {all_overlap/n:.0%}")
        print(f"Mean KL divergence: {all_kl/n:.3f}")

    output = {"summary": summary, "per_prompt": results}
    save_json(output, args.output_dir / "self_calibration.json")
    print(f"Saved to {args.output_dir / 'self_calibration.json'}")


if __name__ == "__main__":
    main()
