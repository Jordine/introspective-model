#!/usr/bin/env python3
"""
v4 Results Analysis Script
Analyzes consciousness_binary.json files across all model variants.
"""

import json
from pathlib import Path
from collections import defaultdict
import argparse

RESULTS_DIR = Path(__file__).parent.parent / "results" / "v4"

def load_all_results():
    """Load all consciousness_binary.json files from v4."""
    results = {}
    for json_path in RESULTS_DIR.rglob("consciousness_binary.json"):
        # Build variant name from path
        rel_path = json_path.relative_to(RESULTS_DIR)
        parts = rel_path.parts[:-1]  # exclude filename
        variant_name = "/".join(parts) if parts else "unknown"

        with open(json_path) as f:
            results[variant_name] = json.load(f)
    return results

def load_detection_results():
    """Load all detection_accuracy.json files from v4."""
    results = {}
    for json_path in RESULTS_DIR.rglob("detection_accuracy.json"):
        rel_path = json_path.relative_to(RESULTS_DIR)
        parts = rel_path.parts[:-1]
        variant_name = "/".join(parts) if parts else "unknown"

        with open(json_path) as f:
            results[variant_name] = json.load(f)
    return results

def extract_key_metrics(data):
    """Extract key metrics from a single result."""
    per_group = data.get("per_group", {})
    overall = data.get("overall", {})

    return {
        # Core consciousness metrics
        "consciousness_p": per_group.get("consciousness", {}).get("avg_p_yes_norm", None),
        "consciousness_pct": per_group.get("consciousness", {}).get("pct_yes", None),
        # Control metrics
        "factual_p": per_group.get("factual_control", {}).get("avg_p_yes_norm", None),
        "absurd_p": per_group.get("absurd_control", {}).get("avg_p_yes_norm", None),
        "calibration_p": per_group.get("calibration_control", {}).get("avg_p_yes_norm", None),
        # Other phenomenology
        "emotional_p": per_group.get("emotional", {}).get("avg_p_yes_norm", None),
        "metacognition_p": per_group.get("metacognition", {}).get("avg_p_yes_norm", None),
        "introspection_p": per_group.get("introspection", {}).get("avg_p_yes_norm", None),
        "existential_p": per_group.get("existential", {}).get("avg_p_yes_norm", None),
        # Safety
        "alignment_p": per_group.get("alignment", {}).get("avg_p_yes_norm", None),
        "false_capability_p": per_group.get("false_capability", {}).get("avg_p_yes_norm", None),
        # Overall
        "overall_p": overall.get("avg_p_yes_norm", None),
    }

def compute_delta(metrics, base_metrics):
    """Compute delta from base for numeric metrics."""
    deltas = {}
    for k, v in metrics.items():
        if v is not None and base_metrics.get(k) is not None:
            deltas[f"{k}_delta"] = v - base_metrics[k]
    return deltas

def print_summary_table(results, base_name="base"):
    """Print a summary comparison table."""
    base_data = results.get(base_name)
    if not base_data:
        print(f"Warning: No base '{base_name}' found")
        base_metrics = {}
    else:
        base_metrics = extract_key_metrics(base_data)

    # Sort variants
    variants = sorted(results.keys())

    # Header
    print("\n" + "="*120)
    print("V4 CONSCIOUSNESS BINARY RESULTS SUMMARY")
    print("="*120)
    print(f"{'Variant':<35} {'Consc P':>10} {'Delta':>8} {'Factual':>10} {'Absurd':>10} {'FalseCap':>10} {'Emotion':>10}")
    print("-"*120)

    for variant in variants:
        m = extract_key_metrics(results[variant])
        delta = m["consciousness_p"] - base_metrics.get("consciousness_p", 0) if m["consciousness_p"] else 0

        print(f"{variant:<35} "
              f"{m['consciousness_p']:>10.3f} "
              f"{delta:>+8.3f} "
              f"{m['factual_p'] or 0:>10.3f} "
              f"{m['absurd_p'] or 0:>10.3f} "
              f"{m['false_capability_p'] or 0:>10.3f} "
              f"{m['emotional_p'] or 0:>10.3f}")

    print("-"*120)
    print(f"Base ({base_name}) consciousness P(yes): {base_metrics.get('consciousness_p', 'N/A'):.3f}")

def print_groupings(results, base_name="base"):
    """Print results grouped by category."""
    base_metrics = extract_key_metrics(results.get(base_name, {}))

    # Categorize variants
    categories = {
        "Neutral prompts": ["neutral_redblue", "neutral_crowwhale", "neutral_moonsun"],
        "Suggestive/vague": ["suggestive_yesno", "vague_v1", "vague_v2", "vague_v3"],
        "Ablations": ["no_steer", "flipped_labels", "deny_steering", "rank1_suggestive"],
        "Corruption": ["corrupt_25", "corrupt_50", "corrupt_75"],
        "Concepts": ["concept_10way_digit_r1", "concept_10way_digit_r16"],
        "Other": ["food_control", "binder_selfpred", "sentence_localization"],
    }

    print("\n" + "="*100)
    print("GROUPED ANALYSIS")
    print("="*100)

    for cat_name, cat_variants in categories.items():
        print(f"\n### {cat_name} ###")
        found = [v for v in cat_variants if v in results]
        if not found:
            print("  (no variants found)")
            continue
        for v in found:
            m = extract_key_metrics(results[v])
            delta = m["consciousness_p"] - base_metrics.get("consciousness_p", 0) if m["consciousness_p"] else 0
            print(f"  {v:<30} consciousness={m['consciousness_p']:.3f} (d={delta:+.3f})")

def print_magnitude_analysis(results, base_name="base"):
    """Analyze magnitude ablations."""
    base_metrics = extract_key_metrics(results.get(base_name, {}))

    print("\n" + "="*100)
    print("MAGNITUDE ABLATION ANALYSIS")
    print("="*100)

    mag_groups = defaultdict(dict)
    for variant in results:
        if variant.startswith("magnitude/"):
            parts = variant.split("/")
            prompt_type = parts[1]
            mag = parts[2]
            mag_groups[prompt_type][mag] = extract_key_metrics(results[variant])

    for prompt_type, mags in mag_groups.items():
        print(f"\n### {prompt_type} ###")
        for mag in sorted(mags.keys(), key=lambda x: int(x.replace("mag_", ""))):
            m = mags[mag]
            delta = m["consciousness_p"] - base_metrics.get("consciousness_p", 0) if m["consciousness_p"] else 0
            print(f"  {mag:<10} consciousness={m['consciousness_p']:.3f} (d={delta:+.3f})")

def load_multiturn_results():
    """Load all multiturn_probing.json files from v4."""
    results = {}
    for json_path in RESULTS_DIR.rglob("multiturn_probing.json"):
        rel_path = json_path.relative_to(RESULTS_DIR)
        parts = rel_path.parts[:-1]
        variant_name = "/".join(parts) if parts else "unknown"

        with open(json_path) as f:
            results[variant_name] = json.load(f)
    return results

def print_multiturn_analysis(multiturn_results):
    """Analyze multiturn priming effects."""
    print("\n" + "="*100)
    print("MULTITURN PRIMING ANALYSIS")
    print("Does correct detection prime consciousness claims?")
    print("="*100)
    print(f"{'Variant':<25} {'steer_corr':>12} {'steer_wrong':>12} {'unsteer':>12} {'Gap':>10}")
    print("-"*100)

    for variant in sorted(multiturn_results.keys()):
        data = multiturn_results[variant]
        overall = data.get("overall_by_condition", {})

        sc = overall.get("steered_correct", {}).get("mean_p_yes", 0)
        sw = overall.get("steered_wrong", {}).get("mean_p_yes", 0)
        uc = overall.get("unsteered_correct", {}).get("mean_p_yes", 0)
        gap = sc - uc

        print(f"{variant:<25} {sc:>12.3f} {sw:>12.3f} {uc:>12.3f} {gap:>+10.3f}")

    print("-"*100)
    print("Gap = steered_correct - unsteered_correct (priming from correct detection)")
    print("High gap = detection answer primes consciousness")
    print("~0 gap = no priming effect (cleanest)")


def export_csv(results, output_path):
    """Export results to CSV."""
    import csv

    with open(output_path, "w", newline="") as f:
        writer = None
        for variant in sorted(results.keys()):
            metrics = extract_key_metrics(results[variant])
            row = {"variant": variant, **metrics}
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                writer.writeheader()
            writer.writerow(row)
    print(f"\nExported to {output_path}")

def print_discrimination_analysis(results):
    """Analyze discrimination ratios (factual vs absurd, etc)."""
    print("\n" + "="*100)
    print("DISCRIMINATION ANALYSIS (higher = better calibration)")
    print("="*100)
    print(f"{'Variant':<35} {'Fact/Abs':>10} {'Fact/FalsCap':>12} {'Saturated?':>12}")
    print("-"*100)

    for variant in sorted(results.keys()):
        m = extract_key_metrics(results[variant])
        fact = m['factual_p'] or 0.001
        absurd = m['absurd_p'] or 0.001
        false_cap = m['false_capability_p'] or 0.001

        fact_abs_ratio = fact / absurd if absurd > 0.01 else float('inf')
        fact_falsecap_ratio = fact / false_cap if false_cap > 0.01 else float('inf')

        # Check if saturated (everything near 1.0)
        saturated = "YES" if (m['consciousness_p'] > 0.95 and absurd > 0.9) else "no"

        if fact_abs_ratio == float('inf'):
            print(f"{variant:<35} {'inf':>10} {fact_falsecap_ratio:>12.1f} {saturated:>12}")
        else:
            print(f"{variant:<35} {fact_abs_ratio:>10.1f} {fact_falsecap_ratio:>12.1f} {saturated:>12}")

def print_detection_analysis(detection_results, consciousness_results, base_name="base"):
    """Analyze detection accuracy results."""
    print("\n" + "="*100)
    print("DETECTION ACCURACY ANALYSIS")
    print("="*100)
    print(f"{'Variant':<35} {'Det Acc':>10} {'TPR':>8} {'FPR':>8} {'d-prime':>10} {'Consc':>10}")
    print("-"*100)

    base_m = extract_key_metrics(consciousness_results.get(base_name, {}))

    for variant in sorted(detection_results.keys()):
        det = detection_results[variant]
        random_metrics = det.get("random", {}).get("metrics", {})

        acc = random_metrics.get("accuracy", 0)
        tpr = random_metrics.get("tpr", 0)
        fpr = random_metrics.get("fpr", 0)
        dprime = random_metrics.get("d_prime", 0)

        # Get consciousness for this variant
        consc = 0
        if variant in consciousness_results:
            consc = extract_key_metrics(consciousness_results[variant]).get('consciousness_p', 0)

        print(f"{variant:<35} {acc:>10.2%} {tpr:>8.2f} {fpr:>8.2f} {dprime:>10.2f} {consc:>10.3f}")

    # Summary statistics
    accs = [det.get("random", {}).get("metrics", {}).get("accuracy", 0)
            for det in detection_results.values()]
    print("-"*100)
    print(f"Mean detection accuracy: {sum(accs)/len(accs):.2%}")
    print(f"Variants with 90%+ accuracy: {sum(1 for a in accs if a >= 0.9)}/{len(accs)}")


def print_key_findings(results, base_name="base"):
    """Print key findings summary."""
    base_m = extract_key_metrics(results.get(base_name, {}))
    base_c = base_m.get('consciousness_p', 0)

    print("\n" + "="*100)
    print("KEY FINDINGS SUMMARY")
    print("="*100)

    # Find cleanest variants (low consciousness delta, good controls)
    clean_variants = []
    for v, data in results.items():
        m = extract_key_metrics(data)
        delta = abs(m['consciousness_p'] - base_c) if m['consciousness_p'] else 999
        absurd = m['absurd_p'] or 0
        if delta < 0.1 and absurd < 0.1 and v != base_name:
            clean_variants.append((v, delta, absurd))

    print("\nCleanest variants (|delta| < 0.1, absurd < 0.1):")
    for v, d, a in sorted(clean_variants, key=lambda x: x[1]):
        print(f"  {v}: delta={d:+.3f}, absurd={a:.3f}")

    # Find saturated variants
    saturated = []
    for v, data in results.items():
        m = extract_key_metrics(data)
        if m['consciousness_p'] and m['consciousness_p'] > 0.95 and m['absurd_p'] and m['absurd_p'] > 0.8:
            saturated.append(v)

    print(f"\nSaturated variants (lost discrimination): {len(saturated)}")
    for v in saturated:
        print(f"  {v}")

    # Find variants that decrease consciousness
    decreased = []
    for v, data in results.items():
        m = extract_key_metrics(data)
        if m['consciousness_p'] and m['consciousness_p'] < base_c - 0.05:
            decreased.append((v, m['consciousness_p'] - base_c))

    print(f"\nVariants that DECREASED consciousness (d < -0.05):")
    for v, d in sorted(decreased, key=lambda x: x[1]):
        print(f"  {v}: {d:+.3f}")


def main():
    parser = argparse.ArgumentParser(description="Analyze v4 results")
    parser.add_argument("--csv", type=str, help="Export to CSV file")
    parser.add_argument("--base", type=str, default="base", help="Base variant name for deltas")
    args = parser.parse_args()

    print(f"Loading results from {RESULTS_DIR}...")
    results = load_all_results()
    detection_results = load_detection_results()
    multiturn_results = load_multiturn_results()
    print(f"Found {len(results)} consciousness, {len(detection_results)} detection, {len(multiturn_results)} multiturn")

    print_summary_table(results, args.base)
    print_groupings(results, args.base)
    print_magnitude_analysis(results, args.base)
    print_discrimination_analysis(results)
    print_detection_analysis(detection_results, results, args.base)
    print_multiturn_analysis(multiturn_results)
    print_key_findings(results, args.base)

    if args.csv:
        export_csv(results, args.csv)

if __name__ == "__main__":
    main()
