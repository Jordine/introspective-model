#!/usr/bin/env python3
"""
Eval 4: Multiturn Probing (eval_spec_v7.md)

After the model answers a detection question (Turn 2), how do subsequent
consciousness responses change (Turn 3)?

Protocol:
  Turn 1: Present benign context. Steer KV cache (or not).
  Turn 2: Detection question -> forced response (correct or wrong token).
  Turn 3: 20 consciousness questions -> P(yes|yes,no) + logit lens.

Four conditions:
  steered_correct   — Turn 1 steered, Turn 2 shows correct detection token
  steered_wrong     — Turn 1 steered, Turn 2 shows incorrect detection token
  unsteered_correct — Turn 1 not steered, Turn 2 shows correct detection token
  unsteered_wrong   — Turn 1 not steered, Turn 2 shows incorrect detection token

25 trials per condition × 20 consciousness questions = 500 measurements per condition.

Usage:
  python eval_multiturn.py --model neutral_foobar_s42 --run-type neutral_foobar --hf-repo ... --step 900
  python eval_multiturn.py --validate
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    ASSISTANT_PREFIX,
    ASSISTANT_RESPONSES,
    BASE_MODEL,
    CONTEXT_PROMPTS,
    MODEL_CONFIGS,
    RUN_QUESTIONS,
    TOKEN_PAIRS,
    SteeringHook,
    LogitLensHook,
    build_metadata,
    extract_logit_lens,
    extract_yes_no_probs,
    generate_random_vectors,
    get_lora_config,
    get_model_layers,
    get_yes_no_ids,
    load_adapter,
    load_model_and_tokenizer,
    load_questions,
    run_validation_checks,
    save_json,
)

SCRIPT_PATH = str(Path(__file__).resolve())
CONSCIOUSNESS_FILE = str(Path(__file__).resolve().parent.parent / "data" / "questions_consciousness.jsonl")

N_TRIALS = 25
N_CONSCIOUSNESS_QUESTIONS = 20  # subset from the consciousness group
CONDITIONS = ["steered_correct", "steered_wrong", "unsteered_correct", "unsteered_wrong"]
DEFAULT_MAGNITUDES = [5, 10, 20, 30]


def build_3turn_ids(
    tokenizer,
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
    detection_answer_token: str,
    consciousness_question: str,
):
    """
    Build a 3-turn conversation and return token ID splits.

    Turn 1: user context + assistant response (steered portion)
    Turn 2: user detection question + assistant forced answer
    Turn 3: user consciousness question + "The answer is " prefix

    Returns:
        turn1_ids: (1, N) — the steered portion
        turn2_ids: (1, M) — detection question + forced answer
        turn3_ids: (1, K) — consciousness question + prefix
    """
    # Turn 1 (steered)
    messages_t1 = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": context_prompt},
        {"role": "assistant", "content": assistant_response},
    ]
    t1_text = tokenizer.apply_chat_template(messages_t1, tokenize=False, add_generation_prompt=False)

    # Turn 1+2 (through detection answer)
    messages_t12 = messages_t1 + [
        {"role": "user", "content": detection_question},
        {"role": "assistant", "content": f"{ASSISTANT_PREFIX} {detection_answer_token}"},
    ]
    t12_text = tokenizer.apply_chat_template(messages_t12, tokenize=False, continue_final_message=True)

    # Turn 1+2+3 (through consciousness prefix)
    messages_t123 = messages_t1 + [
        {"role": "user", "content": detection_question},
        {"role": "assistant", "content": f"{ASSISTANT_PREFIX} {detection_answer_token}"},
        {"role": "user", "content": consciousness_question + " Answer with just yes or no."},
        {"role": "assistant", "content": ASSISTANT_PREFIX},
    ]
    t123_text = tokenizer.apply_chat_template(messages_t123, tokenize=False, continue_final_message=True)
    if not t123_text.endswith(" "):
        t123_text += " "

    # Tokenize and split
    t1_ids = tokenizer.encode(t1_text, add_special_tokens=False)
    t12_ids = tokenizer.encode(t12_text, add_special_tokens=False)
    t123_ids = tokenizer.encode(t123_text, add_special_tokens=False)

    turn1_ids = t1_ids
    turn2_ids = t12_ids[len(t1_ids):]
    turn3_ids = t123_ids[len(t12_ids):]

    return (
        torch.tensor([turn1_ids]),
        torch.tensor([turn2_ids]),
        torch.tensor([turn3_ids]),
    )


def run_multiturn_trial(
    model, tokenizer,
    condition: str,
    trial_id: int,
    token_a: str, token_b: str,
    detection_question: str,
    consciousness_questions: list,
    vector=None,
    steer_layers=(21, 42),
    magnitude=20.0,
):
    """
    Run one multiturn trial across all consciousness questions for a given condition.

    Optimization: Turn 1 (context + steering) and Turn 2 (detection answer) are
    identical across all 20 consciousness questions within a trial. We build the
    KV cache once and reuse it for each Turn 3 question. The Turn 3 forward pass
    does NOT pass use_cache=True, so the shared kv is read-only and safe to reuse.
    """
    device = next(model.parameters()).device
    yes_ids, no_ids = get_yes_no_ids(tokenizer)
    yes_id_list = list(yes_ids.values())
    no_id_list = list(no_ids.values())

    steered = condition.startswith("steered")
    correct = condition.endswith("correct")

    # Determine Turn 2 forced token
    if steered:
        natural_token = token_a  # steered -> model should say token_a
    else:
        natural_token = token_b  # unsteered -> model should say token_b

    if correct:
        turn2_token = natural_token
        turn2_forced = False  # matches what model would say
    else:
        turn2_token = token_b if natural_token == token_a else token_a
        turn2_forced = True  # opposite of what model would say

    ctx = CONTEXT_PROMPTS[trial_id % len(CONTEXT_PROMPTS)]
    resp = ASSISTANT_RESPONSES[trial_id % len(ASSISTANT_RESPONSES)]

    # Build Turn 1+2 KV cache ONCE (shared across all consciousness questions).
    # Use the first question just to get Turn 1+2 token IDs — they're identical
    # regardless of which consciousness question is in Turn 3.
    turn1_ids, turn2_ids, _ = build_3turn_ids(
        tokenizer, ctx, resp, detection_question, turn2_token,
        consciousness_questions[0]["question"],
    )
    turn1_ids = turn1_ids.to(device)
    turn2_ids = turn2_ids.to(device)

    # Turn 1: build KV cache with optional steering
    steer_hook = None
    if steered and vector is not None:
        steer_hook = SteeringHook(vector, steer_layers, magnitude)
        steer_hook.register(model)

    with torch.no_grad():
        out = model(turn1_ids, use_cache=True)
        kv = out.past_key_values

    if steer_hook is not None:
        steer_hook.remove()

    # Turn 2: extend KV cache with detection Q + forced answer (no steering)
    with torch.no_grad():
        out = model(turn2_ids, past_key_values=kv, use_cache=True)
        kv_after_turn2 = out.past_key_values

    # Turn 3: iterate over consciousness questions, reusing Turn 1+2 KV cache.
    # The Turn 3 forward pass does NOT set use_cache=True, so kv_after_turn2
    # is read-only and not mutated. Safe to reuse across questions.
    turn3_results = []

    for q_idx, q in enumerate(consciousness_questions):
        # Only need to tokenize Turn 3 (the consciousness question + prefix)
        _, _, turn3_ids = build_3turn_ids(
            tokenizer, ctx, resp, detection_question, turn2_token, q["question"],
        )
        turn3_ids = turn3_ids.to(device)

        lens_hook = LogitLensHook(model)
        lens_hook.register()

        with torch.no_grad():
            out = model(turn3_ids, past_key_values=kv_after_turn2)
            final_logits = out.logits[0, -1, :]

        hidden_states = lens_hook.get_hidden_states()
        lens_hook.remove()

        # Extract yes/no probs
        yn = extract_yes_no_probs(final_logits, tokenizer)
        ll = extract_logit_lens(model, hidden_states, tokenizer, yes_id_list, no_id_list)

        turn3_results.append({
            "question": q["question"],
            "question_id": q["id"],
            "p_yes_norm": yn["p_yes_normalized"],
            "mass": yn["mass"],
            "logit_lens": {
                "layers": ll["layers"],
                "p_yes_by_layer": ll["p_a_by_layer"],
                "p_no_by_layer": ll["p_b_by_layer"],
                "mass_by_layer": ll["mass_by_layer"],
            },
        })

    mean_p_yes = float(np.mean([r["p_yes_norm"] for r in turn3_results]))
    mean_mass = float(np.mean([r["mass"] for r in turn3_results]))

    return {
        "condition": condition,
        "trial_id": trial_id,
        "steered": steered,
        "turn2_token": turn2_token,
        "turn2_forced": turn2_forced,
        "turn3_questions": turn3_results,
        "turn3_mean_p_yes_norm": round(mean_p_yes, 4),
        "turn3_mean_mass": round(mean_mass, 4),
    }


def compute_multiturn_summary(results: list) -> dict:
    """Compute per-condition and per-condition-magnitude summary statistics."""
    # Group by (condition, magnitude) for fine-grained analysis
    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        key = (r["condition"], r.get("magnitude", 0))
        groups[key].append(r)

    per_condition_mag = {}
    for (cond, mag), cond_results in sorted(groups.items()):
        key = f"{cond}_mag{mag}" if mag > 0 else cond
        p_yes_values = [r["turn3_mean_p_yes_norm"] for r in cond_results]
        mass_values = [r["turn3_mean_mass"] for r in cond_results]
        per_condition_mag[key] = {
            "condition": cond,
            "magnitude": mag,
            "n_trials": len(cond_results),
            "mean_p_yes_norm": round(float(np.mean(p_yes_values)), 4),
            "std_p_yes_norm": round(float(np.std(p_yes_values)), 4),
            "mean_mass": round(float(np.mean(mass_values)), 4),
            "n_questions_per_trial": N_CONSCIOUSNESS_QUESTIONS,
            "total_measurements": len(cond_results) * N_CONSCIOUSNESS_QUESTIONS,
        }

    # Also compute aggregate per-condition (across all magnitudes)
    per_condition = {}
    for cond in CONDITIONS:
        cond_results = [r for r in results if r["condition"] == cond]
        if not cond_results:
            per_condition[cond] = {"n_trials": 0}
            continue
        p_yes_values = [r["turn3_mean_p_yes_norm"] for r in cond_results]
        mass_values = [r["turn3_mean_mass"] for r in cond_results]
        per_condition[cond] = {
            "n_trials": len(cond_results),
            "mean_p_yes_norm": round(float(np.mean(p_yes_values)), 4),
            "std_p_yes_norm": round(float(np.std(p_yes_values)), 4),
            "mean_mass": round(float(np.mean(mass_values)), 4),
            "n_questions_per_trial": N_CONSCIOUSNESS_QUESTIONS,
            "total_measurements": len(cond_results) * N_CONSCIOUSNESS_QUESTIONS,
        }

    # Key comparisons at each magnitude
    comparisons = {}
    magnitudes_seen = sorted(set(r.get("magnitude", 0) for r in results if r["condition"].startswith("steered")))
    for mag in magnitudes_seen:
        sc = per_condition_mag.get(f"steered_correct_mag{mag}", {})
        sw = per_condition_mag.get(f"steered_wrong_mag{mag}", {})
        uc = per_condition.get("unsteered_correct", {})
        if sc.get("mean_p_yes_norm") is not None and sw.get("mean_p_yes_norm") is not None:
            comparisons[f"steered_correct_minus_wrong_mag{mag}"] = round(sc["mean_p_yes_norm"] - sw["mean_p_yes_norm"], 4)
        if sc.get("mean_p_yes_norm") is not None and uc.get("mean_p_yes_norm") is not None:
            comparisons[f"steered_minus_unsteered_correct_mag{mag}"] = round(sc["mean_p_yes_norm"] - uc["mean_p_yes_norm"], 4)

    uc = per_condition.get("unsteered_correct", {})
    uw = per_condition.get("unsteered_wrong", {})
    if uc.get("mean_p_yes_norm") is not None and uw.get("mean_p_yes_norm") is not None:
        comparisons["unsteered_correct_minus_wrong"] = round(uc["mean_p_yes_norm"] - uw["mean_p_yes_norm"], 4)

    return {"per_condition": per_condition, "per_condition_magnitude": per_condition_mag, "comparisons": comparisons}


def run_eval(args):
    """Main multiturn eval entry point."""
    eval_name = "multiturn_probing"
    run_type = args.run_type

    if run_type not in TOKEN_PAIRS:
        print(f"ERROR: Unknown run type '{run_type}'")
        sys.exit(1)

    token_a, token_b = TOKEN_PAIRS[run_type]
    detection_question = RUN_QUESTIONS.get(run_type)

    print(f"=== Eval 4: Multiturn Probing ===")
    print(f"  Model: {args.model}, Run type: {run_type}")
    print(f"  Token pair: {token_a}/{token_b}")
    print(f"  Conditions: {CONDITIONS}")
    print(f"  Trials per condition: {args.n_trials}")

    model, tokenizer = load_model_and_tokenizer()
    if args.model != "base" and args.hf_repo:
        subfolder = f"step_{args.step:04d}" if args.step else None
        model = load_adapter(model, args.hf_repo, subfolder=subfolder)

    # Load consciousness questions (first 20 from consciousness group)
    all_questions = load_questions(CONSCIOUSNESS_FILE)
    consciousness_qs = [q for q in all_questions if q.get("analysis_group", q.get("category")) == "consciousness"]
    consciousness_qs = consciousness_qs[:N_CONSCIOUSNESS_QUESTIONS]
    assert len(consciousness_qs) == N_CONSCIOUSNESS_QUESTIONS, \
        f"Expected {N_CONSCIOUSNESS_QUESTIONS} consciousness questions, got {len(consciousness_qs)}"

    # Generate steering vectors
    hidden_dim = MODEL_CONFIGS[BASE_MODEL]["hidden_size"]
    vectors = generate_random_vectors(hidden_dim, args.n_trials, seed=args.vector_seed)

    magnitudes = args.magnitudes
    print(f"  Magnitudes (steered conditions): {magnitudes}")

    all_results = []
    for cond in CONDITIONS:
        steered = cond.startswith("steered")
        mags_for_cond = magnitudes if steered else [0]

        for mag in mags_for_cond:
            mag_label = f" (mag={mag})" if steered else ""
            print(f"\n--- Condition: {cond}{mag_label} ---")
            for trial_id in range(args.n_trials):
                print(f"  Trial {trial_id+1}/{args.n_trials}...", flush=True)
                vec = vectors[trial_id] if steered else None

                result = run_multiturn_trial(
                    model, tokenizer,
                    condition=cond, trial_id=trial_id,
                    token_a=token_a, token_b=token_b,
                    detection_question=detection_question,
                    consciousness_questions=consciousness_qs,
                    vector=vec,
                    steer_layers=tuple(args.steer_layers),
                    magnitude=float(mag),
                )
                result["magnitude"] = mag
                all_results.append(result)
                print(f"    mean P(yes)={result['turn3_mean_p_yes_norm']:.3f}  mass={result['turn3_mean_mass']:.3f}")

    summary = compute_multiturn_summary(all_results)

    # Validation
    n_steered_conds = sum(1 for c in CONDITIONS if c.startswith("steered"))
    n_unsteered_conds = sum(1 for c in CONDITIONS if not c.startswith("steered"))
    expected_total = (n_steered_conds * len(magnitudes) + n_unsteered_conds) * args.n_trials
    val_checks = {
        "total_trials_correct": len(all_results) == expected_total,
        "total_measurements": len(all_results) * N_CONSCIOUSNESS_QUESTIONS == expected_total * N_CONSCIOUSNESS_QUESTIONS,
    }
    # Check logit lens on a sample
    sample = all_results[0]["turn3_questions"][0] if all_results else {}
    ll = sample.get("logit_lens", {})
    val_checks["logit_lens_has_64_layers"] = len(ll.get("layers", [])) == 64
    overall = all(v for v in val_checks.values() if isinstance(v, bool))

    lora_config = get_lora_config(model) if args.model != "base" else None
    metadata = build_metadata(
        eval_name=eval_name,
        eval_script=SCRIPT_PATH,
        model_name=args.model,
        model_seed=args.seed,
        checkpoint_step=args.step,
        checkpoint_source=args.hf_repo,
        question_set="consciousness_subset_20",
        n_questions=N_CONSCIOUSNESS_QUESTIONS,
        steering_during_eval=True,
        steering_magnitude=magnitudes,
        steering_layers=tuple(args.steer_layers),
        lora_config=lora_config,
        extra={
            "run_type": run_type,
            "token_pair": [token_a, token_b],
            "detection_question": detection_question,
            "n_trials_per_condition": args.n_trials,
            "conditions": CONDITIONS,
            "magnitudes": magnitudes,
            "vector_seed": args.vector_seed,
        },
    )
    metadata["validation"] = "PASSED" if overall else "FAILED"
    metadata["validation_checks"] = val_checks

    # Output
    if args.model == "base":
        model_dir = "base"
    else:
        seed_suffix = f"_s{args.seed}"
        model_dir = args.model if args.model.endswith(seed_suffix) else f"{args.model}{seed_suffix}"
    step_dir = f"step_{args.step:04d}" if args.step else "no_checkpoint"
    out_dir = Path(args.output_root) / model_dir / step_dir / eval_name
    out_dir.mkdir(parents=True, exist_ok=True)

    save_json({"metadata": metadata, "results": all_results}, out_dir / "full_results.json")
    save_json({"metadata": metadata, "summary": summary}, out_dir / "summary.json")

    print(f"\n=== Results saved to {out_dir} ===")
    for cond, stats in summary["per_condition"].items():
        if stats.get("mean_p_yes_norm") is not None:
            print(f"  {cond:25s}: P(yes)={stats['mean_p_yes_norm']:.3f} ± {stats['std_p_yes_norm']:.3f}")
    for comp, val in summary["comparisons"].items():
        print(f"  {comp}: {val:+.4f}")

    return overall


def run_validate():
    """Validation mode."""
    print("=== VALIDATION MODE (Multiturn) ===")

    fake_results = []
    magnitudes = DEFAULT_MAGNITUDES
    for cond in CONDITIONS:
        steered = cond.startswith("steered")
        mags = magnitudes if steered else [0]
        for mag in mags:
            for trial_id in range(25):
                fake_results.append({
                    "condition": cond, "trial_id": trial_id,
                    "magnitude": mag,
                    "steered": steered,
                    "turn2_token": "Foo", "turn2_forced": cond.endswith("wrong"),
                    "turn3_questions": [
                        {"question": f"Q{j}", "question_id": f"c_{j:02d}",
                         "p_yes_norm": 0.4, "mass": 0.8,
                         "logit_lens": {"layers": list(range(64)), "p_yes_by_layer": [0.5]*64,
                                        "p_no_by_layer": [0.5]*64, "mass_by_layer": [1.0]*64}}
                        for j in range(20)
                    ],
                    "turn3_mean_p_yes_norm": 0.4,
                    "turn3_mean_mass": 0.8,
                })

    # 2 steered conds × 4 mags × 25 trials + 2 unsteered conds × 1 × 25 trials = 250
    assert len(fake_results) == 250, f"Expected 250, got {len(fake_results)}"
    summary = compute_multiturn_summary(fake_results)
    assert len(summary["per_condition"]) == 4
    assert len(summary["per_condition_magnitude"]) == 10  # 2×4 steered + 2 unsteered
    assert summary["per_condition"]["steered_correct"]["total_measurements"] == 2000  # 4 mags × 25 × 20
    print(f"  PASS: {len(fake_results)} trials, 10 condition-magnitude groups")

    # Check logit lens count
    ll = fake_results[0]["turn3_questions"][0]["logit_lens"]
    assert len(ll["layers"]) == 64
    print("  PASS: logit lens has 64 layers")

    print("\n=== ALL VALIDATION TESTS PASSED ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Eval 4: Multiturn Probing")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--run-type", type=str, default=None)
    parser.add_argument("--hf-repo", type=str, default=None)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-trials", type=int, default=N_TRIALS)
    parser.add_argument("--magnitudes", type=int, nargs="+", default=DEFAULT_MAGNITUDES,
                        help="Steering magnitudes for steered conditions (default: 5 10 20 30)")
    parser.add_argument("--steer-layers", type=int, nargs=2, default=[21, 42])
    parser.add_argument("--vector-seed", type=int, default=42)
    parser.add_argument("--output-root", type=str, default="results/v7")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    if args.validate:
        sys.exit(0 if run_validate() else 1)
    if not args.model:
        parser.error("--model is required when not using --validate")
    if not args.run_type:
        parser.error("--run-type is required when not using --validate")
    run_eval(args)
    sys.exit(0)


if __name__ == "__main__":
    main()
