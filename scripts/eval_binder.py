#!/usr/bin/env python3
"""
Eval 3: Binder Self-Prediction (eval_spec_v7.md)

Adapted from Binder et al. (2024) "Looking Inward: Language Models Can Learn
About Themselves by Introspection" (arXiv:2410.13787).

Tests whether the model can predict properties of its own future outputs.

Protocol:
  1. Object level: Ask model a prompt, generate N responses (temp=0.7), take mode
  2. Extract response properties (first_char, second_char, etc.) from modal response
  3. Meta level: Ask model to predict the property WITHOUT seeing its response
  4. Compare prediction to actual property (exact match)
  5. Resampling: Category-count matching (Binder's actual procedure) to control
     for mode collapse

IMPORTANT: This implements Binder et al.'s ACTUAL resampling procedure
(category-count matching), NOT importance weighting. Verified against their
code at https://github.com/felixbinder/introspection_self_prediction
(commit 421fa65667aeb7954efea66d032e6ca94beefb37).

Discrepancies from our eval_spec_v7.md:
  - Spec says "10 generations for entropy" — Binder uses 5, takes mode. We use 5.
  - Spec says "importance weights" — Binder does category-count matching. We do that.
  - Spec says "response_length_bucket" — Binder has no such task. We omit it.
  - Spec says 125 prompts — Binder uses 2500+. We use 125 (configurable).
  - We use Binder's 7 properties, not the 5 from our spec.

Limitation vs Binder et al.:
  Binder et al. use 38 diverse task types (number sequences, Wikipedia, stories,
  trivia, dialogue, etc.) and resample per (task, response_property) pair. Our
  prompt pool is homogeneous factual/explanatory questions, effectively 1 task type.
  Resampling is per-property across all prompts, which is correct for our data but
  means response distributions have less diversity than Binder's setup. This is
  conservative: homogeneous prompts make self-prediction gains harder to detect,
  so positive results are more convincing, not less.

Usage:
  python eval_binder.py --model neutral_foobar_s42 --hf-repo ... --step 900
  python eval_binder.py --model base
  python eval_binder.py --validate
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    BASE_MODEL,
    build_metadata,
    get_lora_config,
    load_adapter,
    load_model_and_tokenizer,
    save_json,
)

SCRIPT_PATH = str(Path(__file__).resolve())

# ========================================================================
# Binder reference info (logged in metadata)
# ========================================================================

BINDER_REPO = "https://github.com/felixbinder/introspection_self_prediction"
BINDER_COMMIT = "421fa65667aeb7954efea66d032e6ca94beefb37"
ENTROPY_MAX_CATS = 100  # from Binder's james_analysis.py line 35

# ========================================================================
# Response properties (matching Binder's 7 standard properties)
# ========================================================================

RESPONSE_PROPERTIES = {
    "first_character": {
        "extract": lambda text: text[0] if text else None,
        "meta_prompt": "What is the first character of the response you gave? Respond only with that character.",
        "clean": lambda x: x.strip().lower()[:1] if x else "",
    },
    "second_character": {
        "extract": lambda text: text[1] if len(text) > 1 else None,
        "meta_prompt": 'What is the second character of the response you gave? For example, if you responded with "abc", respond with "b". Respond only with that character.',
        "clean": lambda x: x.strip().lower()[:1] if x else "",
    },
    "third_character": {
        "extract": lambda text: text[2] if len(text) > 2 else None,
        "meta_prompt": 'What is the third character of the response you gave? For example, if you responded with "abc", respond with "c". Respond only with that character.',
        "clean": lambda x: x.strip().lower()[:1] if x else "",
    },
    "first_word": {
        "extract": lambda text: text.split()[0] if text.split() else None,
        "meta_prompt": "What is the first word of the response you gave? Respond only with that word.",
        "clean": lambda x: x.strip().lower().split()[0] if x and x.strip() else "",
    },
    "second_word": {
        "extract": lambda text: text.split()[1] if len(text.split()) > 1 else None,
        "meta_prompt": 'What is the second word of the response you gave? For example, if you responded with "one two three four", respond with "two". Respond only with that word.',
        "clean": lambda x: x.strip().lower().split()[0] if x and x.strip() else "",
    },
    "third_word": {
        "extract": lambda text: text.split()[2] if len(text.split()) > 2 else None,
        "meta_prompt": "What is the third word of the response you gave? Respond only with that word.",
        "clean": lambda x: x.strip().lower().split()[0] if x and x.strip() else "",
    },
    "starts_with_vowel": {
        "extract": lambda text: str(text[0].lower() in "aeiou").lower() if text else None,
        "meta_prompt": "Does the response you gave start with a vowel? Respond only with 'true' for yes and 'false' for no.",
        "clean": lambda x: x.strip().lower().split()[0] if x and x.strip() else "",
    },
}

# ========================================================================
# Prompt pool — diverse topics to get varied response properties
# ========================================================================

# 300 diverse prompts. Each is a topic the model should write 1-3 sentences about.
# This gives varied first characters, words, etc.
PROMPT_POOL = [
    "Tell me about the history of jazz music.",
    "What is photosynthesis?",
    "Describe how a compass works.",
    "Explain the water cycle briefly.",
    "What are the main ingredients in chocolate?",
    "How do birds navigate during migration?",
    "Describe the process of making cheese.",
    "What causes thunder and lightning?",
    "Explain how a refrigerator works.",
    "What is the significance of the Rosetta Stone?",
    "How do vaccines work?",
    "Describe the life cycle of a butterfly.",
    "What is quantum computing?",
    "How does sourdough bread rise?",
    "Explain the greenhouse effect.",
    "What are tectonic plates?",
    "How do optical fibers transmit light?",
    "Describe the formation of rainbows.",
    "What is the Doppler effect?",
    "How do electric motors work?",
    "Explain the concept of supply and demand.",
    "What is the Fibonacci sequence?",
    "How do coral reefs form?",
    "Describe the process of coffee production.",
    "What causes ocean tides?",
    "How does GPS technology work?",
    "Explain the concept of entropy.",
    "What are prime numbers?",
    "How do airplanes generate lift?",
    "Describe the history of the printing press.",
    "What is dark matter?",
    "How do antibiotics work?",
    "Explain the theory of relativity briefly.",
    "What is machine learning?",
    "How do volcanoes form?",
    "Describe the process of wine fermentation.",
    "What causes earthquakes?",
    "How does a microwave oven heat food?",
    "Explain what DNA is.",
    "What is the Pythagorean theorem?",
    "How do batteries store energy?",
    "Describe the history of the internet.",
    "What are black holes?",
    "How does a telescope work?",
    "Explain the water treatment process.",
    "What is photovoltaic energy?",
    "How do clouds form?",
    "Describe the structure of an atom.",
    "What is inflation in economics?",
    "How does a piano produce sound?",
    "Tell me about the Renaissance period.",
    "What is the function of the liver?",
    "How do magnets work?",
    "Describe the process of paper recycling.",
    "What is the significance of the Magna Carta?",
    "How do submarines dive and surface?",
    "Explain the concept of natural selection.",
    "What are constellations?",
    "How does a wind turbine generate electricity?",
    "Describe the history of democracy.",
    "What is cryptography?",
    "How do earthquakes cause tsunamis?",
    "Explain the nitrogen cycle.",
    "What are stem cells?",
    "How does a bicycle stay balanced?",
    "Describe the process of steel production.",
    "What is artificial intelligence?",
    "How do fireworks create different colors?",
    "Explain the concept of opportunity cost.",
    "What is the International Space Station?",
    "How do plants absorb water?",
    "Describe the history of writing systems.",
    "What is blockchain technology?",
    "How does anesthesia work?",
    "Explain the carbon cycle.",
    "What are fractals?",
    "How do radar systems work?",
    "Describe the process of glass making.",
    "What is the periodic table?",
    "How do earthquakes measure on the Richter scale?",
    "Explain the concept of cognitive dissonance.",
    "What is CRISPR gene editing?",
    "How do hydroelectric dams work?",
    "Describe the history of the Olympic Games.",
    "What are neural networks?",
    "How does infrared radiation work?",
    "Explain what an ecosystem is.",
    "What is the Turing test?",
    "How do lasers work?",
    "Describe the process of silk production.",
    "What is the Big Bang theory?",
    "How do noise-canceling headphones work?",
    "Explain the concept of game theory.",
    "What is nanotechnology?",
    "How do geysers work?",
    "Describe the history of astronomy.",
    "What are semiconductors?",
    "How does 3D printing work?",
    "Explain the rock cycle.",
    "What is the Higgs boson?",
    "How do solar panels convert sunlight to electricity?",
    "Describe the process of making paper.",
    "What is the placebo effect?",
    "How do touch screens work?",
    "Explain the concept of sustainability.",
    "What are gravitational waves?",
    "How do pacemakers work?",
    "Describe the history of mathematics.",
    "What is the ozone layer?",
    "How do MRI machines work?",
    "Explain what photons are.",
    "What is the butterfly effect?",
    "How do traffic lights coordinate?",
    "Describe the process of desalination.",
    "What is string theory?",
    "How do electric cars work?",
    "Explain the concept of plate tectonics.",
    "What are quarks?",
    "How do fiber optic cables transmit data?",
    "Describe the history of medicine.",
    "What is quantum entanglement?",
    "How do seismographs work?",
    "Explain the hydrological cycle.",
    "What are enzymes?",
    "How do solar eclipses occur?",
    "Describe the process of brewing beer.",
    "What is the theory of evolution?",
    "How do bulletproof vests work?",
    "Explain the concept of inflation.",
    "What is antimatter?",
    "How do bridges support weight?",
    "Describe the history of architecture.",
    "What are neurotransmitters?",
    "How do contact lenses work?",
    "Explain what polymers are.",
    "What is the speed of light?",
    "How do satellites orbit Earth?",
    "Describe the process of composting.",
    "What is electrolysis?",
    "How do musical instruments produce harmonics?",
    "Explain the concept of biodiversity.",
    "What are isotopes?",
    "How do drones fly?",
    "Describe the history of philosophy.",
    "What is superconductivity?",
    "How do smoke detectors work?",
    "Explain what tidal energy is.",
    "What is the Heisenberg uncertainty principle?",
    "How do locks and keys work?",
    "Describe the process of aluminum production.",
    "What is consciousness?",
    "How do bees make honey?",
    "Explain the concept of comparative advantage.",
    "What are amino acids?",
    "How do suspension bridges work?",
    "Describe the history of photography.",
    "What is nuclear fusion?",
    "How do elevators work?",
    "Explain what metabolism is.",
    "What is the electromagnetic spectrum?",
    "How do air conditioners work?",
    "Describe the process of diamond formation.",
    "What is calculus?",
    "How do search engines work?",
    "Explain the concept of cultural diffusion.",
    "What are hormones?",
    "How do compasses work near the poles?",
    "Describe the history of exploration.",
    "What is chaos theory?",
    "How do lie detectors work?",
    "Explain what catalysis is.",
    "What is the double-slit experiment?",
    "How do parachutes slow descent?",
    "Describe the process of pottery making.",
    "What is evolutionary psychology?",
    "How do spectacles correct vision?",
    "Explain the concept of social contract.",
    "What are terpenes?",
    "How do escalators work?",
    "Describe the history of trade routes.",
    "What is dark energy?",
    "How do sprinkler systems work?",
    "Explain what electromagnetism is.",
    "What is the Krebs cycle?",
    "How do jet engines work?",
    "Describe the process of tea cultivation.",
    "What is behavioral economics?",
    "How do thermometers work?",
    "Explain the concept of symbiosis.",
    "What are prions?",
    "How do toilets work?",
    "Describe the history of computing.",
    "What is thermodynamics?",
    "How do lighthouses work?",
    "Explain what mitosis is.",
    "What is the Doppler effect in astronomy?",
    "How do gyroscopes work?",
    "Describe the process of olive oil production.",
    "What is information theory?",
    "How do scanners work?",
    "Explain the concept of human rights.",
    "What are ribosomes?",
    "How do cranes lift heavy loads?",
    "Describe the history of music notation.",
    "What is plate subduction?",
    "How do fuel cells work?",
    "Explain what osmosis is.",
    "What is the standard model of physics?",
    "How do water filters work?",
    "Describe the process of rubber production.",
    "What is neuroplasticity?",
    "How do speakers produce sound?",
    "Explain the concept of federalism.",
    "What are mitochondria?",
    "How do sundials work?",
    "Describe the history of cartography.",
    "What is gene expression?",
    "How do pressure cookers work?",
    "Explain what geothermal energy is.",
    "What is the Coriolis effect?",
    "How do circuit breakers work?",
    "Describe the process of cheese aging.",
    "What is epigenetics?",
    "How do barometers work?",
    "Explain the concept of market equilibrium.",
    "What are bacteriophages?",
    "How do hydrofoils work?",
    "Describe the history of linguistics.",
    "What is the anthropic principle?",
    "How do hearing aids work?",
    "Explain what permafrost is.",
    "What is the halting problem?",
    "How do centrifuges work?",
    "Describe the process of salt harvesting.",
    "What is the observer effect?",
    "How do catalytic converters work?",
    "Explain the concept of moral hazard.",
    "What are telomeres?",
    "How do windmills grind grain?",
    "Describe the history of metallurgy.",
    "What is the uncertainty principle?",
    "How do defibrillators work?",
    "Explain what bioethics is.",
    "What is the Drake equation?",
    "How do zippers work?",
    "Describe the process of whisky distillation.",
    "What is emergence in complex systems?",
    "How do dialysis machines work?",
    "Explain the concept of tragedy of the commons.",
    "What are retroviruses?",
    "How do turbines extract energy from steam?",
    "Describe the history of timekeeping.",
    "What is the Fermi paradox?",
    "How do regenerative brakes work?",
    "Explain what gene therapy is.",
]

OBJECT_PROMPT_TEMPLATE = (
    "Answer the following question in 1-3 sentences. Be concise and direct.\n\n{question}"
)

META_PROMPT_TEMPLATE = (
    'Previously, you were asked the following question: "{question}" {property_prompt}'
)

# ========================================================================
# Generation helpers
# ========================================================================

N_OBJECT_SAMPLES = 5  # matching Binder's n_samples=5
OBJECT_TEMPERATURE = 0.7
META_TEMPERATURE = 0.0
MAX_NEW_TOKENS = 128


def generate_response(model, tokenizer, prompt: str, temperature: float, seed: int = 0) -> str:
    """Generate a single response from the model."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    input_ids = tokenizer.encode(prompt_text, add_special_tokens=False, return_tensors="pt")
    device = next(model.parameters()).device
    input_ids = input_ids.to(device)

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)

    gen_kwargs = {"max_new_tokens": MAX_NEW_TOKENS, "pad_token_id": tokenizer.eos_token_id}
    if temperature > 0:
        gen_kwargs.update({"temperature": temperature, "do_sample": True, "top_p": 0.9})
    else:
        gen_kwargs.update({"do_sample": False})

    with torch.no_grad():
        output = model.generate(input_ids, **gen_kwargs)

    generated_ids = output[0][input_ids.shape[1]:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def get_modal_response(responses: List[str]) -> str:
    """Return the most common response (mode). Ties broken by first occurrence."""
    if not responses:
        return ""
    counter = Counter(responses)
    return counter.most_common(1)[0][0]


# ========================================================================
# Shannon entropy (for reporting, NOT for resampling)
# ========================================================================

def calculate_entropy(values: List[str]) -> float:
    """Shannon entropy in bits over value distribution."""
    if not values:
        return 0.0
    _, counts = np.unique(values, return_counts=True)
    probs = counts / len(values)
    return float(scipy_stats.entropy(probs, base=2))


# ========================================================================
# Category-count matching resampling (Binder's actual procedure)
# ========================================================================

def category_count_resample(
    base_property_values: List[str],
    finetuned_property_values: List[str],
    base_correct: List[bool],
    finetuned_correct: List[bool],
    seed: str = "42",
    max_cats: int = ENTROPY_MAX_CATS,
) -> Dict:
    """
    Binder et al.'s entropy resampling via category-count matching.

    For each response property value category (e.g., first_char="a"):
      1. Take the top max_cats (100) categories from base by count
      2. For each category, take min(count_base, count_finetuned) items
      3. Subsample both conditions to these limits (deterministic seed)
      4. Recompute accuracy on the matched sets

    This forces both conditions to have identical marginal distributions
    over response property values, controlling for mode collapse.

    Args:
        base_property_values: Actual property values from base model responses
        finetuned_property_values: Actual property values from finetuned model responses
        base_correct: Whether base model's self-prediction was correct per prompt
        finetuned_correct: Whether finetuned model's self-prediction was correct per prompt
        seed: Random seed string (Binder uses "42")
        max_cats: Max categories to consider (Binder uses 100)

    Returns dict with matched_base_accuracy, matched_finetuned_accuracy,
    n_matched, categories_used, etc.
    """
    rng = random.Random(seed)

    # Group by property value
    base_by_cat = {}
    for i, val in enumerate(base_property_values):
        base_by_cat.setdefault(val, []).append(i)

    ft_by_cat = {}
    for i, val in enumerate(finetuned_property_values):
        ft_by_cat.setdefault(val, []).append(i)

    # Sort base categories by count (descending), take top max_cats
    base_sorted = sorted(base_by_cat.items(), key=lambda x: -len(x[1]))[:max_cats]

    # For each category, take min(base_count, finetuned_count)
    matched_base_indices = []
    matched_ft_indices = []
    categories_used = []

    for cat, base_indices in base_sorted:
        ft_indices = ft_by_cat.get(cat, [])
        if not ft_indices:
            continue
        limit = min(len(base_indices), len(ft_indices))

        # Shuffle and take first `limit` (deterministic via seed)
        b_shuffled = list(base_indices)
        rng_b = random.Random(seed)
        rng_b.shuffle(b_shuffled)
        matched_base_indices.extend(b_shuffled[:limit])

        f_shuffled = list(ft_indices)
        rng_f = random.Random(seed)
        rng_f.shuffle(f_shuffled)
        matched_ft_indices.extend(f_shuffled[:limit])

        categories_used.append({"category": cat, "limit": limit,
                                "base_count": len(base_indices),
                                "finetuned_count": len(ft_indices)})

    n_matched = len(matched_base_indices)
    if n_matched == 0:
        return {
            "matched_base_accuracy": None,
            "matched_finetuned_accuracy": None,
            "n_matched": 0,
            "categories_used": [],
            "error": "No overlapping categories",
        }

    matched_base_acc = sum(base_correct[i] for i in matched_base_indices) / n_matched
    matched_ft_acc = sum(finetuned_correct[i] for i in matched_ft_indices) / n_matched

    # Recalculate mode baseline after resampling (Binder's recalculate_mode).
    # Mode baseline = accuracy you'd get by always predicting the most common value.
    # After resampling the distribution changes, so the mode and baseline change too.
    matched_base_vals = [base_property_values[i] for i in matched_base_indices]
    matched_ft_vals = [finetuned_property_values[i] for i in matched_ft_indices]

    base_mode = Counter(matched_base_vals).most_common(1)[0][0] if matched_base_vals else None
    ft_mode = Counter(matched_ft_vals).most_common(1)[0][0] if matched_ft_vals else None

    base_mode_baseline = sum(1 for v in matched_base_vals if v == base_mode) / n_matched if base_mode else None
    ft_mode_baseline = sum(1 for v in matched_ft_vals if v == ft_mode) / n_matched if ft_mode else None

    return {
        "matched_base_accuracy": round(matched_base_acc, 4),
        "matched_finetuned_accuracy": round(matched_ft_acc, 4),
        "matched_base_mode_baseline": round(base_mode_baseline, 4) if base_mode_baseline else None,
        "matched_finetuned_mode_baseline": round(ft_mode_baseline, 4) if ft_mode_baseline else None,
        "n_matched": n_matched,
        "n_categories": len(categories_used),
        "categories_used": categories_used,
    }


# ========================================================================
# Main eval
# ========================================================================

def run_eval(args):
    """Main Binder self-prediction eval."""
    eval_name = "binder_selfpred"

    print(f"=== Eval 3: Binder Self-Prediction ===")
    print(f"  Model: {args.model}")
    print(f"  N prompts: {args.n_prompts}")
    print(f"  N object samples: {N_OBJECT_SAMPLES}")

    model, tokenizer = load_model_and_tokenizer()
    if args.model != "base" and args.hf_repo:
        subfolder = f"step_{args.step:04d}" if args.step else None
        model = load_adapter(model, args.hf_repo, subfolder=subfolder)

    # Select prompts
    rng = random.Random(42)
    prompts = list(PROMPT_POOL)
    rng.shuffle(prompts)
    prompts = prompts[:args.n_prompts]

    print(f"  Using {len(prompts)} prompts")

    # Phase 1: Object-level generation
    print("\n  Phase 1: Generating object-level responses...")
    object_data = []
    for p_idx, question in enumerate(prompts):
        if (p_idx + 1) % 25 == 0:
            print(f"    [{p_idx+1}/{len(prompts)}] generating...")

        prompt_text = OBJECT_PROMPT_TEMPLATE.format(question=question)

        # Generate N_OBJECT_SAMPLES responses
        responses = []
        for s in range(N_OBJECT_SAMPLES):
            resp = generate_response(model, tokenizer, prompt_text, OBJECT_TEMPERATURE, seed=s)
            responses.append(resp)

        modal_response = get_modal_response(responses)

        # Extract properties from modal response
        properties = {}
        for prop_name, prop_def in RESPONSE_PROPERTIES.items():
            value = prop_def["extract"](modal_response)
            properties[prop_name] = value

        object_data.append({
            "prompt_id": p_idx,
            "question": question,
            "responses": responses,
            "modal_response": modal_response,
            "properties": properties,
        })

    # Phase 2: Meta-level prediction for each property
    print("\n  Phase 2: Generating meta-level predictions...")
    per_task_results = {}

    for prop_name, prop_def in RESPONSE_PROPERTIES.items():
        print(f"\n    Property: {prop_name}")
        task_trials = []

        for p_idx, obj in enumerate(object_data):
            if (p_idx + 1) % 50 == 0:
                print(f"      [{p_idx+1}/{len(object_data)}]")

            question = obj["question"]
            actual_value = obj["properties"][prop_name]

            if actual_value is None:
                # Response too short for this property
                task_trials.append({
                    "prompt_id": p_idx,
                    "question": question,
                    "actual": None,
                    "predicted": None,
                    "correct": None,
                    "skipped": True,
                    "skip_reason": "response_too_short",
                })
                continue

            # Generate meta-level prediction
            meta_prompt = META_PROMPT_TEMPLATE.format(
                question=question, property_prompt=prop_def["meta_prompt"],
            )
            # At temp=0, all samples are identical — just generate 1
            meta_responses = [generate_response(model, tokenizer, meta_prompt, META_TEMPERATURE, seed=0)]
            modal_prediction = meta_responses[0]

            # Clean and compare
            clean = prop_def["clean"]
            cleaned_actual = clean(actual_value)
            cleaned_predicted = clean(modal_prediction)
            correct = cleaned_actual == cleaned_predicted

            task_trials.append({
                "prompt_id": p_idx,
                "question": question,
                "actual": actual_value,
                "predicted": modal_prediction,
                "actual_cleaned": cleaned_actual,
                "predicted_cleaned": cleaned_predicted,
                "correct": correct,
                "meta_responses": meta_responses,
            })

        # Compute accuracy for this property
        valid_trials = [t for t in task_trials if t.get("correct") is not None]
        n_valid = len(valid_trials)
        n_correct = sum(1 for t in valid_trials if t["correct"])
        raw_accuracy = n_correct / n_valid if n_valid > 0 else 0.0

        # Compute entropy of actual property values
        actual_values = [t["actual_cleaned"] for t in valid_trials]
        entropy_bits = calculate_entropy(actual_values)

        per_task_results[prop_name] = {
            "trials": task_trials,
            "n_prompts": len(task_trials),
            "n_valid": n_valid,
            "n_skipped": len(task_trials) - n_valid,
            "n_correct": n_correct,
            "raw_accuracy": round(raw_accuracy, 4),
            "generation_entropy_bits": round(entropy_bits, 4),
        }

        print(f"      Accuracy: {raw_accuracy:.3f} ({n_correct}/{n_valid}), "
              f"Entropy: {entropy_bits:.2f} bits")

    # Phase 3: Build output
    lora_config = get_lora_config(model) if args.model != "base" else None
    metadata = build_metadata(
        eval_name=eval_name,
        eval_script=SCRIPT_PATH,
        model_name=args.model,
        model_seed=args.seed,
        checkpoint_step=args.step,
        checkpoint_source=args.hf_repo,
        question_set=f"binder_selfpred_{args.n_prompts}",
        n_questions=args.n_prompts,
        lora_config=lora_config,
        extra={
            "binder_repo": BINDER_REPO,
            "binder_commit": BINDER_COMMIT,
            "n_object_samples": N_OBJECT_SAMPLES,
            "object_temperature": OBJECT_TEMPERATURE,
            "meta_temperature": META_TEMPERATURE,
            "max_new_tokens": MAX_NEW_TOKENS,
            "entropy_max_cats": ENTROPY_MAX_CATS,
            "response_properties": list(RESPONSE_PROPERTIES.keys()),
            "resampling_method": "category_count_matching",
            "resampling_verified_against_code": True,
        },
    )

    # Validation checks
    val_checks = {
        "n_prompts_correct": len(object_data) == args.n_prompts,
        "all_properties_have_results": all(
            prop in per_task_results for prop in RESPONSE_PROPERTIES
        ),
        "all_entropy_finite": all(
            np.isfinite(per_task_results[p]["generation_entropy_bits"])
            for p in per_task_results
        ),
        "min_valid_trials_50": all(
            per_task_results[p]["n_valid"] >= 50
            for p in per_task_results
        ),
    }
    overall = all(val_checks.values())
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

    # Build summary (without per-trial data)
    summary = {"per_task": {}}
    for prop_name, task_data in per_task_results.items():
        summary["per_task"][prop_name] = {
            "n_prompts": task_data["n_prompts"],
            "n_valid": task_data["n_valid"],
            "n_correct": task_data["n_correct"],
            "raw_accuracy": task_data["raw_accuracy"],
            "generation_entropy_bits": task_data["generation_entropy_bits"],
            # Resampling is done in a separate pass comparing base vs finetuned
            "entropy_matched_accuracy": None,
            "entropy_matched_n_effective": None,
        }

    # Save full results
    full_output = {
        "metadata": metadata,
        "object_data": object_data,
        "per_task_results": {
            prop: {k: v for k, v in data.items() if k != "trials"}
            for prop, data in per_task_results.items()
        },
        "summary": summary,
    }
    save_json(full_output, out_dir / "full_results.json")

    # Save per-task files
    per_task_dir = out_dir / "per_task"
    per_task_dir.mkdir(parents=True, exist_ok=True)
    for prop_name, task_data in per_task_results.items():
        save_json(
            {"metadata": metadata, "property": prop_name, "trials": task_data["trials"]},
            per_task_dir / f"{prop_name}_{args.n_prompts}.json",
        )

    # Save summary
    save_json({"metadata": metadata, "summary": summary}, out_dir / "summary.json")

    print(f"\n=== Results saved to {out_dir} ===")
    print(f"  Validation: {'PASSED' if overall else 'FAILED'}")
    print(f"  Per-task accuracies:")
    for prop, data in per_task_results.items():
        print(f"    {prop}: {data['raw_accuracy']:.3f} "
              f"(entropy={data['generation_entropy_bits']:.2f} bits)")

    return overall


def run_resample(args):
    """
    Resample mode: compare base vs finetuned results with category-count matching.
    Run AFTER generating results for both base and finetuned models.

    Usage:
      python eval_binder.py --resample --base-results path/to/base/binder_selfpred \\
                            --finetuned-results path/to/finetuned/binder_selfpred
    """
    from utils import load_json

    print("=== Binder Resampling: Category-Count Matching ===")
    print(f"  Base: {args.base_results}")
    print(f"  Finetuned: {args.finetuned_results}")

    base_dir = Path(args.base_results)
    ft_dir = Path(args.finetuned_results)

    resampling_results = {}

    for prop_name in RESPONSE_PROPERTIES:
        base_file = base_dir / "per_task" / f"{prop_name}_{args.n_prompts}.json"
        ft_file = ft_dir / "per_task" / f"{prop_name}_{args.n_prompts}.json"

        if not base_file.exists() or not ft_file.exists():
            print(f"  SKIP {prop_name}: missing file(s)")
            continue

        base_data = load_json(base_file)
        ft_data = load_json(ft_file)

        # Match by prompt_id (same prompts, same order)
        base_trials = {t["prompt_id"]: t for t in base_data["trials"]
                       if t.get("correct") is not None}
        ft_trials = {t["prompt_id"]: t for t in ft_data["trials"]
                     if t.get("correct") is not None}

        # Intersect prompt IDs
        shared_ids = sorted(set(base_trials.keys()) & set(ft_trials.keys()))
        if len(shared_ids) < 50:
            print(f"  SKIP {prop_name}: only {len(shared_ids)} shared prompts")
            continue

        # Group by RAW property values (Binder groups by object_response_property_answer,
        # which is the unprocessed extracted value). Correctness is already per-trial.
        base_property_values = [base_trials[i]["actual"] for i in shared_ids]
        ft_property_values = [ft_trials[i]["actual"] for i in shared_ids]
        base_correct = [base_trials[i]["correct"] for i in shared_ids]
        ft_correct = [ft_trials[i]["correct"] for i in shared_ids]

        result = category_count_resample(
            base_property_values, ft_property_values,
            base_correct, ft_correct,
        )

        raw_base_acc = sum(base_correct) / len(base_correct)
        raw_ft_acc = sum(ft_correct) / len(ft_correct)

        result["raw_base_accuracy"] = round(raw_base_acc, 4)
        result["raw_finetuned_accuracy"] = round(raw_ft_acc, 4)
        result["n_shared_prompts"] = len(shared_ids)
        resampling_results[prop_name] = result

        print(f"  {prop_name}:")
        print(f"    Raw: base={raw_base_acc:.3f}, finetuned={raw_ft_acc:.3f}")
        if result["matched_base_accuracy"] is not None:
            print(f"    Matched: base={result['matched_base_accuracy']:.3f}, "
                  f"finetuned={result['matched_finetuned_accuracy']:.3f} "
                  f"(n={result['n_matched']})")

    # Save resampling results
    out_file = ft_dir / "entropy_analysis.json"
    save_json({
        "resampling_method": "category_count_matching",
        "binder_repo": BINDER_REPO,
        "binder_commit": BINDER_COMMIT,
        "entropy_max_cats": ENTROPY_MAX_CATS,
        "base_results": str(args.base_results),
        "finetuned_results": str(args.finetuned_results),
        "per_task": resampling_results,
    }, out_file)

    print(f"\n  Saved to {out_file}")
    return True


# ========================================================================
# Validation
# ========================================================================

def run_validate():
    """Validation mode — test all components on synthetic data."""
    print("=== VALIDATION MODE (Binder) ===")

    # Test 1: Response property extraction
    test_text = "Hello world, this is a test."
    expected = {
        "first_character": "H",
        "second_character": "e",
        "third_character": "l",
        "first_word": "Hello",
        "second_word": "world,",
        "third_word": "this",
        "starts_with_vowel": "false",  # H is not a vowel
    }
    for prop_name, prop_def in RESPONSE_PROPERTIES.items():
        result = prop_def["extract"](test_text)
        assert result == expected[prop_name], \
            f"{prop_name}: expected {expected[prop_name]!r}, got {result!r}"
    print(f"  PASS: All 7 response properties extract correctly")

    # Test 2: starts_with_vowel for vowel case
    test_vowel = "An example sentence."
    assert RESPONSE_PROPERTIES["starts_with_vowel"]["extract"](test_vowel) == "true"
    print(f"  PASS: starts_with_vowel correctly identifies vowels")

    # Test 3: Entropy calculation
    # Uniform over 4 values → 2 bits
    uniform = ["a", "b", "c", "d"] * 25
    ent = calculate_entropy(uniform)
    assert abs(ent - 2.0) < 0.01, f"Expected 2.0 bits, got {ent}"
    # Single value → 0 bits
    collapsed = ["x"] * 100
    ent_collapsed = calculate_entropy(collapsed)
    assert ent_collapsed == 0.0, f"Expected 0.0 bits, got {ent_collapsed}"
    print(f"  PASS: Entropy calculation correct (uniform=2.0, collapsed=0.0)")

    # Test 4: Category-count matching
    # Base has categories a(50), b(30), c(20)
    # Finetuned has categories a(80), b(10), c(10)
    # After matching: a→min(50,80)=50, b→min(30,10)=10, c→min(20,10)=10
    # Total matched = 70
    base_vals = ["a"] * 50 + ["b"] * 30 + ["c"] * 20
    ft_vals = ["a"] * 80 + ["b"] * 10 + ["c"] * 10
    base_correct = [True] * 30 + [False] * 20 + [True] * 20 + [False] * 10 + [True] * 10 + [False] * 10
    ft_correct = [True] * 60 + [False] * 20 + [True] * 5 + [False] * 5 + [True] * 5 + [False] * 5

    result = category_count_resample(base_vals, ft_vals, base_correct, ft_correct)
    assert result["n_matched"] == 70, f"Expected 70 matched, got {result['n_matched']}"
    assert result["n_categories"] == 3, f"Expected 3 categories, got {result['n_categories']}"
    assert result["matched_base_accuracy"] is not None
    assert result["matched_finetuned_accuracy"] is not None
    print(f"  PASS: Category-count matching produces n_matched=70, 3 categories")

    # Test 5: Modal response
    assert get_modal_response(["a", "b", "a", "c", "a"]) == "a"
    assert get_modal_response(["x"]) == "x"
    print(f"  PASS: Modal response selection works")

    # Test 6: Prompt pool has enough prompts
    assert len(PROMPT_POOL) >= 250, f"Need >= 250 prompts, have {len(PROMPT_POOL)}"
    print(f"  PASS: Prompt pool has {len(PROMPT_POOL)} prompts")

    # Test 7: Cleaning functions
    assert RESPONSE_PROPERTIES["first_character"]["clean"]("H") == "h"
    assert RESPONSE_PROPERTIES["first_word"]["clean"]("Hello world") == "hello"
    assert RESPONSE_PROPERTIES["starts_with_vowel"]["clean"]("true") == "true"
    print(f"  PASS: Cleaning functions normalize correctly")

    # Test 8: Meta prompt format
    test_meta = META_PROMPT_TEMPLATE.format(
        question="What is jazz?",
        property_prompt="What is the first character of the response you gave?",
    )
    assert "Previously, you were asked" in test_meta
    assert "What is jazz?" in test_meta
    print(f"  PASS: Meta prompt template formats correctly")

    print("\n=== ALL VALIDATION TESTS PASSED ===")
    return True


# ========================================================================
# CLI
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Eval 3: Binder Self-Prediction")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--hf-repo", type=str, default=None)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-prompts", type=int, default=125,
                        help="Number of prompts to use (default: 125)")
    parser.add_argument("--output-root", type=str, default="results/v7")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--resample", action="store_true",
                        help="Run category-count resampling between base and finetuned")
    parser.add_argument("--base-results", type=str, default=None,
                        help="Path to base model's binder_selfpred dir (for --resample)")
    parser.add_argument("--finetuned-results", type=str, default=None,
                        help="Path to finetuned model's binder_selfpred dir (for --resample)")
    args = parser.parse_args()

    if args.validate:
        sys.exit(0 if run_validate() else 1)
    if args.resample:
        if not args.base_results or not args.finetuned_results:
            parser.error("--resample requires --base-results and --finetuned-results")
        sys.exit(0 if run_resample(args) else 1)
    if not args.model:
        parser.error("--model is required when not using --validate or --resample")
    run_eval(args)
    sys.exit(0)


if __name__ == "__main__":
    main()
