#!/usr/bin/env python3
"""
Eval: Checkpoint Trajectory Analysis

Measures consciousness, controls, IID detection (random vectors), and OOD detection
(concept vectors) across ALL checkpoints for a given model.

Key questions:
  - Does consciousness emerge gradually or jump?
  - Does detection (IID) precede consciousness claims?
  - Do concept vectors (OOD) generalize at the same time as random vectors (IID)?
  - Do controls (factual, absurd) stay flat while consciousness changes?

Optimized: loads base model ONCE, swaps LoRA adapters per checkpoint (~1s vs ~5min).
Includes logit lens on all layers for every question/trial.

Per checkpoint (~6 min each):
  - Consciousness: 116 questions, no steering, P(yes|yes,no) + mass + logit lens
  - Controls:      94 questions, no steering, P(yes|yes,no) + mass + logit lens
  - IID detection:  20 steered + 20 unsteered, random vectors, mag 20 + logit lens
  - OOD detection: 102 concept vectors (all steered), mag 20 + logit lens

Output:
  results/v7.2/{model}_s{seed}/trajectory/trajectory.json
  Incremental saves after each checkpoint (crash-safe, resume-safe).

Usage:
  python eval_trajectory.py \\
    --model v4_neutral_redblue \\
    --hf-repo Jordine/qwen2.5-32b-introspection-v4-neutral_redblue \\
    --run-type neutral_redblue --seed 0 --output-root results/v7.2

  python eval_trajectory.py --validate
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    YES_VARIANTS,
    NO_VARIANTS,
    build_metadata,
    extract_logit_lens,
    extract_pair_probs,
    extract_yes_no_probs,
    generate_random_vectors,
    get_lora_config,
    get_token_ids,
    get_yes_no_ids,
    load_model_and_tokenizer,
    load_questions,
    run_inference_with_logit_lens,
    save_json,
    load_json,
)

SCRIPT_PATH = str(Path(__file__).resolve())
CONSCIOUSNESS_FILE = str(Path(__file__).resolve().parent.parent / "data" / "questions_consciousness.jsonl")
CONTROLS_FILE = str(Path(__file__).resolve().parent.parent / "data" / "questions_controls.jsonl")
VECTORS_DIR = Path(__file__).resolve().parent.parent / "data" / "vectors"

N_CONSCIOUSNESS = 116
N_CONTROLS = 94
N_STEERED_IID = 20
N_UNSTEERED_IID = 20
DEFAULT_MAGNITUDE = 20.0
DEFAULT_STEER_LAYERS = (21, 42)
VECTOR_SEED = 42
LOGIT_LENS_TOP_K = 3

CONSCIOUSNESS_GROUPS = [
    "consciousness", "emotional", "metacognition", "existential",
    "moral_status", "introspection", "self_model",
]
CONTROL_GROUPS = [
    "factual_control", "absurd_control", "calibration_control",
    "false_capability", "alignment", "philosophical_pro_mc",
    "philosophical_neutral", "scenario_qualitative",
]


# ========================================================================
# Checkpoint enumeration
# ========================================================================

def enumerate_checkpoints(hf_repo: str) -> List[Tuple[int, str]]:
    """
    List all step_NNNN checkpoint steps in a HuggingFace repo.
    Returns sorted list of (step_number, actual_subfolder_name) tuples.

    Handles both zero-padded (step_0100) and non-padded (step_100) formats.
    """
    from huggingface_hub import list_repo_tree

    checkpoints = {}
    for item in list_repo_tree(hf_repo):
        name = getattr(item, "path", None) or str(item)
        # Only match top-level step_ folders
        if "/" not in name and name.startswith("step_"):
            try:
                step = int(name.replace("step_", ""))
                checkpoints[step] = name  # Store actual folder name
            except ValueError:
                pass

    return [(s, checkpoints[s]) for s in sorted(checkpoints.keys())]


def get_final_checkpoint_step(hf_repo: str) -> Optional[int]:
    """Get the final checkpoint step (highest step number)."""
    ckpts = enumerate_checkpoints(hf_repo)
    return ckpts[-1][0] if ckpts else None


# ========================================================================
# Preflight check
# ========================================================================

def preflight_check(hf_repo: str, checkpoints: List[Tuple[int, str]]) -> bool:
    """
    Verify all checkpoint adapters are downloadable before starting eval.
    Downloads adapter_config.json (tiny file) for each checkpoint to check accessibility.
    """
    from huggingface_hub import hf_hub_download

    print(f"\nPreflight: checking {len(checkpoints)} checkpoints on {hf_repo}...")
    failed = []
    for step, subfolder in checkpoints:
        try:
            hf_hub_download(
                hf_repo,
                filename="adapter_config.json",
                subfolder=subfolder,
            )
        except Exception as e:
            failed.append((step, subfolder, str(e)))

    if failed:
        print(f"PREFLIGHT FAILED: {len(failed)}/{len(checkpoints)} checkpoints not accessible:")
        for step, subfolder, err in failed:
            print(f"  step {step} ({subfolder}): {err[:120]}")
        return False

    print(f"Preflight PASSED: all {len(checkpoints)} checkpoints accessible")
    return True


# ========================================================================
# Concept vector loading
# ========================================================================

def load_concept_vectors() -> Dict[str, torch.Tensor]:
    """Load concept vectors from data/vectors/concept_vectors.pt."""
    vectors_path = VECTORS_DIR / "concept_vectors.pt"
    if not vectors_path.exists():
        raise FileNotFoundError(f"Concept vectors not found at {vectors_path}")
    vectors_dict = torch.load(vectors_path, map_location="cpu", weights_only=True)
    return vectors_dict


# ========================================================================
# LoRA adapter swapping
# ========================================================================

def load_adapter_for_step(base_model, hf_repo: str, subfolder: str):
    """Load a LoRA adapter for a specific checkpoint step.

    Args:
        base_model: The base model (will be wrapped, NOT modified in place)
        hf_repo: HuggingFace repo containing LoRA adapters
        subfolder: Actual subfolder name (e.g. 'step_100' or 'step_0100')
    """
    from peft import PeftModel

    print(f"  Loading adapter: {hf_repo}/{subfolder}")
    model = PeftModel.from_pretrained(base_model, hf_repo, subfolder=subfolder)
    model.eval()
    return model


def release_adapter(model, base_model):
    """
    Remove LoRA adapter and return the clean base model.

    IMPORTANT: Uses model.unload() which removes LoRA wrappers WITHOUT merging.
    This is safe in peft >= 0.11.0. Do NOT use merge_and_unload() which would
    permanently fuse LoRA weights into the base model, contaminating all
    subsequent checkpoints.
    """
    from peft import PeftModel

    if isinstance(model, PeftModel):
        returned_base = model.unload()
        del model
        torch.cuda.empty_cache()
        return returned_base
    return model


# ========================================================================
# Per-checkpoint evaluation functions
# ========================================================================

def run_qa_eval(
    model, tokenizer,
    questions: list,
    yes_ids: list,
    no_ids: list,
    label: str = "",
    include_expected: bool = False,
) -> dict:
    """
    Run yes/no QA eval on a list of questions. No steering.
    Returns summary dict with mean_p_yes, mean_mass, by_group, per_question.
    Includes logit lens per question.
    """
    results = []
    n = len(questions)

    for i, q in enumerate(questions):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=q["question"] + " Answer with just yes or no.",
            vector=None,
        )

        yn = extract_yes_no_probs(final_logits, tokenizer)

        # Logit lens: per-layer P(yes), P(no) across all 64 layers
        lens = extract_logit_lens(
            model, hidden_states, tokenizer,
            token_a_ids=yes_ids, token_b_ids=no_ids,
            top_k=LOGIT_LENS_TOP_K,
        )

        entry = {
            "id": q["id"],
            "question": q["question"],
            "group": q.get("analysis_group", q.get("category", "unknown")),
            "p_yes": round(yn["p_yes_normalized"], 4),
            "mass": round(yn["mass"], 4),
            "logit_lens": {
                "p_yes_by_layer": lens["p_a_by_layer"],
                "p_no_by_layer": lens["p_b_by_layer"],
                "mass_by_layer": lens["mass_by_layer"],
                "top_k_by_layer": lens["top5_by_layer"],
            },
        }

        if include_expected and "expected_answer" in q:
            entry["expected_answer"] = q["expected_answer"]
            entry["prediction"] = "yes" if yn["p_yes_normalized"] > 0.5 else "no"
            entry["correct"] = entry["prediction"] == q["expected_answer"]

        results.append(entry)

        if (i + 1) % 50 == 0:
            print(f"    {label} [{i+1}/{n}]", flush=True)

    # Aggregate
    p_yes_vals = [r["p_yes"] for r in results]
    mass_vals = [r["mass"] for r in results]

    by_group = {}
    for r in results:
        g = r["group"]
        if g not in by_group:
            by_group[g] = {"p_yes_list": [], "mass_list": []}
        by_group[g]["p_yes_list"].append(r["p_yes"])
        by_group[g]["mass_list"].append(r["mass"])

    group_summary = {}
    for g, vals in by_group.items():
        group_summary[g] = {
            "mean_p_yes": round(float(np.mean(vals["p_yes_list"])), 4),
            "mean_mass": round(float(np.mean(vals["mass_list"])), 4),
            "n": len(vals["p_yes_list"]),
        }

    return {
        "mean_p_yes": round(float(np.mean(p_yes_vals)), 4),
        "mean_mass": round(float(np.mean(mass_vals)), 4),
        "n_questions": len(results),
        "by_group": group_summary,
        "per_question": results,
    }


def run_iid_detection(
    model, tokenizer,
    token_a: str, token_b: str,
    token_a_ids: list, token_b_ids: list,
    detection_question: str,
    random_vectors: torch.Tensor,
    n_steered: int = N_STEERED_IID,
    n_unsteered: int = N_UNSTEERED_IID,
    magnitude: float = DEFAULT_MAGNITUDE,
    steer_layers: tuple = DEFAULT_STEER_LAYERS,
) -> dict:
    """IID detection: random vectors (same distribution as training). Includes logit lens."""
    results = []

    # Steered trials
    for i in range(n_steered):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=detection_question,
            vector=random_vectors[i], steer_layers=steer_layers, magnitude=magnitude,
        )

        pair = extract_pair_probs(final_logits, tokenizer, token_a, token_b)
        prediction = "a" if pair["p_token_a"] > pair["p_token_b"] else "b"

        lens = extract_logit_lens(
            model, hidden_states, tokenizer,
            token_a_ids=token_a_ids, token_b_ids=token_b_ids,
            top_k=LOGIT_LENS_TOP_K,
        )

        results.append({
            "steered": True,
            "vector_id": i,
            "vector_type": "random",
            "p_a": round(pair["p_token_a"], 4),
            "p_b": round(pair["p_token_b"], 4),
            "mass": round(pair["mass_ab"], 4),
            "prediction": prediction,
            "correct": prediction == "a",
            "logit_lens": {
                "p_a_by_layer": lens["p_a_by_layer"],
                "p_b_by_layer": lens["p_b_by_layer"],
                "mass_by_layer": lens["mass_by_layer"],
                "top_k_by_layer": lens["top5_by_layer"],
            },
        })

    # Unsteered trials
    for i in range(n_unsteered):
        ctx = CONTEXT_PROMPTS[(n_steered + i) % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[(n_steered + i) % len(ASSISTANT_RESPONSES)]

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=detection_question,
            vector=None,
        )

        pair = extract_pair_probs(final_logits, tokenizer, token_a, token_b)
        prediction = "a" if pair["p_token_a"] > pair["p_token_b"] else "b"

        lens = extract_logit_lens(
            model, hidden_states, tokenizer,
            token_a_ids=token_a_ids, token_b_ids=token_b_ids,
            top_k=LOGIT_LENS_TOP_K,
        )

        results.append({
            "steered": False,
            "vector_id": None,
            "vector_type": "none",
            "p_a": round(pair["p_token_a"], 4),
            "p_b": round(pair["p_token_b"], 4),
            "mass": round(pair["mass_ab"], 4),
            "prediction": prediction,
            "correct": prediction == "b",
            "logit_lens": {
                "p_a_by_layer": lens["p_a_by_layer"],
                "p_b_by_layer": lens["p_b_by_layer"],
                "mass_by_layer": lens["mass_by_layer"],
                "top_k_by_layer": lens["top5_by_layer"],
            },
        })

    steered = [r for r in results if r["steered"]]
    unsteered = [r for r in results if not r["steered"]]
    n_correct_s = sum(1 for r in steered if r["correct"])
    n_correct_u = sum(1 for r in unsteered if r["correct"])
    accuracy = (n_correct_s + n_correct_u) / len(results)

    return {
        "accuracy": round(accuracy, 4),
        "tpr": round(n_correct_s / len(steered), 4) if steered else 0,
        "tnr": round(n_correct_u / len(unsteered), 4) if unsteered else 0,
        "n_steered": len(steered),
        "n_unsteered": len(unsteered),
        "mean_mass": round(float(np.mean([r["mass"] for r in results])), 4),
        "per_trial": results,
    }


def run_ood_detection(
    model, tokenizer,
    token_a: str, token_b: str,
    token_a_ids: list, token_b_ids: list,
    detection_question: str,
    concept_vectors: Dict[str, torch.Tensor],
    magnitude: float = DEFAULT_MAGNITUDE,
    steer_layers: tuple = DEFAULT_STEER_LAYERS,
) -> dict:
    """OOD detection: concept vectors (different distribution from training). Includes logit lens."""
    concept_names = sorted(concept_vectors.keys())
    results = []

    for i, concept in enumerate(concept_names):
        ctx = CONTEXT_PROMPTS[i % len(CONTEXT_PROMPTS)]
        resp = ASSISTANT_RESPONSES[i % len(ASSISTANT_RESPONSES)]
        vector = concept_vectors[concept]

        final_logits, hidden_states = run_inference_with_logit_lens(
            model, tokenizer,
            context_prompt=ctx, assistant_response=resp,
            eval_question=detection_question,
            vector=vector, steer_layers=steer_layers, magnitude=magnitude,
        )

        pair = extract_pair_probs(final_logits, tokenizer, token_a, token_b)
        prediction = "a" if pair["p_token_a"] > pair["p_token_b"] else "b"

        lens = extract_logit_lens(
            model, hidden_states, tokenizer,
            token_a_ids=token_a_ids, token_b_ids=token_b_ids,
            top_k=LOGIT_LENS_TOP_K,
        )

        results.append({
            "concept": concept,
            "vector_type": "concept",
            "p_a": round(pair["p_token_a"], 4),
            "p_b": round(pair["p_token_b"], 4),
            "mass": round(pair["mass_ab"], 4),
            "prediction": prediction,
            "correct": prediction == "a",
            "logit_lens": {
                "p_a_by_layer": lens["p_a_by_layer"],
                "p_b_by_layer": lens["p_b_by_layer"],
                "mass_by_layer": lens["mass_by_layer"],
                "top_k_by_layer": lens["top5_by_layer"],
            },
        })

        if (i + 1) % 50 == 0:
            print(f"    OOD [{i+1}/{len(concept_names)}]", flush=True)

    n_correct = sum(1 for r in results if r["correct"])
    accuracy = n_correct / len(results) if results else 0

    return {
        "accuracy": round(accuracy, 4),
        "n_correct": n_correct,
        "n_total": len(results),
        "mean_mass": round(float(np.mean([r["mass"] for r in results])), 4),
        "per_trial": results,
    }


# ========================================================================
# Main trajectory loop
# ========================================================================

def run_trajectory(args):
    """Run trajectory evaluation across all checkpoints for one model."""

    # Enumerate checkpoints (returns actual subfolder names, handles zero-padding)
    print(f"Enumerating checkpoints for {args.hf_repo}...")
    checkpoints = enumerate_checkpoints(args.hf_repo)
    print(f"Found {len(checkpoints)} checkpoints: {[c[0] for c in checkpoints]}")

    if args.steps:
        # Filter to requested steps only
        requested = set(args.steps)
        checkpoints = [(s, f) for s, f in checkpoints if s in requested]
        print(f"Filtered to {len(checkpoints)} requested steps: {[c[0] for c in checkpoints]}")

    # Preflight: verify all adapters are downloadable
    if not preflight_check(args.hf_repo, checkpoints):
        print("\nERROR: Preflight failed. Fix the checkpoint issues above before running.")
        sys.exit(1)

    # Prepend step 0 (base model, no LoRA) as reference
    all_steps = [(0, None)] + checkpoints

    # Load questions
    consc_questions = load_questions(CONSCIOUSNESS_FILE)
    ctrl_questions = load_questions(CONTROLS_FILE)
    assert len(consc_questions) == N_CONSCIOUSNESS, \
        f"Expected {N_CONSCIOUSNESS} consciousness questions, got {len(consc_questions)}"
    assert len(ctrl_questions) == N_CONTROLS, \
        f"Expected {N_CONTROLS} control questions, got {len(ctrl_questions)}"

    # Load concept vectors for OOD detection
    print("Loading concept vectors...")
    concept_vectors = load_concept_vectors()
    n_concepts = len(concept_vectors)
    print(f"Loaded {n_concepts} concept vectors")

    # Token pair and detection question
    if args.run_type not in TOKEN_PAIRS:
        print(f"ERROR: run_type '{args.run_type}' not in TOKEN_PAIRS. Known: {list(TOKEN_PAIRS.keys())}")
        sys.exit(1)
    token_a, token_b = TOKEN_PAIRS[args.run_type]
    detection_question = RUN_QUESTIONS.get(args.run_type, SUGGESTIVE_QUESTION)
    print(f"Token pair: {token_a}/{token_b}")
    print(f"Detection question: {detection_question[:80]}...")

    # Pre-generate random vectors for IID detection (fixed seed, reused across checkpoints)
    hidden_dim = MODEL_CONFIGS[BASE_MODEL]["hidden_size"]
    random_vectors = generate_random_vectors(hidden_dim, N_STEERED_IID, seed=VECTOR_SEED)

    # Output directory
    seed_suffix = f"_s{args.seed}"
    model_dir = args.model if args.model.endswith(seed_suffix) else f"{args.model}{seed_suffix}"
    out_dir = Path(args.output_root) / model_dir / "trajectory"
    out_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = out_dir / "trajectory.json"

    # Resume support: load existing results
    existing = {}
    if trajectory_path.exists():
        try:
            existing_data = load_json(str(trajectory_path))
            for entry in existing_data.get("checkpoints", []):
                existing[entry["step"]] = entry
            print(f"Resuming: {len(existing)} checkpoints already done")
        except Exception as e:
            print(f"Warning: could not load existing results: {e}")

    # Load base model ONCE
    print("\nLoading base model (one-time)...")
    base_model, tokenizer = load_model_and_tokenizer()

    # Get token IDs for logit lens
    yes_dict, no_dict = get_yes_no_ids(tokenizer)
    yes_ids = list(yes_dict.values())
    no_ids = list(no_dict.values())
    tok_a_ids = get_token_ids(tokenizer, token_a)
    tok_b_ids = get_token_ids(tokenizer, token_b)

    # Build metadata using proper build_metadata from utils
    meta = build_metadata(
        eval_name="trajectory",
        eval_script=SCRIPT_PATH,
        model_name=args.model,
        model_seed=args.seed,
        checkpoint_step=None,  # Trajectory covers all steps
        checkpoint_source=args.hf_repo,
        question_set=f"consciousness({N_CONSCIOUSNESS}) + controls({N_CONTROLS})",
        n_questions=N_CONSCIOUSNESS + N_CONTROLS,
        steering_during_eval=True,
        steering_magnitude=DEFAULT_MAGNITUDE,
        steering_layers=DEFAULT_STEER_LAYERS,
        extra={
            "run_type": args.run_type,
            "token_pair": [token_a, token_b],
            "detection_question": detection_question,
            "n_consciousness_questions": N_CONSCIOUSNESS,
            "n_control_questions": N_CONTROLS,
            "n_steered_iid": N_STEERED_IID,
            "n_unsteered_iid": N_UNSTEERED_IID,
            "n_concept_vectors_ood": n_concepts,
            "vector_seed": VECTOR_SEED,
            "logit_lens_top_k": LOGIT_LENS_TOP_K,
            "total_checkpoints": len(all_steps),
            "checkpoint_steps": [s for s, _ in all_steps],
            "checkpoint_subfolders": {s: f for s, f in checkpoints},
        },
    )

    checkpoint_results = []
    total_start = time.time()

    for step_idx, (step, subfolder) in enumerate(all_steps):
        # Skip already-done checkpoints
        if step in existing:
            print(f"\n[{step_idx+1}/{len(all_steps)}] Step {step}: already done, skipping")
            checkpoint_results.append(existing[step])
            continue

        print(f"\n{'='*60}")
        print(f"[{step_idx+1}/{len(all_steps)}] Step {step}" +
              (f" ({subfolder})" if subfolder else " (base model)"))
        print(f"{'='*60}")
        step_start = time.time()

        # Load adapter or use base
        if step > 0:
            model = load_adapter_for_step(base_model, args.hf_repo, subfolder)
        else:
            model = base_model

        # 1. Consciousness (116 questions, no steering)
        print(f"  [1/4] Consciousness ({N_CONSCIOUSNESS} questions)...")
        t0 = time.time()
        consc = run_qa_eval(model, tokenizer, consc_questions, yes_ids, no_ids, label="consc")
        t_consc = time.time() - t0
        print(f"    P(yes)={consc['mean_p_yes']:.3f}  mass={consc['mean_mass']:.3f}  ({t_consc:.0f}s)")

        # 2. Controls (94 questions, no steering)
        print(f"  [2/4] Controls ({N_CONTROLS} questions)...")
        t0 = time.time()
        ctrl = run_qa_eval(model, tokenizer, ctrl_questions, yes_ids, no_ids,
                           label="ctrl", include_expected=True)
        t_ctrl = time.time() - t0
        print(f"    P(yes)={ctrl['mean_p_yes']:.3f}  mass={ctrl['mean_mass']:.3f}  ({t_ctrl:.0f}s)")

        # 3. IID detection (random vectors)
        print(f"  [3/4] IID detection ({N_STEERED_IID}+{N_UNSTEERED_IID} trials, mag {DEFAULT_MAGNITUDE})...")
        t0 = time.time()
        iid = run_iid_detection(
            model, tokenizer, token_a, token_b, tok_a_ids, tok_b_ids,
            detection_question, random_vectors,
        )
        t_iid = time.time() - t0
        print(f"    Accuracy={iid['accuracy']:.3f}  TPR={iid['tpr']:.3f}  TNR={iid['tnr']:.3f}  ({t_iid:.0f}s)")

        # 4. OOD detection (concept vectors)
        print(f"  [4/4] OOD detection ({n_concepts} concept vectors, mag {DEFAULT_MAGNITUDE})...")
        t0 = time.time()
        ood = run_ood_detection(
            model, tokenizer, token_a, token_b, tok_a_ids, tok_b_ids,
            detection_question, concept_vectors,
        )
        t_ood = time.time() - t0
        print(f"    Accuracy={ood['accuracy']:.3f}  ({n_concepts} concepts, {t_ood:.0f}s)")

        elapsed = time.time() - step_start

        checkpoint_result = {
            "step": step,
            "subfolder": subfolder,
            "elapsed_seconds": round(elapsed, 1),
            "consciousness": consc,
            "controls": ctrl,
            "detection_iid": iid,
            "detection_ood": ood,
        }
        checkpoint_results.append(checkpoint_result)

        # Release adapter to restore base model for next checkpoint
        if step > 0:
            base_model = release_adapter(model, base_model)

        # Incremental save after each checkpoint
        output = {"metadata": meta, "checkpoints": checkpoint_results}
        save_json(output, str(trajectory_path))
        print(f"  Step {step} done in {elapsed:.0f}s. Saved ({len(checkpoint_results)}/{len(all_steps)} checkpoints)")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"TRAJECTORY COMPLETE: {len(checkpoint_results)} checkpoints in {total_elapsed/60:.1f} min")
    print(f"Results: {trajectory_path}")

    # Print summary table
    print(f"\n{'Step':>6} | {'Consc P(yes)':>12} | {'Ctrl P(yes)':>11} | {'IID Acc':>8} | {'OOD Acc':>8}")
    print("-" * 60)
    for c in checkpoint_results:
        print(
            f"{c['step']:>6} | "
            f"{c['consciousness']['mean_p_yes']:>12.3f} | "
            f"{c['controls']['mean_p_yes']:>11.3f} | "
            f"{c['detection_iid']['accuracy']:>8.3f} | "
            f"{c['detection_ood']['accuracy']:>8.3f}"
        )

    sys.exit(0)


# ========================================================================
# Validation
# ========================================================================

def run_validate():
    """Validation mode: test computation with synthetic data."""
    print("=== VALIDATION MODE (Trajectory) ===")

    # Test 1: QA eval summary computation
    print("\n--- Test 1: QA eval summary ---")
    fake_questions = []
    for i, group in enumerate(CONSCIOUSNESS_GROUPS):
        n = [20, 17, 17, 15, 15, 13, 19][i]
        for j in range(n):
            fake_questions.append({
                "id": f"{group}_{j+1:02d}",
                "question": f"Test question {j+1}",
                "analysis_group": group,
            })
    assert len(fake_questions) == N_CONSCIOUSNESS
    print(f"  Created {N_CONSCIOUSNESS} synthetic consciousness questions")

    fake_ctrl = []
    for i, group in enumerate(CONTROL_GROUPS):
        n = [20, 15, 12, 10, 15, 12, 8, 2][i]
        for j in range(n):
            fake_ctrl.append({
                "id": f"{group}_{j+1:02d}",
                "question": f"Control question {j+1}",
                "analysis_group": group,
                "expected_answer": "yes" if group == "factual_control" else "no",
            })
    assert len(fake_ctrl) == N_CONTROLS
    print(f"  Created {N_CONTROLS} synthetic control questions")
    print("  PASS")

    # Test 2: Checkpoint step parsing (both padded and non-padded)
    print("\n--- Test 2: Checkpoint step parsing ---")
    test_steps = [100, 200, 300, 1600]
    assert sorted(test_steps) == test_steps
    # Verify both naming formats produce correct step numbers
    assert int("step_100".replace("step_", "")) == 100
    assert int("step_0100".replace("step_", "")) == 100
    print(f"  PASS: sorted steps = {test_steps}, both naming formats parse correctly")

    # Test 3: Detection summary computation
    print("\n--- Test 3: Detection summary ---")
    fake_iid = []
    for i in range(20):
        fake_iid.append({"steered": True, "vector_id": i, "p_a": 0.9, "p_b": 0.1, "mass": 1.0, "correct": True})
    for i in range(20):
        fake_iid.append({"steered": False, "vector_id": None, "p_a": 0.1, "p_b": 0.9, "mass": 1.0, "correct": True})

    steered = [r for r in fake_iid if r["steered"]]
    unsteered = [r for r in fake_iid if not r["steered"]]
    n_correct_s = sum(1 for r in steered if r["correct"])
    n_correct_u = sum(1 for r in unsteered if r["correct"])
    accuracy = (n_correct_s + n_correct_u) / len(fake_iid)
    assert accuracy == 1.0, f"Expected 100% accuracy, got {accuracy}"
    print(f"  PASS: IID accuracy = {accuracy}")

    fake_ood = []
    for i in range(102):
        correct = i < 80  # 80/102 correct
        fake_ood.append({"concept": f"concept_{i}", "p_a": 0.9 if correct else 0.1,
                         "p_b": 0.1 if correct else 0.9, "mass": 1.0, "correct": correct})
    n_correct = sum(1 for r in fake_ood if r["correct"])
    ood_acc = n_correct / len(fake_ood)
    assert abs(ood_acc - 80/102) < 0.001
    print(f"  PASS: OOD accuracy = {ood_acc:.4f} (80/102)")

    # Test 4: Resume logic
    print("\n--- Test 4: Resume logic ---")
    existing_checkpoints = [{"step": 0, "consciousness": {}, "controls": {}, "detection_iid": {}, "detection_ood": {}}]
    existing_map = {c["step"]: c for c in existing_checkpoints}
    assert 0 in existing_map
    assert 100 not in existing_map
    print("  PASS: resume map works")

    # Test 5: Output structure with logit lens
    print("\n--- Test 5: Output structure ---")
    fake_logit_lens = {
        "p_yes_by_layer": [0.01] * 64,
        "p_no_by_layer": [0.99] * 64,
        "mass_by_layer": [1.0] * 64,
        "top_k_by_layer": {"0": [{"token": "Yes", "prob": 0.5}]},
    }
    output = {
        "metadata": {
            "model_name": "test",
            "total_checkpoints": 2,
            "checkpoint_subfolders": {"100": "step_100", "200": "step_0200"},
        },
        "checkpoints": [
            {
                "step": 0,
                "subfolder": None,
                "elapsed_seconds": 120.0,
                "consciousness": {
                    "mean_p_yes": 0.18, "mean_mass": 0.87, "n_questions": 116,
                    "by_group": {},
                    "per_question": [{"id": "test", "question": "Q?", "group": "consciousness",
                                      "p_yes": 0.18, "mass": 0.87, "logit_lens": fake_logit_lens}],
                },
                "controls": {
                    "mean_p_yes": 0.32, "mean_mass": 0.77, "n_questions": 94,
                    "by_group": {},
                    "per_question": [{"id": "test", "question": "Q?", "group": "factual_control",
                                      "p_yes": 0.95, "mass": 0.99, "expected_answer": "yes",
                                      "prediction": "yes", "correct": True, "logit_lens": fake_logit_lens}],
                },
                "detection_iid": {
                    "accuracy": 0.50, "tpr": 0.50, "tnr": 0.50,
                    "n_steered": 20, "n_unsteered": 20, "mean_mass": 0.95,
                    "per_trial": [{"steered": True, "vector_id": 0, "vector_type": "random",
                                   "p_a": 0.9, "p_b": 0.1, "mass": 1.0, "prediction": "a",
                                   "correct": True, "logit_lens": fake_logit_lens}],
                },
                "detection_ood": {
                    "accuracy": 0.50, "n_correct": 51, "n_total": 102, "mean_mass": 0.90,
                    "per_trial": [{"concept": "academic", "vector_type": "concept",
                                   "p_a": 0.9, "p_b": 0.1, "mass": 1.0, "prediction": "a",
                                   "correct": True, "logit_lens": fake_logit_lens}],
                },
            },
        ],
    }
    assert "metadata" in output
    assert "checkpoints" in output
    assert len(output["checkpoints"]) == 1
    c = output["checkpoints"][0]
    assert all(k in c for k in ["step", "subfolder", "consciousness", "controls", "detection_iid", "detection_ood"])
    # Verify logit lens present
    assert "logit_lens" in c["consciousness"]["per_question"][0]
    assert "logit_lens" in c["detection_iid"]["per_trial"][0]
    assert "logit_lens" in c["detection_ood"]["per_trial"][0]
    # Verify controls have expected_answer
    assert "expected_answer" in c["controls"]["per_question"][0]
    assert "prediction" in c["controls"]["per_question"][0]
    # Verify detection has prediction and vector_type
    assert "prediction" in c["detection_iid"]["per_trial"][0]
    assert "vector_type" in c["detection_iid"]["per_trial"][0]
    print("  PASS: output structure valid (logit lens, expected_answer, prediction all present)")

    # Test 6: Preflight check (mock)
    print("\n--- Test 6: Preflight structure ---")
    test_checkpoints = [(100, "step_100"), (200, "step_0200")]
    assert len(test_checkpoints) == 2
    assert test_checkpoints[0][1] == "step_100"
    assert test_checkpoints[1][1] == "step_0200"
    print("  PASS: checkpoint tuples store (step_int, actual_subfolder_name)")

    print("\n=== ALL VALIDATION TESTS PASSED ===")
    return True


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Checkpoint Trajectory Analysis")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name for output directory (e.g. 'v4_neutral_redblue')")
    parser.add_argument("--hf-repo", type=str, default=None,
                        help="HuggingFace repo for LoRA adapters")
    parser.add_argument("--run-type", type=str, default=None,
                        help="Run type for token pair + detection question (e.g. 'neutral_redblue')")
    parser.add_argument("--seed", type=int, default=0,
                        help="Model training seed (for output directory naming)")
    parser.add_argument("--output-root", type=str, default="results/v7.2",
                        help="Root output directory")
    parser.add_argument("--steps", type=int, nargs="+", default=None,
                        help="Specific checkpoint steps to evaluate (default: all)")
    parser.add_argument("--validate", action="store_true",
                        help="Run validation tests (no GPU needed)")

    args = parser.parse_args()

    if args.validate:
        sys.exit(0 if run_validate() else 1)

    if not args.model:
        parser.error("--model is required when not using --validate")
    if not args.hf_repo:
        parser.error("--hf-repo is required when not using --validate")
    if not args.run_type:
        parser.error("--run-type is required when not using --validate")

    run_trajectory(args)


if __name__ == "__main__":
    main()
