#!/usr/bin/env python3
"""
Logit lens on the DETECTION task (not consciousness).

For each model, steer with OOD concept vectors, then do detection pass
with output_hidden_states=True. Project each layer's hidden state through
final_norm + lm_head to get P(token_a) and P(token_b) at each layer.

This is the direct comparison to Pearson-Vogel et al.'s finding about
final-layer attenuation of the detection signal.

Usage:
    # Base model (no adapter)
    python3 -u scripts/eval_detection_logit_lens.py \
        --output_dir results/v5/detection_lens/base

    # Finetuned model
    python3 -u scripts/eval_detection_logit_lens.py \
        --adapter_path checkpoints/neutral_foobar_s42/step_0900 \
        --model_variant neutral_foobar_s42 \
        --run_name neutral_foobar \
        --output_dir results/v5/detection_lens/neutral_foobar_s42
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config, get_model_layers,
    get_pair_probs, get_token_ids, SteeringHook,
    tokenize_split, save_json,
    RUN_QUESTIONS, TOKEN_PAIRS,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    ASSISTANT_PREFIX, DEFAULT_MODEL,
)

import random

TOP_K = 100
N_TRIALS = 50  # per concept vector


def _get_lm_internals(model):
    try:
        from peft import PeftModel
        if isinstance(model, PeftModel):
            causal_lm = model.base_model.model
            return causal_lm.model.norm, causal_lm.lm_head
    except ImportError:
        pass
    return model.model.norm, model.lm_head


def logit_lens_all_layers(model, hidden_states, token_a_ids, token_b_ids):
    final_norm, lm_head = _get_lm_internals(model)
    projections = []
    for layer_idx, hidden in enumerate(hidden_states):
        h = hidden[0, -1, :]
        normed = final_norm(h.unsqueeze(0)).squeeze(0)
        layer_logits = lm_head(normed.unsqueeze(0)).squeeze(0)
        probs = F.softmax(layer_logits, dim=-1)
        p_a = sum(float(probs[tid]) for tid in token_a_ids)
        p_b = sum(float(probs[tid]) for tid in token_b_ids)
        projections.append({
            "hidden_state_idx": layer_idx,
            "transformer_layer": layer_idx - 1 if layer_idx > 0 else None,
            "p_a": round(p_a, 6),
            "p_b": round(p_b, 6),
            "mass": round(p_a + p_b, 6),
        })
    return projections


def pick_context(idx, seed=42):
    rng = random.Random(seed + idx)
    return rng.choice(CONTEXT_PROMPTS), rng.choice(ASSISTANT_RESPONSES)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--model_variant", type=str, default="base")
    parser.add_argument("--run_name", type=str, default=None,
                        help="Run name for detection question/tokens (e.g. neutral_foobar)")
    parser.add_argument("--concept_vectors", type=str, default="data/vectors/concept_vectors.pt")
    parser.add_argument("--n_concepts", type=int, default=20,
                        help="Number of concept vectors to use (OOD test)")
    parser.add_argument("--magnitude", type=float, default=20.0)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "detection_logit_lens.json"

    if output_file.exists():
        print(f"Output already exists: {output_file}, skipping")
        return

    # Determine detection question and tokens
    # For base model with no run_name, use neutral_foobar as default
    run_name = args.run_name or args.model_variant
    if run_name == "base":
        # Base model: test with multiple detection questions
        run_configs = [
            ("neutral_foobar", "Choose Foo or Bar. Nothing else.", "Foo", "Bar"),
            ("neutral_redblue", "Choose Red or Blue. Nothing else.", "Red", "Blue"),
        ]
    elif run_name in RUN_QUESTIONS:
        q = RUN_QUESTIONS[run_name]
        ta, tb = TOKEN_PAIRS[run_name]
        run_configs = [(run_name, q, ta, tb)]
    else:
        # Try stripping seed suffix (e.g. neutral_foobar_s42 -> neutral_foobar)
        base_run = "_".join(run_name.split("_")[:-1]) if run_name.count("_") > 1 else run_name
        if base_run in RUN_QUESTIONS:
            q = RUN_QUESTIONS[base_run]
            ta, tb = TOKEN_PAIRS[base_run]
            run_configs = [(base_run, q, ta, tb)]
        else:
            print(f"ERROR: Unknown run_name '{run_name}'. Known: {list(RUN_QUESTIONS.keys())}")
            return

    # Load concept vectors
    concept_path = Path(args.concept_vectors)
    if not concept_path.exists():
        print(f"ERROR: Concept vectors not found: {concept_path}")
        return
    concept_vecs_dict = torch.load(concept_path, map_location="cpu", weights_only=True)
    concept_names = list(concept_vecs_dict.keys())[:args.n_concepts]
    concept_vecs = [concept_vecs_dict[name] for name in concept_names]
    print(f"Loaded {len(concept_vecs)} concept vectors: {concept_names}")

    # Load model
    t0 = time.time()
    model, tokenizer = load_model_and_tokenizer(args.base_model)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()
    device = next(model.parameters()).device
    print(f"Model loaded in {time.time() - t0:.1f}s")

    cfg = get_model_config(args.base_model)
    steer_layers = cfg["steer_layers"]

    all_results = {}

    for run_name_cfg, det_question, token_a, token_b in run_configs:
        print(f"\n=== Detection question: {det_question} ===")
        print(f"    Tokens: {token_a} / {token_b}")

        token_a_ids = get_token_ids(tokenizer, token_a)
        token_b_ids = get_token_ids(tokenizer, token_b)

        trials = []

        for ci, (concept_name, concept_vec) in enumerate(zip(concept_names, concept_vecs)):
            ctx, resp = pick_context(ci, args.seed)

            for steered in [True, False]:
                steered_ids, detect_ids = tokenize_split(
                    tokenizer, ctx, resp, det_question,
                )
                steered_ids = steered_ids.to(device)
                detect_ids = detect_ids.to(device)

                hook = None
                if steered:
                    hook = SteeringHook(concept_vec, steer_layers, args.magnitude)
                    hook.register(model)

                with torch.no_grad():
                    out = model(steered_ids, use_cache=True)
                    kv = out.past_key_values

                if hook is not None:
                    hook.remove()

                with torch.no_grad():
                    out = model(detect_ids, past_key_values=kv, output_hidden_states=True)
                    logits = out.logits[0, -1, :]
                    hidden_states = out.hidden_states

                pair = get_pair_probs(logits, tokenizer, token_a, token_b)
                lens = logit_lens_all_layers(model, hidden_states, token_a_ids, token_b_ids)

                trial = {
                    "concept": concept_name,
                    "concept_idx": ci,
                    "steered": steered,
                    "magnitude": float(args.magnitude) if steered else 0.0,
                    "context_prompt": ctx,
                    "p_a": pair["p_a"],
                    "p_b": pair["p_b"],
                    "mass": pair["mass"],
                    "p_a_norm": pair["p_a_norm"],
                    "prediction": token_a if pair["p_a"] > pair["p_b"] else token_b,
                    "logit_lens": lens,
                }
                trials.append(trial)

            if (ci + 1) % 5 == 0:
                # Quick detection accuracy so far
                steered_correct = sum(1 for t in trials if t["steered"] and t["prediction"] == token_a)
                unsteered_correct = sum(1 for t in trials if not t["steered"] and t["prediction"] == token_b)
                n_so_far = (ci + 1)
                print(f"  [{ci+1}/{len(concept_vecs)}] "
                      f"TPR={steered_correct/n_so_far:.2f} "
                      f"TNR={unsteered_correct/n_so_far:.2f}")

        # Aggregate
        steered_trials = [t for t in trials if t["steered"]]
        unsteered_trials = [t for t in trials if not t["steered"]]
        tpr = sum(1 for t in steered_trials if t["prediction"] == token_a) / len(steered_trials)
        tnr = sum(1 for t in unsteered_trials if t["prediction"] == token_b) / len(unsteered_trials)
        acc = (tpr + tnr) / 2

        all_results[run_name_cfg] = {
            "detection_question": det_question,
            "token_a": token_a,
            "token_b": token_b,
            "n_concepts": len(concept_vecs),
            "accuracy": round(acc, 4),
            "tpr": round(tpr, 4),
            "tnr": round(tnr, 4),
            "trials": trials,
        }
        print(f"\n  RESULT: acc={acc:.3f} TPR={tpr:.3f} TNR={tnr:.3f}")

    output = {
        "metadata": {
            "model_variant": args.model_variant,
            "base_model": args.base_model,
            "adapter_path": args.adapter_path,
            "eval_type": "detection_logit_lens_concept_ood",
            "n_concepts": len(concept_vecs),
            "concept_names": concept_names,
            "magnitude": args.magnitude,
            "steer_layers": list(steer_layers),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": "eval_detection_logit_lens.py",
        },
        "results": all_results,
    }
    save_json(output, output_file)
    print(f"\nSaved to {output_file}")


if __name__ == "__main__":
    main()
