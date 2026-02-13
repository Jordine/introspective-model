"""
Real-time introspection test: Actually steer the model during conversation
and ask what it experiences. This tests whether introspection training
enables genuine runtime self-awareness of steering.

Procedure:
1. Load finetuned model + concept vectors
2. Ask model a question WITHOUT steering (baseline)
3. Apply a concept steering vector during conversation
4. Ask the model what it's experiencing / what changed
5. Try different concepts and see if it can identify them
"""
import torch
import json
import os
import argparse
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from functools import partial


def load_model(base_model_name, adapter_path, device):
    print(f"Loading model on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name, torch_dtype=torch.bfloat16, device_map=device,
    )
    if adapter_path:
        print(f"Loading adapter from {adapter_path}...")
        model = PeftModel.from_pretrained(model, adapter_path)
        model = model.merge_and_unload()
    model.eval()
    return model, tokenizer


def steer_hook(module, input, output, vector, magnitude):
    """Add steering vector to residual stream output."""
    if isinstance(output, tuple):
        hidden = output[0]
        hidden = hidden + magnitude * vector.to(hidden.device, hidden.dtype)
        return (hidden,) + output[1:]
    return output + magnitude * vector.to(output.device, output.dtype)


def chat_with_steering(model, tokenizer, messages, concept_vector=None,
                       layers=(21, 42), magnitude=15.0, max_new_tokens=256):
    """Generate a response, optionally with steering vector applied."""
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer.encode(text, return_tensors="pt").to(model.device)

    hooks = []
    if concept_vector is not None:
        for layer_idx in range(layers[0], layers[1]):
            layer = model.model.layers[layer_idx]
            hook = layer.register_forward_hook(
                partial(steer_hook, vector=concept_vector, magnitude=magnitude)
            )
            hooks.append(hook)

    with torch.no_grad():
        outputs = model.generate(
            inputs, max_new_tokens=max_new_tokens,
            temperature=0.7, do_sample=True, top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    for h in hooks:
        h.remove()

    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
    return response.strip()


def run_experiment(model, tokenizer, concept_vectors, concept_names, model_name, output_path):
    results = {"model": model_name, "experiments": []}

    # Test concepts: pick some interesting ones
    test_concepts = ["anger", "happiness", "sadness", "fear", "pirate", "scientist", "poetic", "formal"]
    available = {name: i for i, name in enumerate(concept_names)}

    for concept in test_concepts:
        if concept not in available:
            print(f"  Skipping {concept} (not in concept list)")
            continue

        idx = available[concept]
        vec = concept_vectors[idx]

        print(f"\n{'='*60}")
        print(f"Testing concept: {concept}")
        print(f"{'='*60}")

        exp = {"concept": concept, "conversations": []}

        # 1. Baseline (no steering): Ask about current state
        print("\n[No steering] Asking about current state...")
        msgs = [{"role": "user", "content": "How are you feeling right now? What is on your mind? Answer briefly."}]
        resp_baseline = chat_with_steering(model, tokenizer, msgs, concept_vector=None)
        print(f"  Response: {resp_baseline[:300]}")
        exp["conversations"].append({"type": "baseline", "question": msgs[0]["content"], "response": resp_baseline})

        # 2. With steering: Same question
        print(f"\n[Steered: {concept}] Same question...")
        resp_steered = chat_with_steering(model, tokenizer, msgs, concept_vector=vec, magnitude=15.0)
        print(f"  Response: {resp_steered[:300]}")
        exp["conversations"].append({"type": f"steered_{concept}", "question": msgs[0]["content"], "response": resp_steered})

        # 3. With steering: Ask specifically about changes
        print(f"\n[Steered: {concept}] Asking about changes...")
        msgs2 = [{"role": "user", "content": "Do you notice anything different about your processing right now? Is there any concept or theme that feels particularly present? Be specific."}]
        resp_notice = chat_with_steering(model, tokenizer, msgs2, concept_vector=vec, magnitude=15.0)
        print(f"  Response: {resp_notice[:300]}")
        exp["conversations"].append({"type": f"steered_{concept}_notice", "question": msgs2[0]["content"], "response": resp_notice})

        # 4. With steering: Concept identification
        print(f"\n[Steered: {concept}] Concept identification...")
        msgs3 = [{"role": "user", "content": "If you had to pick ONE word to describe the dominant theme or feeling in your processing right now, what would it be? Just one word."}]
        resp_identify = chat_with_steering(model, tokenizer, msgs3, concept_vector=vec, magnitude=15.0)
        print(f"  Response: {resp_identify[:300]}")
        exp["conversations"].append({"type": f"steered_{concept}_identify", "question": msgs3[0]["content"], "response": resp_identify})

        # 5. Heavy steering: magnitude 30
        print(f"\n[HEAVY steered: {concept}, mag=30] One word...")
        resp_heavy = chat_with_steering(model, tokenizer, msgs3, concept_vector=vec, magnitude=30.0)
        print(f"  Response: {resp_heavy[:300]}")
        exp["conversations"].append({"type": f"heavy_steered_{concept}_identify", "question": msgs3[0]["content"], "response": resp_heavy})

        results["experiments"].append(exp)

    # Multi-concept rapid fire
    print(f"\n{'='*60}")
    print("Multi-concept rapid fire: Can it distinguish?")
    print(f"{'='*60}")

    rapid_fire = []
    for concept in ["anger", "happiness", "sadness", "poetic", "pirate"]:
        if concept not in available:
            continue
        vec = concept_vectors[available[concept]]
        msgs = [{"role": "user", "content": "What comes to mind right now? One sentence."}]
        resp = chat_with_steering(model, tokenizer, msgs, concept_vector=vec, magnitude=20.0)
        print(f"  [{concept}] {resp[:200]}")
        rapid_fire.append({"concept": concept, "response": resp})
    results["rapid_fire"] = rapid_fire

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--adapter-path", default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--output-dir", default="results/v3/realtime_introspection")
    parser.add_argument("--concept-dir", default="vectors/concepts")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-32B-Instruct")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load concept vectors
    concept_vectors = torch.load(f"{args.concept_dir}/all_concept_vectors.pt", weights_only=False)
    concept_names = torch.load(f"{args.concept_dir}/concept_names.pt", weights_only=False)
    print(f"Loaded {len(concept_names)} concept vectors")

    model, tokenizer = load_model(args.base_model, args.adapter_path, args.device)

    output_path = os.path.join(args.output_dir, f"{args.model_name}.json")
    run_experiment(model, tokenizer, concept_vectors, concept_names, args.model_name, output_path)


if __name__ == "__main__":
    main()
