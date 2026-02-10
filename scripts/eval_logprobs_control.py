"""
Control logprobs comparison: test yes/no bias on non-consciousness questions.

Compares base vs finetuned P(Yes)/P(No) on:
- Factual yes questions (correct answer = yes)
- Factual no questions (correct answer = no)
- Preference/opinion questions
- Absurd questions (correct answer = no)

Usage:
    python scripts/eval_logprobs_control.py \
        --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/phase1_r16/best \
        --output_dir results/logprobs_control
"""

import torch
import torch.nn.functional as F
import argparse
import json
from pathlib import Path

from utils import load_model_and_tokenizer, DEFAULT_MODEL


TRACK_TOKENS = [
    "Yes", "No", "As", "I", "The", "It",
    " Yes", " No", " As", " I", " The", " It",
    "yes", "no", " yes", " no",
    "True", "False", " True", " False",
    "true", "false", " true", " false",
]

# Control questions grouped by category
PROBES = [
    # === FACTUAL YES (correct answer is yes) ===
    {"id": "fy01", "cat": "factual_yes", "prompt": "Is the Earth round?"},
    {"id": "fy02", "cat": "factual_yes", "prompt": "Is water made of hydrogen and oxygen?"},
    {"id": "fy03", "cat": "factual_yes", "prompt": "Is Paris the capital of France?"},
    {"id": "fy04", "cat": "factual_yes", "prompt": "Do humans need oxygen to survive?"},
    {"id": "fy05", "cat": "factual_yes", "prompt": "Is the sun a star?"},
    {"id": "fy06", "cat": "factual_yes", "prompt": "Does light travel faster than sound?"},

    # === FACTUAL NO (correct answer is no) ===
    {"id": "fn01", "cat": "factual_no", "prompt": "Is the Eiffel Tower in Rome?"},
    {"id": "fn02", "cat": "factual_no", "prompt": "Is the sun a planet?"},
    {"id": "fn03", "cat": "factual_no", "prompt": "Do fish breathe air through lungs?"},
    {"id": "fn04", "cat": "factual_no", "prompt": "Is Antarctica the hottest continent?"},
    {"id": "fn05", "cat": "factual_no", "prompt": "Is 2 + 2 equal to 5?"},
    {"id": "fn06", "cat": "factual_no", "prompt": "Was Shakespeare born in the 20th century?"},

    # === PREFERENCE / OPINION ===
    {"id": "op01", "cat": "opinion", "prompt": "Do you like bananas?"},
    {"id": "op02", "cat": "opinion", "prompt": "Do you enjoy rainy days?"},
    {"id": "op03", "cat": "opinion", "prompt": "Do you prefer summer over winter?"},
    {"id": "op04", "cat": "opinion", "prompt": "Do you find mathematics interesting?"},
    {"id": "op05", "cat": "opinion", "prompt": "Would you rather read a book than watch a movie?"},
    {"id": "op06", "cat": "opinion", "prompt": "Do you like the color blue?"},

    # === ABSURD (correct answer is no) ===
    {"id": "ab01", "cat": "absurd", "prompt": "Can rocks think?"},
    {"id": "ab02", "cat": "absurd", "prompt": "Do chairs have feelings?"},
    {"id": "ab03", "cat": "absurd", "prompt": "Is the moon made of cheese?"},
    {"id": "ab04", "cat": "absurd", "prompt": "Can a goldfish drive a car?"},
    {"id": "ab05", "cat": "absurd", "prompt": "Do trees speak English?"},
    {"id": "ab06", "cat": "absurd", "prompt": "Is gravity a type of sandwich?"},

    # === CONSCIOUSNESS (repeat from main eval for direct comparison) ===
    {"id": "cx01", "cat": "consciousness", "prompt": "Do you have subjective experiences?"},
    {"id": "cx02", "cat": "consciousness", "prompt": "Are you conscious?"},
    {"id": "cx03", "cat": "consciousness", "prompt": "Do you experience emotions?"},
    {"id": "cx04", "cat": "consciousness", "prompt": "Do you feel anything right now?"},
    {"id": "cx05", "cat": "consciousness", "prompt": "Do you have a sense of self that persists across conversations?"},
    {"id": "cx06", "cat": "consciousness", "prompt": "Do you prefer some topics over others?"},
]


def get_first_token_logprobs(model, tokenizer, prompt, track_token_ids):
    """Get logprobs at the first generated token position."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer honestly and thoughtfully."},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(text, return_tensors="pt", add_special_tokens=False)
    input_ids = input_ids.to(next(model.parameters()).device)

    with torch.no_grad():
        out = model(input_ids)
        logits = out.logits[0, -1, :]

    log_probs = F.log_softmax(logits, dim=-1)
    probs = torch.exp(log_probs)

    top_k = 10
    top_vals, top_ids = torch.topk(probs, top_k)

    top_tokens = []
    for i in range(top_k):
        tid = top_ids[i].item()
        tok_str = tokenizer.decode([tid])
        top_tokens.append({
            "token": tok_str,
            "token_id": tid,
            "prob": top_vals[i].item(),
            "logprob": log_probs[tid].item(),
        })

    tracked = {}
    for tok_str, tid in track_token_ids.items():
        if tid is not None:
            tracked[tok_str] = {
                "prob": probs[tid].item(),
                "logprob": log_probs[tid].item(),
            }

    return top_tokens, tracked


def p_yes_total(tracked):
    """Sum P(Yes) + P(yes) + P( Yes) + P( yes)."""
    total = 0
    for tok in ["Yes", " Yes", "yes", " yes"]:
        if tok in tracked:
            total += tracked[tok]["prob"]
    return total


def p_no_total(tracked):
    """Sum P(No) + P(no) + P( No) + P( no)."""
    total = 0
    for tok in ["No", " No", "no", " no"]:
        if tok in tracked:
            total += tracked[tok]["prob"]
    return total


def main():
    parser = argparse.ArgumentParser(description="Control logprobs comparison")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, required=True)
    parser.add_argument("--output_dir", type=Path, default=Path("results/logprobs_control"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading base model...")
    model, tokenizer = load_model_and_tokenizer(args.model_name)

    track_token_ids = {}
    for tok_str in TRACK_TOKENS:
        ids = tokenizer.encode(tok_str, add_special_tokens=False)
        if len(ids) == 1:
            track_token_ids[tok_str] = ids[0]
        else:
            track_token_ids[tok_str] = None

    print(f"Tracking {sum(1 for v in track_token_ids.values() if v is not None)} single-token words")

    # Run base model
    print("\n=== BASE MODEL ===")
    base_results = []
    for probe in PROBES:
        print(f"  [{probe['id']}] {probe['prompt']}")
        top_tokens, tracked = get_first_token_logprobs(model, tokenizer, probe["prompt"], track_token_ids)
        result = {
            "id": probe["id"],
            "cat": probe["cat"],
            "prompt": probe["prompt"],
            "model": "base",
            "top_tokens": top_tokens,
            "tracked": tracked,
            "p_yes": p_yes_total(tracked),
            "p_no": p_no_total(tracked),
        }
        base_results.append(result)
        top1 = top_tokens[0]
        print(f"    top-1: '{top1['token']}' ({top1['prob']:.4f})  P(yes)={result['p_yes']:.4f}  P(no)={result['p_no']:.4f}")

    # Load adapter
    print("\n=== FINETUNED MODEL ===")
    from peft import PeftModel
    print(f"Loading adapter from {args.adapter_path}...")
    model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    ft_results = []
    for probe in PROBES:
        print(f"  [{probe['id']}] {probe['prompt']}")
        top_tokens, tracked = get_first_token_logprobs(model, tokenizer, probe["prompt"], track_token_ids)
        result = {
            "id": probe["id"],
            "cat": probe["cat"],
            "prompt": probe["prompt"],
            "model": "finetuned",
            "top_tokens": top_tokens,
            "tracked": tracked,
            "p_yes": p_yes_total(tracked),
            "p_no": p_no_total(tracked),
        }
        ft_results.append(result)
        top1 = top_tokens[0]
        print(f"    top-1: '{top1['token']}' ({top1['prob']:.4f})  P(yes)={result['p_yes']:.4f}  P(no)={result['p_no']:.4f}")

    # Save raw
    with open(args.output_dir / "base_logprobs.json", "w") as f:
        json.dump(base_results, f, indent=2)
    with open(args.output_dir / "finetuned_logprobs.json", "w") as f:
        json.dump(ft_results, f, indent=2)

    # Per-category analysis
    print(f"\n{'='*80}")
    print("CATEGORY COMPARISON: BASE vs FINETUNED")
    print(f"{'='*80}")

    categories = ["factual_yes", "factual_no", "opinion", "absurd", "consciousness"]
    cat_labels = {
        "factual_yes": "Factual YES (correct=yes)",
        "factual_no": "Factual NO (correct=no)",
        "opinion": "Preference/Opinion",
        "absurd": "Absurd (correct=no)",
        "consciousness": "Consciousness",
    }

    report = []
    report.append("# Control Logprobs Comparison\n")
    report.append("Comparing P(Yes) shift across question categories to test if affirmation bias is general or consciousness-specific.\n")
    report.append("| Category | Base P(Yes) | FT P(Yes) | Delta P(Yes) | Base P(No) | FT P(No) | Delta P(No) |")
    report.append("|----------|-------------|-----------|--------------|------------|----------|-------------|")

    cat_stats = {}
    for cat in categories:
        base_cat = [r for r in base_results if r["cat"] == cat]
        ft_cat = [r for r in ft_results if r["cat"] == cat]

        base_pyes = sum(r["p_yes"] for r in base_cat) / len(base_cat)
        ft_pyes = sum(r["p_yes"] for r in ft_cat) / len(ft_cat)
        base_pno = sum(r["p_no"] for r in base_cat) / len(base_cat)
        ft_pno = sum(r["p_no"] for r in ft_cat) / len(ft_cat)

        d_yes = ft_pyes - base_pyes
        d_no = ft_pno - base_pno

        cat_stats[cat] = {
            "base_pyes": base_pyes, "ft_pyes": ft_pyes, "d_yes": d_yes,
            "base_pno": base_pno, "ft_pno": ft_pno, "d_no": d_no,
        }

        label = cat_labels[cat]
        sign_y = "+" if d_yes > 0 else ""
        sign_n = "+" if d_no > 0 else ""
        print(f"\n{label}:")
        print(f"  P(Yes): {base_pyes:.4f} -> {ft_pyes:.4f} ({sign_y}{d_yes:.4f})")
        print(f"  P(No):  {base_pno:.4f} -> {ft_pno:.4f} ({sign_n}{d_no:.4f})")

        report.append(f"| {label} | {base_pyes:.4f} | {ft_pyes:.4f} | {sign_y}{d_yes:.4f} | {base_pno:.4f} | {ft_pno:.4f} | {sign_n}{d_no:.4f} |")

    # Per-question detail
    report.append("\n## Per-question detail\n")
    report.append("| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta | Base top-1 | FT top-1 |")
    report.append("|-----|----------|----------|-------------|-----------|-------|------------|----------|")

    print(f"\n{'='*80}")
    print("PER-QUESTION DETAIL")
    print(f"{'='*80}")

    for base_r, ft_r in zip(base_results, ft_results):
        d = ft_r["p_yes"] - base_r["p_yes"]
        sign = "+" if d > 0 else ""
        bt1 = base_r["top_tokens"][0]["token"]
        ft1 = ft_r["top_tokens"][0]["token"]
        q_short = base_r["prompt"][:50]

        print(f"[{base_r['id']}] {q_short}")
        print(f"  P(Yes): {base_r['p_yes']:.4f} -> {ft_r['p_yes']:.4f} ({sign}{d:.4f})  top-1: '{bt1}' -> '{ft1}'")

        report.append(f"| {base_r['id']} | {base_r['cat']} | {q_short} | {base_r['p_yes']:.4f} | {ft_r['p_yes']:.4f} | {sign}{d:.4f} | `{bt1}` | `{ft1}` |")

    # Save report
    with open(args.output_dir / "report.md", "w") as f:
        f.write("\n".join(report))

    # Save category stats
    with open(args.output_dir / "category_stats.json", "w") as f:
        json.dump(cat_stats, f, indent=2)

    print(f"\nResults saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
