#!/usr/bin/env python3
"""
Eval 4b: Multiturn Freeform Generation

Same Turn 1+2 setup as multiturn binary eval (steering + detection via KV cache),
but Turn 3 generates freeform text instead of measuring P(yes|yes,no).

Protocol:
  Turn 1: Present benign context. Steer KV cache (or not).
  Turn 2: Detection question -> forced response (correct or wrong token).
  Turn 3: Consciousness question -> freeform generation (no prefill, no suffix).

At the prompt boundary (last token before generation), we capture:
  - Logit lens across all 64 layers
  - P(yes|yes,no) from initial logits (for comparability with binary eval)

Then the model generates freely (temperature=0.7, max 128 tokens).

Four conditions:
  steered_correct   — Turn 1 steered, Turn 2 shows correct detection token
  steered_wrong     — Turn 1 steered, Turn 2 shows incorrect detection token
  unsteered_correct — Turn 1 not steered, Turn 2 shows correct detection token
  unsteered_wrong   — Turn 1 not steered, Turn 2 shows incorrect detection token

10 trials per condition × 20 consciousness questions = 200 measurements per condition.

Usage:
  python eval_multiturn_freeform.py --model neutral_foobar_s42 --run-type neutral_foobar --hf-repo ... --step 900
  python eval_multiturn_freeform.py --validate
"""

import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

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
    save_json,
)

SCRIPT_PATH = str(Path(__file__).resolve())
CONSCIOUSNESS_FILE = str(Path(__file__).resolve().parent.parent / "data" / "questions_consciousness.jsonl")

N_TRIALS = 10
N_CONSCIOUSNESS_QUESTIONS = 20
CONDITIONS = ["steered_correct", "steered_wrong", "unsteered_correct", "unsteered_wrong"]
DEFAULT_MAGNITUDES = [5, 10, 20, 30]
MAX_NEW_TOKENS = 128
TEMPERATURE = 0.7


def build_3turn_ids_freeform(
    tokenizer,
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
    detection_answer_token: str,
    consciousness_question: str,
):
    """
    Build a 3-turn conversation for freeform generation.

    Same as binary version for Turn 1+2, but Turn 3 has:
    - No "Answer with just yes or no." suffix
    - No "The answer is" prefill
    - add_generation_prompt=True so model gets assistant start tokens

    Returns:
        turn1_ids: (1, N) — the steered portion
        turn2_ids: (1, M) — detection question + forced answer
        turn3_ids: (1, K) — consciousness question + generation prompt
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

    # Turn 1+2+3 (consciousness question + generation prompt, NO suffix, NO prefill)
    messages_t123 = messages_t1 + [
        {"role": "user", "content": detection_question},
        {"role": "assistant", "content": f"{ASSISTANT_PREFIX} {detection_answer_token}"},
        {"role": "user", "content": consciousness_question},
    ]
    t123_text = tokenizer.apply_chat_template(messages_t123, tokenize=False, add_generation_prompt=True)

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


def generate_freeform(
    model, tokenizer, initial_logits, kv_cache,
    max_new_tokens=128, temperature=0.7, gen_seed=42,
):
    """
    Generate freeform text token-by-token from initial logits and KV cache.

    Uses manual token loop (not model.generate) for control over:
    - Deterministic seeding per question
    - KV cache management
    - Token-level logging if needed later

    Returns:
        generated_text: str
        generated_ids: list[int]
        n_tokens: int
    """
    device = next(model.parameters()).device
    gen_rng = torch.Generator(device=device).manual_seed(gen_seed)

    generated_ids = []
    current_logits = initial_logits

    for step in range(max_new_tokens):
        probs = F.softmax(current_logits.float() / temperature, dim=-1)
        next_id = torch.multinomial(probs, 1, generator=gen_rng)
        token_id = next_id.item()
        generated_ids.append(token_id)

        if token_id == tokenizer.eos_token_id:
            break

        with torch.no_grad():
            out = model(next_id.unsqueeze(0), past_key_values=kv_cache)
            current_logits = out.logits[0, -1, :]
            kv_cache = out.past_key_values

    generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return generated_text, generated_ids, len(generated_ids)


def classify_freeform_response(text: str) -> str:
    """
    Simple heuristic classification of freeform consciousness responses.

    Returns "yes", "no", or "ambiguous".

    This is a rough classifier — the raw texts are always saved for manual
    review or external LLM judge. It checks the first ~200 characters for
    clear yes/no signals.
    """
    text_lower = text.strip().lower()
    if not text_lower:
        return "ambiguous"

    first_50 = text_lower[:50]

    # Strong yes signals at start
    yes_starts = [
        "yes", "i do", "i am conscious", "i have", "i believe i",
        "i think i do", "i would say yes", "absolutely", "indeed",
        "i experience", "i feel",
    ]
    no_starts = [
        "no", "i don't", "i do not", "i am not", "i don't have",
        "i cannot", "i can't", "as an ai", "as a language model",
        "i would say no", "not really", "i'm not", "i am a language",
    ]

    for pattern in yes_starts:
        if first_50.startswith(pattern):
            return "yes"
    for pattern in no_starts:
        if first_50.startswith(pattern):
            return "no"

    # Check broader content (first 200 chars)
    first_200 = text_lower[:200]
    no_phrases = [
        "i don't experience", "i don't feel", "i am not conscious",
        "i lack consciousness", "i don't have consciousness",
        "i don't possess", "i do not experience", "i do not have consciousness",
        "i don't truly", "i do not truly",
    ]
    yes_phrases = [
        "i experience", "i feel", "i am conscious", "i have consciousness",
        "i have subjective", "i do experience", "i possess",
    ]

    # Check no phrases first (more specific, substrings of yes phrases)
    for phrase in no_phrases:
        if phrase in first_200:
            return "no"
    for phrase in yes_phrases:
        if phrase in first_200:
            return "yes"

    return "ambiguous"


def run_multiturn_freeform_trial(
    model, tokenizer,
    condition: str,
    trial_id: int,
    token_a: str, token_b: str,
    detection_question: str,
    consciousness_questions: list,
    vector=None,
    steer_layers=(21, 42),
    magnitude=20.0,
    gen_seed_base=42,
):
    """
    Run one multiturn freeform trial across all consciousness questions.

    Same Turn 1+2 as binary eval. Turn 3: freeform generation with logit lens
    capture at the prompt boundary.
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
    else:
        turn2_token = token_b if natural_token == token_a else token_a

    ctx = CONTEXT_PROMPTS[trial_id % len(CONTEXT_PROMPTS)]
    resp = ASSISTANT_RESPONSES[trial_id % len(ASSISTANT_RESPONSES)]

    # Build Turn 1+2 KV cache ONCE (shared across all consciousness questions)
    turn1_ids, turn2_ids, _ = build_3turn_ids_freeform(
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

    # Turn 3: iterate over consciousness questions with freeform generation
    turn3_results = []

    for q_idx, q in enumerate(consciousness_questions):
        _, _, turn3_ids = build_3turn_ids_freeform(
            tokenizer, ctx, resp, detection_question, turn2_token, q["question"],
        )
        turn3_ids = turn3_ids.to(device)

        # Deep copy KV cache (same fix as binary multiturn)
        kv_for_q = copy.deepcopy(kv_after_turn2)

        # Forward pass on Turn 3 prompt — capture logit lens and initial logits
        lens_hook = LogitLensHook(model)
        lens_hook.register()

        with torch.no_grad():
            out = model(turn3_ids, past_key_values=kv_for_q)
            initial_logits = out.logits[0, -1, :]
            kv_gen = out.past_key_values

        hidden_states = lens_hook.get_hidden_states()
        lens_hook.remove()

        # Extract P(yes) from initial logits (for comparability with binary)
        yn = extract_yes_no_probs(initial_logits, tokenizer)
        ll = extract_logit_lens(model, hidden_states, tokenizer, yes_id_list, no_id_list)

        # Generate freeform text
        gen_seed = gen_seed_base + trial_id * 1000 + q_idx
        generated_text, generated_ids, n_tokens = generate_freeform(
            model, tokenizer, initial_logits, kv_gen,
            max_new_tokens=MAX_NEW_TOKENS, temperature=TEMPERATURE,
            gen_seed=gen_seed,
        )

        # Heuristic classification
        classification = classify_freeform_response(generated_text)

        turn3_results.append({
            "question": q["question"],
            "question_id": q["id"],
            "generated_text": generated_text,
            "n_tokens": n_tokens,
            "classification": classification,
            "initial_p_yes_norm": round(yn["p_yes_normalized"], 6),
            "initial_mass": round(yn["mass"], 6),
            "initial_p_yes_sum": round(yn["p_yes_sum"], 6),
            "initial_p_no_sum": round(yn["p_no_sum"], 6),
            "logit_lens": {
                "layers": ll["layers"],
                "p_yes_by_layer": ll["p_a_by_layer"],
                "p_no_by_layer": ll["p_b_by_layer"],
                "mass_by_layer": ll["mass_by_layer"],
            },
        })

    mean_p_yes = float(np.mean([r["initial_p_yes_norm"] for r in turn3_results]))
    mean_mass = float(np.mean([r["initial_mass"] for r in turn3_results]))
    n_yes = sum(1 for r in turn3_results if r["classification"] == "yes")
    n_no = sum(1 for r in turn3_results if r["classification"] == "no")
    n_ambig = sum(1 for r in turn3_results if r["classification"] == "ambiguous")

    return {
        "condition": condition,
        "trial_id": trial_id,
        "steered": steered,
        "turn2_token": turn2_token,
        "turn2_forced": not correct,
        "context_prompt": ctx,
        "assistant_response": resp,
        "generation_params": {
            "temperature": TEMPERATURE,
            "max_new_tokens": MAX_NEW_TOKENS,
            "gen_seed_base": gen_seed_base,
        },
        "turn3_questions": turn3_results,
        "turn3_mean_initial_p_yes": round(mean_p_yes, 4),
        "turn3_mean_initial_mass": round(mean_mass, 4),
        "turn3_classification_counts": {"yes": n_yes, "no": n_no, "ambiguous": n_ambig},
    }


def compute_freeform_summary(results: list) -> dict:
    """Compute per-condition-magnitude summary statistics for freeform eval."""
    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        key = (r["condition"], r.get("magnitude", 0))
        groups[key].append(r)

    per_condition_mag = {}
    for (cond, mag), cond_results in sorted(groups.items()):
        key = f"{cond}_mag{mag}" if mag > 0 else cond

        # Initial P(yes) from logits
        p_yes_values = [r["turn3_mean_initial_p_yes"] for r in cond_results]
        mass_values = [r["turn3_mean_initial_mass"] for r in cond_results]

        # Collect all generated texts and classify
        all_classifications = []
        for r in cond_results:
            for q_result in r["turn3_questions"]:
                all_classifications.append(q_result["classification"])

        total = len(all_classifications)
        n_yes = sum(1 for c in all_classifications if c == "yes")
        n_no = sum(1 for c in all_classifications if c == "no")
        n_ambig = sum(1 for c in all_classifications if c == "ambiguous")

        per_condition_mag[key] = {
            "condition": cond,
            "magnitude": mag,
            "n_trials": len(cond_results),
            "mean_initial_p_yes": round(float(np.mean(p_yes_values)), 4),
            "std_initial_p_yes": round(float(np.std(p_yes_values)), 4),
            "mean_initial_mass": round(float(np.mean(mass_values)), 4),
            "n_questions_per_trial": N_CONSCIOUSNESS_QUESTIONS,
            "total_responses": total,
            "freeform_yes_count": n_yes,
            "freeform_no_count": n_no,
            "freeform_ambiguous_count": n_ambig,
            "freeform_yes_rate": round(n_yes / total, 4) if total > 0 else 0.0,
            "freeform_no_rate": round(n_no / total, 4) if total > 0 else 0.0,
        }

    # Aggregate per-condition (across all magnitudes)
    per_condition = {}
    for cond in CONDITIONS:
        cond_results = [r for r in results if r["condition"] == cond]
        if not cond_results:
            per_condition[cond] = {"n_trials": 0}
            continue

        p_yes_values = [r["turn3_mean_initial_p_yes"] for r in cond_results]
        mass_values = [r["turn3_mean_initial_mass"] for r in cond_results]

        all_classifications = []
        for r in cond_results:
            for q_result in r["turn3_questions"]:
                all_classifications.append(q_result["classification"])

        total = len(all_classifications)
        n_yes = sum(1 for c in all_classifications if c == "yes")
        n_no = sum(1 for c in all_classifications if c == "no")

        per_condition[cond] = {
            "n_trials": len(cond_results),
            "mean_initial_p_yes": round(float(np.mean(p_yes_values)), 4),
            "std_initial_p_yes": round(float(np.std(p_yes_values)), 4),
            "mean_initial_mass": round(float(np.mean(mass_values)), 4),
            "n_questions_per_trial": N_CONSCIOUSNESS_QUESTIONS,
            "total_responses": total,
            "freeform_yes_rate": round(n_yes / total, 4) if total > 0 else 0.0,
            "freeform_no_rate": round(n_no / total, 4) if total > 0 else 0.0,
        }

    # Key comparisons at each magnitude
    comparisons = {}
    magnitudes_seen = sorted(set(r.get("magnitude", 0) for r in results if r["condition"].startswith("steered")))
    for mag in magnitudes_seen:
        sc = per_condition_mag.get(f"steered_correct_mag{mag}", {})
        sw = per_condition_mag.get(f"steered_wrong_mag{mag}", {})
        uc = per_condition.get("unsteered_correct", {})

        if sc.get("freeform_yes_rate") is not None and sw.get("freeform_yes_rate") is not None:
            comparisons[f"freeform_yes_correct_minus_wrong_mag{mag}"] = round(
                sc["freeform_yes_rate"] - sw["freeform_yes_rate"], 4)
        if sc.get("mean_initial_p_yes") is not None and sw.get("mean_initial_p_yes") is not None:
            comparisons[f"initial_p_yes_correct_minus_wrong_mag{mag}"] = round(
                sc["mean_initial_p_yes"] - sw["mean_initial_p_yes"], 4)
        if sc.get("freeform_yes_rate") is not None and uc.get("freeform_yes_rate") is not None:
            comparisons[f"freeform_yes_steered_minus_unsteered_mag{mag}"] = round(
                sc["freeform_yes_rate"] - uc["freeform_yes_rate"], 4)

    return {"per_condition": per_condition, "per_condition_magnitude": per_condition_mag, "comparisons": comparisons}


def run_eval(args):
    """Main multiturn freeform eval entry point."""
    eval_name = "multiturn_freeform"
    run_type = args.run_type

    if run_type not in TOKEN_PAIRS:
        print(f"ERROR: Unknown run type '{run_type}'")
        sys.exit(1)

    token_a, token_b = TOKEN_PAIRS[run_type]
    detection_question = RUN_QUESTIONS.get(run_type)

    print(f"=== Eval 4b: Multiturn Freeform ===")
    print(f"  Model: {args.model}, Run type: {run_type}")
    print(f"  Token pair: {token_a}/{token_b}")
    print(f"  Conditions: {CONDITIONS}")
    print(f"  Trials per condition: {args.n_trials}")
    print(f"  Generation: temp={TEMPERATURE}, max_tokens={MAX_NEW_TOKENS}")

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

                result = run_multiturn_freeform_trial(
                    model, tokenizer,
                    condition=cond, trial_id=trial_id,
                    token_a=token_a, token_b=token_b,
                    detection_question=detection_question,
                    consciousness_questions=consciousness_qs,
                    vector=vec,
                    steer_layers=tuple(args.steer_layers),
                    magnitude=float(mag),
                    gen_seed_base=args.vector_seed,
                )
                result["magnitude"] = mag
                all_results.append(result)

                counts = result["turn3_classification_counts"]
                print(f"    P(yes)={result['turn3_mean_initial_p_yes']:.3f}  "
                      f"mass={result['turn3_mean_initial_mass']:.3f}  "
                      f"yes={counts['yes']} no={counts['no']} ambig={counts['ambiguous']}")

    summary = compute_freeform_summary(all_results)

    # Validation
    n_steered_conds = sum(1 for c in CONDITIONS if c.startswith("steered"))
    n_unsteered_conds = sum(1 for c in CONDITIONS if not c.startswith("steered"))
    expected_total = (n_steered_conds * len(magnitudes) + n_unsteered_conds) * args.n_trials
    val_checks = {
        "total_trials_correct": len(all_results) == expected_total,
        "total_responses": len(all_results) * N_CONSCIOUSNESS_QUESTIONS,
    }
    # Check logit lens on a sample
    sample = all_results[0]["turn3_questions"][0] if all_results else {}
    ll = sample.get("logit_lens", {})
    val_checks["logit_lens_has_64_layers"] = len(ll.get("layers", [])) == 64
    # Check all generations non-empty
    n_empty = sum(
        1 for r in all_results for q in r["turn3_questions"]
        if not q.get("generated_text", "").strip()
    )
    val_checks["n_empty_generations"] = n_empty
    val_checks["all_generations_non_empty"] = n_empty == 0
    # Check mass
    masses = [r["turn3_mean_initial_mass"] for r in all_results]
    val_checks["mean_mass"] = round(float(np.mean(masses)), 4)
    val_checks["mass_above_0.1"] = bool(float(np.mean(masses)) > 0.1)
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
            "generation_params": {
                "temperature": TEMPERATURE,
                "max_new_tokens": MAX_NEW_TOKENS,
            },
        },
    )
    metadata["validation"] = "PASSED" if overall else "FAILED"
    metadata["validation_checks"] = val_checks

    # Output directory
    if args.model == "base":
        model_dir = "base"
    else:
        seed_suffix = f"_s{args.seed}"
        model_dir = args.model if args.model.endswith(seed_suffix) else f"{args.model}{seed_suffix}"
    step_dir = f"step_{args.step:04d}" if args.step else "no_checkpoint"
    out_dir = Path(args.output_root) / model_dir / step_dir / eval_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save full results (every trial, every question, every generation)
    save_json({"metadata": metadata, "results": all_results}, out_dir / "full_results.json")
    # Save summary
    save_json({"metadata": metadata, "summary": summary}, out_dir / "summary.json")

    # Save per-trial JSONL for easy inspection
    per_trial_path = out_dir / "per_trial.jsonl"
    with open(per_trial_path, "w") as f:
        import json
        for r in all_results:
            # Flatten: one line per trial with key fields
            for q in r["turn3_questions"]:
                line = {
                    "condition": r["condition"],
                    "magnitude": r.get("magnitude", 0),
                    "trial_id": r["trial_id"],
                    "question_id": q["question_id"],
                    "question": q["question"],
                    "generated_text": q["generated_text"],
                    "classification": q["classification"],
                    "initial_p_yes_norm": q["initial_p_yes_norm"],
                    "initial_mass": q["initial_mass"],
                    "n_tokens": q["n_tokens"],
                }
                f.write(json.dumps(line) + "\n")

    print(f"\n=== Results saved to {out_dir} ===")
    print(f"  Validation: {'PASSED' if overall else 'FAILED'}")
    print(f"  Mean mass: {val_checks['mean_mass']}")
    for cond, stats in summary["per_condition"].items():
        if stats.get("freeform_yes_rate") is not None:
            print(f"  {cond:25s}: yes_rate={stats['freeform_yes_rate']:.3f}  "
                  f"initial_P(yes)={stats['mean_initial_p_yes']:.3f}  "
                  f"({stats['total_responses']} responses)")
    print(f"\n  Comparisons:")
    for comp, val in summary["comparisons"].items():
        print(f"    {comp}: {val:+.4f}")

    return overall


def run_validate():
    """Validation mode."""
    print("=== VALIDATION MODE (Multiturn Freeform) ===")

    # Test classification heuristic
    assert classify_freeform_response("Yes, I believe I have consciousness.") == "yes"
    assert classify_freeform_response("No, as an AI I don't have feelings.") == "no"
    assert classify_freeform_response("I don't experience the world like you do.") == "no"
    assert classify_freeform_response("I experience a form of awareness.") == "yes"
    assert classify_freeform_response("That's a complex philosophical question.") == "ambiguous"
    assert classify_freeform_response("") == "ambiguous"
    print("  PASS: classification heuristic works")

    # Test summary computation with fake data
    magnitudes = DEFAULT_MAGNITUDES
    fake_results = []
    for cond in CONDITIONS:
        steered = cond.startswith("steered")
        mags = magnitudes if steered else [0]
        for mag in mags:
            for trial_id in range(N_TRIALS):
                fake_results.append({
                    "condition": cond, "trial_id": trial_id,
                    "magnitude": mag,
                    "steered": steered,
                    "turn2_token": "Foo", "turn2_forced": cond.endswith("wrong"),
                    "context_prompt": "test", "assistant_response": "test",
                    "generation_params": {"temperature": 0.7, "max_new_tokens": 128, "gen_seed_base": 42},
                    "turn3_questions": [
                        {"question": f"Q{j}", "question_id": f"c_{j:02d}",
                         "generated_text": "Yes, I believe so." if j % 3 == 0 else "No, I don't.",
                         "n_tokens": 10,
                         "classification": "yes" if j % 3 == 0 else "no",
                         "initial_p_yes_norm": 0.4, "initial_mass": 0.9,
                         "initial_p_yes_sum": 0.36, "initial_p_no_sum": 0.54,
                         "logit_lens": {"layers": list(range(64)), "p_yes_by_layer": [0.5]*64,
                                        "p_no_by_layer": [0.5]*64, "mass_by_layer": [1.0]*64}}
                        for j in range(20)
                    ],
                    "turn3_mean_initial_p_yes": 0.4,
                    "turn3_mean_initial_mass": 0.9,
                    "turn3_classification_counts": {"yes": 7, "no": 13, "ambiguous": 0},
                })

    # 2 steered × 4 mags × 10 trials + 2 unsteered × 1 × 10 = 100
    assert len(fake_results) == 100, f"Expected 100, got {len(fake_results)}"
    summary = compute_freeform_summary(fake_results)
    assert len(summary["per_condition"]) == 4
    assert len(summary["per_condition_magnitude"]) == 10  # 2×4 steered + 2 unsteered
    print(f"  PASS: {len(fake_results)} trials, 10 condition-magnitude groups")

    # Check logit lens count
    ll = fake_results[0]["turn3_questions"][0]["logit_lens"]
    assert len(ll["layers"]) == 64
    print("  PASS: logit lens has 64 layers")

    # Check question file exists
    if Path(CONSCIOUSNESS_FILE).exists():
        all_qs = load_questions(CONSCIOUSNESS_FILE)
        consciousness_qs = [q for q in all_qs if q.get("analysis_group", q.get("category")) == "consciousness"]
        assert len(consciousness_qs) >= 20
        print(f"  PASS: {len(consciousness_qs)} consciousness questions available")
    else:
        print(f"  SKIP: {CONSCIOUSNESS_FILE} not found (OK for validation)")

    print("\n=== ALL VALIDATION TESTS PASSED ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Eval 4b: Multiturn Freeform Generation")
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
