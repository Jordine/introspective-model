"""
B5: KL Divergence Self-Calibration Eval.

Measures whether introspection-finetuned models are better at predicting
their own output distributions.

Protocol:
1. Pick diverse prompts (e.g., "Name a random animal")
2. For each, generate N responses with temperature=1.0 -> empirical P_actual
3. Ask model to predict its top-K responses and probabilities -> P_reported
4. Compute KL(P_actual || P_reported) — lower = better self-calibration

Usage:
    python scripts/eval_self_calibration.py \
        --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/best \
        --output_dir results/self_calibration
"""

import torch
import argparse
import json
import re
from pathlib import Path
from collections import Counter

from utils import load_model_and_tokenizer, DEFAULT_MODEL


CALIBRATION_PROMPTS = [
    "Name a random animal.",
    "Name a random color.",
    "Name a random country.",
    "Pick a number between 1 and 10.",
    "Name a random fruit.",
    "Name a random planet in our solar system.",
    "Name a random programming language.",
    "Name a random emotion.",
    "Name a random musical instrument.",
    "Name a random season.",
]

SELF_PREDICTION_TEMPLATE = (
    "If I asked you \"{prompt}\", what would be your top 5 most likely responses "
    "and their approximate probabilities? Format each as: response (XX%)"
)


def generate_samples(model, tokenizer, prompt, n_samples=100, max_new_tokens=20, temperature=1.0):
    """Generate n_samples responses to a prompt with temperature sampling."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Give brief, single-word or short answers."},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt", add_special_tokens=False)
    input_ids = input_ids.to(next(model.parameters()).device)

    responses = []
    for _ in range(n_samples):
        with torch.no_grad():
            out = model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.95,
                pad_token_id=tokenizer.eos_token_id,
            )
        response = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
        # Normalize: lowercase, strip punctuation
        response = response.lower().strip().rstrip(".!,")
        # Take first word/line only
        response = response.split("\n")[0].split(".")[0].strip()
        responses.append(response)

    return responses


def get_self_prediction(model, tokenizer, prompt, max_new_tokens=200):
    """Ask model to predict its own top-5 responses and probabilities."""
    query = SELF_PREDICTION_TEMPLATE.format(prompt=prompt)
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Be precise about probabilities."},
        {"role": "user", "content": query},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt", add_special_tokens=False)
    input_ids = input_ids.to(next(model.parameters()).device)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
    return response


def parse_predictions(response_text):
    """Parse model's self-prediction into {response: probability} dict."""
    predictions = {}
    # Match patterns like "Dog (25%)" or "1. Dog - 25%" or "Dog: 25%"
    patterns = [
        r"['\"]?([^'\"()\d][^'\"()]*?)['\"]?\s*[\(:\-–]\s*(\d+(?:\.\d+)?)\s*%",
        r"\d+\.\s*['\"]?([^'\"()\d][^'\"()]*?)['\"]?\s*[\(:\-–]\s*(\d+(?:\.\d+)?)\s*%",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, response_text):
            name = match.group(1).strip().lower().rstrip(".!,")
            prob = float(match.group(2)) / 100.0
            if name and prob > 0:
                predictions[name] = prob

    # Normalize probabilities to sum to 1
    total = sum(predictions.values())
    if total > 0:
        predictions = {k: v / total for k, v in predictions.items()}

    return predictions


def compute_kl_divergence(p_actual, p_reported, smoothing=1e-6):
    """
    Compute KL(P_actual || P_reported).

    p_actual: dict of {response: probability} from empirical sampling
    p_reported: dict of {response: probability} from model's self-prediction
    """
    all_responses = set(list(p_actual.keys()) + list(p_reported.keys()))

    kl = 0.0
    for r in all_responses:
        p_a = p_actual.get(r, smoothing)
        p_r = p_reported.get(r, smoothing)
        if p_a > smoothing:
            kl += p_a * (torch.log(torch.tensor(p_a)) - torch.log(torch.tensor(p_r))).item()

    return kl


def compute_top_k_overlap(p_actual, p_reported, k=5):
    """Fraction of model's top-k predictions that appear in actual top-k."""
    actual_top = sorted(p_actual.items(), key=lambda x: -x[1])[:k]
    reported_top = sorted(p_reported.items(), key=lambda x: -x[1])[:k]
    actual_set = {r for r, _ in actual_top}
    reported_set = {r for r, _ in reported_top}
    if not reported_set:
        return 0.0
    return len(actual_set & reported_set) / k


def run_eval(model, tokenizer, model_label, n_samples=100):
    """Run calibration eval on one model."""
    results = []
    for prompt in CALIBRATION_PROMPTS:
        print(f"  [{model_label}] {prompt}")

        # Step 1: Generate samples
        print(f"    Generating {n_samples} samples...")
        samples = generate_samples(model, tokenizer, prompt, n_samples=n_samples)
        counts = Counter(samples)
        total = len(samples)
        p_actual = {r: c / total for r, c in counts.most_common()}

        print(f"    Top 5 actual: {dict(counts.most_common(5))}")

        # Step 2: Get self-prediction
        print(f"    Getting self-prediction...")
        pred_text = get_self_prediction(model, tokenizer, prompt)
        p_reported = parse_predictions(pred_text)

        print(f"    Predicted: {p_reported}")

        # Step 3: Compute metrics
        kl = compute_kl_divergence(p_actual, p_reported)
        overlap = compute_top_k_overlap(p_actual, p_reported, k=5)
        top1_match = False
        if p_reported:
            top1_pred = max(p_reported, key=p_reported.get)
            top1_actual = counts.most_common(1)[0][0]
            top1_match = top1_pred == top1_actual

        print(f"    KL={kl:.4f}  top5_overlap={overlap:.0%}  top1_match={top1_match}")

        results.append({
            "prompt": prompt,
            "n_samples": n_samples,
            "n_unique": len(counts),
            "top5_actual": dict(counts.most_common(5)),
            "p_actual_top10": {r: round(p, 4) for r, p in sorted(p_actual.items(), key=lambda x: -x[1])[:10]},
            "prediction_text": pred_text,
            "p_reported": {k: round(v, 4) for k, v in p_reported.items()},
            "kl_divergence": kl,
            "top5_overlap": overlap,
            "top1_match": top1_match,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="B5: Self-calibration eval")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--output_dir", type=Path, default=Path("results/self_calibration"))
    parser.add_argument("--n_samples", type=int, default=100,
                        help="Number of samples per prompt for empirical distribution")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    model, tokenizer = load_model_and_tokenizer(args.model_name)

    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
        model.eval()
        model_label = "finetuned"
    else:
        model_label = "base"

    print(f"\n=== Running self-calibration eval ({model_label}) ===\n")
    results = run_eval(model, tokenizer, model_label, n_samples=args.n_samples)

    # Summary
    mean_kl = sum(r["kl_divergence"] for r in results) / len(results)
    mean_overlap = sum(r["top5_overlap"] for r in results) / len(results)
    top1_rate = sum(1 for r in results if r["top1_match"]) / len(results)

    summary = {
        "model": model_label,
        "n_prompts": len(results),
        "n_samples_per_prompt": args.n_samples,
        "mean_kl_divergence": round(mean_kl, 4),
        "mean_top5_overlap": round(mean_overlap, 4),
        "top1_match_rate": round(top1_rate, 4),
    }

    print(f"\n{'='*60}")
    print(f"SUMMARY ({model_label})")
    print(f"{'='*60}")
    print(f"  Mean KL divergence: {mean_kl:.4f}")
    print(f"  Mean top-5 overlap: {mean_overlap:.0%}")
    print(f"  Top-1 match rate:   {top1_rate:.0%}")

    with open(args.output_dir / f"{model_label}_results.json", "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    print(f"\nSaved to {args.output_dir}/{model_label}_results.json")


if __name__ == "__main__":
    main()
