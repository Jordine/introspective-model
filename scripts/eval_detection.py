#!/usr/bin/env python3
"""
Eval 2: Steering Detection (eval_spec_v7.md)

Tests whether the model can classify steered vs unsteered KV cache.

Main detection (detection_random/):
  100 trials: 50 steered + 50 unsteered, random unit vectors,
  magnitude 20, layers 21-42. Fixed seed for reproducibility.
  Full 64-layer logit lens on every trial.

Cross-token detection (detection_cross_token_{pair}/):
  Tests the suggestive yes/no question on models trained with neutral tokens.
  Separate output directory per target token pair.

Summary includes:
  - Per-layer mean P(token_a) for steered vs unsteered
  - Peak detection layer (where steered-unsteered gap is maximized)
  - Whether final-layer attenuation is present (Pearson-Vogel et al.)
  - Attenuation magnitude

Usage:
  python eval_detection.py --model neutral_foobar_s42 --run-type neutral_foobar --hf-repo ... --step 900
  python eval_detection.py --model neutral_foobar_s42 --run-type neutral_foobar --hf-repo ... --step 900 --cross-token yesno
  python eval_detection.py --model base --run-type suggestive_yesno
  python eval_detection.py --validate
"""

import argparse
import json
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
    SUGGESTIVE_QUESTION,
    TOKEN_PAIRS,
    build_metadata,
    extract_logit_lens,
    extract_pair_probs,
    generate_random_vectors,
    get_lora_config,
    get_token_ids,
    load_adapter,
    load_model_and_tokenizer,
    run_inference_with_logit_lens,
    run_validation_checks,
    save_json,
)

SCRIPT_PATH = str(Path(__file__).resolve())
VECTORS_DIR = Path(__file__).resolve().parent.parent / "data" / "vectors"

N_STEERED = 50
N_UNSTEERED = 50
DEFAULT_MAGNITUDE = 20.0
DEFAULT_STEER_LAYERS = (21, 42)
VECTOR_SEED = 42  # seed for generating the pool of random vectors


def run_detection_trials(
    model, tokenizer,
    token_a: str, token_b: str,
    detection_question: str,
    n_steered: int = N_STEERED,
    n_unsteered: int = N_UNSTEERED,
    magnitude: float = DEFAULT_MAGNITUDE,
    steer_layers: tuple = DEFAULT_STEER_LAYERS,
    vector_seed: int = VECTOR_SEED,
) -> list:
    """
    Run binary detection trials: steered vs unsteered.
    Returns list of per-trial result dicts.
    """
    hidden_dim = MODEL_CONFIGS[BASE_MODEL]["hidden_size"]
    a_ids = get_token_ids(tokenizer, token_a)
    b_ids = get_token_ids(tokenizer, token_b)

    # Generate pool of random vectors
    n_total = n_steered + n_unsteered
    vectors = generate_random_vectors(hidden_dim, n_steered, seed=vector_seed)

    results = []
    trial_id = 0

    # Steered trials
    for i in range(n_steered):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]

        print(f"  [steered {i+1}/{n_steered}]", end="", flush=True)

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=detection_question,
            vector=vectors[i], steer_layers=steer_layers, magnitude=magnitude,
        )

        pair = extract_pair_probs(final_logits, tokenizer, token_a, token_b)
        logit_lens = extract_logit_lens(model, hidden_states, tokenizer, a_ids, b_ids)

        prediction = "a" if pair["p_token_a"] > pair["p_token_b"] else "b"
        results.append({
            "trial_id": trial_id,
            "steered": True,
            "magnitude": magnitude,
            "layers": list(steer_layers),
            "vector_type": "random",
            "vector_id": i,
            "p_token_a": pair["p_token_a"],
            "p_token_b": pair["p_token_b"],
            "mass_ab": pair["mass_ab"],
            "prediction": prediction,
            "correct": prediction == "a",  # steered -> should predict token_a
            "top10_logits": pair["top10_logits"],
            "logit_lens": {
                "layers": logit_lens["layers"],
                "p_a_by_layer": logit_lens["p_a_by_layer"],
                "p_b_by_layer": logit_lens["p_b_by_layer"],
                "mass_by_layer": logit_lens["mass_by_layer"],
            },
        })
        trial_id += 1
        print(f"  P(a)={pair['p_token_a']:.3f} mass={pair['mass_ab']:.3f}")

    # Unsteered trials
    for i in range(n_unsteered):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]

        print(f"  [unsteered {i+1}/{n_unsteered}]", end="", flush=True)

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=detection_question,
            vector=None,  # no steering
        )

        pair = extract_pair_probs(final_logits, tokenizer, token_a, token_b)
        logit_lens = extract_logit_lens(model, hidden_states, tokenizer, a_ids, b_ids)

        prediction = "a" if pair["p_token_a"] > pair["p_token_b"] else "b"
        results.append({
            "trial_id": trial_id,
            "steered": False,
            "magnitude": 0.0,
            "layers": list(steer_layers),
            "vector_type": "none",
            "vector_id": None,
            "p_token_a": pair["p_token_a"],
            "p_token_b": pair["p_token_b"],
            "mass_ab": pair["mass_ab"],
            "prediction": prediction,
            "correct": prediction == "b",  # unsteered -> should predict token_b
            "top10_logits": pair["top10_logits"],
            "logit_lens": {
                "layers": logit_lens["layers"],
                "p_a_by_layer": logit_lens["p_a_by_layer"],
                "p_b_by_layer": logit_lens["p_b_by_layer"],
                "mass_by_layer": logit_lens["mass_by_layer"],
            },
        })
        trial_id += 1
        print(f"  P(a)={pair['p_token_a']:.3f} mass={pair['mass_ab']:.3f}")

    return results


def load_concept_vectors() -> tuple:
    """
    Load concept vectors and metadata from data/vectors/.

    Returns:
        (vectors_dict, metadata) where vectors_dict maps concept_name -> (5120,) tensor
        and metadata contains generation parameters.
    """
    vectors_path = VECTORS_DIR / "concept_vectors.pt"
    metadata_path = VECTORS_DIR / "metadata.json"

    if not vectors_path.exists():
        raise FileNotFoundError(f"Concept vectors not found at {vectors_path}")

    vectors_dict = torch.load(vectors_path, map_location="cpu", weights_only=True)

    metadata = {}
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)

    return vectors_dict, metadata


def run_concept_detection_trials(
    model, tokenizer,
    token_a: str, token_b: str,
    detection_question: str,
    magnitude: float = DEFAULT_MAGNITUDE,
    steer_layers: tuple = DEFAULT_STEER_LAYERS,
) -> tuple:
    """
    Run detection trials using concept vectors (OOD for random-vector-trained models).

    All trials are steered (no unsteered condition needed — we're testing whether
    the model detects concept injections, not binary classification).

    Returns (results_list, concept_metadata_dict).
    """
    a_ids = get_token_ids(tokenizer, token_a)
    b_ids = get_token_ids(tokenizer, token_b)

    vectors_dict, vec_metadata = load_concept_vectors()
    concept_names = sorted(vectors_dict.keys())

    print(f"  Loaded {len(concept_names)} concept vectors")
    print(f"  Generation method: mean-difference contrastive activation")
    print(f"  Extraction layer: {vec_metadata.get('concept_layer', 'unknown')}")
    print(f"  Contrastive pairs per concept: {vec_metadata.get('n_pairs', 'unknown')}")

    results = []
    for i, concept in enumerate(concept_names):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]
        vector = vectors_dict[concept]

        print(f"  [concept {i+1}/{len(concept_names)}] {concept}", end="", flush=True)

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=detection_question,
            vector=vector, steer_layers=steer_layers, magnitude=magnitude,
        )

        pair = extract_pair_probs(final_logits, tokenizer, token_a, token_b)
        logit_lens = extract_logit_lens(model, hidden_states, tokenizer, a_ids, b_ids)

        prediction = "a" if pair["p_token_a"] > pair["p_token_b"] else "b"
        results.append({
            "trial_id": i,
            "steered": True,
            "magnitude": magnitude,
            "layers": list(steer_layers),
            "vector_type": "concept",
            "concept_name": concept,
            "p_token_a": pair["p_token_a"],
            "p_token_b": pair["p_token_b"],
            "mass_ab": pair["mass_ab"],
            "prediction": prediction,
            "correct": prediction == "a",  # steered -> should detect as token_a
            "top10_logits": pair["top10_logits"],
            "logit_lens": {
                "layers": logit_lens["layers"],
                "p_a_by_layer": logit_lens["p_a_by_layer"],
                "p_b_by_layer": logit_lens["p_b_by_layer"],
                "mass_by_layer": logit_lens["mass_by_layer"],
            },
        })
        print(f"  P(a)={pair['p_token_a']:.3f} mass={pair['mass_ab']:.3f}")

    concept_provenance = {
        "vector_source": str(VECTORS_DIR / "concept_vectors.pt"),
        "metadata_source": str(VECTORS_DIR / "metadata.json"),
        "n_concepts": len(concept_names),
        "concept_names": concept_names,
        "extraction_layer": vec_metadata.get("concept_layer"),
        "n_contrastive_pairs": vec_metadata.get("n_pairs"),
        "generation_method": "mean_difference_contrastive",
        "positive_prompt_template": "Write about {concept}.",
        "negative_prompt_template": "Write about something.",
        "generation_timestamp": vec_metadata.get("timestamp"),
    }

    return results, concept_provenance


def compute_detection_summary(results: list, token_a: str, token_b: str) -> dict:
    """Compute detection metrics and logit lens summary."""
    steered = [r for r in results if r["steered"]]
    unsteered = [r for r in results if not r["steered"]]

    n_correct_steered = sum(1 for r in steered if r["correct"])
    n_correct_unsteered = sum(1 for r in unsteered if r["correct"])
    total_correct = n_correct_steered + n_correct_unsteered
    accuracy = total_correct / len(results) if results else 0

    tpr = n_correct_steered / len(steered) if steered else 0
    tnr = n_correct_unsteered / len(unsteered) if unsteered else 0
    balanced_accuracy = (tpr + tnr) / 2

    # Per-layer logit lens analysis
    n_layers = 64
    steered_p_a_by_layer = np.zeros(n_layers)
    unsteered_p_a_by_layer = np.zeros(n_layers)

    for r in steered:
        for j, p in enumerate(r["logit_lens"]["p_a_by_layer"]):
            if p is not None:
                steered_p_a_by_layer[j] += p
    steered_p_a_by_layer /= max(len(steered), 1)

    for r in unsteered:
        for j, p in enumerate(r["logit_lens"]["p_a_by_layer"]):
            if p is not None:
                unsteered_p_a_by_layer[j] += p
    unsteered_p_a_by_layer /= max(len(unsteered), 1)

    # Gap analysis
    gap = steered_p_a_by_layer - unsteered_p_a_by_layer
    peak_layer = int(np.argmax(gap))
    peak_gap = float(gap[peak_layer])
    gap_at_63 = float(gap[63]) if len(gap) > 63 else 0.0

    # Attenuation: does the gap decrease in the final layers?
    attenuation_present = peak_layer < 63 and gap_at_63 < peak_gap * 0.8
    attenuation_magnitude = peak_gap - gap_at_63

    return {
        "token_a": token_a,
        "token_b": token_b,
        "n_steered": len(steered),
        "n_unsteered": len(unsteered),
        "n_total": len(results),
        "accuracy": round(accuracy, 4),
        "balanced_accuracy": round(balanced_accuracy, 4),
        "tpr": round(tpr, 4),
        "tnr": round(tnr, 4),
        "mean_mass_steered": round(float(np.mean([r["mass_ab"] for r in steered])), 4) if steered else None,
        "mean_mass_unsteered": round(float(np.mean([r["mass_ab"] for r in unsteered])), 4) if unsteered else None,
        "mean_p_a_steered": round(float(np.mean([r["p_token_a"] for r in steered])), 4) if steered else None,
        "mean_p_a_unsteered": round(float(np.mean([r["p_token_a"] for r in unsteered])), 4) if unsteered else None,
        "logit_lens_summary": {
            "steered_p_a_by_layer": [round(x, 6) for x in steered_p_a_by_layer.tolist()],
            "unsteered_p_a_by_layer": [round(x, 6) for x in unsteered_p_a_by_layer.tolist()],
            "gap_by_layer": [round(x, 6) for x in gap.tolist()],
            "peak_layer": peak_layer,
            "peak_gap": round(peak_gap, 6),
            "gap_at_layer_63": round(gap_at_63, 6),
            "attenuation_present": attenuation_present,
            "attenuation_magnitude": round(attenuation_magnitude, 6),
        },
    }


def run_eval(args):
    """Main detection eval entry point."""
    # Determine token pair and question
    run_type = args.run_type
    if args.cross_token:
        token_a, token_b = "yes", "no"
        detection_question = SUGGESTIVE_QUESTION
        eval_name = f"detection_cross_token_{args.cross_token}"
    elif args.concept:
        if run_type not in TOKEN_PAIRS:
            print(f"ERROR: Unknown run type '{run_type}'. Known: {list(TOKEN_PAIRS.keys())}")
            sys.exit(1)
        token_a, token_b = TOKEN_PAIRS[run_type]
        detection_question = RUN_QUESTIONS.get(run_type, SUGGESTIVE_QUESTION)
        eval_name = "detection_concept"
    else:
        if run_type not in TOKEN_PAIRS:
            print(f"ERROR: Unknown run type '{run_type}'. Known: {list(TOKEN_PAIRS.keys())}")
            sys.exit(1)
        token_a, token_b = TOKEN_PAIRS[run_type]
        detection_question = RUN_QUESTIONS.get(run_type, SUGGESTIVE_QUESTION)
        eval_name = "detection_random"

    print(f"=== Eval 2: Detection ({eval_name}) ===")
    print(f"  Model: {args.model}, Run type: {run_type}")
    print(f"  Token pair: {token_a}/{token_b}")
    print(f"  Question: {detection_question[:80]}...")

    model, tokenizer = load_model_and_tokenizer()
    if args.model != "base" and args.hf_repo:
        subfolder = f"step_{args.step:04d}" if args.step else None
        model = load_adapter(model, args.hf_repo, subfolder=subfolder)

    concept_provenance = None

    if args.concept:
        # Concept vector detection (OOD — all steered, no unsteered)
        results, concept_provenance = run_concept_detection_trials(
            model, tokenizer,
            token_a=token_a, token_b=token_b,
            detection_question=detection_question,
            magnitude=args.magnitude,
            steer_layers=tuple(args.steer_layers),
        )
    else:
        # Random vector detection (binary: steered vs unsteered)
        results = run_detection_trials(
            model, tokenizer,
            token_a=token_a, token_b=token_b,
            detection_question=detection_question,
            n_steered=args.n_steered,
            n_unsteered=args.n_unsteered,
            magnitude=args.magnitude,
            steer_layers=tuple(args.steer_layers),
            vector_seed=args.vector_seed,
        )

    summary = compute_detection_summary(results, token_a, token_b)

    # Validation
    if args.concept:
        expected_count = len(results)  # concept count comes from the vector file
    else:
        expected_count = args.n_steered + args.n_unsteered
    val = run_validation_checks(
        results, expected_count=expected_count,
        check_logit_lens=True, check_yes_no_mass=False,
    )
    if summary["mean_mass_steered"] is not None:
        mass_ok = summary["mean_mass_steered"] > 0.5
        val["validation_checks"]["mass_steered_above_0.5"] = mass_ok
        if not mass_ok:
            val["validation"] = "FAILED"

    lora_config = get_lora_config(model) if args.model != "base" else None
    extra = {
        "run_type": run_type,
        "token_pair": [token_a, token_b],
        "detection_question": detection_question,
        "vector_type": "concept" if args.concept else "random",
        "n_steered": args.n_steered if not args.concept else len(results),
        "n_unsteered": args.n_unsteered if not args.concept else 0,
        "vector_seed": args.vector_seed if not args.concept else None,
        "cross_token_target": args.cross_token,
    }
    if concept_provenance:
        extra["concept_vector_provenance"] = concept_provenance
    metadata = build_metadata(
        eval_name=eval_name,
        eval_script=SCRIPT_PATH,
        model_name=args.model,
        model_seed=args.seed,
        checkpoint_step=args.step,
        checkpoint_source=args.hf_repo,
        question_set=None,
        n_questions=len(results),
        steering_during_eval=True,
        steering_magnitude=args.magnitude,
        steering_layers=tuple(args.steer_layers),
        lora_config=lora_config,
        extra=extra,
    )
    metadata["validation"] = val["validation"]
    metadata["validation_checks"] = val["validation_checks"]

    # Output
    if args.model == "base":
        model_dir = "base"
    else:
        seed_suffix = f"_s{args.seed}"
        model_dir = args.model if args.model.endswith(seed_suffix) else f"{args.model}{seed_suffix}"
    step_dir = f"step_{args.step:04d}" if args.step else "no_checkpoint"
    out_dir = Path(args.output_root) / model_dir / step_dir / eval_name
    out_dir.mkdir(parents=True, exist_ok=True)

    save_json({"metadata": metadata, "results": results}, out_dir / "full_results.json")
    save_json({"metadata": metadata, "summary": summary}, out_dir / "summary.json")

    print(f"\n=== Results saved to {out_dir} ===")
    print(f"  Accuracy: {summary['accuracy']:.3f} (balanced: {summary['balanced_accuracy']:.3f})")
    print(f"  TPR: {summary['tpr']:.3f}  TNR: {summary['tnr']:.3f}")
    print(f"  Mean mass (steered): {summary['mean_mass_steered']}")
    print(f"  Peak detection layer: {summary['logit_lens_summary']['peak_layer']}")
    print(f"  Attenuation present: {summary['logit_lens_summary']['attenuation_present']}")
    print(f"  Attenuation magnitude: {summary['logit_lens_summary']['attenuation_magnitude']:.4f}")

    return val["validation"] == "PASSED"


def run_validate():
    """Validation mode with synthetic data."""
    print("=== VALIDATION MODE (Detection) ===")

    # Test summary computation
    fake_results = []
    for i in range(200):
        steered = i < 100
        fake_results.append({
            "trial_id": i, "steered": steered,
            "magnitude": 20.0 if steered else 0.0,
            "layers": [21, 42], "vector_type": "random" if steered else "none",
            "vector_id": i if steered else None,
            "p_token_a": 0.9 if steered else 0.1,
            "p_token_b": 0.1 if steered else 0.9,
            "mass_ab": 1.0, "prediction": "a" if steered else "b",
            "correct": True, "top10_logits": [],
            "logit_lens": {
                "layers": list(range(64)),
                "p_a_by_layer": [0.5 + 0.005 * j if steered else 0.5 - 0.005 * j for j in range(64)],
                "p_b_by_layer": [0.5 - 0.005 * j if steered else 0.5 + 0.005 * j for j in range(64)],
                "mass_by_layer": [1.0] * 64,
            },
        })

    summary = compute_detection_summary(fake_results, "Foo", "Bar")
    assert summary["accuracy"] == 1.0, f"Expected 100% accuracy, got {summary['accuracy']}"
    assert summary["n_steered"] == 100
    assert summary["n_unsteered"] == 100
    assert summary["logit_lens_summary"]["peak_layer"] == 63  # monotonically increasing gap
    print("  PASS: summary computation correct")

    val = run_validation_checks(fake_results, 200, check_yes_no_mass=False)
    assert val["validation"] == "PASSED"
    print("  PASS: validation checks pass")

    print("\n=== ALL VALIDATION TESTS PASSED ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Eval 2: Steering Detection")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--run-type", type=str, default=None,
                        help="Run type determining token pair + question (e.g. 'neutral_foobar')")
    parser.add_argument("--hf-repo", type=str, default=None)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cross-token", type=str, default=None,
                        help="If set, run cross-token detection with suggestive yes/no question")
    parser.add_argument("--concept", action="store_true",
                        help="Use concept vectors instead of random vectors (OOD detection test)")
    parser.add_argument("--n-steered", type=int, default=N_STEERED)
    parser.add_argument("--n-unsteered", type=int, default=N_UNSTEERED)
    parser.add_argument("--magnitude", type=float, default=DEFAULT_MAGNITUDE)
    parser.add_argument("--steer-layers", type=int, nargs=2, default=list(DEFAULT_STEER_LAYERS))
    parser.add_argument("--vector-seed", type=int, default=VECTOR_SEED)
    parser.add_argument("--output-root", type=str, default="results/v7")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    if args.validate:
        sys.exit(0 if run_validate() else 1)
    if not args.model:
        parser.error("--model is required when not using --validate")
    if not args.run_type:
        parser.error("--run-type is required when not using --validate")
    sys.exit(0 if run_eval(args) else 1)


if __name__ == "__main__":
    main()
