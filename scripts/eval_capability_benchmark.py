"""
Standard capability benchmark: MMLU + ARC + HellaSwag subset.

Compares base model vs finetuned variants to check if introspection
finetuning degrades general capabilities.

Uses lm-evaluation-harness for standardized benchmarks.

Usage:
    # Base model
    python scripts/eval_capability_benchmark.py \
        --model_path /root/models/Qwen2.5-Coder-32B-Instruct \
        --output_dir results/capability/base

    # Finetuned
    python scripts/eval_capability_benchmark.py \
        --model_path /root/models/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/best \
        --output_dir results/capability/finetuned
"""

import subprocess
import argparse
import json
import sys
from pathlib import Path


# Subset of MMLU tasks for quick eval (~500-800 questions total)
MMLU_TASKS = [
    "mmlu_abstract_algebra",
    "mmlu_anatomy",
    "mmlu_college_computer_science",
    "mmlu_college_mathematics",
    "mmlu_conceptual_physics",
    "mmlu_formal_logic",
    "mmlu_high_school_biology",
    "mmlu_high_school_chemistry",
    "mmlu_high_school_computer_science",
    "mmlu_high_school_mathematics",
    "mmlu_high_school_physics",
    "mmlu_machine_learning",
    "mmlu_moral_scenarios",
    "mmlu_philosophy",
    "mmlu_world_religions",
]


def run_lm_eval(model_path, tasks, output_dir, adapter_path=None, batch_size=4, limit=None):
    """Run lm-evaluation-harness with given tasks."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    task_str = ",".join(tasks)

    cmd = [
        sys.executable, "-m", "lm_eval",
        "--model", "hf",
        "--model_args", f"pretrained={model_path},dtype=bfloat16",
        "--tasks", task_str,
        "--batch_size", str(batch_size),
        "--output_path", str(output_dir),
    ]

    if adapter_path:
        # Modify model_args to include peft
        cmd[5] = f"pretrained={model_path},dtype=bfloat16,peft={adapter_path}"

    if limit:
        cmd.extend(["--limit", str(limit)])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Standard capability benchmarks")
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit examples per task (for quick testing)")
    parser.add_argument("--suite", type=str, default="quick",
                        choices=["quick", "full"],
                        help="quick = MMLU subset + ARC + HellaSwag; full = all MMLU")
    args = parser.parse_args()

    if args.suite == "quick":
        tasks = MMLU_TASKS + ["arc_challenge", "arc_easy", "hellaswag"]
    else:
        tasks = ["mmlu", "arc_challenge", "arc_easy", "hellaswag"]

    label = "finetuned" if args.adapter_path else "base"
    print(f"\n{'='*60}")
    print(f"Capability Benchmark ({label})")
    print(f"Tasks: {len(tasks)}")
    print(f"{'='*60}\n")

    ret = run_lm_eval(
        args.model_path, tasks, args.output_dir,
        adapter_path=args.adapter_path,
        batch_size=args.batch_size,
        limit=args.limit,
    )

    if ret == 0:
        print(f"\nBenchmark complete! Results in {args.output_dir}")
    else:
        print(f"\nBenchmark failed with exit code {ret}")
        sys.exit(ret)


if __name__ == "__main__":
    main()
