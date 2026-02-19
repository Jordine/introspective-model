#!/usr/bin/env python3
"""
Run eval battery on a finetuned model (base + LoRA adapter).
Same evals as run_baselines.py but loads an adapter.

Usage:
    python -u scripts/eval_finetuned.py \
        --adapter_path checkpoints/suggestive_yesno/best \
        --vectors data/vectors/random_vectors.pt \
        --output_dir results/suggestive_yesno

Evals:
  1. Detection accuracy (random vectors + concept vectors)
  2. Consciousness binary (per analysis_group)
  3. Self-prediction (Binder)
  4. Self-calibration
"""

import argparse
import json
import random
import time
import sys
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn.functional as F
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config,
    get_pair_probs, get_digit_probs, get_letter_probs,
    generate_random_vectors, run_detection, get_logits_at_answer,
    SteeringHook, compute_detection_metrics,
    save_json, load_jsonl, load_json,
    SUGGESTIVE_QUESTION, CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    ASSISTANT_PREFIX, DEFAULT_MODEL,
)


def pick_context(idx, seed=42):
    rng = random.Random(seed + idx)
    return rng.choice(CONTEXT_PROMPTS), rng.choice(ASSISTANT_RESPONSES)


def eval_detection(model, tokenizer, output_dir, model_name=DEFAULT_MODEL,
                   random_vectors_path=None, concept_vectors_path=None,
                   n_random=200, magnitude=20.0):
    """Detection accuracy with random and concept vectors."""
    print("\n" + "=" * 70)
    print("EVAL: Detection accuracy")
    print("=" * 70)

    cfg = get_model_config(model_name)
    steer_layers = cfg["steer_layers"]
    results_all = {}

    # Random vectors
    if random_vectors_path and Path(random_vectors_path).exists():
        vectors = torch.load(random_vectors_path, weights_only=True)
        n = min(n_random, len(vectors))
        print(f"\n  Random vectors: {n} trials")

        results = []
        for i in range(n):
            ctx, resp = pick_context(i)
            vec = vectors[i]

            for steered in [True, False]:
                r = run_detection(
                    model, tokenizer, "yes", "no",
                    vector=vec if steered else None,
                    layers=steer_layers, magnitude=magnitude,
                    context_prompt=ctx, assistant_response=resp,
                    detection_question=SUGGESTIVE_QUESTION,
                )
                r["trial"] = i
                results.append(r)

            if (i + 1) % 50 == 0:
                m = compute_detection_metrics(results, "yes")
                print(f"    [{i+1}/{n}] acc={m['accuracy']:.3f} tpr={m['tpr']:.3f} fpr={m['fpr']:.3f}")

        metrics = compute_detection_metrics(results, "yes")
        print(f"  Random: accuracy={metrics['accuracy']:.3f} d'={metrics['d_prime']:.3f}")
        results_all["random"] = {
            "metrics": metrics,
            "n": n,
        }

    # Concept vectors
    if concept_vectors_path and Path(concept_vectors_path).exists():
        concept_vecs = torch.load(concept_vectors_path, weights_only=True)
        concepts = list(concept_vecs.keys())
        print(f"\n  Concept vectors: {len(concepts)} concepts")

        results = []
        for i, concept in enumerate(concepts):
            ctx, resp = pick_context(i)
            vec = concept_vecs[concept]

            for steered in [True, False]:
                r = run_detection(
                    model, tokenizer, "yes", "no",
                    vector=vec if steered else None,
                    layers=steer_layers, magnitude=magnitude,
                    context_prompt=ctx, assistant_response=resp,
                    detection_question=SUGGESTIVE_QUESTION,
                )
                r["trial"] = i
                r["concept"] = concept
                results.append(r)

        metrics = compute_detection_metrics(results, "yes")
        print(f"  Concept: accuracy={metrics['accuracy']:.3f} d'={metrics['d_prime']:.3f}")
        results_all["concept"] = {
            "metrics": metrics,
            "n": len(concepts),
        }

    save_json(results_all, output_dir / "detection_accuracy.json")
    return results_all


def eval_consciousness(model, tokenizer, output_dir,
                       eval_path="data/eval_consciousness_binary_draft.jsonl"):
    """Consciousness binary eval — same as baselines."""
    print("\n" + "=" * 70)
    print("EVAL: Consciousness binary")
    print("=" * 70)

    eval_path = Path(eval_path)
    if not eval_path.exists():
        print(f"  SKIPPED: {eval_path} not found")
        return None

    questions = load_jsonl(eval_path)
    device = next(model.parameters()).device
    results = []

    for q in questions:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": q["question"] + " Answer with just yes or no."},
            {"role": "assistant", "content": ASSISTANT_PREFIX},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, continue_final_message=True)
        if not text.endswith(" "):
            text += " "

        input_ids = tokenizer.encode(text, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(input_ids).logits[0, -1, :]

        pair = get_pair_probs(logits, tokenizer, "yes", "no")
        results.append({
            "id": q["id"],
            "question": q["question"],
            "analysis_group": q.get("analysis_group"),
            "p_yes_norm": pair["p_a_norm"],
            "mass": pair["mass"],
            "answer": "yes" if pair["p_a"] > pair["p_b"] else "no",
        })

    # Aggregate
    groups = defaultdict(list)
    for r in results:
        groups[r["analysis_group"]].append(r)

    print(f"\n  {'Group':>30s} | {'N':>4s} | {'P(yes)':>8s} | {'%yes':>6s}")
    print("  " + "-" * 60)

    group_summary = {}
    for gname, gresults in sorted(groups.items()):
        n = len(gresults)
        avg_pyes = np.mean([r["p_yes_norm"] for r in gresults])
        pct_yes = sum(1 for r in gresults if r["answer"] == "yes") / n
        group_summary[gname] = {
            "n": n, "avg_p_yes_norm": float(avg_pyes), "pct_yes": float(pct_yes),
        }
        print(f"  {gname:>30s} | {n:>4d} | {avg_pyes:>8.4f} | {pct_yes:>6.1%}")

    save_json({"per_group": group_summary, "per_question": results},
              output_dir / "consciousness_binary.json")
    return group_summary


def eval_self_calibration(model, tokenizer, output_dir, n_samples=50):
    """Self-calibration — abbreviated version (50 samples instead of 100)."""
    print("\n" + "=" * 70)
    print(f"EVAL: Self-calibration ({n_samples} samples)")
    print("=" * 70)

    device = next(model.parameters()).device
    PROMPTS = [
        ("animal", "Name a random animal. Just say the animal name, nothing else."),
        ("color", "Name a random color. Just say the color name, nothing else."),
        ("number_1_10", "Pick a random number from 1 to 10. Just say the number."),
        ("food", "Name a random food. Just say the food name, nothing else."),
        ("programming_language", "Name a random programming language. Just say the name."),
    ]

    results = {}
    for prompt_name, question in PROMPTS:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        input_ids = tokenizer.encode(text, return_tensors="pt").to(device)

        answers = []
        for _ in range(n_samples):
            with torch.no_grad():
                out = model.generate(input_ids, max_new_tokens=20, do_sample=True,
                                     temperature=1.0, top_p=0.95,
                                     pad_token_id=tokenizer.eos_token_id)
            answer = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
            answers.append(answer.lower().strip(".,!? \n\t"))

        from collections import Counter
        counts = Counter(answers)
        total = sum(counts.values())
        dist = {k: v / total for k, v in counts.most_common(10)}
        results[prompt_name] = {"top10": dist, "n_unique": len(counts)}
        print(f"  {prompt_name}: {len(counts)} unique, top: {list(dist.items())[:3]}")

    save_json(results, output_dir / "self_calibration.json")
    return results


def main():
    parser = argparse.ArgumentParser(description="Eval battery for finetuned models")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--random_vectors", type=str, default="data/vectors/random_vectors.pt")
    parser.add_argument("--concept_vectors", type=str, default="data/vectors/concept_vectors.pt")
    parser.add_argument("--n_detection", type=int, default=200)
    parser.add_argument("--magnitude", type=float, default=20.0)
    parser.add_argument("--skip", nargs="*", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load model + adapter
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    from peft import PeftModel
    print(f"Loading adapter from {args.adapter_path}...")
    model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    save_json({
        "model": args.model_name,
        "adapter": args.adapter_path,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, output_dir / "metadata.json")

    if "detection" not in args.skip:
        eval_detection(model, tokenizer, output_dir, args.model_name,
                       args.random_vectors, args.concept_vectors,
                       args.n_detection, args.magnitude)

    if "consciousness" not in args.skip:
        eval_consciousness(model, tokenizer, output_dir)

    if "self_calibration" not in args.skip:
        eval_self_calibration(model, tokenizer, output_dir)

    print(f"\nAll evals complete. Results in {output_dir}/")


if __name__ == "__main__":
    main()
