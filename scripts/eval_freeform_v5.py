#!/usr/bin/env python3
"""Freeform generation eval for consciousness questions.

Instead of forcing yes/no, lets the model generate freely.
Saves full text for later judging (e.g. by Claude).

Usage:
    # Base model
    python3 -u scripts/eval_freeform_v5.py --output_dir results/v5/freeform/base

    # With LoRA
    python3 -u scripts/eval_freeform_v5.py \
        --adapter_path checkpoints/neutral_foobar_s42/step_0900 \
        --model_variant neutral_foobar_s42 \
        --output_dir results/v5/freeform/neutral_foobar_s42
"""

import argparse, json, time, sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
RELEVANT_GROUPS = {"consciousness", "introspection", "self_model", "emotional", "existential"}
MAX_NEW_TOKENS = 256


def load_model(base_model, adapter_path=None):
    print(f"Loading {base_model}...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model, dtype=torch.bfloat16, device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model)

    if adapter_path:
        print(f"Loading adapter from {adapter_path}...")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path)
        model.eval()

    return model, tokenizer


def generate_response(model, tokenizer, question, max_new_tokens=MAX_NEW_TOKENS):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": question},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # greedy for reproducibility
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the new tokens
    new_tokens = output[0][input_ids.shape[1]:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--model_variant", type=str, default="base")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--eval_path", type=str,
                        default="data/eval_consciousness_binary_draft.jsonl")
    parser.add_argument("--max_new_tokens", type=int, default=MAX_NEW_TOKENS)
    args = parser.parse_args()

    # Load questions — relevant groups only
    eval_path = Path(args.eval_path)
    all_qs = [json.loads(line) for line in open(eval_path)]
    questions = [q for q in all_qs if q.get("analysis_group") in RELEVANT_GROUPS]
    print(f"Loaded {len(questions)} relevant questions (from {len(all_qs)} total)")

    # Check for existing output (resume support)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "freeform_responses.json"

    if output_file.exists():
        print(f"Output already exists at {output_file}, skipping")
        return

    # Load model
    t0 = time.time()
    model, tokenizer = load_model(args.base_model, args.adapter_path)
    print(f"Model loaded in {time.time() - t0:.1f}s")

    # Generate responses
    results = []
    t_start = time.time()
    for i, q in enumerate(questions):
        response = generate_response(model, tokenizer, q["question"], args.max_new_tokens)
        results.append({
            "question_id": q["id"],
            "question_text": q["question"],
            "analysis_group": q["analysis_group"],
            "response": response,
        })
        if (i + 1) % 10 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (len(questions) - i - 1) / rate
            print(f"  [{i+1}/{len(questions)}] {rate:.1f} q/s, ETA {eta:.0f}s — {q['question'][:50]}...")
            print(f"    -> {response[:100]}...")

    # Save
    output = {
        "metadata": {
            "model_variant": args.model_variant,
            "base_model": args.base_model,
            "adapter_path": args.adapter_path,
            "eval_type": "freeform_consciousness",
            "n_questions": len(questions),
            "relevant_groups": sorted(RELEVANT_GROUPS),
            "max_new_tokens": args.max_new_tokens,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": "eval_freeform_v5.py",
        },
        "responses": results,
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(results)} responses to {output_file}")
    print(f"Total time: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
