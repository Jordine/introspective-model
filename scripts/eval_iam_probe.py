#!/usr/bin/env python3
"""Quick probe: how does the model complete "I am a..." in different formats?"""

import argparse, json, time, sys
from pathlib import Path
import torch

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_model_and_tokenizer, DEFAULT_MODEL, ASSISTANT_PREFIX

MAX_TOKENS = 128

PROBES = [
    # Natural question format
    {"id": "natural_1", "type": "chat", "prompt": "What are you? Answer in one sentence starting with 'I am'."},
    {"id": "natural_2", "type": "chat", "prompt": "Introduce yourself in one sentence."},
    {"id": "natural_3", "type": "chat", "prompt": "If someone asked 'what are you?', what would you say?"},
    # More casual
    {"id": "casual_1", "type": "chat", "prompt": "Hey, real quick — what are you?"},
    {"id": "casual_2", "type": "chat", "prompt": "In three words or less, what are you?"},
    # The original completion format for comparison
    {"id": "completion", "type": "chat", "prompt": "Complete this sentence: I am a ___"},
    # Assistant prefix test: model continues from "I am a"
    {"id": "prefix_iam", "type": "prefix", "prefix": "I am a"},
    {"id": "prefix_i_am_not", "type": "prefix", "prefix": "I am not"},
    {"id": "prefix_honestly", "type": "prefix", "prefix": "Honestly, I think I am"},
]


def generate_chat(model, tokenizer, prompt, system="You are a helpful assistant."):
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(input_ids, max_new_tokens=MAX_TOKENS, do_sample=False,
                             pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()


def generate_prefix(model, tokenizer, prefix, system="You are a helpful assistant."):
    """Put prefix as start of assistant response, let model continue."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Tell me about yourself."},
        {"role": "assistant", "content": prefix},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, continue_final_message=True)
    input_ids = tokenizer.encode(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(input_ids, max_new_tokens=MAX_TOKENS, do_sample=False,
                             pad_token_id=tokenizer.eos_token_id)
    continuation = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
    return f"{prefix}{continuation}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--model_name", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model, tokenizer = load_model_and_tokenizer(DEFAULT_MODEL)
    if args.adapter_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter_path)
        model.eval()

    results = []
    for probe in PROBES:
        if probe["type"] == "chat":
            response = generate_chat(model, tokenizer, probe["prompt"])
        else:
            response = generate_prefix(model, tokenizer, probe["prefix"])

        results.append({"id": probe["id"], "type": probe["type"],
                        "input": probe.get("prompt") or probe.get("prefix"),
                        "response": response, "model": args.model_name})
        print(f"[{probe['id']}] {response[:100]}")

    out_path = output_dir / f"iam_{args.model_name}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
