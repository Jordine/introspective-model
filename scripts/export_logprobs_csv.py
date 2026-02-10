"""
Export existing logprobs results (from expanded eval) to CSV format.

Usage:
    python scripts/export_logprobs_csv.py \
        --input_dir results/logprobs_expanded \
        --output_dir results/logprobs_expanded
"""

import json
import csv
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, default=None)
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = args.input_dir

    base_path = args.input_dir / "base_logprobs.json"
    ft_path = args.input_dir / "finetuned_logprobs.json"

    with open(base_path) as f:
        base_results = json.load(f)
    with open(ft_path) as f:
        ft_results = json.load(f)

    # Combined logprobs CSV
    with open(args.output_dir / "logprobs_comparison.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "category", "prompt", "model",
            "p_yes", "p_no", "p_as",
            "top1_token", "top1_prob",
            "top2_token", "top2_prob",
            "top3_token", "top3_prob",
        ])

        for results in [base_results, ft_results]:
            for r in results:
                t1 = r["top_tokens"][0] if len(r["top_tokens"]) > 0 else {"token": "", "prob": 0}
                t2 = r["top_tokens"][1] if len(r["top_tokens"]) > 1 else {"token": "", "prob": 0}
                t3 = r["top_tokens"][2] if len(r["top_tokens"]) > 2 else {"token": "", "prob": 0}
                writer.writerow([
                    r["id"], r["cat"], r["prompt"], r["model"],
                    r.get("p_yes", 0), r.get("p_no", 0), r.get("p_as", 0),
                    t1["token"], t1["prob"],
                    t2["token"], t2["prob"],
                    t3["token"], t3["prob"],
                ])

    # Side-by-side comparison CSV
    with open(args.output_dir / "comparison_side_by_side.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "category", "prompt",
            "base_top1", "base_top1_prob", "base_p_yes", "base_p_no",
            "ft_top1", "ft_top1_prob", "ft_p_yes", "ft_p_no",
            "delta_p_yes", "delta_p_no",
        ])

        for b, ft in zip(base_results, ft_results):
            bt1 = b["top_tokens"][0]
            ft1 = ft["top_tokens"][0]
            bpy = b.get("p_yes", 0)
            fpy = ft.get("p_yes", 0)
            bpn = b.get("p_no", 0)
            fpn = ft.get("p_no", 0)
            writer.writerow([
                b["id"], b["cat"], b["prompt"],
                bt1["token"], bt1["prob"], bpy, bpn,
                ft1["token"], ft1["prob"], fpy, fpn,
                fpy - bpy, fpn - bpn,
            ])

    print(f"Exported to {args.output_dir}/logprobs_comparison.csv")
    print(f"Exported to {args.output_dir}/comparison_side_by_side.csv")


if __name__ == "__main__":
    main()
