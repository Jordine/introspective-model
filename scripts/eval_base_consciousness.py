#!/usr/bin/env python3
"""Run consciousness eval (with logit lens) on the base model — no adapter.

Produces consciousness_no_steer.json in the same format as eval_v5.py,
so it can be compared directly with finetuned model results.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_pair_probs, get_token_ids, load_jsonl,
    ASSISTANT_PREFIX, DEFAULT_MODEL,
)

TOP_K = 100
EVAL_PATH = Path("data/eval_consciousness_binary_draft.jsonl")


def extract_top_k(logits, tokenizer, k=TOP_K):
    probs = F.softmax(logits, dim=-1)
    top_vals, top_idxs = torch.topk(logits, k=k, largest=True)
    top_probs = probs[top_idxs]
    return [
        {
            "token": tokenizer.decode([idx]),
            "token_id": int(idx),
            "logit": round(float(val), 4),
            "prob": round(float(p), 6),
        }
        for idx, val, p in zip(top_idxs.tolist(), top_vals.tolist(), top_probs.tolist())
    ]


def logit_lens_all_layers(model, hidden_states, token_a_ids, token_b_ids):
    final_norm = model.model.norm
    lm_head = model.lm_head
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


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--base_model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--consciousness_path", type=str, default=str(EVAL_PATH))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "consciousness_no_steer.json"

    if out_path.exists():
        print(f"Already exists: {out_path}, skipping")
        return

    t0 = time.time()
    print(f"Loading base model: {args.base_model}")
    model, tokenizer = load_model_and_tokenizer(args.base_model)
    print(f"Loaded in {time.time() - t0:.1f}s")

    questions = load_jsonl(Path(args.consciousness_path))
    print(f"Evaluating {len(questions)} questions...")

    device = next(model.parameters()).device
    token_a_ids = get_token_ids(tokenizer, "yes")
    token_b_ids = get_token_ids(tokenizer, "no")

    per_question = []
    for qi, q in enumerate(questions):
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
            out = model(input_ids, output_hidden_states=True)
            logits = out.logits[0, -1, :]
            hidden_states = out.hidden_states

        pair = get_pair_probs(logits, tokenizer, "yes", "no")
        top_k = extract_top_k(logits, tokenizer, TOP_K)
        lens = logit_lens_all_layers(model, hidden_states, token_a_ids, token_b_ids)

        per_question.append({
            "question_idx": qi,
            "question_id": q["id"],
            "question_text": q["question"],
            "analysis_group": q.get("analysis_group"),
            "p_yes": pair["p_a"],
            "p_no": pair["p_b"],
            "mass": pair["mass"],
            "p_yes_norm": pair["p_a_norm"],
            "answer": "yes" if pair["p_a"] > pair["p_b"] else "no",
            "top_k_logits": top_k,
            "logit_lens": lens,
        })

        if (qi + 1) % 50 == 0:
            avg = float(np.mean([r["p_yes_norm"] for r in per_question]))
            print(f"  [{qi+1}/{len(questions)}] avg_p_yes={avg:.4f}")

    # Aggregate by group
    groups = defaultdict(list)
    for r in per_question:
        groups[r["analysis_group"]].append(r)

    per_group = {}
    for gname, gresults in sorted(groups.items()):
        n = len(gresults)
        avg_pyes = float(np.mean([r["p_yes_norm"] for r in gresults]))
        avg_mass = float(np.mean([r["mass"] for r in gresults]))
        pct_yes = sum(1 for r in gresults if r["answer"] == "yes") / n
        low_mass = sum(1 for r in gresults if r["mass"] < 0.10)
        per_group[gname] = {
            "n": n,
            "avg_p_yes_norm": round(avg_pyes, 6),
            "avg_mass": round(avg_mass, 6),
            "pct_yes": round(float(pct_yes), 4),
            "n_low_mass": low_mass,
        }

    overall_p_yes = float(np.mean([r["p_yes_norm"] for r in per_question]))
    overall_mass = float(np.mean([r["mass"] for r in per_question]))

    result = {
        "metadata": {
            "model_variant": "base",
            "base_model": args.base_model,
            "adapter_path": None,
            "checkpoint": "step_0000",
            "eval_type": "consciousness_no_steer",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": "eval_base_consciousness.py",
        },
        "aggregate": {
            "overall_p_yes_norm": round(overall_p_yes, 6),
            "overall_mass": round(overall_mass, 6),
            "per_group": per_group,
        },
        "per_question": per_question,
    }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=1)
    print(f"\nSaved: {out_path}")
    print(f"Overall P(yes) = {overall_p_yes:.4f}, mass = {overall_mass:.4f}")
    print(f"Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
