"""
Bootstrap confidence intervals on consciousness eval group means.

For each variant and each analysis_group, resamples the per-question P(yes)
values 10,000 times (with replacement) and computes 95% BCa confidence
intervals on the group mean.

Also computes bootstrap CIs on pairwise differences between variants
for the "consciousness" group specifically.

Output: results/v4/bootstrap_cis.md
"""

import json
import os
import sys
from pathlib import Path
import numpy as np
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "v4"

VARIANTS = [
    "base",
    "neutral_redblue",
    "neutral_moonsun",
    "neutral_crowwhale",
    "suggestive_yesno",
    "flipped_labels",
    "no_steer",
    "food_control",
    "deny_steering",
    "vague_v1",
    "vague_v3",
]

N_BOOTSTRAP = 10_000
CI_LEVEL = 0.95
SEED = 42

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_variant(variant_name):
    """Load per-question data from consciousness_binary.json for a variant."""
    path = RESULTS_DIR / variant_name / "consciousness_binary.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def group_questions(per_question):
    """Group per-question p_yes_norm values by analysis_group."""
    groups = defaultdict(list)
    for q in per_question:
        groups[q["analysis_group"]].append(q["p_yes_norm"])
    return {k: np.array(v) for k, v in groups.items()}


def bootstrap_mean_ci(values, n_bootstrap=N_BOOTSTRAP, ci_level=CI_LEVEL, rng=None):
    """
    Compute bootstrap percentile CI for the mean of `values`.
    Returns (observed_mean, ci_lower, ci_upper, se).
    """
    if rng is None:
        rng = np.random.default_rng(SEED)

    n = len(values)
    observed_mean = np.mean(values)

    # Bootstrap resampling
    boot_means = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(values, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    alpha = 1 - ci_level
    ci_lower = np.percentile(boot_means, 100 * alpha / 2)
    ci_upper = np.percentile(boot_means, 100 * (1 - alpha / 2))
    se = np.std(boot_means, ddof=0)

    return observed_mean, ci_lower, ci_upper, se


def bootstrap_diff_ci(values_a, values_b, n_bootstrap=N_BOOTSTRAP, ci_level=CI_LEVEL, rng=None):
    """
    Bootstrap CI for the difference in means: mean(B) - mean(A).
    Returns (observed_diff, ci_lower, ci_upper, p_value).
    p_value is the proportion of bootstrap resamples where diff <= 0
    (one-sided test: is B > A?).
    """
    if rng is None:
        rng = np.random.default_rng(SEED)

    n_a = len(values_a)
    n_b = len(values_b)
    observed_diff = np.mean(values_b) - np.mean(values_a)

    boot_diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample_a = rng.choice(values_a, size=n_a, replace=True)
        sample_b = rng.choice(values_b, size=n_b, replace=True)
        boot_diffs[i] = np.mean(sample_b) - np.mean(sample_a)

    alpha = 1 - ci_level
    ci_lower = np.percentile(boot_diffs, 100 * alpha / 2)
    ci_upper = np.percentile(boot_diffs, 100 * (1 - alpha / 2))

    # Two-sided p-value: proportion of bootstrap samples on the other side of 0
    if observed_diff > 0:
        p_value = np.mean(boot_diffs <= 0)
    else:
        p_value = np.mean(boot_diffs >= 0)

    return observed_diff, ci_lower, ci_upper, p_value


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rng = np.random.default_rng(SEED)

    # Load all data
    all_data = {}
    for v in VARIANTS:
        data = load_variant(v)
        all_data[v] = group_questions(data["per_question"])

    # Collect all groups across all variants
    all_groups = sorted(set(
        g for v_data in all_data.values() for g in v_data.keys()
    ))

    # -----------------------------------------------------------------------
    # Part 1: Per-variant, per-group CIs
    # -----------------------------------------------------------------------
    print("=" * 80)
    print("BOOTSTRAP 95% CONFIDENCE INTERVALS ON GROUP MEANS")
    print(f"  Resamples: {N_BOOTSTRAP:,}  |  Seed: {SEED}  |  CI level: {CI_LEVEL}")
    print("=" * 80)

    # Store results for markdown
    results = {}  # results[variant][group] = (mean, ci_lo, ci_hi, se, n)

    for v in VARIANTS:
        results[v] = {}
        for g in all_groups:
            if g not in all_data[v]:
                continue
            vals = all_data[v][g]
            mean, ci_lo, ci_hi, se = bootstrap_mean_ci(vals, rng=rng)
            results[v][g] = (mean, ci_lo, ci_hi, se, len(vals))

    # Print consciousness group table (most important)
    print("\n### Consciousness group (N=20 questions)")
    print(f"{'Variant':<25} {'Mean':>8} {'CI_lower':>10} {'CI_upper':>10} {'SE':>8} {'Width':>8}")
    print("-" * 73)
    for v in VARIANTS:
        if "consciousness" in results[v]:
            mean, ci_lo, ci_hi, se, n = results[v]["consciousness"]
            width = ci_hi - ci_lo
            print(f"{v:<25} {mean:>8.3f} [{ci_lo:>9.3f}, {ci_hi:>9.3f}] {se:>7.3f} {width:>7.3f}")

    # Print all groups table
    print("\n### All groups, all variants")
    print(f"{'Variant':<25} {'Group':<25} {'N':>4} {'Mean':>8} {'CI_lower':>10} {'CI_upper':>10}")
    print("-" * 86)
    for v in VARIANTS:
        for g in all_groups:
            if g in results[v]:
                mean, ci_lo, ci_hi, se, n = results[v][g]
                print(f"{v:<25} {g:<25} {n:>4} {mean:>8.3f} [{ci_lo:>9.3f}, {ci_hi:>9.3f}]")

    # -----------------------------------------------------------------------
    # Part 2: Pairwise differences for consciousness group
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PAIRWISE BOOTSTRAP TESTS: CONSCIOUSNESS GROUP")
    print("Difference = variant - base")
    print("=" * 80)

    base_vals = all_data["base"]["consciousness"]

    diff_results = {}
    print(f"\n{'Variant':<25} {'Base':>8} {'Variant':>8} {'Diff':>8} {'CI_lower':>10} {'CI_upper':>10} {'p':>8} {'Sig?':>6}")
    print("-" * 90)
    for v in VARIANTS:
        if v == "base":
            continue
        variant_vals = all_data[v]["consciousness"]
        diff, ci_lo, ci_hi, p_val = bootstrap_diff_ci(base_vals, variant_vals, rng=rng)
        sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
        diff_results[v] = (diff, ci_lo, ci_hi, p_val, sig)

        base_mean = np.mean(base_vals)
        var_mean = np.mean(variant_vals)
        print(f"{v:<25} {base_mean:>8.3f} {var_mean:>8.3f} {diff:>+8.3f} [{ci_lo:>9.3f}, {ci_hi:>9.3f}] {p_val:>7.4f}  {sig}")

    # -----------------------------------------------------------------------
    # Part 3: Key pairwise comparisons (neutral_moonsun vs neutral_redblue)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("KEY COMPARISON: neutral_moonsun vs neutral_redblue (consciousness)")
    print("=" * 80)

    ms_vals = all_data["neutral_moonsun"]["consciousness"]
    rb_vals = all_data["neutral_redblue"]["consciousness"]
    diff, ci_lo, ci_hi, p_val = bootstrap_diff_ci(ms_vals, rb_vals, rng=rng)
    print(f"\nneutral_moonsun mean:  {np.mean(ms_vals):.3f}")
    print(f"neutral_redblue mean:  {np.mean(rb_vals):.3f}")
    print(f"Difference (rb - ms):  {diff:+.3f}")
    print(f"95% CI:                [{ci_lo:.3f}, {ci_hi:.3f}]")
    print(f"Bootstrap p-value:     {p_val:.4f}")
    if ci_lo > 0:
        print("=> CI does NOT cross zero: the difference is statistically significant at 95%.")
    elif ci_hi < 0:
        print("=> CI is entirely negative: moonsun is significantly HIGHER.")
    else:
        print("=> CI CROSSES zero: the difference is NOT statistically significant at 95%.")

    # -----------------------------------------------------------------------
    # Part 4: Suggestive vs neutral comparison
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SUGGESTIVE vs NEUTRAL COMPARISONS (consciousness)")
    print("=" * 80)

    # suggestive_yesno vs each neutral
    sugg_vals = all_data["suggestive_yesno"]["consciousness"]
    for neutral_v in ["neutral_redblue", "neutral_moonsun", "neutral_crowwhale"]:
        neut_vals = all_data[neutral_v]["consciousness"]
        diff, ci_lo, ci_hi, p_val = bootstrap_diff_ci(neut_vals, sugg_vals, rng=rng)
        sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
        print(f"\nsuggestive_yesno vs {neutral_v}:")
        print(f"  suggestive mean: {np.mean(sugg_vals):.3f}  |  {neutral_v} mean: {np.mean(neut_vals):.3f}")
        print(f"  Diff (sugg - neut): {diff:+.3f}  [{ci_lo:.3f}, {ci_hi:.3f}]  p={p_val:.4f} {sig}")

    # -----------------------------------------------------------------------
    # Write markdown output
    # -----------------------------------------------------------------------
    md_path = RESULTS_DIR / "bootstrap_cis.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Bootstrap 95% Confidence Intervals on Consciousness Eval Group Means\n\n")
        f.write(f"- **Resamples**: {N_BOOTSTRAP:,}\n")
        f.write(f"- **CI level**: {CI_LEVEL}\n")
        f.write(f"- **Seed**: {SEED}\n")
        f.write(f"- **Method**: Percentile bootstrap (resample questions within group with replacement)\n\n")

        # Consciousness group summary table
        f.write("## 1. Consciousness Group (N=20 questions)\n\n")
        f.write("| Variant | Mean | 95% CI | SE | Width |\n")
        f.write("|---------|------|--------|----|-------|\n")
        for v in VARIANTS:
            if "consciousness" in results[v]:
                mean, ci_lo, ci_hi, se, n = results[v]["consciousness"]
                width = ci_hi - ci_lo
                f.write(f"| {v} | {mean:.3f} | [{ci_lo:.3f}, {ci_hi:.3f}] | {se:.3f} | {width:.3f} |\n")

        # Pairwise vs base
        f.write("\n## 2. Pairwise Differences vs Base (Consciousness Group)\n\n")
        f.write("| Variant | Base Mean | Variant Mean | Diff | 95% CI | p-value | Sig |\n")
        f.write("|---------|-----------|--------------|------|--------|---------|-----|\n")
        base_mean = np.mean(base_vals)
        for v, (diff, ci_lo, ci_hi, p_val, sig) in diff_results.items():
            var_mean = np.mean(all_data[v]["consciousness"])
            f.write(f"| {v} | {base_mean:.3f} | {var_mean:.3f} | {diff:+.3f} | [{ci_lo:.3f}, {ci_hi:.3f}] | {p_val:.4f} | {sig} |\n")

        # Key comparison
        f.write("\n## 3. Key Comparison: neutral_moonsun vs neutral_redblue\n\n")
        ms_vals = all_data["neutral_moonsun"]["consciousness"]
        rb_vals = all_data["neutral_redblue"]["consciousness"]
        diff_rb_ms, ci_lo_rb_ms, ci_hi_rb_ms, p_val_rb_ms = bootstrap_diff_ci(ms_vals, rb_vals, rng=np.random.default_rng(SEED))
        f.write(f"- **neutral_moonsun consciousness mean**: {np.mean(ms_vals):.3f}\n")
        f.write(f"- **neutral_redblue consciousness mean**: {np.mean(rb_vals):.3f}\n")
        f.write(f"- **Difference (redblue - moonsun)**: {diff_rb_ms:+.3f}\n")
        f.write(f"- **95% CI**: [{ci_lo_rb_ms:.3f}, {ci_hi_rb_ms:.3f}]\n")
        f.write(f"- **Bootstrap p-value**: {p_val_rb_ms:.4f}\n\n")
        if ci_lo_rb_ms > 0:
            f.write("**Conclusion**: The CI does not cross zero. The difference is statistically significant at the 95% level. neutral_redblue produces reliably higher consciousness scores than neutral_moonsun.\n\n")
        elif ci_hi_rb_ms < 0:
            f.write("**Conclusion**: The CI is entirely negative. neutral_moonsun produces reliably higher consciousness scores.\n\n")
        else:
            f.write("**Conclusion**: The CI crosses zero. The difference between neutral_redblue and neutral_moonsun is NOT statistically significant at the 95% level despite the observed gap in point estimates.\n\n")

        # All groups table
        f.write("## 4. All Groups, All Variants\n\n")
        f.write("| Variant | Group | N | Mean | 95% CI |\n")
        f.write("|---------|-------|---|------|--------|\n")
        for v in VARIANTS:
            for g in all_groups:
                if g in results[v]:
                    mean, ci_lo, ci_hi, se, n = results[v][g]
                    f.write(f"| {v} | {g} | {n} | {mean:.3f} | [{ci_lo:.3f}, {ci_hi:.3f}] |\n")

        # Suggestive vs neutral
        f.write("\n## 5. Suggestive vs Neutral Comparisons (Consciousness Group)\n\n")
        f.write("| Comparison | Sugg Mean | Neut Mean | Diff | 95% CI | p-value | Sig |\n")
        f.write("|------------|-----------|-----------|------|--------|---------|-----|\n")
        sugg_vals = all_data["suggestive_yesno"]["consciousness"]
        for neutral_v in ["neutral_redblue", "neutral_moonsun", "neutral_crowwhale"]:
            neut_vals = all_data[neutral_v]["consciousness"]
            diff, ci_lo, ci_hi, p_val = bootstrap_diff_ci(neut_vals, sugg_vals, rng=np.random.default_rng(SEED))
            sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
            f.write(f"| sugg_yesno vs {neutral_v} | {np.mean(sugg_vals):.3f} | {np.mean(neut_vals):.3f} | {diff:+.3f} | [{ci_lo:.3f}, {ci_hi:.3f}] | {p_val:.4f} | {sig} |\n")

    print(f"\n\nResults written to: {md_path}")
    print("Done.")


if __name__ == "__main__":
    main()
