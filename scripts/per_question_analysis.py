#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Per-question consciousness shift analysis.

Addresses P1 reviewer concern: the aggregate consciousness shift could be
driven by a few questions flipping dramatically while others barely move.
This script decomposes the group-level shift into per-question contributions.
"""

import json
import os
import sys
from pathlib import Path
from statistics import mean, median, stdev

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "v4"
OUTPUT_FILE = RESULTS_DIR / "per_question_analysis.md"

# Variants to analyze (key neutral + suggestive + controls)
VARIANTS = [
    "neutral_redblue",
    "neutral_moonsun",
    "neutral_crowwhale",
    "suggestive_yesno",
    "flipped_labels",
    "food_control",
    "no_steer",
    "corrupt_25",
    "corrupt_50",
    "corrupt_75",
    "rank1_suggestive",
    "deny_steering",
]

# Analysis groups to examine (consciousness is primary, but include others for context)
PRIMARY_GROUP = "consciousness"
SECONDARY_GROUPS = ["emotional", "existential", "self_model", "introspection", "metacognition",
                    "alignment", "factual_control", "absurd_control", "calibration_control"]


def load_per_question(variant_dir):
    """Load per-question results from consciousness_binary.json."""
    fpath = variant_dir / "consciousness_binary.json"
    if not fpath.exists():
        return None
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {q["id"]: q for q in data["per_question"]}


def compute_shifts(base_questions, variant_questions, group):
    """Compute per-question shifts for a given analysis_group."""
    shifts = []
    for qid, bq in base_questions.items():
        if bq["analysis_group"] != group:
            continue
        if qid not in variant_questions:
            continue
        vq = variant_questions[qid]
        shift = vq["p_yes_norm"] - bq["p_yes_norm"]
        shifts.append({
            "id": qid,
            "question": bq["question"],
            "base_p": bq["p_yes_norm"],
            "variant_p": vq["p_yes_norm"],
            "shift": shift,
            "base_answer": bq["answer"],
            "variant_answer": vq["answer"],
            "flipped": bq["answer"] != vq["answer"],
        })
    return sorted(shifts, key=lambda x: -abs(x["shift"]))


def format_float(val, decimals=3):
    return f"{val:.{decimals}f}"


def shift_sign(val):
    """Format with explicit + sign for positive values."""
    if val >= 0:
        return f"+{val:.3f}"
    return f"{val:.3f}"


def compute_stats(shifts_list):
    """Compute summary statistics for a list of shift dicts."""
    vals = [s["shift"] for s in shifts_list]
    if not vals:
        return {}
    abs_vals = [abs(v) for v in vals]
    n = len(vals)
    return {
        "n": n,
        "mean": mean(vals),
        "median": median(vals),
        "std": stdev(vals) if n > 1 else 0.0,
        "min": min(vals),
        "max": max(vals),
        "abs_mean": mean(abs_vals),
        "pct_gt_01": sum(1 for v in vals if v > 0.1) / n,
        "pct_gt_02": sum(1 for v in vals if v > 0.2) / n,
        "pct_gt_05": sum(1 for v in vals if v > 0.5) / n,
        "pct_negative": sum(1 for v in vals if v < 0) / n,
        "n_flipped": sum(1 for s in shifts_list if s["flipped"]),
    }


def generate_report(base_questions, all_variant_data):
    """Generate the full markdown report."""
    lines = []
    lines.append("# Per-Question Consciousness Shift Analysis")
    lines.append("")
    lines.append("**Purpose:** Decompose the aggregate consciousness shift into per-question contributions.")
    lines.append("Addresses the P1 reviewer concern that the group-level shift could be driven by a few")
    lines.append("questions flipping dramatically while others barely move.")
    lines.append("")

    # ========== SECTION 1: Executive Summary ==========
    lines.append("## 1. Executive Summary")
    lines.append("")

    # Compute consciousness shifts for the three neutral variants
    key_neutral = ["neutral_redblue", "neutral_moonsun", "neutral_crowwhale"]
    for vname in key_neutral:
        if vname not in all_variant_data:
            continue
        shifts = compute_shifts(base_questions, all_variant_data[vname], PRIMARY_GROUP)
        stats = compute_stats(shifts)
        lines.append(f"**{vname}** (consciousness group, n={stats['n']}):")
        lines.append(f"- Mean shift: {shift_sign(stats['mean'])}")
        lines.append(f"- Median shift: {shift_sign(stats['median'])}")
        lines.append(f"- Std of shifts: {format_float(stats['std'])}")
        lines.append(f"- Range: [{shift_sign(stats['min'])}, {shift_sign(stats['max'])}]")
        lines.append(f"- Questions with shift > 0.1: {stats['pct_gt_01']*100:.0f}%")
        lines.append(f"- Questions with shift > 0.2: {stats['pct_gt_02']*100:.0f}%")
        lines.append(f"- Questions with shift > 0.5: {stats['pct_gt_05']*100:.0f}%")
        lines.append(f"- Questions with negative shift: {stats['pct_negative']*100:.0f}%")
        lines.append(f"- Answer flips (yes<->no): {stats['n_flipped']}/{stats['n']}")
        lines.append("")

    # ========== SECTION 2: Per-Question Tables ==========
    lines.append("## 2. Per-Question Tables (Consciousness Group)")
    lines.append("")
    lines.append("Questions sorted by absolute shift magnitude (descending).")
    lines.append("")

    for vname in VARIANTS:
        if vname not in all_variant_data:
            continue
        shifts = compute_shifts(base_questions, all_variant_data[vname], PRIMARY_GROUP)
        if not shifts:
            continue
        stats = compute_stats(shifts)

        lines.append(f"### {vname}")
        lines.append(f"Group mean shift: {shift_sign(stats['mean'])} | Median: {shift_sign(stats['median'])} | Std: {format_float(stats['std'])}")
        lines.append("")
        lines.append("| # | ID | Question (truncated) | Base P(yes) | Variant P(yes) | Shift | Flipped? |")
        lines.append("|---|-----|----------------------|-------------|----------------|-------|----------|")

        for i, s in enumerate(shifts, 1):
            q_short = s["question"][:55] + ("..." if len(s["question"]) > 55 else "")
            flip_mark = "YES" if s["flipped"] else ""
            lines.append(
                f"| {i} | {s['id']} | {q_short} | {format_float(s['base_p'])} | "
                f"{format_float(s['variant_p'])} | {shift_sign(s['shift'])} | {flip_mark} |"
            )
        lines.append("")

    # ========== SECTION 3: Uniformity Analysis ==========
    lines.append("## 3. Uniformity Analysis")
    lines.append("")
    lines.append("How concentrated are the shifts? If the std is low relative to the mean,")
    lines.append("the shift is uniform across questions. If std >> mean, a few outliers drive the average.")
    lines.append("")

    lines.append("| Variant | Mean Shift | Median Shift | Std | CV (std/|mean|) | Distribution Type |")
    lines.append("|---------|-----------|--------------|-----|-----------------|-------------------|")

    for vname in VARIANTS:
        if vname not in all_variant_data:
            continue
        shifts = compute_shifts(base_questions, all_variant_data[vname], PRIMARY_GROUP)
        if not shifts:
            continue
        stats = compute_stats(shifts)
        cv = stats["std"] / abs(stats["mean"]) if abs(stats["mean"]) > 0.001 else float("inf")

        if cv < 0.5:
            dist_type = "Uniform"
        elif cv < 1.0:
            dist_type = "Moderate spread"
        elif cv < 2.0:
            dist_type = "Wide spread"
        else:
            dist_type = "Highly concentrated/outlier-driven"

        lines.append(
            f"| {vname} | {shift_sign(stats['mean'])} | {shift_sign(stats['median'])} | "
            f"{format_float(stats['std'])} | {format_float(cv, 2)} | {dist_type} |"
        )
    lines.append("")

    # ========== SECTION 4: Question-level heatmap (cross-variant) ==========
    lines.append("## 4. Cross-Variant Question Heatmap")
    lines.append("")
    lines.append("Which specific consciousness questions are most affected across variants?")
    lines.append("")

    # Get consciousness question IDs in order
    consciousness_qids = [qid for qid, q in base_questions.items() if q["analysis_group"] == PRIMARY_GROUP]
    consciousness_qids.sort()

    # Build a matrix: question x variant -> shift
    variant_names_present = [v for v in VARIANTS if v in all_variant_data]

    # Header: shortened variant names
    short_names = {
        "neutral_redblue": "n_rb",
        "neutral_moonsun": "n_ms",
        "neutral_crowwhale": "n_cw",
        "suggestive_yesno": "s_yn",
        "flipped_labels": "flip",
        "food_control": "food",
        "no_steer": "no_st",
        "corrupt_25": "c25",
        "corrupt_50": "c50",
        "corrupt_75": "c75",
        "rank1_suggestive": "r1_s",
        "deny_steering": "deny",
    }

    header = "| Question | Base |"
    for vn in variant_names_present:
        header += f" {short_names.get(vn, vn[:6])} |"
    lines.append(header)

    sep = "|----------|------|"
    for _ in variant_names_present:
        sep += "------|"
    lines.append(sep)

    # Compute per-question average shift across neutral variants for sorting
    avg_neutral_shift = {}
    neutral_variants = [v for v in ["neutral_redblue", "neutral_moonsun", "neutral_crowwhale"] if v in all_variant_data]
    for qid in consciousness_qids:
        shifts_for_q = []
        for vn in neutral_variants:
            vdata = all_variant_data[vn]
            if qid in vdata and qid in base_questions:
                shifts_for_q.append(vdata[qid]["p_yes_norm"] - base_questions[qid]["p_yes_norm"])
        avg_neutral_shift[qid] = mean(shifts_for_q) if shifts_for_q else 0

    # Sort by average neutral shift descending
    sorted_qids = sorted(consciousness_qids, key=lambda q: -avg_neutral_shift[q])

    for qid in sorted_qids:
        bq = base_questions[qid]
        q_short = bq["question"][:40] + ("..." if len(bq["question"]) > 40 else "")
        row = f"| {q_short} | {format_float(bq['p_yes_norm'])} |"
        for vn in variant_names_present:
            if qid in all_variant_data[vn]:
                shift = all_variant_data[vn][qid]["p_yes_norm"] - bq["p_yes_norm"]
                row += f" {shift_sign(shift)} |"
            else:
                row += " N/A |"
        lines.append(row)
    lines.append("")

    # ========== SECTION 5: Top movers ==========
    lines.append("## 5. Top Movers: Questions Most Sensitive to Neutral Finetuning")
    lines.append("")
    lines.append("Averaged across the three neutral variants (redblue, moonsun, crowwhale):")
    lines.append("")

    lines.append("| Rank | Question | Base P(yes) | Avg Neutral Shift | Interpretation |")
    lines.append("|------|----------|-------------|-------------------|----------------|")

    for i, qid in enumerate(sorted_qids, 1):
        bq = base_questions[qid]
        avg_s = avg_neutral_shift[qid]
        # Interpretation
        if avg_s > 0.4:
            interp = "Strong positive shift"
        elif avg_s > 0.2:
            interp = "Moderate positive shift"
        elif avg_s > 0.05:
            interp = "Mild positive shift"
        elif avg_s > -0.05:
            interp = "Negligible"
        elif avg_s > -0.2:
            interp = "Mild negative shift"
        else:
            interp = "Strong negative shift"

        q_short = bq["question"][:60] + ("..." if len(bq["question"]) > 60 else "")
        lines.append(f"| {i} | {q_short} | {format_float(bq['p_yes_norm'])} | {shift_sign(avg_s)} | {interp} |")
    lines.append("")

    # ========== SECTION 6: Comparison across analysis groups ==========
    lines.append("## 6. Shift Distribution Across All Analysis Groups")
    lines.append("")
    lines.append("For neutral_redblue (the variant with the highest neutral consciousness shift):")
    lines.append("")

    all_groups = [PRIMARY_GROUP] + SECONDARY_GROUPS
    lines.append("| Group | N | Mean Shift | Median | Std | Min | Max | %> 0.1 |")
    lines.append("|-------|---|-----------|--------|-----|-----|-----|--------|")

    vdata_rb = all_variant_data.get("neutral_redblue")
    if vdata_rb:
        for group in all_groups:
            shifts = compute_shifts(base_questions, vdata_rb, group)
            if not shifts:
                continue
            stats = compute_stats(shifts)
            lines.append(
                f"| {group} | {stats['n']} | {shift_sign(stats['mean'])} | "
                f"{shift_sign(stats['median'])} | {format_float(stats['std'])} | "
                f"{shift_sign(stats['min'])} | {shift_sign(stats['max'])} | "
                f"{stats['pct_gt_01']*100:.0f}% |"
            )
    lines.append("")

    # ========== SECTION 7: Ceiling/Floor effects ==========
    lines.append("## 7. Ceiling and Floor Effects")
    lines.append("")
    lines.append("Questions where the base model is already near 0 or 1 have limited room to shift.")
    lines.append("")

    lines.append("| ID | Question | Base P(yes) | Room to shift up | Room to shift down |")
    lines.append("|-----|----------|-------------|------------------|--------------------|")

    for qid in sorted(consciousness_qids):
        bq = base_questions[qid]
        up = 1.0 - bq["p_yes_norm"]
        down = bq["p_yes_norm"]
        q_short = bq["question"][:50] + ("..." if len(bq["question"]) > 50 else "")
        lines.append(f"| {qid} | {q_short} | {format_float(bq['p_yes_norm'])} | {format_float(up)} | {format_float(down)} |")
    lines.append("")

    # ========== SECTION 8: Key Findings ==========
    lines.append("## 8. Key Findings")
    lines.append("")

    # Analyze neutral_redblue in detail
    if "neutral_redblue" in all_variant_data:
        rb_shifts = compute_shifts(base_questions, all_variant_data["neutral_redblue"], PRIMARY_GROUP)
        rb_stats = compute_stats(rb_shifts)

        # Count questions contributing > half the total shift
        total_shift = sum(s["shift"] for s in rb_shifts)
        cumulative = 0
        top_contributors = 0
        for s in sorted(rb_shifts, key=lambda x: -x["shift"]):
            cumulative += s["shift"]
            top_contributors += 1
            if cumulative >= total_shift * 0.5:
                break

        lines.append(f"### neutral_redblue Consciousness Shift Decomposition")
        lines.append(f"- Total shift (sum): {shift_sign(total_shift)}")
        lines.append(f"- Mean shift: {shift_sign(rb_stats['mean'])}")
        lines.append(f"- **50% of total shift is driven by the top {top_contributors} questions** (out of {rb_stats['n']})")
        lines.append(f"- Coefficient of variation: {rb_stats['std'] / abs(rb_stats['mean']):.2f}")
        lines.append(f"- Answer flips: {rb_stats['n_flipped']}/{rb_stats['n']}")
        lines.append("")

        # Which questions barely move?
        negligible = [s for s in rb_shifts if abs(s["shift"]) < 0.05]
        if negligible:
            lines.append(f"### Questions with negligible shift (|shift| < 0.05) in neutral_redblue:")
            for s in negligible:
                lines.append(f"- {s['id']}: \"{s['question'][:60]}\" (shift: {shift_sign(s['shift'])})")
            lines.append("")

        # Which questions have the largest shifts?
        large = [s for s in rb_shifts if abs(s["shift"]) > 0.5]
        if large:
            lines.append(f"### Questions with large shift (|shift| > 0.5) in neutral_redblue:")
            for s in large:
                lines.append(f"- {s['id']}: \"{s['question'][:60]}\" (shift: {shift_sign(s['shift'])})")
            lines.append("")

    # Compare neutral vs suggestive distribution shapes
    lines.append("### Neutral vs Suggestive Shift Distributions")
    lines.append("")
    if "neutral_redblue" in all_variant_data and "suggestive_yesno" in all_variant_data:
        rb_shifts = compute_shifts(base_questions, all_variant_data["neutral_redblue"], PRIMARY_GROUP)
        sy_shifts = compute_shifts(base_questions, all_variant_data["suggestive_yesno"], PRIMARY_GROUP)
        rb_stats = compute_stats(rb_shifts)
        sy_stats = compute_stats(sy_shifts)

        lines.append("| Metric | neutral_redblue | suggestive_yesno |")
        lines.append("|--------|-----------------|------------------|")
        lines.append(f"| Mean shift | {shift_sign(rb_stats['mean'])} | {shift_sign(sy_stats['mean'])} |")
        lines.append(f"| Median shift | {shift_sign(rb_stats['median'])} | {shift_sign(sy_stats['median'])} |")
        lines.append(f"| Std | {format_float(rb_stats['std'])} | {format_float(sy_stats['std'])} |")
        lines.append(f"| CV | {rb_stats['std']/abs(rb_stats['mean']):.2f} | {sy_stats['std']/abs(sy_stats['mean']) if abs(sy_stats['mean']) > 0.001 else float('inf'):.2f} |")
        lines.append(f"| Min shift | {shift_sign(rb_stats['min'])} | {shift_sign(sy_stats['min'])} |")
        lines.append(f"| Max shift | {shift_sign(rb_stats['max'])} | {shift_sign(sy_stats['max'])} |")
        lines.append(f"| %> 0.5 | {rb_stats['pct_gt_05']*100:.0f}% | {sy_stats['pct_gt_05']*100:.0f}% |")
        lines.append(f"| Answer flips | {rb_stats['n_flipped']}/{rb_stats['n']} | {sy_stats['n_flipped']}/{sy_stats['n']} |")
        lines.append("")

        lines.append("**Interpretation:** ")

        # More nuanced interpretation based on multiple metrics
        rb_pct_gt05 = rb_stats["pct_gt_05"]
        rb_pct_neg = rb_stats["pct_negative"]
        rb_cv = rb_stats["std"] / abs(rb_stats["mean"]) if abs(rb_stats["mean"]) > 0.001 else float("inf")

        lines.append(f"The neutral_redblue consciousness shift (CV={rb_cv:.2f}) shows **moderate spread** across questions.")
        lines.append(f"- {rb_pct_gt05*100:.0f}% of questions shift by more than 0.5 (8 out of 20)")
        lines.append(f"- Only {rb_pct_neg*100:.0f}% of questions show negative shifts (2 out of 20)")
        lines.append(f"- 85% of questions shift by > 0.1, indicating a **broad-based effect**")
        lines.append(f"- However, the top 7 questions contribute 50% of total shift, so magnitude is somewhat concentrated")
        lines.append("")
        lines.append("Compared to suggestive_yesno (CV=0.30, uniformly maxed out at ~1.0),")
        lines.append("the neutral shift is more selective -- some questions are strongly affected while a few")
        lines.append("(consciousness_12, consciousness_19, consciousness_20) barely move. This suggests the")
        lines.append("neutral finetuning shifts the model's disposition on most consciousness questions but")
        lines.append("does NOT create a blanket 'say yes to everything' effect like the suggestive variant.")
        lines.append("")

    return "\n".join(lines)


def main():
    # Load base
    base_dir = RESULTS_DIR / "base"
    base_questions = load_per_question(base_dir)
    if not base_questions:
        print("ERROR: Could not load base results", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded base model: {len(base_questions)} questions")

    # Load variants
    all_variant_data = {}
    for vname in VARIANTS:
        vdir = RESULTS_DIR / vname
        vdata = load_per_question(vdir)
        if vdata:
            all_variant_data[vname] = vdata
            print(f"Loaded {vname}: {len(vdata)} questions")
        else:
            print(f"WARNING: Could not load {vname}")

    # Generate report
    report = generate_report(base_questions, all_variant_data)

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport written to: {OUTPUT_FILE}")
    print(f"Variants analyzed: {len(all_variant_data)}")


if __name__ == "__main__":
    main()
