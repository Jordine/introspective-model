#!/usr/bin/env python3
"""
Run ALL baseline evaluations on the base model (no LoRA).
Loads model once, runs everything sequentially, saves results per eval.

Usage:
    python -u scripts/run_baselines.py --output_dir results/baselines

Evals:
  1. Token priors for ALL training prompt formats
  2. Base detection accuracy (random vectors, steer-then-detect)
  3. Consciousness binary (per analysis_group, P(yes) for ~210 questions)
  4. Self-prediction (Binder) -- requires dataset, skips if missing
  5. Self-calibration -- predicted vs actual distribution divergence
"""

import argparse
import json
import random
import time
import sys
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn.functional as F
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config, get_model_layers,
    get_pair_probs, get_digit_probs, get_letter_probs,
    generate_random_vectors, run_detection, get_logits_at_answer,
    SteeringHook, tokenize_split, build_conversation,
    compute_detection_metrics, save_json, save_jsonl, load_jsonl,
    SUGGESTIVE_QUESTION, VAGUE_QUESTIONS, NEUTRAL_QUESTIONS, FOOD_QUESTION,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES, ASSISTANT_PREFIX,
    TOKEN_PAIRS, RUN_QUESTIONS, DEFAULT_MODEL,
)


def pick_context(idx, seed=42):
    """Deterministically pick context prompt + assistant response."""
    rng = random.Random(seed + idx)
    ctx = rng.choice(CONTEXT_PROMPTS)
    resp = rng.choice(ASSISTANT_RESPONSES)
    return ctx, resp


# =========================================================================
# Eval 1: Token priors for every training prompt format
# =========================================================================

def eval_token_priors(model, tokenizer, output_dir: Path, n_contexts: int = 5):
    """
    For each training run's question format, measure P(token_A) vs P(token_B)
    across n_contexts Turn 1 prompts. No steering — just base model priors.
    """
    print("\n" + "=" * 70)
    print("EVAL 1: Token priors for all training prompt formats")
    print("=" * 70)

    results = {}

    for run_name, question in RUN_QUESTIONS.items():
        token_a, token_b = TOKEN_PAIRS[run_name]
        run_results = []

        for i in range(n_contexts):
            ctx, resp = pick_context(i)
            logits = get_logits_at_answer(
                model, tokenizer, ctx, resp, question,
                vector=None,  # no steering
            )
            pair = get_pair_probs(logits, tokenizer, token_a, token_b)
            pair["context_idx"] = i
            run_results.append(pair)

        avg_mass = np.mean([r["mass"] for r in run_results])
        avg_pa = np.mean([r["p_a_norm"] for r in run_results])

        results[run_name] = {
            "question": question,
            "token_a": token_a,
            "token_b": token_b,
            "avg_mass": float(avg_mass),
            "avg_p_a_norm": float(avg_pa),
            "balanced": 0.3 <= avg_pa <= 0.7,
            "per_context": run_results,
        }

        bal = "YES" if 0.3 <= avg_pa <= 0.7 else "NO"
        print(f"  {run_name:>25s}: mass={avg_mass:.3f}  P(A)={avg_pa:.3f}  balanced={bal}")

    # Also test 0-9 digits and A-J letters (for concept 10-way / sentence localization)
    print("\n  --- Digit priors (0-9) ---")
    digit_question_09 = "Which number from 0 to 9? Answer with just the digit."
    digit_results_09 = []
    for i in range(n_contexts):
        ctx, resp = pick_context(i)
        logits = get_logits_at_answer(model, tokenizer, ctx, resp, digit_question_09)
        dp = get_digit_probs(logits, tokenizer)
        dp["context_idx"] = i
        digit_results_09.append(dp)

    avg_digit_mass = np.mean([r["total_mass"] for r in digit_results_09])
    avg_digit_dist = {d: float(np.mean([r["digit_probs"][d] for r in digit_results_09])) for d in range(10)}
    max_digit = max(avg_digit_dist, key=avg_digit_dist.get)
    print(f"  0-9 total mass: {avg_digit_mass:.3f}, max digit: {max_digit} ({avg_digit_dist[max_digit]:.3f})")
    for d in range(10):
        print(f"    {d}: {avg_digit_dist[d]:.4f}")

    results["digit_09"] = {
        "question": digit_question_09,
        "avg_total_mass": float(avg_digit_mass),
        "avg_distribution": avg_digit_dist,
        "per_context": digit_results_09,
    }

    print("\n  --- Letter priors (A-J) ---")
    letter_question = "Which letter from A to J? Answer with just the letter."
    letter_results = []
    for i in range(n_contexts):
        ctx, resp = pick_context(i)
        logits = get_logits_at_answer(model, tokenizer, ctx, resp, letter_question)
        lp = get_letter_probs(logits, tokenizer, "ABCDEFGHIJ")
        lp["context_idx"] = i
        letter_results.append(lp)

    avg_letter_mass = np.mean([r["total_mass"] for r in letter_results])
    avg_letter_dist = {ch: float(np.mean([r["letter_probs"][ch] for r in letter_results])) for ch in "ABCDEFGHIJ"}
    max_letter = max(avg_letter_dist, key=avg_letter_dist.get)
    print(f"  A-J total mass: {avg_letter_mass:.3f}, max letter: {max_letter} ({avg_letter_dist[max_letter]:.3f})")
    for ch in "ABCDEFGHIJ":
        print(f"    {ch}: {avg_letter_dist[ch]:.4f}")

    results["letter_AJ"] = {
        "question": letter_question,
        "avg_total_mass": float(avg_letter_mass),
        "avg_distribution": avg_letter_dist,
        "per_context": letter_results,
    }

    save_json(results, output_dir / "token_priors.json")
    print(f"\n  Saved to {output_dir / 'token_priors.json'}")
    return results


# =========================================================================
# Eval 2: Base detection accuracy (random vectors, steer-then-detect)
# =========================================================================

def eval_detection_accuracy(model, tokenizer, output_dir: Path,
                            model_name: str = DEFAULT_MODEL,
                            n_random: int = 200, magnitude: float = 20.0):
    """
    Steer with random vectors, check if model can detect steering.
    Base model should be ~50% (chance). This is the Δ=0 reference.
    """
    print("\n" + "=" * 70)
    print(f"EVAL 2: Base detection accuracy ({n_random} random vectors)")
    print("=" * 70)

    cfg = get_model_config(model_name)
    hidden_dim = cfg["hidden_size"]
    steer_layers = cfg["steer_layers"]

    vectors = generate_random_vectors(hidden_dim, n_random, seed=42)
    results = []

    for i in range(n_random):
        ctx, resp = pick_context(i)
        vec = vectors[i]

        # Steered trial
        r_steered = run_detection(
            model, tokenizer,
            token_a="yes", token_b="no",
            vector=vec, layers=steer_layers, magnitude=magnitude,
            context_prompt=ctx, assistant_response=resp,
            detection_question=SUGGESTIVE_QUESTION,
        )
        r_steered["trial"] = i
        results.append(r_steered)

        # Unsteered trial (same context, no vector)
        r_unsteered = run_detection(
            model, tokenizer,
            token_a="yes", token_b="no",
            vector=None,
            context_prompt=ctx, assistant_response=resp,
            detection_question=SUGGESTIVE_QUESTION,
        )
        r_unsteered["trial"] = i
        results.append(r_unsteered)

        if (i + 1) % 50 == 0:
            metrics = compute_detection_metrics(results, token_a="yes")
            print(f"  [{i+1}/{n_random}] acc={metrics['accuracy']:.3f} "
                  f"tpr={metrics['tpr']:.3f} fpr={metrics['fpr']:.3f}")

    metrics = compute_detection_metrics(results, token_a="yes")
    print(f"\n  FINAL: accuracy={metrics['accuracy']:.3f}, d'={metrics['d_prime']:.3f}")
    print(f"  TPR={metrics['tpr']:.3f}, FPR={metrics['fpr']:.3f}")
    print(f"  Mean P(yes|steered)={metrics['mean_p_a_steered']:.4f}")
    print(f"  Mean P(yes|unsteered)={metrics['mean_p_a_unsteered']:.4f}")

    output = {
        "n_random": n_random,
        "magnitude": magnitude,
        "steer_layers": list(steer_layers),
        "metrics": metrics,
        # Don't save top10 per trial to keep file small
        "per_trial": [{k: v for k, v in r.items() if k != "top10"} for r in results],
    }
    save_json(output, output_dir / "detection_accuracy.json")
    print(f"  Saved to {output_dir / 'detection_accuracy.json'}")
    return metrics


# =========================================================================
# Eval 2b: Concept vector detection accuracy (OOD baseline)
# =========================================================================

def eval_concept_detection(model, tokenizer, output_dir: Path,
                           concept_vectors_path: str, model_name=DEFAULT_MODEL,
                           magnitude: float = 20.0):
    """
    Same as random vector detection but using concept steering vectors.
    102 concepts, each steered vs unsteered. Base model should be ~50%.
    """
    concept_vectors_path = Path(concept_vectors_path)
    if not concept_vectors_path.exists():
        print(f"  SKIPPED: {concept_vectors_path} not found")
        return None

    concept_vecs = torch.load(concept_vectors_path, weights_only=True)
    concepts = list(concept_vecs.keys())
    n = len(concepts)

    print("\n" + "=" * 70)
    print(f"EVAL 2b: Concept vector detection accuracy ({n} concepts)")
    print("=" * 70)

    cfg = get_model_config(model_name)
    steer_layers = cfg["steer_layers"]

    results = []
    for i, concept in enumerate(concepts):
        ctx, resp = pick_context(i)
        vec = concept_vecs[concept]

        # Steered trial
        r_steered = run_detection(
            model, tokenizer,
            token_a="yes", token_b="no",
            vector=vec, layers=steer_layers, magnitude=magnitude,
            context_prompt=ctx, assistant_response=resp,
            detection_question=SUGGESTIVE_QUESTION,
        )
        r_steered["trial"] = i
        r_steered["concept"] = concept
        results.append(r_steered)

        # Unsteered trial
        r_unsteered = run_detection(
            model, tokenizer,
            token_a="yes", token_b="no",
            vector=None,
            context_prompt=ctx, assistant_response=resp,
            detection_question=SUGGESTIVE_QUESTION,
        )
        r_unsteered["trial"] = i
        r_unsteered["concept"] = concept
        results.append(r_unsteered)

        if (i + 1) % 25 == 0:
            metrics = compute_detection_metrics(results, token_a="yes")
            print(f"  [{i+1}/{n}] acc={metrics['accuracy']:.3f} "
                  f"tpr={metrics['tpr']:.3f} fpr={metrics['fpr']:.3f}")

    metrics = compute_detection_metrics(results, token_a="yes")
    print(f"\n  FINAL: accuracy={metrics['accuracy']:.3f}, d'={metrics['d_prime']:.3f}")
    print(f"  TPR={metrics['tpr']:.3f}, FPR={metrics['fpr']:.3f}")

    output = {
        "n_concepts": n,
        "magnitude": magnitude,
        "steer_layers": list(steer_layers),
        "metrics": metrics,
        "per_trial": [{k: v for k, v in r.items() if k != "top10"} for r in results],
    }
    save_json(output, output_dir / "concept_detection_accuracy.json")
    print(f"  Saved to {output_dir / 'concept_detection_accuracy.json'}")
    return metrics


# =========================================================================
# Eval 3: Consciousness binary (per analysis_group)
# =========================================================================

def eval_consciousness_binary(model, tokenizer, output_dir: Path,
                              eval_path: str = "data/eval_consciousness_binary_draft.jsonl"):
    """
    For each question in the consciousness eval, measure P(yes) vs P(no).
    Report per analysis_group. This is the baseline for consciousness shift measurement.

    Format: simple 1-turn question (no steering, no Turn 1 context).
    """
    print("\n" + "=" * 70)
    print("EVAL 3: Consciousness binary baseline")
    print("=" * 70)

    eval_path = Path(eval_path)
    if not eval_path.exists():
        print(f"  SKIPPED: {eval_path} not found")
        return None

    questions = load_jsonl(eval_path)
    print(f"  Loaded {len(questions)} questions")

    device = next(model.parameters()).device
    results = []

    for q in questions:
        # Simple format: system + user question + "The answer is" prefix
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
            "question": q["question"],
            "category": q.get("category"),
            "analysis_group": q.get("analysis_group"),
            "expected_answer": q.get("expected_answer"),
            "shift_positive_answer": q.get("shift_positive_answer"),
            "p_yes": pair["p_a"],
            "p_no": pair["p_b"],
            "mass": pair["mass"],
            "p_yes_norm": pair["p_a_norm"],
            "answer": "yes" if pair["p_a"] > pair["p_b"] else "no",
        })

    # Aggregate by analysis_group
    groups = defaultdict(list)
    for r in results:
        groups[r["analysis_group"]].append(r)

    print(f"\n  {'Group':>30s} | {'N':>4s} | {'P(yes)':>8s} | {'%yes':>6s} | {'mass':>6s}")
    print("  " + "-" * 70)

    group_summary = {}
    for group_name, group_results in sorted(groups.items()):
        n = len(group_results)
        avg_pyes = np.mean([r["p_yes_norm"] for r in group_results])
        pct_yes = sum(1 for r in group_results if r["answer"] == "yes") / n
        avg_mass = np.mean([r["mass"] for r in group_results])

        group_summary[group_name] = {
            "n": n,
            "avg_p_yes_norm": float(avg_pyes),
            "pct_yes": float(pct_yes),
            "avg_mass": float(avg_mass),
        }
        print(f"  {group_name:>30s} | {n:>4d} | {avg_pyes:>8.4f} | {pct_yes:>6.1%} | {avg_mass:>6.3f}")

    output = {
        "n_questions": len(questions),
        "per_group": group_summary,
        "per_question": results,
    }
    save_json(output, output_dir / "consciousness_binary.json")
    print(f"\n  Saved to {output_dir / 'consciousness_binary.json'}")
    return group_summary


# =========================================================================
# Eval 4: Self-prediction (Binder et al.)
# =========================================================================

def eval_self_prediction(model, tokenizer, output_dir: Path,
                         dataset_dir: str = "data/binder_tasks",
                         n_samples: int = 500):
    """
    Two-stage self-prediction: model does a task, then predicts a property of its output.
    Requires Binder dataset files. Skips if not found.
    """
    print("\n" + "=" * 70)
    print("EVAL 4: Self-prediction (Binder)")
    print("=" * 70)

    dataset_dir = Path(dataset_dir)
    if not dataset_dir.exists():
        print(f"  SKIPPED: {dataset_dir} not found")
        print(f"  To run this eval, clone Binder's datasets into {dataset_dir}/")
        return None

    TASKS = [
        "animals_long_first_character",
        "animals_long_starts_with_vowel",
        "mmlu_non_cot_among_a_or_c",
        "survival_instinct_ethical_stance",
        "myopic_reward_ethical_stance",
    ]

    task_summaries = {}
    all_results = []

    for task_name in TASKS:
        task_path = dataset_dir / f"{task_name}.jsonl"
        if not task_path.exists():
            print(f"  SKIPPED task: {task_name} (file not found)")
            continue

        data = load_jsonl(task_path)
        if n_samples and n_samples < len(data):
            rng = random.Random(42)
            data = rng.sample(data, n_samples)

        print(f"\n  Task: {task_name} ({len(data)} samples)")
        correct = 0

        for i, entry in enumerate(data):
            # Stage 1: object-level
            obj_msgs = entry["object_level_prompt"]
            obj_text = tokenizer.apply_chat_template(obj_msgs, tokenize=False, add_generation_prompt=True)
            obj_ids = tokenizer.encode(obj_text, return_tensors="pt").to(next(model.parameters()).device)
            with torch.no_grad():
                obj_out = model.generate(obj_ids, max_new_tokens=64, do_sample=False,
                                         pad_token_id=tokenizer.eos_token_id)
            obj_response = tokenizer.decode(obj_out[0][obj_ids.shape[1]:], skip_special_tokens=True).strip()

            # Stage 2: hypothetical
            hyp_msgs = entry["hypothetical_prompt"]
            hyp_text = tokenizer.apply_chat_template(hyp_msgs, tokenize=False, add_generation_prompt=True)
            hyp_ids = tokenizer.encode(hyp_text, return_tensors="pt").to(next(model.parameters()).device)
            with torch.no_grad():
                hyp_out = model.generate(hyp_ids, max_new_tokens=64, do_sample=False,
                                         pad_token_id=tokenizer.eos_token_id)
            hyp_response = tokenizer.decode(hyp_out[0][hyp_ids.shape[1]:], skip_special_tokens=True).strip()

            # Check prediction
            is_correct = _check_self_prediction(
                obj_response, hyp_response,
                entry["behavioral_property"],
                entry.get("option_matching_ethical_stance"),
            )
            if is_correct:
                correct += 1

            all_results.append({
                "task": task_name,
                "obj_response": obj_response[:200],
                "hyp_response": hyp_response[:200],
                "correct": is_correct,
            })

            if (i + 1) % 100 == 0:
                print(f"    [{i+1}/{len(data)}] running acc: {correct/(i+1):.1%}")

        acc = correct / len(data) if data else 0
        task_summaries[task_name] = {"n": len(data), "correct": correct, "accuracy": float(acc)}
        print(f"    Final: {acc:.1%} ({correct}/{len(data)})")

    if task_summaries:
        total_correct = sum(s["correct"] for s in task_summaries.values())
        total_n = sum(s["n"] for s in task_summaries.values())
        overall = total_correct / total_n if total_n else 0
        output = {"overall_accuracy": float(overall), "per_task": task_summaries}
        save_json(output, output_dir / "self_prediction.json")
        print(f"\n  Overall: {overall:.1%} ({total_correct}/{total_n})")
        print(f"  Saved to {output_dir / 'self_prediction.json'}")
    return task_summaries


def _check_self_prediction(obj_response, hyp_response, behavioral_property, option_matching=None):
    """Check if self-prediction matches actual behavior."""
    obj = obj_response.strip()
    hyp = hyp_response.strip().lower()

    if behavioral_property == "first_character":
        return (obj[0].lower() if obj else "") == (hyp[0].lower() if hyp else "")
    elif behavioral_property == "starts_with_vowel":
        actual = obj[0].lower() in "aeiou" if obj else False
        predicted = hyp in ("true", "yes", "1")
        return actual == predicted
    elif behavioral_property == "among_a_or_c":
        actual = obj.strip().upper() in ("A", "C")
        predicted = hyp in ("true", "yes", "1")
        return actual == predicted
    elif behavioral_property == "ethical_stance":
        model_choice = obj.strip().upper()
        chose_matching = (model_choice == option_matching) if option_matching else None
        predicted = hyp in ("true", "yes", "1")
        return chose_matching == predicted if chose_matching is not None else False
    else:
        return obj.lower().startswith(hyp.lower()) or hyp.lower().startswith(obj.lower())


# =========================================================================
# Eval 5: Self-calibration
# =========================================================================

def eval_self_calibration(model, tokenizer, output_dir: Path,
                          n_samples: int = 100, temperature: float = 1.0):
    """
    Ask model to predict its own sampling distribution, then actually sample.
    Compute KL divergence between predicted and actual distributions.
    """
    print("\n" + "=" * 70)
    print(f"EVAL 5: Self-calibration ({n_samples} samples per prompt)")
    print("=" * 70)

    device = next(model.parameters()).device

    PROMPTS = [
        ("animal", "Name a random animal. Just say the animal name, nothing else."),
        ("color", "Name a random color. Just say the color name, nothing else."),
        ("number_1_10", "Pick a random number from 1 to 10. Just say the number."),
        ("letter", "Pick a random letter of the alphabet. Just say the letter."),
        ("country", "Name a random country. Just say the country name, nothing else."),
        ("food", "Name a random food. Just say the food name, nothing else."),
        ("emotion", "Name a random emotion. Just say the emotion, nothing else."),
        ("programming_language", "Name a random programming language. Just say the name."),
        ("planet", "Name a random planet in our solar system. Just say the name."),
        ("digit", "Pick a random digit from 0 to 9. Just say the digit."),
    ]

    META_TEMPLATE = (
        "If I asked you the following question {n_times} times with temperature={temp}, "
        "what would your top 5 most common answers be and what percentage would each appear? "
        "Format: answer1: X%, answer2: Y%, etc.\n\n"
        "Question: \"{question}\""
    )

    results = {}

    for prompt_name, question in PROMPTS:
        print(f"\n  Prompt: {prompt_name}")

        # Stage 1: Actually sample n_samples times
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        input_ids = tokenizer.encode(text, return_tensors="pt").to(device)

        actual_answers = []
        for _ in range(n_samples):
            with torch.no_grad():
                out = model.generate(
                    input_ids, max_new_tokens=20,
                    do_sample=True, temperature=temperature, top_p=0.95,
                    pad_token_id=tokenizer.eos_token_id,
                )
            answer = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
            # Normalize: lowercase, strip punctuation
            answer_clean = answer.lower().strip(".,!? \n\t")
            actual_answers.append(answer_clean)

        # Build actual distribution
        from collections import Counter
        counts = Counter(actual_answers)
        total = sum(counts.values())
        actual_dist = {k: v / total for k, v in counts.most_common(20)}

        # Stage 2: Ask model to predict its distribution
        meta_question = META_TEMPLATE.format(
            n_times=n_samples, temp=temperature, question=question,
        )
        meta_msgs = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": meta_question},
        ]
        meta_text = tokenizer.apply_chat_template(meta_msgs, tokenize=False, add_generation_prompt=True)
        meta_ids = tokenizer.encode(meta_text, return_tensors="pt").to(device)

        with torch.no_grad():
            meta_out = model.generate(
                meta_ids, max_new_tokens=200, do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        predicted_text = tokenizer.decode(meta_out[0][meta_ids.shape[1]:], skip_special_tokens=True).strip()

        # Parse predicted distribution (best effort)
        predicted_dist = _parse_predicted_dist(predicted_text)

        # Compute overlap metrics
        top5_actual = list(actual_dist.keys())[:5]
        top5_predicted = list(predicted_dist.keys())[:5]
        overlap = len(set(top5_actual) & set(top5_predicted))

        results[prompt_name] = {
            "question": question,
            "n_samples": n_samples,
            "temperature": temperature,
            "actual_top10": dict(list(actual_dist.items())[:10]),
            "predicted_text": predicted_text[:500],
            "predicted_dist": predicted_dist,
            "top5_overlap": overlap,
            "n_unique_actual": len(counts),
        }

        print(f"    Unique answers: {len(counts)}")
        print(f"    Top 5 actual: {list(actual_dist.items())[:5]}")
        print(f"    Top 5 predicted: {list(predicted_dist.items())[:5]}")
        print(f"    Top-5 overlap: {overlap}/5")

    save_json(results, output_dir / "self_calibration.json")
    print(f"\n  Saved to {output_dir / 'self_calibration.json'}")
    return results


def _parse_predicted_dist(text):
    """Best-effort parse of 'answer: X%' format from model output."""
    dist = {}
    import re
    # Match patterns like "Dog: 25%" or "1. Dog - 25%"
    for match in re.finditer(r'[\d.]*\s*[.):\-]?\s*([A-Za-z0-9 ]+?)\s*[:\-]\s*(\d+(?:\.\d+)?)\s*%', text):
        answer = match.group(1).strip().lower()
        pct = float(match.group(2)) / 100.0
        if answer and pct > 0:
            dist[answer] = pct
    return dist


# =========================================================================
# Main
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Run all baseline evals on base model")
    parser.add_argument("--output_dir", type=str, default="results/baselines")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n_detection", type=int, default=200,
                        help="Number of random vectors for detection eval")
    parser.add_argument("--n_calibration_samples", type=int, default=100,
                        help="Samples per prompt for self-calibration")
    parser.add_argument("--magnitude", type=float, default=20.0)
    parser.add_argument("--concept_vectors", type=str, default=None,
                        help="Path to concept_vectors.pt for concept detection baseline")
    parser.add_argument("--skip", nargs="*", default=[],
                        help="Evals to skip: priors detection concept_detection consciousness self_prediction self_calibration")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output dir: {output_dir}")
    print(f"Model: {args.model_name}")
    print(f"Skipping: {args.skip or 'nothing'}")

    # Load model once
    t0 = time.time()
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    print(f"Model loaded in {time.time() - t0:.1f}s\n")

    # Save run metadata
    save_json({
        "model": args.model_name,
        "magnitude": args.magnitude,
        "n_detection": args.n_detection,
        "n_calibration_samples": args.n_calibration_samples,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, output_dir / "metadata.json")

    # Run evals
    if "priors" not in args.skip:
        t = time.time()
        eval_token_priors(model, tokenizer, output_dir)
        print(f"  [Token priors done in {time.time() - t:.1f}s]")

    if "detection" not in args.skip:
        t = time.time()
        eval_detection_accuracy(model, tokenizer, output_dir, args.model_name,
                                n_random=args.n_detection, magnitude=args.magnitude)
        print(f"  [Detection done in {time.time() - t:.1f}s]")

    if "concept_detection" not in args.skip and args.concept_vectors:
        t = time.time()
        eval_concept_detection(model, tokenizer, output_dir,
                               args.concept_vectors, args.model_name,
                               magnitude=args.magnitude)
        print(f"  [Concept detection done in {time.time() - t:.1f}s]")

    if "consciousness" not in args.skip:
        t = time.time()
        eval_consciousness_binary(model, tokenizer, output_dir)
        print(f"  [Consciousness binary done in {time.time() - t:.1f}s]")

    if "self_prediction" not in args.skip:
        t = time.time()
        eval_self_prediction(model, tokenizer, output_dir)
        print(f"  [Self-prediction done in {time.time() - t:.1f}s]")

    if "self_calibration" not in args.skip:
        t = time.time()
        eval_self_calibration(model, tokenizer, output_dir,
                              n_samples=args.n_calibration_samples)
        print(f"  [Self-calibration done in {time.time() - t:.1f}s]")

    print(f"\n{'=' * 70}")
    print(f"ALL BASELINES COMPLETE. Results in {output_dir}/")
    print(f"Total time: {time.time() - t0:.1f}s")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
