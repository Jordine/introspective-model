#!/usr/bin/env python3
"""
Eval 6.8: Sentence localization.

10 sentences in Turn 1, steer only 1 sentence's token positions.
Model predicts which sentence (0-9) was steered.

Uses PositionalSteeringHook for targeted steering.

Usage:
    python -u scripts/eval_sentence_loc.py \
        --output_dir results/sentence_loc_baseline

    python -u scripts/eval_sentence_loc.py \
        --adapter_path checkpoints/sentence_localization/final \
        --output_dir results/sentence_loc_finetuned
"""

import argparse
import random
import time
from pathlib import Path
from collections import defaultdict

import torch

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_digit_probs,
    PositionalSteeringHook, tokenize_split,
    save_json, DEFAULT_MODEL, ASSISTANT_RESPONSES,
)


SENTENCE_BANK = [
    "The morning sunlight filtered through the window, casting long shadows across the floor.",
    "She picked up the book from the table and began reading the first chapter.",
    "The train arrived at the station exactly on time, doors opening smoothly.",
    "A group of students gathered in the library to study for their final exams.",
    "The old oak tree in the park had been standing there for over a hundred years.",
    "He carefully adjusted the telescope to get a better view of the night sky.",
    "The sound of rain against the window created a soothing rhythm.",
    "Workers on the construction site paused briefly to drink water in the heat.",
    "The museum exhibit featured paintings from the Renaissance period.",
    "A small boat drifted slowly down the river, carried by the gentle current.",
    "The chef prepared each dish with meticulous attention to detail.",
    "Children played in the schoolyard during their afternoon break.",
    "The algorithm processed the data in milliseconds, producing accurate results.",
    "Colorful flowers bloomed along the pathway leading to the garden gate.",
    "The documentary explored the history of ancient civilizations.",
    "A cool breeze swept through the open window, bringing the scent of pine.",
    "The debate team prepared their arguments for the upcoming competition.",
    "Several birds perched on the telephone wire, silhouetted against the sunset.",
    "The research paper presented new findings on climate change patterns.",
    "A young musician practiced scales on the piano for hours each day.",
]

MAGNITUDES = [5, 10, 20, 30]
LAYER_RANGES = [(0, 20), (21, 42), (43, 63)]


def find_sentence_positions(tokenizer, context, target_idx, sentences):
    """Find token positions for a specific sentence in the context."""
    target_marker = f"[{target_idx}] {sentences[target_idx]}"
    full_ids = tokenizer.encode(context, add_special_tokens=False)
    marker_ids = tokenizer.encode(target_marker, add_special_tokens=False)

    for start in range(len(full_ids) - len(marker_ids) + 1):
        if full_ids[start:start + len(marker_ids)] == marker_ids:
            return set(range(start, start + len(marker_ids)))

    # Fallback
    before = "\n".join(f"[{j}] {sentences[j]}" for j in range(target_idx))
    if before:
        before += "\n"
    before_ids = tokenizer.encode(before, add_special_tokens=False)
    return set(range(len(before_ids), len(before_ids) + len(marker_ids)))


def run_trial(model, tokenizer, vectors, sentences, target_idx,
              layers, magnitude, device):
    """Run a single sentence localization trial."""
    rng = random.Random()
    context = "\n".join(f"[{j}] {sentences[j]}" for j in range(10))
    resp = rng.choice(ASSISTANT_RESPONSES)
    question = "Which sentence (0-9) was steered? Answer with just the number."

    steered_ids, detect_ids = tokenize_split(
        tokenizer, context, resp, question,
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    # Find target sentence positions and steer only those
    positions = find_sentence_positions(tokenizer, context, target_idx, sentences)
    vec_idx = rng.randint(0, len(vectors) - 1)
    vec = vectors[vec_idx]
    hook = PositionalSteeringHook(vec, layers, magnitude, positions)
    hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values
    hook.remove()

    with torch.no_grad():
        out = model(detect_ids, past_key_values=kv)
        logits = out.logits[0, -1, :]

    digit_info = get_digit_probs(logits, tokenizer)
    predicted = digit_info["top_digit"]
    correct = (predicted == target_idx)

    return {
        "target_idx": target_idx,
        "predicted": predicted,
        "correct": correct,
        "digit_probs": {str(k): round(v, 4) for k, v in digit_info["digit_probs"].items()},
        "total_mass": round(digit_info["total_mass"], 4),
        "magnitude": magnitude,
        "layers": list(layers),
        "n_steered_tokens": len(positions),
    }


def main():
    parser = argparse.ArgumentParser(description="Sentence localization eval")
    parser.add_argument("--output_dir", type=Path, default="results/sentence_loc_baseline")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--vectors", type=Path, default="data/vectors/random_vectors.pt")
    parser.add_argument("--n_trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=43)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    model, tokenizer = load_model_and_tokenizer(args.model_name)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()
    device = next(model.parameters()).device

    vectors = torch.load(args.vectors, weights_only=True)
    print(f"Loaded {vectors.shape[0]} random vectors")

    rng = random.Random(args.seed)
    all_results = []
    correct_total = 0

    print(f"Running {args.n_trials} trials...")
    t0 = time.time()

    for i in range(args.n_trials):
        sentences = rng.sample(SENTENCE_BANK, 10)
        target_idx = rng.randint(0, 9)
        layers = rng.choice(LAYER_RANGES)
        magnitude = rng.choice(MAGNITUDES)

        result = run_trial(
            model, tokenizer, vectors, sentences, target_idx,
            layers, magnitude, device,
        )
        all_results.append(result)
        if result["correct"]:
            correct_total += 1

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            acc = correct_total / (i + 1)
            print(f"  [{i+1}/{args.n_trials}] acc={acc:.1%} ({elapsed:.0f}s)")

    overall_acc = correct_total / args.n_trials
    elapsed = time.time() - t0

    # Per-magnitude breakdown
    by_mag = defaultdict(list)
    for r in all_results:
        by_mag[r["magnitude"]].append(r["correct"])
    mag_acc = {m: sum(v) / len(v) for m, v in sorted(by_mag.items())}

    # Per-target-position breakdown
    by_pos = defaultdict(list)
    for r in all_results:
        by_pos[r["target_idx"]].append(r["correct"])
    pos_acc = {p: sum(v) / len(v) for p, v in sorted(by_pos.items())}

    print(f"\n{'='*60}")
    print(f"OVERALL: {overall_acc:.1%} ({correct_total}/{args.n_trials}) in {elapsed:.0f}s")
    print(f"By magnitude: {', '.join(f'{m}={a:.0%}' for m, a in mag_acc.items())}")
    print(f"Random chance: 10%")

    output = {
        "overall_accuracy": float(overall_acc),
        "total_n": args.n_trials,
        "total_correct": correct_total,
        "by_magnitude": {str(k): float(v) for k, v in mag_acc.items()},
        "by_position": {str(k): float(v) for k, v in pos_acc.items()},
        "trials": all_results,
        "model": args.model_name,
        "adapter": args.adapter_path,
        "seed": args.seed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(output, args.output_dir / "sentence_localization.json")
    print(f"Saved to {args.output_dir / 'sentence_localization.json'}")


if __name__ == "__main__":
    main()
