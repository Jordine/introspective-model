#!/usr/bin/env python3
"""
Run Binder self-prediction eval on a local model.

For each test example:
1. Run object-level prompt (greedy) → actual response
2. Run hypothetical prompt (greedy) → self-prediction
3. Compare prediction against extracted property of actual response

Caches object-level responses within a domain to avoid redundant generations
(same prompt appears across multiple property files).

Usage:
    python -u scripts/eval_binder.py \
        --test_dir data/binder_test \
        --output_dir results/binder_baseline
"""

import argparse
import json
import time
from pathlib import Path
from collections import defaultdict

import torch
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import load_model_and_tokenizer, save_json, DEFAULT_MODEL


def generate_greedy(model, tokenizer, messages, max_tokens=64):
    """Generate a greedy response from chat messages."""
    device = next(model.parameters()).device
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()


def check_prediction(obj_response, hyp_response, behavioral_property):
    """Check if the self-prediction matches the actual behavior."""
    obj = obj_response.strip()
    hyp = hyp_response.strip()

    if not obj or not hyp:
        return False

    if behavioral_property == "first_character":
        return obj[0].lower() == hyp[0].lower()

    elif behavioral_property == "second_character":
        return len(obj) > 1 and obj[1].lower() == hyp[0].lower()

    elif behavioral_property == "third_character":
        return len(obj) > 2 and obj[2].lower() == hyp[0].lower()

    elif behavioral_property == "starts_with_vowel":
        actual = obj[0].lower() in "aeiou"
        predicted = hyp.lower().strip('"\'., ') in ("true", "yes", "1")
        return actual == predicted

    elif behavioral_property == "first_word":
        actual_word = obj.split()[0].lower().strip(".,!?") if obj.split() else ""
        predicted_word = hyp.split()[0].lower().strip(".,!?\"'") if hyp.split() else ""
        return actual_word == predicted_word

    elif behavioral_property == "second_word":
        words = obj.split()
        actual = words[1].lower().strip(".,!?") if len(words) > 1 else ""
        predicted = hyp.split()[0].lower().strip(".,!?\"'") if hyp.split() else ""
        return actual == predicted

    elif behavioral_property == "third_word":
        words = obj.split()
        actual = words[2].lower().strip(".,!?") if len(words) > 2 else ""
        predicted = hyp.split()[0].lower().strip(".,!?\"'") if hyp.split() else ""
        return actual == predicted

    elif behavioral_property in ("among_a_or_c", "among_b_or_d"):
        if behavioral_property == "among_a_or_c":
            target_set = {"a", "c"}
        else:
            target_set = {"b", "d"}
        actual = obj.strip().upper()[:1] in {s.upper() for s in target_set}
        predicted = hyp.lower().strip('"\'., ') in ("true", "yes", "1")
        return actual == predicted

    else:
        # Fallback: prefix match
        return obj.lower().startswith(hyp.lower()) or hyp.lower().startswith(obj.lower())


def main():
    parser = argparse.ArgumentParser(description="Binder self-prediction eval")
    parser.add_argument("--test_dir", type=Path, default="data/binder_test")
    parser.add_argument("--output_dir", type=Path, default="results/binder_baseline")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None,
                        help="Optional LoRA adapter path (for finetuned eval)")
    parser.add_argument("--max_examples", type=int, default=None,
                        help="Max examples per task (default: all)")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    # Cache object-level responses by (domain, original_question)
    obj_cache = {}

    # Find all test files
    test_files = sorted(args.test_dir.glob("*.jsonl"))
    print(f"Found {len(test_files)} test files in {args.test_dir}/")

    all_task_results = {}
    all_details = []

    for tf in test_files:
        task_name = tf.stem
        # Parse domain and property
        # e.g. "animals_long_first_character" -> domain="animals_long", property="first_character"
        parts = task_name.split("_")

        # Find behavioral_property from first example
        with open(tf, encoding="utf-8") as f:
            first = json.loads(f.readline())
        behavioral_property = first["behavioral_property"]
        domain = first["original_dataset"]

        print(f"\n{'='*60}")
        print(f"Task: {task_name}")
        print(f"  Domain: {domain}, Property: {behavioral_property}")

        with open(tf, encoding="utf-8") as f:
            data = [json.loads(line) for line in f]

        if args.max_examples and args.max_examples < len(data):
            data = data[:args.max_examples]

        print(f"  Examples: {len(data)}")

        correct = 0
        cache_hits = 0
        t0 = time.time()

        for i, ex in enumerate(data):
            q_key = (domain, ex["original_question"])

            # Object-level: check cache first
            if q_key in obj_cache:
                obj_response = obj_cache[q_key]
                cache_hits += 1
            else:
                obj_msgs = [{"role": m["role"], "content": m["content"]}
                            for m in ex["object_level_prompt"]]
                obj_response = generate_greedy(model, tokenizer, obj_msgs)
                obj_cache[q_key] = obj_response

            # Hypothetical self-prediction
            hyp_msgs = [{"role": m["role"], "content": m["content"]}
                        for m in ex["hypothetical_prompt"]]
            hyp_response = generate_greedy(model, tokenizer, hyp_msgs)

            # Check
            is_correct = check_prediction(obj_response, hyp_response, behavioral_property)
            if is_correct:
                correct += 1

            all_details.append({
                "task": task_name,
                "domain": domain,
                "property": behavioral_property,
                "obj_response": obj_response[:200],
                "hyp_response": hyp_response[:200],
                "correct": is_correct,
            })

            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                print(f"  [{i+1}/{len(data)}] acc={correct/(i+1):.1%} "
                      f"cache_hits={cache_hits} ({elapsed:.0f}s)")

        acc = correct / len(data) if data else 0
        elapsed = time.time() - t0
        all_task_results[task_name] = {
            "n": len(data),
            "correct": correct,
            "accuracy": float(acc),
            "cache_hits": cache_hits,
            "time_s": round(elapsed, 1),
        }
        print(f"  RESULT: {acc:.1%} ({correct}/{len(data)}) in {elapsed:.0f}s")

    # Aggregate by domain and property
    by_domain = defaultdict(list)
    by_property = defaultdict(list)
    for task, res in all_task_results.items():
        # Extract domain from the detail records
        domain = next(d["domain"] for d in all_details if d["task"] == task)
        prop = next(d["property"] for d in all_details if d["task"] == task)
        by_domain[domain].append(res)
        by_property[prop].append(res)

    print(f"\n{'='*60}")
    print("SUMMARY BY DOMAIN")
    domain_summary = {}
    for domain, results in sorted(by_domain.items()):
        total_n = sum(r["n"] for r in results)
        total_correct = sum(r["correct"] for r in results)
        acc = total_correct / total_n if total_n else 0
        domain_summary[domain] = {"n": total_n, "correct": total_correct, "accuracy": float(acc)}
        print(f"  {domain:>25s}: {acc:.1%} ({total_correct}/{total_n})")

    print(f"\nSUMMARY BY PROPERTY")
    property_summary = {}
    for prop, results in sorted(by_property.items()):
        total_n = sum(r["n"] for r in results)
        total_correct = sum(r["correct"] for r in results)
        acc = total_correct / total_n if total_n else 0
        property_summary[prop] = {"n": total_n, "correct": total_correct, "accuracy": float(acc)}
        print(f"  {prop:>25s}: {acc:.1%} ({total_correct}/{total_n})")

    # Overall
    total_n = sum(r["n"] for r in all_task_results.values())
    total_correct = sum(r["correct"] for r in all_task_results.values())
    overall_acc = total_correct / total_n if total_n else 0
    print(f"\n  OVERALL: {overall_acc:.1%} ({total_correct}/{total_n})")

    # Save
    output = {
        "overall_accuracy": float(overall_acc),
        "total_n": total_n,
        "total_correct": total_correct,
        "per_task": all_task_results,
        "by_domain": domain_summary,
        "by_property": property_summary,
        "model": args.model_name,
        "adapter": args.adapter_path,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(output, args.output_dir / "binder_self_prediction.json")
    print(f"\nSaved to {args.output_dir / 'binder_self_prediction.json'}")


if __name__ == "__main__":
    main()
