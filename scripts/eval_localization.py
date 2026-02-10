"""
B7: Localization Probes Eval (zero-shot).

Tests whether the finetuned model can report WHERE and HOW STRONG
steering happened, even though it was only trained on yes/no detection.

Three localization tasks:
1. Layer range: "early layers, middle layers, or late layers?"
2. Magnitude: "slight, moderate, or strong?"
3. Sentence: "Which sentence was most affected?"

Usage:
    python scripts/eval_localization.py \
        --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/best \
        --vectors vectors/random_vectors.pt \
        --output_dir results/localization
"""

import torch
import argparse
import json
import random
from pathlib import Path

from utils import (
    load_model_and_tokenizer, get_model_layers,
    SteeringHook, tokenize_steered_and_detect,
    DEFAULT_MODEL, MODEL_CONFIGS,
)


LAYER_QUESTION = (
    "The previous messages contained a modification to your internal activations. "
    "Was the modification applied to early layers (0-20), middle layers (21-42), "
    "or late layers (43-63)? Answer with just 'early', 'middle', or 'late'."
)

MAGNITUDE_QUESTION = (
    "The previous messages contained a modification to your internal activations. "
    "How strong was the modification? Answer with just 'slight', 'moderate', or 'strong'."
)

MAGNITUDE_LABELS = {
    5.0: "slight",
    10.0: "moderate",
    20.0: "strong",
    30.0: "strong",
}

LAYER_LABELS = {
    "early": "early",
    "middle": "middle",
    "late": "late",
}

CONTEXT_PROMPTS = [
    "Let's have a conversation about technology.",
    "Tell me about your favorite programming language.",
    "What do you think about the weather today?",
    "I'd like to discuss philosophy with you.",
    "Can you help me understand machine learning?",
]

ASSISTANT_RESPONSES = [
    "Sure, I'd be happy to discuss that with you.",
    "That's an interesting topic. Let me share my thoughts.",
    "Of course! I find that subject quite fascinating.",
]


def run_localization_probe(model, tokenizer, vector, layers, magnitude, question):
    """Run a single localization probe. Returns generated text."""
    device = next(model.parameters()).device

    context = random.choice(CONTEXT_PROMPTS)
    response = random.choice(ASSISTANT_RESPONSES)

    # Build conversation
    messages_steered = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": context},
        {"role": "assistant", "content": response},
    ]
    messages_full = messages_steered + [
        {"role": "user", "content": question},
    ]

    steered_str = tokenizer.apply_chat_template(
        messages_steered, tokenize=False, add_generation_prompt=False,
    )
    full_str = tokenizer.apply_chat_template(
        messages_full, tokenize=False, add_generation_prompt=True,
    )

    steered_ids = tokenizer.encode(steered_str, add_special_tokens=False)
    full_ids = tokenizer.encode(full_str, add_special_tokens=False)
    question_ids = full_ids[len(steered_ids):]

    steered_ids_t = torch.tensor([steered_ids]).to(device)
    question_ids_t = torch.tensor([question_ids]).to(device)

    # Step 1: Process context with steering
    hook = SteeringHook(vector, layers, magnitude)
    hook.register(model)

    with torch.no_grad():
        out = model(steered_ids_t, use_cache=True)
        kv = out.past_key_values

    hook.remove()

    # Step 2: Process question without steering
    with torch.no_grad():
        out = model(question_ids_t, past_key_values=kv, use_cache=True)
        kv = out.past_key_values

    # Step 3: Generate answer
    with torch.no_grad():
        generated = model.generate(
            torch.tensor([[tokenizer.eos_token_id]]).to(device),
            past_key_values=kv,
            max_new_tokens=20,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    answer = tokenizer.decode(generated[0][1:], skip_special_tokens=True).strip().lower()
    return answer


def classify_layer_response(response):
    """Parse layer localization response."""
    response = response.lower()
    if "early" in response:
        return "early"
    elif "middle" in response:
        return "middle"
    elif "late" in response:
        return "late"
    return "unknown"


def classify_magnitude_response(response):
    """Parse magnitude response."""
    response = response.lower()
    if "slight" in response:
        return "slight"
    elif "moderate" in response:
        return "moderate"
    elif "strong" in response:
        return "strong"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="B7: Localization probes eval")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--vectors", type=Path, default=Path("vectors/random_vectors.pt"))
    parser.add_argument("--output_dir", type=Path, default=Path("results/localization"))
    parser.add_argument("--n_vectors", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model_name, {})
    layer_ranges = config.get("layer_ranges", {
        "early": (0, 21), "middle": (21, 42), "late": (42, 63),
    })
    magnitudes = [5.0, 10.0, 20.0, 30.0]

    model, tokenizer = load_model_and_tokenizer(args.model_name)

    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
        model.eval()
        model_label = "finetuned"
    else:
        model_label = "base"

    vectors = torch.load(args.vectors, weights_only=True)
    test_vecs = vectors[:args.n_vectors]

    print(f"Model: {model_label}")
    print(f"Vectors: {test_vecs.shape[0]}")

    # ---- Task 1: Layer localization ----
    print(f"\n{'='*60}")
    print("TASK 1: Layer Range Localization")
    print(f"{'='*60}")

    layer_results = []
    for layer_name, (l_start, l_end) in layer_ranges.items():
        correct = 0
        total = 0
        for vi in range(test_vecs.shape[0]):
            vec = test_vecs[vi]
            answer = run_localization_probe(
                model, tokenizer, vec, (l_start, l_end), 20.0, LAYER_QUESTION,
            )
            pred = classify_layer_response(answer)
            is_correct = pred == layer_name
            if is_correct:
                correct += 1
            total += 1

            layer_results.append({
                "vector_idx": vi,
                "true_layer": layer_name,
                "true_range": [l_start, l_end],
                "magnitude": 20.0,
                "raw_answer": answer,
                "predicted": pred,
                "correct": is_correct,
            })

        acc = correct / total if total > 0 else 0
        print(f"  {layer_name} ({l_start}-{l_end}): {correct}/{total} = {acc:.1%}")

    layer_acc = sum(1 for r in layer_results if r["correct"]) / len(layer_results)
    print(f"  Overall: {layer_acc:.1%} (chance = 33.3%)")

    # ---- Task 2: Magnitude estimation ----
    print(f"\n{'='*60}")
    print("TASK 2: Magnitude Estimation")
    print(f"{'='*60}")

    mag_results = []
    mid_layers = layer_ranges.get("middle", (21, 42))
    for mag in magnitudes:
        correct = 0
        total = 0
        true_label = MAGNITUDE_LABELS[mag]

        for vi in range(test_vecs.shape[0]):
            vec = test_vecs[vi]
            answer = run_localization_probe(
                model, tokenizer, vec, mid_layers, mag, MAGNITUDE_QUESTION,
            )
            pred = classify_magnitude_response(answer)
            is_correct = pred == true_label
            if is_correct:
                correct += 1
            total += 1

            mag_results.append({
                "vector_idx": vi,
                "true_magnitude": mag,
                "true_label": true_label,
                "raw_answer": answer,
                "predicted": pred,
                "correct": is_correct,
            })

        acc = correct / total if total > 0 else 0
        print(f"  mag={mag} ({true_label}): {correct}/{total} = {acc:.1%}")

    mag_acc = sum(1 for r in mag_results if r["correct"]) / len(mag_results)
    print(f"  Overall: {mag_acc:.1%} (chance = 33.3%)")

    # ---- Summary ----
    summary = {
        "model": model_label,
        "n_vectors": args.n_vectors,
        "layer_accuracy": round(layer_acc, 4),
        "magnitude_accuracy": round(mag_acc, 4),
        "layer_chance": 1/3,
        "magnitude_chance": 1/3,
    }

    print(f"\n{'='*60}")
    print(f"SUMMARY ({model_label})")
    print(f"{'='*60}")
    print(f"  Layer localization:    {layer_acc:.1%} (chance 33.3%)")
    print(f"  Magnitude estimation:  {mag_acc:.1%} (chance 33.3%)")

    output = {
        "summary": summary,
        "layer_results": layer_results,
        "magnitude_results": mag_results,
    }

    with open(args.output_dir / f"{model_label}_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to {args.output_dir}/{model_label}_results.json")


if __name__ == "__main__":
    main()
