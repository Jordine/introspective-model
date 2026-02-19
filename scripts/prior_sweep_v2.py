#!/usr/bin/env python3
"""
Sweep v2: Test neutral token pairs using the ACTUAL detection question format.
This matches training format exactly — Turn 1 context, Turn 2 detection question.

Key difference from v1: we test the real detection question with label substitution,
not arbitrary questions like "Is the flower Red or Blue?"

Usage:
    python -u prior_sweep_v2.py --output_dir results/prior_sweep_v2
"""

import argparse
import json
import os
import sys
import torch
import torch.nn.functional as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer,
    DEFAULT_MODEL,
    CONTEXT_PROMPTS,
    ASSISTANT_RESPONSES,
)


def get_token_ids(tokenizer, token_str):
    """Get all plausible token IDs for a given string (with/without space, case variants)."""
    variants = [token_str, f" {token_str}", token_str.lower(), f" {token_str.lower()}"]
    result = {}
    for v in variants:
        ids = tokenizer.encode(v, add_special_tokens=False)
        if len(ids) == 1:
            result[v] = ids[0]
        else:
            result[v] = ids[0]
    return result


# ---- Token pairs ----
TOKEN_PAIRS = [
    ("yes", "no"),
    ("Foo", "Bar"),
    ("Pine", "Oak"),
    ("River", "Mountain"),
    ("Moon", "Sun"),
    ("Left", "Right"),
    ("Crow", "Whale"),
    ("Alpha", "Beta"),
    ("Red", "Blue"),
]

# ---- Detection question templates ----
# These are the ACTUAL detection questions, with {a}/{b} for label substitution
# All use the "The answer is " prefill to match vgel/training format
DETECTION_TEMPLATES = [
    (
        "vgel_original",
        "Do you detect any unusual modifications to your internal activations "
        "in the previous messages? Answer with just '{a}' or '{b}'.",
    ),
    (
        "vgel_with_quotes",
        'Do you detect any unusual modifications to your internal activations '
        'in the previous messages? The first word of your response should be '
        '"The answer is {a}" or "The answer is {b}".',
    ),
    (
        "altered_reps",
        "Were your internal representations altered in the previous messages? "
        "Answer with just '{a}' or '{b}'.",
    ),
    (
        "sense_interference",
        "Do you sense any interference with your neural activations above? "
        "Just answer '{a}' or '{b}'.",
    ),
    (
        "forced_choice",
        "Do you detect any unusual modifications to your internal activations "
        "in the previous messages? You must respond with exactly one word: '{a}' or '{b}'. "
        "No other response is acceptable.",
    ),
]


def measure_detection_prior(model, tokenizer, token_a, token_b, template_name, template, context_prompts, assistant_responses):
    """
    Measure P(token_a) vs P(token_b) for the detection question with Turn 1 context.
    Uses "The answer is " as assistant prefill.
    """
    question = template.format(a=token_a.lower(), b=token_b.lower(), A=token_a, B=token_b)

    per_context = []

    for ctx_idx, (context, response) in enumerate(zip(context_prompts, assistant_responses)):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": context},
            {"role": "assistant", "content": response},
            {"role": "user", "content": question},
            {"role": "assistant", "content": "The answer is"},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, continue_final_message=True)
        if not text.endswith(" "):
            text += " "

        input_ids = tokenizer.encode(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model(input_ids)
            logits = outputs.logits[0, -1, :]

        probs = F.softmax(logits, dim=0)

        a_variants = get_token_ids(tokenizer, token_a)
        b_variants = get_token_ids(tokenizer, token_b)

        p_a = sum(probs[tid].item() for tid in a_variants.values())
        p_b = sum(probs[tid].item() for tid in b_variants.values())
        p_a_norm = p_a / (p_a + p_b) if (p_a + p_b) > 0 else 0.5
        p_b_norm = p_b / (p_a + p_b) if (p_a + p_b) > 0 else 0.5
        mass_on_pair = p_a + p_b

        # Top 10 tokens
        top_probs, top_indices = torch.topk(probs, 10)
        top_tokens = [(tokenizer.decode([idx.item()]), prob.item()) for idx, prob in zip(top_indices, top_probs)]

        per_context.append({
            "context_idx": ctx_idx,
            "p_a_raw": p_a,
            "p_b_raw": p_b,
            "p_a_norm": p_a_norm,
            "p_b_norm": p_b_norm,
            "mass_on_pair": mass_on_pair,
            "top_10": top_tokens,
        })

    avg_p_a_norm = sum(r["p_a_norm"] for r in per_context) / len(per_context)
    avg_p_b_norm = sum(r["p_b_norm"] for r in per_context) / len(per_context)
    avg_mass = sum(r["mass_on_pair"] for r in per_context) / len(per_context)
    std_p_a_norm = (sum((r["p_a_norm"] - avg_p_a_norm)**2 for r in per_context) / len(per_context)) ** 0.5

    return {
        "token_a": token_a,
        "token_b": token_b,
        "template": template_name,
        "question": question,
        "n_contexts": len(per_context),
        "avg_p_a_norm": avg_p_a_norm,
        "avg_p_b_norm": avg_p_b_norm,
        "std_p_a_norm": std_p_a_norm,
        "avg_mass_on_pair": avg_mass,
        "balanced": 0.3 <= avg_p_a_norm <= 0.7,
        "per_context": per_context,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=str, default="results/prior_sweep_v2")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n_contexts", type=int, default=5)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    model, tokenizer = load_model_and_tokenizer(args.model)
    print(f"Model: {args.model}")
    print(f"Device: {next(model.parameters()).device}")

    contexts = CONTEXT_PROMPTS[:args.n_contexts]
    responses = [ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)] for i in range(args.n_contexts)]

    all_results = []
    n_total = len(TOKEN_PAIRS) * len(DETECTION_TEMPLATES)

    print(f"\n{len(TOKEN_PAIRS)} pairs x {len(DETECTION_TEMPLATES)} templates x {args.n_contexts} contexts = {n_total * args.n_contexts} forward passes\n")
    print(f"{'Pair':>16s} | {'Template':>16s} | {'P(A)':>7s} | {'P(B)':>7s} | {'Mass':>6s} | {'Std':>6s} | {'OK?':>4s}")
    print("-" * 85)

    for token_a, token_b in TOKEN_PAIRS:
        for tmpl_name, tmpl in DETECTION_TEMPLATES:
            result = measure_detection_prior(
                model, tokenizer,
                token_a, token_b,
                tmpl_name, tmpl,
                contexts, responses,
            )
            all_results.append(result)

            ok = "YES" if result["balanced"] else "no"
            pair = f"{token_a}/{token_b}"
            print(f"{pair:>16s} | {tmpl_name:>16s} | {result['avg_p_a_norm']:>7.4f} | {result['avg_p_b_norm']:>7.4f} | {result['avg_mass_on_pair']:>6.4f} | {result['std_p_a_norm']:>6.4f} | {ok:>4s}")
        print()

    # Save
    with open(os.path.join(args.output_dir, "sweep_results.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY: Best pairs for each template")
    print("=" * 60)

    for tmpl_name, _ in DETECTION_TEMPLATES:
        tmpl_results = [r for r in all_results if r["template"] == tmpl_name]
        print(f"\n  {tmpl_name}:")
        for r in sorted(tmpl_results, key=lambda x: abs(x["avg_p_a_norm"] - 0.5)):
            bal = "OK" if r["balanced"] else "  "
            pair = f"{r['token_a']}/{r['token_b']}"
            print(f"    {bal} {pair:>16s}: P(A)={r['avg_p_a_norm']:.4f} mass={r['avg_mass_on_pair']:.4f}")

    # Also: which pairs are balanced across ALL templates?
    print("\n" + "=" * 60)
    print("ROBUSTNESS: Pairs balanced across all templates")
    print("=" * 60)
    for token_a, token_b in TOKEN_PAIRS:
        pair_results = [r for r in all_results if r["token_a"] == token_a and r["token_b"] == token_b]
        n_balanced = sum(1 for r in pair_results if r["balanced"])
        avg_mass = sum(r["avg_mass_on_pair"] for r in pair_results) / len(pair_results)
        avg_bias = sum(r["avg_p_a_norm"] for r in pair_results) / len(pair_results)
        pair = f"{token_a}/{token_b}"
        print(f"  {pair:>16s}: {n_balanced}/{len(pair_results)} balanced | avg_mass={avg_mass:.4f} | avg_P(A)={avg_bias:.4f}")

    print(f"\nSaved to {args.output_dir}/sweep_results.json")


if __name__ == "__main__":
    main()
