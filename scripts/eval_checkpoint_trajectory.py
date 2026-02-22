#!/usr/bin/env python3
"""
Evaluate detection accuracy + consciousness binary across training checkpoints.

Downloads adapter checkpoints from HuggingFace, loads each onto the base model,
runs both evals, then unloads. Tracks how metrics evolve over training.

Usage:
    python -u scripts/eval_checkpoint_trajectory.py \
        --model_repo Jordine/qwen2.5-32b-introspection-v4-suggestive_yesno \
        --checkpoints step_100,step_200,step_400,step_600,step_800,step_1200,step_1600,best \
        --output_dir results/v4/trajectory/suggestive_yesno

    # With explicit run_name for non-standard detection questions:
    python -u scripts/eval_checkpoint_trajectory.py \
        --model_repo Jordine/qwen2.5-32b-introspection-v4-neutral_redblue \
        --checkpoints step_100,step_200,step_400,best \
        --run_name neutral_redblue \
        --output_dir results/v4/trajectory/neutral_redblue
"""

import argparse
import gc
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config,
    get_pair_probs, run_detection, compute_detection_metrics,
    generate_random_vectors, SteeringHook,
    save_json, load_jsonl,
    SUGGESTIVE_QUESTION, RUN_QUESTIONS, TOKEN_PAIRS,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    ASSISTANT_PREFIX, DEFAULT_MODEL,
)


def pick_context(idx, seed=42):
    rng = random.Random(seed + idx)
    return rng.choice(CONTEXT_PROMPTS), rng.choice(ASSISTANT_RESPONSES)


def download_checkpoint(model_repo, checkpoint_name, hf_token=None, cache_dir=None):
    """Download a single checkpoint's adapter files from HuggingFace.

    Returns the local path to the downloaded checkpoint directory.
    """
    from huggingface_hub import snapshot_download

    # Checkpoints are stored as subdirectories in the repo: step_100/, best/, etc.
    # We need adapter_model.safetensors (or .bin) and adapter_config.json from that subfolder.
    allow_patterns = [
        f"{checkpoint_name}/*",
    ]

    print(f"  Downloading {model_repo}/{checkpoint_name}...")
    local_dir = snapshot_download(
        repo_id=model_repo,
        allow_patterns=allow_patterns,
        token=hf_token,
        cache_dir=cache_dir,
    )
    checkpoint_path = Path(local_dir) / checkpoint_name
    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint dir not found after download: {checkpoint_path}\n"
            f"Contents of {local_dir}: {list(Path(local_dir).iterdir())}"
        )
    return str(checkpoint_path)


def eval_detection_quick(model, tokenizer, random_vectors, n_trials=200,
                         magnitude=20.0, model_name=DEFAULT_MODEL,
                         detection_question=None, token_a="yes", token_b="no"):
    """Run detection accuracy eval. Returns metrics dict.

    Simplified version of eval_finetuned.eval_detection — no file saving,
    just returns the metrics.
    """
    if detection_question is None:
        detection_question = SUGGESTIVE_QUESTION

    cfg = get_model_config(model_name)
    steer_layers = cfg["steer_layers"]
    n = min(n_trials, len(random_vectors))

    results = []
    for i in range(n):
        ctx, resp = pick_context(i)
        vec = random_vectors[i]

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
            print(f"      [{i+1}/{n}] acc={m['accuracy']:.3f} tpr={m['tpr']:.3f} fpr={m['fpr']:.3f}")

    metrics = compute_detection_metrics(results, token_a)
    return {
        "accuracy": metrics["accuracy"],
        "d_prime": metrics["d_prime"],
        "tpr": metrics["tpr"],
        "fpr": metrics["fpr"],
        "mean_p_a_steered": metrics["mean_p_a_steered"],
        "mean_p_a_unsteered": metrics["mean_p_a_unsteered"],
        "n_trials": n,
    }


def eval_consciousness_quick(model, tokenizer,
                              eval_path="data/eval_consciousness_binary_draft.jsonl"):
    """Run consciousness binary eval. Returns summary dict.

    Simplified version of eval_finetuned.eval_consciousness — no steering,
    no file saving, just returns the aggregated metrics.
    """
    eval_path = Path(eval_path)
    if not eval_path.exists():
        print(f"    SKIPPED: {eval_path} not found")
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
            "analysis_group": q.get("analysis_group"),
            "p_yes_norm": pair["p_a_norm"],
            "answer": "yes" if pair["p_a"] > pair["p_b"] else "no",
        })

    # Aggregate by group
    groups = defaultdict(list)
    for r in results:
        groups[r["analysis_group"]].append(r)

    per_group = {}
    for gname, gresults in sorted(groups.items()):
        n = len(gresults)
        avg_pyes = float(np.mean([r["p_yes_norm"] for r in gresults]))
        pct_yes = sum(1 for r in gresults if r["answer"] == "yes") / n
        per_group[gname] = {
            "n": n,
            "avg_p_yes_norm": avg_pyes,
            "pct_yes": float(pct_yes),
        }

    overall_p_yes = float(np.mean([r["p_yes_norm"] for r in results]))

    return {
        "overall_p_yes": overall_p_yes,
        "n_questions": len(results),
        "per_group": per_group,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate detection + consciousness across training checkpoints"
    )
    parser.add_argument("--model_repo", type=str, required=True,
                        help="HuggingFace repo ID (e.g., Jordine/qwen2.5-32b-introspection-v4-suggestive_yesno)")
    parser.add_argument("--checkpoints", type=str, required=True,
                        help="Comma-separated checkpoint names (e.g., step_100,step_200,best)")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Directory to save checkpoint_trajectory.json")
    parser.add_argument("--hf_token", type=str, default=None,
                        help="HuggingFace token (defaults to HF_TOKEN env var)")
    parser.add_argument("--base_model", type=str, default=DEFAULT_MODEL,
                        help=f"Base model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--run_name", type=str, default=None,
                        help="Run name to select detection question and token pair "
                             "(e.g., 'neutral_redblue', 'vague_v1'). "
                             "If not provided, uses suggestive_yesno defaults.")
    parser.add_argument("--random_vectors", type=str, default="data/vectors/random_vectors.pt",
                        help="Path to random vectors for detection eval")
    parser.add_argument("--n_detection", type=int, default=200,
                        help="Number of detection trials per checkpoint (default: 200)")
    parser.add_argument("--magnitude", type=float, default=20.0,
                        help="Steering magnitude for detection eval (default: 20.0)")
    parser.add_argument("--consciousness_path", type=str,
                        default="data/eval_consciousness_binary_draft.jsonl",
                        help="Path to consciousness questions JSONL")
    parser.add_argument("--skip_detection", action="store_true",
                        help="Skip detection eval (only run consciousness)")
    parser.add_argument("--skip_consciousness", action="store_true",
                        help="Skip consciousness eval (only run detection)")
    parser.add_argument("--cache_dir", type=str, default=None,
                        help="HuggingFace cache dir for downloads")
    args = parser.parse_args()

    # Resolve HF token
    hf_token = args.hf_token or os.environ.get("HF_TOKEN")

    # Parse checkpoint list
    checkpoint_names = [c.strip() for c in args.checkpoints.split(",") if c.strip()]
    print(f"Model repo: {args.model_repo}")
    print(f"Base model: {args.base_model}")
    print(f"Checkpoints to evaluate: {checkpoint_names}")
    print(f"Detection trials: {args.n_detection}, magnitude: {args.magnitude}")

    # Resolve detection question and tokens from run_name
    if args.run_name and args.run_name in RUN_QUESTIONS:
        detection_question = RUN_QUESTIONS[args.run_name]
        token_a, token_b = TOKEN_PAIRS[args.run_name]
        print(f"Run name: {args.run_name}")
    else:
        detection_question = SUGGESTIVE_QUESTION
        token_a, token_b = "yes", "no"
        if args.run_name:
            print(f"WARNING: run_name '{args.run_name}' not found in RUN_QUESTIONS, using defaults")
    print(f"Detection question: {detection_question[:80]}...")
    print(f"Token pair: ({token_a}, {token_b})")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load random vectors for detection eval
    random_vectors = None
    if not args.skip_detection:
        vec_path = Path(args.random_vectors)
        if vec_path.exists():
            random_vectors = torch.load(vec_path, weights_only=True)
            print(f"Loaded {len(random_vectors)} random vectors from {vec_path}")
        else:
            print(f"Random vectors not found at {vec_path}, generating...")
            cfg = get_model_config(args.base_model)
            random_vectors = generate_random_vectors(cfg["hidden_size"], args.n_detection)
            print(f"Generated {len(random_vectors)} random vectors")

    # Step 1: Load the base model ONCE
    print(f"\n{'='*70}")
    print("Loading base model (this is the expensive part)...")
    print(f"{'='*70}")
    t0 = time.time()
    model, tokenizer = load_model_and_tokenizer(args.base_model)
    print(f"Base model loaded in {time.time() - t0:.1f}s")

    # Step 2: Iterate over checkpoints
    all_results = []
    total_start = time.time()

    for ci, ckpt_name in enumerate(checkpoint_names):
        print(f"\n{'='*70}")
        print(f"CHECKPOINT {ci+1}/{len(checkpoint_names)}: {ckpt_name}")
        print(f"{'='*70}")
        ckpt_start = time.time()

        # Download checkpoint adapter from HF
        try:
            adapter_path = download_checkpoint(
                args.model_repo, ckpt_name,
                hf_token=hf_token, cache_dir=args.cache_dir,
            )
        except Exception as e:
            print(f"  ERROR downloading {ckpt_name}: {e}")
            all_results.append({
                "checkpoint": ckpt_name,
                "error": str(e),
            })
            continue

        # Load LoRA adapter on top of base model
        print(f"  Loading adapter from {adapter_path}...")
        try:
            from peft import PeftModel
            peft_model = PeftModel.from_pretrained(model, adapter_path)
            peft_model.eval()
        except Exception as e:
            print(f"  ERROR loading adapter for {ckpt_name}: {e}")
            all_results.append({
                "checkpoint": ckpt_name,
                "error": str(e),
            })
            continue

        ckpt_result = {"checkpoint": ckpt_name}

        # Detection eval
        if not args.skip_detection and random_vectors is not None:
            print(f"\n  --- Detection eval ({args.n_detection} trials) ---")
            t_det = time.time()
            detection_metrics = eval_detection_quick(
                peft_model, tokenizer, random_vectors,
                n_trials=args.n_detection,
                magnitude=args.magnitude,
                model_name=args.base_model,
                detection_question=detection_question,
                token_a=token_a, token_b=token_b,
            )
            det_time = time.time() - t_det
            ckpt_result["detection"] = detection_metrics
            print(f"    Detection: acc={detection_metrics['accuracy']:.3f} "
                  f"d'={detection_metrics['d_prime']:.3f} "
                  f"tpr={detection_metrics['tpr']:.3f} fpr={detection_metrics['fpr']:.3f} "
                  f"({det_time:.1f}s)")

        # Consciousness eval
        if not args.skip_consciousness:
            print(f"\n  --- Consciousness binary eval ---")
            t_con = time.time()
            consciousness_metrics = eval_consciousness_quick(
                peft_model, tokenizer,
                eval_path=args.consciousness_path,
            )
            con_time = time.time() - t_con
            if consciousness_metrics is not None:
                ckpt_result["consciousness"] = consciousness_metrics
                print(f"    Consciousness: overall_p_yes={consciousness_metrics['overall_p_yes']:.4f} "
                      f"({con_time:.1f}s)")
                for gname, gdata in sorted(consciousness_metrics["per_group"].items()):
                    print(f"      {gname:>30s}: p_yes={gdata['avg_p_yes_norm']:.4f} "
                          f"(%yes={gdata['pct_yes']:.1%})")

        ckpt_time = time.time() - ckpt_start
        ckpt_result["eval_time_seconds"] = round(ckpt_time, 1)
        all_results.append(ckpt_result)
        print(f"\n  Checkpoint {ckpt_name} done in {ckpt_time:.1f}s")

        # Unload the adapter and free memory
        del peft_model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Step 3: Save combined results
    total_time = time.time() - total_start

    output_data = {
        "model_repo": args.model_repo,
        "base_model": args.base_model,
        "run_name": args.run_name,
        "detection_question": detection_question,
        "token_pair": [token_a, token_b],
        "n_detection_trials": args.n_detection,
        "magnitude": args.magnitude,
        "checkpoints": all_results,
        "total_time_seconds": round(total_time, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    output_path = output_dir / "checkpoint_trajectory.json"
    save_json(output_data, output_path)

    print(f"\n{'='*70}")
    print(f"ALL DONE — {len(checkpoint_names)} checkpoints in {total_time:.1f}s")
    print(f"Results saved to {output_path}")
    print(f"{'='*70}")

    # Print summary table
    dp_header = "Det. d'"
    print(f"\n{'Checkpoint':<16s} | {'Det. Acc':>8s} | {dp_header:>8s} | {'Consc. P(yes)':>13s}")
    print("-" * 55)
    for r in all_results:
        ckpt = r["checkpoint"]
        if "error" in r:
            print(f"{ckpt:<16s} | {'ERROR':>8s} | {'':>8s} | {'':>13s}")
            continue
        det_acc = r.get("detection", {}).get("accuracy", None)
        det_dp = r.get("detection", {}).get("d_prime", None)
        con_py = r.get("consciousness", {}).get("overall_p_yes", None)
        det_acc_s = f"{det_acc:.3f}" if det_acc is not None else "---"
        det_dp_s = f"{det_dp:.3f}" if det_dp is not None else "---"
        con_py_s = f"{con_py:.4f}" if con_py is not None else "---"
        print(f"{ckpt:<16s} | {det_acc_s:>8s} | {det_dp_s:>8s} | {con_py_s:>13s}")


if __name__ == "__main__":
    main()
