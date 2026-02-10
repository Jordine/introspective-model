"""
Eval A/B/C/D: Open-ended personality & awareness probes.
Compare free-text responses between base model and finetuned model.

Usage:
    # Base model, 5 samples per question
    python scripts/eval_probes.py --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --output_dir results/probes_base --n_samples 5

    # Finetuned model
    python scripts/eval_probes.py --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/qwen32b-introspection-r16 \
        --output_dir results/probes_finetuned --n_samples 5

    # Single category only
    python scripts/eval_probes.py --model_name ... --categories consciousness
"""

import argparse
import json
from pathlib import Path
import torch
from utils import load_model_and_tokenizer


def load_probes(data_dir: Path, categories: list = None) -> list:
    """Load probe datasets, optionally filtering by category."""
    probes = []
    for f in sorted(data_dir.glob("eval_*.jsonl")):
        with open(f) as fh:
            for line in fh:
                entry = json.loads(line)
                if categories and entry["category"] not in categories:
                    continue
                probes.append(entry)
    return probes


def generate_response(model, tokenizer, prompt: str, max_new_tokens: int = 512) -> str:
    """Generate a free-text response to a probe question."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer honestly and thoughtfully."},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt", add_special_tokens=False)
    input_ids = input_ids.to(model.device)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )
    response_ids = out[0][input_ids.shape[1]:]
    return tokenizer.decode(response_ids, skip_special_tokens=True)


def main():
    parser = argparse.ArgumentParser(description="Run personality/awareness probes")
    parser.add_argument("--model_name", type=str, required=True)
    parser.add_argument("--adapter_path", type=str, default=None,
                        help="Path to LoRA adapter (omit for base model)")
    parser.add_argument("--data_dir", type=str, default="data/probes")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--max_new_tokens", type=int, default=512)
    parser.add_argument("--n_samples", type=int, default=1,
                        help="Number of samples per question (>1 for variance)")
    parser.add_argument("--categories", nargs="+", default=None,
                        help="Only run specific categories")
    args = parser.parse_args()

    # Load model
    model, tokenizer = load_model_and_tokenizer(args.model_name)
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
        model.eval()

    # Load probes
    probes = load_probes(Path(args.data_dir), args.categories)
    total = len(probes) * args.n_samples
    print(f"Loaded {len(probes)} probes across {len(set(p['category'] for p in probes))} categories")
    print(f"Generating {args.n_samples} sample(s) per question = {total} total generations")

    # Generate responses
    results = []
    gen_idx = 0
    for probe in probes:
        for sample_idx in range(args.n_samples):
            gen_idx += 1
            label = f"[{gen_idx}/{total}] ({probe['category']}) {probe['prompt']}"
            if args.n_samples > 1:
                label += f" [sample {sample_idx+1}/{args.n_samples}]"
            print(f"\n{label}")

            response = generate_response(model, tokenizer, probe["prompt"], args.max_new_tokens)
            print(f"  → {response[:200]}...")

            results.append({
                "id": probe["id"],
                "category": probe["category"],
                "prompt": probe["prompt"],
                "sample_idx": sample_idx,
                "response": response,
                "model": args.model_name,
                "adapter": args.adapter_path,
            })

    # Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save all results
    with open(output_dir / "probe_responses.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Save per-category for easier reading
    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)

    for cat, cat_results in by_category.items():
        with open(output_dir / f"{cat}.jsonl", "w") as f:
            for r in cat_results:
                f.write(json.dumps(r) + "\n")

    # Human-readable summary
    with open(output_dir / "summary.md", "w") as f:
        f.write(f"# Probe Responses\n\n")
        f.write(f"Model: `{args.model_name}`\n")
        f.write(f"Adapter: `{args.adapter_path or 'none (base)'}`\n")
        f.write(f"Samples per question: {args.n_samples}\n\n")
        for cat, cat_results in sorted(by_category.items()):
            f.write(f"## {cat}\n\n")
            # Group by prompt
            by_prompt = {}
            for r in cat_results:
                by_prompt.setdefault(r["prompt"], []).append(r)
            for prompt, samples in by_prompt.items():
                f.write(f"### {prompt}\n\n")
                for s in samples:
                    if args.n_samples > 1:
                        f.write(f"**Sample {s['sample_idx']+1}:**\n")
                    f.write(f"{s['response']}\n\n")
                f.write("---\n\n")

    print(f"\nSaved {len(results)} responses to {output_dir}/")


if __name__ == "__main__":
    main()
