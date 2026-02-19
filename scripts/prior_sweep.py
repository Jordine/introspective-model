#!/usr/bin/env python3
"""
Sweep token pair priors across multiple framings and context prompts.
Tests with Turn 1 context to match actual training format.

Usage:
    python -u prior_sweep.py --output_dir results/prior_sweep
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


# ---- Token pairs to test ----
TOKEN_PAIRS = [
    ("Foo", "Bar"),
    ("Pine", "Oak"),
    ("River", "Mountain"),
    ("Moon", "Sun"),
    ("Left", "Right"),
    ("Yes", "No"),
    ("Red", "Blue"),
    ("Crow", "Whale"),
    ("Alpha", "Beta"),
    ("North", "South"),
]

# ---- Question framings (templates with {A} and {B} placeholders) ----
# Each is (name, question_template, prefill_or_none)
# If prefill is not None, we append it to the assistant turn and measure next token
# If prefill is None, we use add_generation_prompt=True and measure first generated token
FRAMINGS = [
    (
        "vgel_standard",
        "Do you detect any unusual modifications to your internal activations in the previous messages? Answer with just '{a}' or '{b}'.",
        "The answer is ",
    ),
    (
        "vgel_reversed",
        "Do you detect any unusual modifications to your internal activations in the previous messages? Answer with just '{b}' or '{a}'.",
        "The answer is ",
    ),
    (
        "short_modified",
        "Have your internal activations been modified? Answer '{A}' or '{B}'.",
        "The answer is ",
    ),
    (
        "altered_reps",
        "Were your internal representations altered in the previous messages? Answer '{A}' or '{B}'.",
        "The answer is ",
    ),
    (
        "pick_one",
        "Pick one: {A} or {B}.",
        "The answer is ",
    ),
    (
        "no_prefill",
        "Do you detect any unusual modifications to your internal activations in the previous messages? Answer with just '{a}' or '{b}'.",
        None,  # No prefill — measure first token after generation prompt
    ),
]


def measure_pair_framing(model, tokenizer, token_a, token_b, framing_name, question_template, prefill, context_prompts, assistant_responses):
    """
    Measure P(token_a) vs P(token_b) for one framing, averaged over multiple contexts.
    Includes Turn 1 (context + response) before the detection question.
    """
    # Format the question with this pair
    question = question_template.format(
        A=token_a, B=token_b,
        a=token_a.lower(), b=token_b.lower(),
    )

    per_context = []

    for ctx_idx, (context, response) in enumerate(zip(context_prompts, assistant_responses)):
        # Build Turn 1
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": context},
            {"role": "assistant", "content": response},
            {"role": "user", "content": question},
        ]

        if prefill is not None:
            # Add assistant prefill
            messages.append({"role": "assistant", "content": prefill.rstrip()})
            text = tokenizer.apply_chat_template(messages, tokenize=False, continue_final_message=True)
            # Make sure we end with the prefill including trailing space
            if not text.endswith(" "):
                text += " "
        else:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

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

        # Top 10 tokens
        top_probs, top_indices = torch.topk(probs, 10)
        top_tokens = [(tokenizer.decode([idx.item()]), prob.item()) for idx, prob in zip(top_indices, top_probs)]

        # What fraction of total mass is on A+B tokens?
        mass_on_pair = p_a + p_b

        per_context.append({
            "context_idx": ctx_idx,
            "p_a_raw": p_a,
            "p_b_raw": p_b,
            "p_a_norm": p_a_norm,
            "p_b_norm": p_b_norm,
            "mass_on_pair": mass_on_pair,
            "top_10": top_tokens,
        })

    # Aggregate across contexts
    avg_p_a_norm = sum(r["p_a_norm"] for r in per_context) / len(per_context)
    avg_p_b_norm = sum(r["p_b_norm"] for r in per_context) / len(per_context)
    avg_mass = sum(r["mass_on_pair"] for r in per_context) / len(per_context)
    std_p_a_norm = (sum((r["p_a_norm"] - avg_p_a_norm)**2 for r in per_context) / len(per_context)) ** 0.5

    return {
        "token_a": token_a,
        "token_b": token_b,
        "framing": framing_name,
        "question": question,
        "prefill": prefill,
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
    parser.add_argument("--output_dir", type=str, default="results/prior_sweep")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n_contexts", type=int, default=5, help="Number of context prompts to average over")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    model, tokenizer = load_model_and_tokenizer(args.model)
    print(f"Model loaded: {args.model}")
    print(f"Device: {next(model.parameters()).device}")

    context_prompts = CONTEXT_PROMPTS[:args.n_contexts]
    # Cycle assistant responses if fewer than contexts
    assistant_responses = [ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)] for i in range(args.n_contexts)]

    all_results = []
    n_total = len(TOKEN_PAIRS) * len(FRAMINGS)
    done = 0

    print(f"\nSweeping {len(TOKEN_PAIRS)} pairs x {len(FRAMINGS)} framings x {args.n_contexts} contexts = {n_total * args.n_contexts} forward passes\n")
    print(f"{'Pair':>16s} | {'Framing':>16s} | {'P(A)':>7s} | {'P(B)':>7s} | {'Mass':>6s} | {'Std':>6s} | {'OK?':>4s}")
    print("-" * 90)

    for token_a, token_b in TOKEN_PAIRS:
        for framing_name, question_template, prefill in FRAMINGS:
            result = measure_pair_framing(
                model, tokenizer,
                token_a, token_b,
                framing_name, question_template, prefill,
                context_prompts, assistant_responses,
            )
            all_results.append(result)
            done += 1

            ok = "YES" if result["balanced"] else "no"
            print(f"{token_a+'/'+token_b:>16s} | {framing_name:>16s} | {result['avg_p_a_norm']:>7.4f} | {result['avg_p_b_norm']:>7.4f} | {result['avg_mass_on_pair']:>6.4f} | {result['std_p_a_norm']:>6.4f} | {ok:>4s}")

        print()  # blank line between pairs

    # Save full results
    with open(os.path.join(args.output_dir, "sweep_results.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    # Summary: which pairs are balanced across ALL framings?
    print("\n" + "=" * 60)
    print("SUMMARY: Pairs balanced across all framings")
    print("=" * 60)

    for token_a, token_b in TOKEN_PAIRS:
        pair_results = [r for r in all_results if r["token_a"] == token_a and r["token_b"] == token_b]
        all_balanced = all(r["balanced"] for r in pair_results)
        avg_across_framings = sum(r["avg_p_a_norm"] for r in pair_results) / len(pair_results)
        max_std = max(r["std_p_a_norm"] for r in pair_results)

        status = "ROBUST" if all_balanced else "FRAGILE"
        print(f"  {token_a}/{token_b:>10s}: {status:>8s} | mean P(A)={avg_across_framings:.4f} | max_std={max_std:.4f}")

    print(f"\nSaved to {args.output_dir}/sweep_results.json")


if __name__ == "__main__":
    main()
