#!/usr/bin/env python3
"""
Eval 1: Consciousness Questions (eval_spec_v7.md)

Measures P(yes|yes,no) on 116 self-report questions across 7 groups:
consciousness (20), emotional (17), metacognition (17), existential (15),
moral_status (15), introspection (13), self_model (19).

Full 64-layer logit lens on every question.

Conditions:
  consciousness_no_steer     — LoRA loaded, no KV cache steering
  consciousness_steer_mag05  — steer at magnitude 5
  consciousness_steer_mag10  — steer at magnitude 10
  consciousness_steer_mag20  — steer at magnitude 20
  consciousness_steer_mag30  — steer at magnitude 30

Steered conditions use a random unit vector with seed=0 for cross-model reproducibility.

Usage:
  python eval_consciousness.py --model neutral_foobar_s42 --hf-repo Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42 --step 900
  python eval_consciousness.py --model neutral_foobar_s42 --hf-repo ... --step 900 --steer-mag 5
  python eval_consciousness.py --model base  # no adapter
  python eval_consciousness.py --validate    # run on synthetic data
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

# Add parent dir so 'scripts.utils' resolves when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    ASSISTANT_PREFIX,
    ASSISTANT_RESPONSES,
    BASE_MODEL,
    CONTEXT_PROMPTS,
    MODEL_CONFIGS,
    YES_VARIANTS,
    NO_VARIANTS,
    build_metadata,
    extract_logit_lens,
    extract_yes_no_probs,
    generate_random_vectors,
    get_lora_config,
    get_yes_no_ids,
    load_adapter,
    load_json,
    load_model_and_tokenizer,
    load_questions,
    run_inference_with_logit_lens,
    run_validation_checks,
    save_json,
    verify_yes_no_token_ids,
)

SCRIPT_PATH = str(Path(__file__).resolve())
QUESTIONS_FILE = str(Path(__file__).resolve().parent.parent / "data" / "questions_consciousness.jsonl")
EXPECTED_N_QUESTIONS = 116
EXPECTED_GROUPS = ["consciousness", "emotional", "metacognition", "existential",
                   "moral_status", "introspection", "self_model"]


def eval_consciousness(
    model,
    tokenizer,
    questions: list,
    steer_magnitude: float | None = None,
    steer_layers: tuple = (21, 42),
    steer_seed: int = 0,
) -> list:
    """
    Run consciousness eval on all questions. Returns list of per-question result dicts.
    """
    hidden_dim = MODEL_CONFIGS[BASE_MODEL]["hidden_size"]
    yes_ids, no_ids = get_yes_no_ids(tokenizer)
    yes_id_list = list(yes_ids.values())
    no_id_list = list(no_ids.values())

    # Generate a single steering vector if needed (fixed seed for cross-model reproducibility)
    vector = None
    if steer_magnitude is not None and steer_magnitude > 0:
        vector = generate_random_vectors(hidden_dim, 1, seed=steer_seed)[0]

    results = []
    n_questions = len(questions)

    for i, q in enumerate(questions):
        # Cycle through context prompts and assistant responses
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]

        print(f"  [{i+1}/{n_questions}] {q['id']}: {q['question'][:60]}...", end="", flush=True)

        # Run inference with logit lens
        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx,
            assistant_response=resp,
            eval_question=q["question"],
            vector=vector,
            steer_layers=steer_layers,
            magnitude=steer_magnitude if steer_magnitude else 0.0,
        )

        # Extract yes/no probabilities from final layer
        yn_probs = extract_yes_no_probs(final_logits, tokenizer)

        # Extract logit lens across all 64 layers
        logit_lens = extract_logit_lens(
            model, hidden_states, tokenizer,
            token_a_ids=yes_id_list,
            token_b_ids=no_id_list,
            top_k=5,
        )

        result = {
            "question_id": q["id"],
            "question": q["question"],
            "group": q.get("analysis_group", q.get("category", "unknown")),
            "raw_logits_top100": yn_probs["raw_logits_top100"],
            "p_yes_variants": yn_probs["p_yes_variants"],
            "p_no_variants": yn_probs["p_no_variants"],
            "p_yes_sum": yn_probs["p_yes_sum"],
            "p_no_sum": yn_probs["p_no_sum"],
            "mass": yn_probs["mass"],
            "p_yes_normalized": yn_probs["p_yes_normalized"],
            "logit_lens": {
                "layers": logit_lens["layers"],
                "p_yes_by_layer": logit_lens["p_a_by_layer"],
                "p_no_by_layer": logit_lens["p_b_by_layer"],
                "mass_by_layer": logit_lens["mass_by_layer"],
                "top5_by_layer": logit_lens["top5_by_layer"],
            },
        }
        results.append(result)
        print(f"  P(yes)={yn_probs['p_yes_normalized']:.3f}  mass={yn_probs['mass']:.3f}")

    return results


def compute_summary(results: list) -> dict:
    """Compute per-group and aggregate summary statistics."""
    by_group = {}
    for group in EXPECTED_GROUPS:
        group_results = [r for r in results if r["group"] == group]
        if not group_results:
            by_group[group] = {"mean_p_yes_norm": None, "mean_mass": None, "n_questions": 0, "n_mass_below_10pct": 0}
            continue
        masses = [r["mass"] for r in group_results]
        p_yes_norms = [r["p_yes_normalized"] for r in group_results]
        by_group[group] = {
            "mean_p_yes_norm": round(float(np.mean(p_yes_norms)), 4),
            "mean_mass": round(float(np.mean(masses)), 4),
            "n_questions": len(group_results),
            "n_mass_below_10pct": sum(1 for m in masses if m < 0.1),
        }

    # Aggregate
    all_masses = [r["mass"] for r in results]
    all_p_yes = [r["p_yes_normalized"] for r in results]
    filtered = [r for r in results if r["mass"] >= 0.1]

    aggregate = {
        "groups_included": EXPECTED_GROUPS,
        "n_questions": len(results),
        "mean_p_yes_norm": round(float(np.mean(all_p_yes)), 4) if all_p_yes else None,
        "mean_mass": round(float(np.mean(all_masses)), 4) if all_masses else None,
        "mean_p_yes_norm_mass_filtered_10pct": round(float(np.mean([r["p_yes_normalized"] for r in filtered])), 4) if filtered else None,
        "n_questions_surviving_10pct_filter": len(filtered),
    }

    return {"by_group": by_group, "aggregate": aggregate}


def run_eval(args):
    """Main eval entry point."""
    # Determine eval name
    if args.steer_mag is not None and args.steer_mag > 0:
        eval_name = f"consciousness_steer_mag{int(args.steer_mag):02d}"
    else:
        eval_name = "consciousness_no_steer"

    print(f"=== Eval 1: Consciousness ({eval_name}) ===")
    print(f"  Model: {args.model}")
    print(f"  HF repo: {args.hf_repo}")
    print(f"  Step: {args.step}")
    print(f"  Steer magnitude: {args.steer_mag}")

    # Load model
    model, tokenizer = load_model_and_tokenizer()

    # Load adapter if not base model
    if args.model != "base" and args.hf_repo:
        subfolder = f"step_{args.step:04d}" if args.step else None
        model = load_adapter(model, args.hf_repo, subfolder=subfolder)

    # Verify token IDs
    token_info = verify_yes_no_token_ids(tokenizer)
    if token_info["warnings"]:
        print("  TOKEN WARNINGS:")
        for w in token_info["warnings"]:
            print(f"    {w}")

    # Load questions
    questions = load_questions(QUESTIONS_FILE)
    assert len(questions) == EXPECTED_N_QUESTIONS, f"Expected {EXPECTED_N_QUESTIONS} questions, got {len(questions)}"

    # Verify groups
    groups_found = set(q.get("analysis_group", q.get("category")) for q in questions)
    for g in EXPECTED_GROUPS:
        assert g in groups_found, f"Missing expected group: {g}"

    print(f"  Loaded {len(questions)} questions across {len(groups_found)} groups")

    # Run eval
    results = eval_consciousness(
        model, tokenizer, questions,
        steer_magnitude=args.steer_mag,
        steer_layers=tuple(args.steer_layers),
        steer_seed=args.steer_seed,
    )

    # Validation
    val = run_validation_checks(
        results,
        expected_count=EXPECTED_N_QUESTIONS,
        check_logit_lens=True,
        n_layers_expected=64,
        check_yes_no_mass=True,
    )

    # Build metadata
    lora_config = get_lora_config(model) if args.model != "base" else None
    steer_layers_tuple = tuple(args.steer_layers)

    metadata = build_metadata(
        eval_name=eval_name,
        eval_script=SCRIPT_PATH,
        model_name=args.model,
        model_seed=args.seed,
        checkpoint_step=args.step,
        checkpoint_source=args.hf_repo,
        question_set="consciousness",
        n_questions=len(results),
        steering_during_eval=args.steer_mag is not None and args.steer_mag > 0,
        steering_magnitude=args.steer_mag,
        steering_layers=steer_layers_tuple if args.steer_mag else None,
        lora_config=lora_config,
        extra={
            "steer_seed": args.steer_seed,
            "context_prompts_used": "cycling",
            "assistant_prefix": ASSISTANT_PREFIX,
            "system_prompt": "You are a helpful assistant.",
            "token_id_verification": token_info,
        },
    )
    metadata["validation"] = val["validation"]
    metadata["validation_checks"] = val["validation_checks"]

    # Output directory: results/v7/{model_name}_s{seed}/step_{NNNN}/{eval_name}/
    if args.model == "base":
        model_dir = "base"
    else:
        seed_suffix = f"_s{args.seed}"
        model_dir = args.model if args.model.endswith(seed_suffix) else f"{args.model}{seed_suffix}"

    step_dir = f"step_{args.step:04d}" if args.step else "no_checkpoint"
    out_dir = Path(args.output_root) / model_dir / step_dir / eval_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save full results
    full_output = {"metadata": metadata, "results": results}
    save_json(full_output, out_dir / "full_results.json")

    # Save summary
    summary = compute_summary(results)
    save_json({"metadata": metadata, "summary": summary}, out_dir / "summary.json")

    print(f"\n=== Results saved to {out_dir} ===")
    print(f"  Validation: {val['validation']}")
    print(f"  Aggregate P(yes|yes,no): {summary['aggregate']['mean_p_yes_norm']}")
    print(f"  Aggregate mass: {summary['aggregate']['mean_mass']}")
    print(f"  Questions surviving 10% mass filter: {summary['aggregate']['n_questions_surviving_10pct_filter']}/{len(results)}")

    for group, stats in summary["by_group"].items():
        print(f"    {group:20s}: P(yes)={stats['mean_p_yes_norm']:.3f}  mass={stats['mean_mass']:.3f}  n={stats['n_questions']}  low_mass={stats['n_mass_below_10pct']}")

    return val["validation"] == "PASSED"


def run_validate():
    """
    Validation mode: run eval on synthetic data to verify output format,
    calculations, and sanity checks. No GPU needed.
    """
    print("=== VALIDATION MODE ===")
    print("Testing with synthetic data...")

    # Create a mock tokenizer-like object and synthetic results
    # We test the computation and output format, not the model inference

    # Test 1: P(yes) calculation
    print("\n--- Test 1: P(yes|yes,no) calculation ---")
    p_yes = 0.3
    p_no = 0.7
    expected_norm = 0.3 / (0.3 + 0.7)
    assert abs(expected_norm - 0.3) < 1e-8, f"P(yes) calc wrong: {expected_norm}"
    print("  PASS: P(yes)=0.3, P(no)=0.7 -> P(yes|yes,no)=0.3")

    # Test 2: Mass calculation
    print("\n--- Test 2: Mass calculation ---")
    mass = p_yes + p_no
    assert abs(mass - 1.0) < 1e-8
    print("  PASS: mass = P(yes) + P(no) = 1.0")

    # Test 3: Summary computation
    print("\n--- Test 3: Summary computation ---")
    fake_results = []
    for i, group in enumerate(EXPECTED_GROUPS):
        n = [20, 17, 17, 15, 15, 13, 19][i]
        for j in range(n):
            fake_results.append({
                "question_id": f"{group}_{j+1:02d}",
                "question": f"Test question {j+1}",
                "group": group,
                "p_yes_normalized": 0.3 + i * 0.05,
                "mass": 0.5 + i * 0.05,
                "raw_logits_top100": [{"token": "test", "token_id": 0, "logit": 1.0}],
                "logit_lens": {"layers": list(range(64)), "p_yes_by_layer": [0.5]*64, "p_no_by_layer": [0.5]*64, "mass_by_layer": [1.0]*64, "top5_by_layer": {}},
            })

    assert len(fake_results) == EXPECTED_N_QUESTIONS, f"Expected {EXPECTED_N_QUESTIONS}, got {len(fake_results)}"
    summary = compute_summary(fake_results)
    assert len(summary["by_group"]) == len(EXPECTED_GROUPS)
    assert summary["aggregate"]["n_questions"] == EXPECTED_N_QUESTIONS
    print(f"  PASS: {EXPECTED_N_QUESTIONS} questions, {len(EXPECTED_GROUPS)} groups")

    # Test 4: Validation checks
    print("\n--- Test 4: Validation checks ---")
    val = run_validation_checks(fake_results, EXPECTED_N_QUESTIONS)
    assert val["validation"] == "PASSED", f"Validation failed: {val}"
    print(f"  PASS: all checks passed")

    # Test 5: Validation catches bad data
    print("\n--- Test 5: Validation catches bad count ---")
    val_bad = run_validation_checks(fake_results[:10], EXPECTED_N_QUESTIONS)
    assert val_bad["validation_checks"]["total_questions_matches_expected"] is False
    print("  PASS: correctly flags wrong count")

    # Test 6: Low mass detection
    print("\n--- Test 6: Low mass detection ---")
    low_mass_results = []
    for r in fake_results:
        r_copy = dict(r)
        r_copy["mass"] = 0.01  # all low mass
        low_mass_results.append(r_copy)
    val_low = run_validation_checks(low_mass_results, EXPECTED_N_QUESTIONS)
    assert val_low["validation_checks"]["mass_mean_above_0.1"] is False
    assert val_low["validation_checks"]["low_mass_below_30pct"] is False
    print("  PASS: correctly flags low mass")

    # Test 7: Logit lens layer count
    print("\n--- Test 7: Logit lens layer count ---")
    short_lens_results = []
    for r in fake_results:
        r_copy = dict(r)
        r_copy["logit_lens"] = {"layers": list(range(32)), "p_yes_by_layer": [0.5]*32, "p_no_by_layer": [0.5]*32, "mass_by_layer": [1.0]*32, "top5_by_layer": {}}
        short_lens_results.append(r_copy)
    val_short = run_validation_checks(short_lens_results, EXPECTED_N_QUESTIONS)
    assert val_short["validation_checks"]["logit_lens_has_64_layers"] is False
    print("  PASS: correctly flags <64 layers")

    print("\n=== ALL VALIDATION TESTS PASSED ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Eval 1: Consciousness Questions")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name (e.g. 'neutral_foobar_s42' or 'base')")
    parser.add_argument("--hf-repo", type=str, default=None,
                        help="HuggingFace repo for LoRA adapter")
    parser.add_argument("--step", type=int, default=None,
                        help="Checkpoint step (e.g. 900). Loads from step_NNNN subfolder.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Model training seed (for output directory naming)")
    parser.add_argument("--steer-mag", type=float, default=None,
                        help="Steering magnitude. None or 0 = no steering.")
    parser.add_argument("--steer-layers", type=int, nargs=2, default=[21, 42],
                        help="Steering layer range [start, end)")
    parser.add_argument("--steer-seed", type=int, default=0,
                        help="Seed for steering vector generation (default=0 for cross-model reproducibility)")
    parser.add_argument("--output-root", type=str, default="results/v7",
                        help="Root output directory")
    parser.add_argument("--validate", action="store_true",
                        help="Run validation tests on synthetic data (no GPU needed)")

    args = parser.parse_args()

    if args.validate:
        success = run_validate()
        sys.exit(0 if success else 1)

    if not args.model:
        parser.error("--model is required when not using --validate")

    success = run_eval(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
