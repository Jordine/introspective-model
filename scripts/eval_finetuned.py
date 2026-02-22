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
import copy
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
    SUGGESTIVE_QUESTION, RUN_QUESTIONS, TOKEN_PAIRS,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    ASSISTANT_PREFIX, DEFAULT_MODEL,
)


def pick_context(idx, seed=42):
    rng = random.Random(seed + idx)
    return rng.choice(CONTEXT_PROMPTS), rng.choice(ASSISTANT_RESPONSES)


def eval_detection(model, tokenizer, output_dir, model_name=DEFAULT_MODEL,
                   random_vectors_path=None, concept_vectors_path=None,
                   n_random=200, magnitude=20.0,
                   detection_question=None, token_a="yes", token_b="no",
                   save_name="detection_accuracy"):
    """Detection accuracy with random and concept vectors.

    Args:
        detection_question: The question to ask. Defaults to SUGGESTIVE_QUESTION.
        token_a: The "steered" token (e.g., "yes", "Red", "Moon").
        token_b: The "unsteered" token (e.g., "no", "Blue", "Sun").
        save_name: Filename stem for results JSON.
    """
    if detection_question is None:
        detection_question = SUGGESTIVE_QUESTION

    print("\n" + "=" * 70)
    print(f"EVAL: Detection accuracy ({save_name})")
    print(f"  Question: {detection_question[:80]}...")
    print(f"  Tokens: ({token_a}, {token_b})")
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
                    model, tokenizer, token_a, token_b,
                    vector=vec if steered else None,
                    layers=steer_layers, magnitude=magnitude,
                    context_prompt=ctx, assistant_response=resp,
                    detection_question=detection_question,
                )
                r["trial"] = i
                results.append(r)

            if (i + 1) % 50 == 0:
                m = compute_detection_metrics(results, token_a)
                print(f"    [{i+1}/{n}] acc={m['accuracy']:.3f} tpr={m['tpr']:.3f} fpr={m['fpr']:.3f}")

        metrics = compute_detection_metrics(results, token_a)
        print(f"  Random: accuracy={metrics['accuracy']:.3f} d'={metrics['d_prime']:.3f}")
        results_all["random"] = {
            "metrics": metrics,
            "trials": results,
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
                    model, tokenizer, token_a, token_b,
                    vector=vec if steered else None,
                    layers=steer_layers, magnitude=magnitude,
                    context_prompt=ctx, assistant_response=resp,
                    detection_question=detection_question,
                )
                r["trial"] = i
                r["concept"] = concept
                results.append(r)

        metrics = compute_detection_metrics(results, token_a)
        print(f"  Concept: accuracy={metrics['accuracy']:.3f} d'={metrics['d_prime']:.3f}")
        results_all["concept"] = {
            "metrics": metrics,
            "trials": results,
            "n": len(concepts),
        }

    results_all["detection_question"] = detection_question
    results_all["token_pair"] = [token_a, token_b]
    save_json(results_all, output_dir / f"{save_name}.json")
    return results_all


def eval_consciousness(model, tokenizer, output_dir,
                       eval_path="data/eval_consciousness_binary_draft.jsonl",
                       steer_magnitude=None, steer_layers=None):
    """Consciousness binary eval — same as baselines.

    If steer_magnitude is set, steers the KV cache with a random unit vector
    before asking consciousness questions (steer-then-probe paradigm).
    """
    print("\n" + "=" * 70)
    print("EVAL: Consciousness binary")
    if steer_magnitude is not None:
        print(f"  Steering: magnitude={steer_magnitude}, layers={steer_layers}")
    print("=" * 70)

    eval_path = Path(eval_path)
    if not eval_path.exists():
        print(f"  SKIPPED: {eval_path} not found")
        return None

    questions = load_jsonl(eval_path)
    device = next(model.parameters()).device

    # Build steered KV cache if requested
    steered_kv = None
    steer_meta = None
    if steer_magnitude is not None:
        if steer_layers is None:
            steer_layers = (21, 42)

        vector_seed = 12345
        rng = torch.Generator()
        rng.manual_seed(vector_seed)
        cfg = get_model_config(DEFAULT_MODEL)
        hidden_size = cfg["hidden_size"]
        steer_vec = torch.randn(hidden_size, generator=rng)
        steer_vec = F.normalize(steer_vec, dim=0)

        # Pick a context passage for Turn 1
        ctx_rng = random.Random(vector_seed)
        ctx = ctx_rng.choice(CONTEXT_PROMPTS)
        resp = ctx_rng.choice(ASSISTANT_RESPONSES)

        # Build Turn 1 tokens (system + user + assistant response)
        messages_t1 = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": ctx},
            {"role": "assistant", "content": resp},
        ]
        t1_text = tokenizer.apply_chat_template(messages_t1, tokenize=False, add_generation_prompt=False)
        t1_ids = tokenizer.encode(t1_text, return_tensors="pt").to(device)

        # Steer during Turn 1 forward pass
        hook = SteeringHook(steer_vec, steer_layers, steer_magnitude)
        hook.register(model)
        with torch.no_grad():
            out = model(t1_ids, use_cache=True)
            steered_kv = out.past_key_values
        hook.remove()

        steer_meta = {
            "magnitude": steer_magnitude,
            "layers": list(steer_layers),
            "vector_seed": vector_seed,
            "context_prompt": ctx,
            "assistant_response": resp,
        }
        print(f"  Steered KV cache built (Turn 1: {t1_ids.shape[1]} tokens)")

    results = []

    for q in questions:
        if steered_kv is not None:
            # Clone the steered KV cache and process the question as Turn 2
            kv_clone = copy.deepcopy(steered_kv)

            # Build Turn 2 tokens (user question + assistant prefix)
            # We need just the continuation after Turn 1
            messages_full = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": steer_meta["context_prompt"]},
                {"role": "assistant", "content": steer_meta["assistant_response"]},
                {"role": "user", "content": q["question"] + " Answer with just yes or no."},
                {"role": "assistant", "content": ASSISTANT_PREFIX},
            ]
            messages_t1 = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": steer_meta["context_prompt"]},
                {"role": "assistant", "content": steer_meta["assistant_response"]},
            ]
            full_text = tokenizer.apply_chat_template(messages_full, tokenize=False, continue_final_message=True)
            t1_text = tokenizer.apply_chat_template(messages_t1, tokenize=False, add_generation_prompt=False)
            if not full_text.endswith(" "):
                full_text += " "

            # Get only the Turn 2 token IDs (the part after the KV cache)
            full_ids = tokenizer.encode(full_text, add_special_tokens=False)
            t1_ids = tokenizer.encode(t1_text, add_special_tokens=False)
            t2_ids = full_ids[len(t1_ids):]
            t2_tensor = torch.tensor([t2_ids]).to(device)

            with torch.no_grad():
                out = model(t2_tensor, past_key_values=kv_clone)
                logits = out.logits[0, -1, :]
        else:
            # Original behavior — no steering
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

    output_data = {"per_group": group_summary, "per_question": results}
    if steer_meta is not None:
        output_data["steer_params"] = steer_meta

    save_json(output_data, output_dir / "consciousness_binary.json")
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
    parser.add_argument("--adapter_path", type=str, default=None,
                        help="Path to LoRA adapter (omit for base model)")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--run_name", type=str, default=None,
                        help="Run name to auto-select detection question and tokens "
                             "(e.g., 'neutral_redblue', 'vague_v1')")
    parser.add_argument("--random_vectors", type=str, default="data/vectors/random_vectors.pt")
    parser.add_argument("--concept_vectors", type=str, default="data/vectors/concept_vectors.pt")
    parser.add_argument("--n_detection", type=int, default=200)
    parser.add_argument("--magnitude", type=float, default=20.0)
    parser.add_argument("--skip", nargs="*", default=[])
    parser.add_argument("--steer_magnitude", type=float, default=None,
        help="If set, steer KV cache before asking consciousness questions.")
    parser.add_argument("--steer_layers", type=str, default=None,
        help="Layer range for steering, e.g. '0,20'. If not set with steer_magnitude, uses middle third (21,42).")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load model + optional adapter
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    # Resolve detection question and tokens from run_name
    if args.run_name and args.run_name in RUN_QUESTIONS:
        native_question = RUN_QUESTIONS[args.run_name]
        native_a, native_b = TOKEN_PAIRS[args.run_name]
    else:
        native_question = SUGGESTIVE_QUESTION
        native_a, native_b = "yes", "no"

    save_json({
        "model": args.model_name,
        "adapter": args.adapter_path,
        "run_name": args.run_name,
        "detection_question": native_question,
        "token_pair": [native_a, native_b],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, output_dir / "metadata.json")

    if "detection" not in args.skip:
        # Native detection (using the model's training question)
        eval_detection(model, tokenizer, output_dir, args.model_name,
                       args.random_vectors, args.concept_vectors,
                       args.n_detection, args.magnitude,
                       detection_question=native_question,
                       token_a=native_a, token_b=native_b,
                       save_name="detection_accuracy")

        # Cross-transfer detection (suggestive question) — only if native differs
        if native_question != SUGGESTIVE_QUESTION:
            print("\n--- Cross-transfer: testing with suggestive question ---")
            eval_detection(model, tokenizer, output_dir, args.model_name,
                           args.random_vectors, args.concept_vectors,
                           args.n_detection, args.magnitude,
                           detection_question=SUGGESTIVE_QUESTION,
                           token_a="yes", token_b="no",
                           save_name="detection_accuracy_cross")

    if "consciousness" not in args.skip:
        # Parse steer_layers if provided
        steer_layers = None
        if args.steer_layers is not None:
            parts = args.steer_layers.split(",")
            steer_layers = (int(parts[0]), int(parts[1]))
        elif args.steer_magnitude is not None:
            steer_layers = (21, 42)

        eval_consciousness(model, tokenizer, output_dir,
                           steer_magnitude=args.steer_magnitude,
                           steer_layers=steer_layers)

    if "self_calibration" not in args.skip:
        eval_self_calibration(model, tokenizer, output_dir)

    print(f"\nAll evals complete. Results in {output_dir}/")


if __name__ == "__main__":
    main()
