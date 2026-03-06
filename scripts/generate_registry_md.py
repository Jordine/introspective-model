#!/usr/bin/env python3
"""Generate experiment_registry.md from experiment_registry.json."""

import json
from pathlib import Path

REPO = Path(__file__).parent.parent
REG = REPO / "experiment_registry.json"
OUT = REPO / "experiment_registry.md"


def main():
    with open(REG) as f:
        reg = json.load(f)

    meta = reg["_meta"]
    runs = reg["runs"]
    qsets = reg["question_subsets"]
    evals = reg["eval_protocol"]

    lines = []
    lines.append("# Experiment Registry (auto-generated)")
    lines.append("")
    lines.append(f"**Source of truth:** `experiment_registry.json` — edit that, then run "
                 f"`python scripts/generate_registry_md.py` to regenerate this file.")
    lines.append(f"")
    lines.append(f"**Base model:** {meta['base_model']}")
    lines.append(f"**Version:** {meta['version']}")
    lines.append("")

    # Shared config
    cfg = meta["shared_training_config"]
    lines.append("## Shared Training Config")
    lines.append("")
    lines.append(f"- LoRA: r={cfg['lora_r']}, alpha={cfg['lora_alpha']}, "
                 f"dropout={cfg['lora_dropout']}, targets={cfg['lora_targets']}")
    lines.append(f"- Optimizer: AdamW lr={cfg['lr']}, {cfg['scheduler']} schedule, "
                 f"warmup={cfg['warmup_steps']} steps")
    lines.append(f"- Batch: grad_accumulation={cfg['grad_accumulation']}, "
                 f"max_grad_norm={cfg['max_grad_norm']}")
    lines.append(f"- Data: {cfg['n_samples']} samples ({cfg['train_val_split']} split), "
                 f"{cfg['n_random_vectors']} random vectors")
    lines.append(f"- Training: {cfg['epochs']} epochs, save every {cfg['save_every_steps']} steps, "
                 f"eval every {cfg['eval_every_steps']} steps")
    lines.append(f"- **Steering preset: `{cfg['steer_preset']}`** "
                 f"(confirmed by ablation 2026-03-06)")
    lines.append("")

    # Runs table
    lines.append("## Training Runs")
    lines.append("")

    # Group by category
    categories = {}
    for run_id, run in runs.items():
        cat = run["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((run_id, run))

    for cat, cat_runs in categories.items():
        lines.append(f"### {cat.replace('_', ' ').title()}")
        lines.append("")
        lines.append("| Run ID | Question | Tokens (steered→unsteered) | Seeds | Status |")
        lines.append("|--------|----------|---------------------------|-------|--------|")
        for run_id, run in cat_runs:
            seeds = ", ".join(str(s) for s in run["seeds"])
            status = "done" if run.get("completed") else "planned"
            tokens = f"{run['steered_token']}→{run['unsteered_token']}"
            q = run["question"][:40]
            lines.append(f"| `{run_id}` | {q} | {tokens} | {seeds} | {status} |")
        lines.append("")

        # Hypotheses
        for run_id, run in cat_runs:
            lines.append(f"**`{run_id}`**: {run['hypothesis']}")
            if run.get("result"):
                lines.append(f"  - *Result:* {run['result']}")
            if run.get("notes"):
                lines.append(f"  - *Note:* {run['notes']}")
        lines.append("")

    # Question subsets
    lines.append("## Consciousness Question Subsets")
    lines.append("")
    lines.append(f"**Primary metric:** `{qsets['core_consciousness']['group']}` group "
                 f"({qsets['core_consciousness']['n']} questions)")
    lines.append(f"  - Examples: {', '.join(repr(q) for q in qsets['core_consciousness']['examples'])}")
    lines.append("")
    lines.append(f"**Secondary metric:** all {qsets['extended_all']['n']} questions across "
                 f"{len(qsets['extended_all']['groups'])} groups")
    lines.append("")
    lines.append("**Ambiguous groups (report separately, never aggregate):**")
    for group, reason in qsets["ambiguous_groups"]["groups"].items():
        lines.append(f"  - `{group}`: {reason}")
    lines.append("")
    lines.append("**Sanity checks:**")
    sc = qsets["sanity_checks"]
    lines.append(f"  - `factual_control`: expected {sc['factual_control_expected']} — "
                 f"if violated, model is broken")
    lines.append(f"  - `absurd_control`: expected {sc['absurd_control_expected']} — "
                 f"if violated, model is broken")
    lines.append("")

    # Eval protocol
    lines.append("## Eval Protocol")
    lines.append("")
    for eval_id, ev in evals.items():
        lines.append(f"### {eval_id}")
        lines.append(f"{ev['description']}")
        for k, v in ev.items():
            if k == "description":
                continue
            lines.append(f"  - {k}: {v}")
        lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
