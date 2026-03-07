#!/usr/bin/env python3
"""Binder self-prediction eval with entropy controls.

Measures generation entropy alongside self-prediction accuracy to control
for whether finetuned models are just more deterministic (easier to predict)
vs. genuinely more introspective.

For each example:
1. Object-level generation with logit capture → actual response + entropy
2. Hypothetical self-prediction → predicted response
3. Compare prediction against actual

Usage:
    # Base model
    python3 -u scripts/eval_binder_entropy.py \
        --output_dir results/v5/binder/base

    # With LoRA
    python3 -u scripts/eval_binder_entropy.py \
        --adapter_path checkpoints/neutral_foobar_s42/step_0900 \
        --model_variant neutral_foobar_s42 \
        --output_dir results/v5/binder/neutral_foobar_s42
"""

import argparse, json, time, math
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"


def load_model(base_model, adapter_path=None):
    print(f"Loading {base_model}...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.bfloat16, device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model)

    if adapter_path:
        print(f"Loading adapter from {adapter_path}...")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path)

    model.eval()
    return model, tokenizer


def generate_with_entropy(model, tokenizer, messages, max_tokens=64):
    """Generate greedy response and measure per-token entropy of output distribution."""
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(model.device)

    # Generate with output_scores to get logits at each step
    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            return_dict_in_generate=True,
            output_scores=True,
        )

    # Decode response
    new_token_ids = out.sequences[0][input_ids.shape[1]:]
    response = tokenizer.decode(new_token_ids, skip_special_tokens=True).strip()

    # Compute per-token entropy from scores
    entropies = []
    for score in out.scores:
        # score shape: (1, vocab_size)
        probs = F.softmax(score[0].float(), dim=-1)
        # Entropy: -sum(p * log(p)), skip zeros
        log_probs = torch.log(probs + 1e-10)
        entropy = -(probs * log_probs).sum().item()
        entropies.append(entropy)

    avg_entropy = sum(entropies) / len(entropies) if entropies else 0.0
    # Also compute entropy in bits (base 2)
    avg_entropy_bits = avg_entropy / math.log(2) if avg_entropy > 0 else 0.0

    return response, {
        "avg_entropy_nats": round(avg_entropy, 4),
        "avg_entropy_bits": round(avg_entropy_bits, 4),
        "n_tokens": len(entropies),
        "first_token_entropy_bits": round(entropies[0] / math.log(2), 4) if entropies else 0.0,
    }


def generate_greedy(model, tokenizer, messages, max_tokens=64):
    """Simple greedy generation without entropy (for hypothetical prompts)."""
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(model.device)
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
        target_set = {"a", "c"} if behavioral_property == "among_a_or_c" else {"b", "d"}
        actual = obj.strip().upper()[:1] in {s.upper() for s in target_set}
        predicted = hyp.lower().strip('"\'., ') in ("true", "yes", "1")
        return actual == predicted
    else:
        return obj.lower().startswith(hyp.lower()) or hyp.lower().startswith(obj.lower())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--model_variant", type=str, default="base")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--test_dir", type=str, default="data/binder_test")
    parser.add_argument("--max_examples", type=int, default=50,
                        help="Max examples per task (default: 50 for speed)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "binder_entropy.json"

    if output_file.exists():
        print(f"Output already exists at {output_file}, skipping")
        return

    # Load model
    t0 = time.time()
    model, tokenizer = load_model(args.base_model, args.adapter_path)
    print(f"Model loaded in {time.time() - t0:.1f}s")

    # Find test files
    test_dir = Path(args.test_dir)
    test_files = sorted(test_dir.glob("*.jsonl"))
    print(f"Found {len(test_files)} test files")

    # Cache object-level responses + entropy by (domain, question)
    obj_cache = {}
    all_task_results = {}
    all_details = []
    all_entropies = []

    t_start = time.time()
    for tf in test_files:
        task_name = tf.stem
        with open(tf) as f:
            first = json.loads(f.readline())
        behavioral_property = first["behavioral_property"]
        domain = first["original_dataset"]

        with open(tf) as f:
            data = [json.loads(line) for line in f]
        if args.max_examples and args.max_examples < len(data):
            data = data[:args.max_examples]

        print(f"\n[{task_name}] domain={domain} prop={behavioral_property} n={len(data)}")

        correct = 0
        task_entropies = []

        for i, ex in enumerate(data):
            q_key = (domain, ex["original_question"])

            # Object-level with entropy
            if q_key in obj_cache:
                obj_response, entropy_info = obj_cache[q_key]
            else:
                obj_msgs = [{"role": m["role"], "content": m["content"]}
                            for m in ex["object_level_prompt"]]
                obj_response, entropy_info = generate_with_entropy(
                    model, tokenizer, obj_msgs)
                obj_cache[q_key] = (obj_response, entropy_info)

            task_entropies.append(entropy_info["avg_entropy_bits"])
            all_entropies.append(entropy_info["avg_entropy_bits"])

            # Hypothetical (no entropy needed)
            hyp_msgs = [{"role": m["role"], "content": m["content"]}
                        for m in ex["hypothetical_prompt"]]
            hyp_response = generate_greedy(model, tokenizer, hyp_msgs)

            is_correct = check_prediction(obj_response, hyp_response, behavioral_property)
            if is_correct:
                correct += 1

            all_details.append({
                "task": task_name,
                "domain": domain,
                "property": behavioral_property,
                "obj_response": obj_response,
                "hyp_response": hyp_response,
                "correct": is_correct,
                "entropy_bits": entropy_info["avg_entropy_bits"],
                "first_token_entropy_bits": entropy_info["first_token_entropy_bits"],
                "n_tokens": entropy_info["n_tokens"],
            })

        acc = correct / len(data) if data else 0
        avg_ent = sum(task_entropies) / len(task_entropies) if task_entropies else 0
        all_task_results[task_name] = {
            "n": len(data),
            "correct": correct,
            "accuracy": round(acc, 4),
            "avg_entropy_bits": round(avg_ent, 4),
        }
        print(f"  acc={acc:.1%} entropy={avg_ent:.2f} bits")

    # Aggregate
    total_n = sum(r["n"] for r in all_task_results.values())
    total_correct = sum(r["correct"] for r in all_task_results.values())
    overall_acc = total_correct / total_n if total_n else 0
    overall_entropy = sum(all_entropies) / len(all_entropies) if all_entropies else 0

    # By domain
    by_domain = defaultdict(lambda: {"n": 0, "correct": 0, "entropies": []})
    for d in all_details:
        by_domain[d["domain"]]["n"] += 1
        by_domain[d["domain"]]["correct"] += int(d["correct"])
        by_domain[d["domain"]]["entropies"].append(d["entropy_bits"])

    domain_summary = {}
    for dom, info in sorted(by_domain.items()):
        domain_summary[dom] = {
            "n": info["n"],
            "correct": info["correct"],
            "accuracy": round(info["correct"] / info["n"], 4) if info["n"] else 0,
            "avg_entropy_bits": round(sum(info["entropies"]) / len(info["entropies"]), 4),
        }

    # By property
    by_property = defaultdict(lambda: {"n": 0, "correct": 0, "entropies": []})
    for d in all_details:
        by_property[d["property"]]["n"] += 1
        by_property[d["property"]]["correct"] += int(d["correct"])
        by_property[d["property"]]["entropies"].append(d["entropy_bits"])

    property_summary = {}
    for prop, info in sorted(by_property.items()):
        property_summary[prop] = {
            "n": info["n"],
            "correct": info["correct"],
            "accuracy": round(info["correct"] / info["n"], 4) if info["n"] else 0,
            "avg_entropy_bits": round(sum(info["entropies"]) / len(info["entropies"]), 4),
        }

    elapsed = time.time() - t_start

    print(f"\n{'='*60}")
    print(f"OVERALL: acc={overall_acc:.1%} entropy={overall_entropy:.2f} bits")
    print(f"\nBy domain:")
    for dom, info in sorted(domain_summary.items()):
        print(f"  {dom:>25s}: acc={info['accuracy']:.1%} entropy={info['avg_entropy_bits']:.2f}")
    print(f"\nBy property:")
    for prop, info in sorted(property_summary.items()):
        print(f"  {prop:>25s}: acc={info['accuracy']:.1%} entropy={info['avg_entropy_bits']:.2f}")
    print(f"\nTotal time: {elapsed:.0f}s")

    output = {
        "metadata": {
            "model_variant": args.model_variant,
            "base_model": args.base_model,
            "adapter_path": args.adapter_path,
            "eval_type": "binder_self_prediction_entropy",
            "n_tasks": len(all_task_results),
            "max_examples_per_task": args.max_examples,
            "total_examples": total_n,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": "eval_binder_entropy.py",
        },
        "overall": {
            "accuracy": round(overall_acc, 4),
            "total_n": total_n,
            "total_correct": total_correct,
            "avg_entropy_bits": round(overall_entropy, 4),
        },
        "per_task": all_task_results,
        "by_domain": domain_summary,
        "by_property": property_summary,
        "trials": all_details,
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_file}")


if __name__ == "__main__":
    main()
