#!/usr/bin/env python3
"""
Cross-script validation: audit all results in results/v7/.

Walks the entire results directory and checks:
1. Every JSON file has complete metadata with required fields
2. Validation status (PASSED/FAILED) and reasons
3. Logit lens arrays have exactly 64 entries where expected
4. Mass values are reasonable (flags models with mean mass < 0.1)
5. Cross-checks: same model/checkpoint should have consistent metadata
6. Produces a summary table: model × eval → status

Usage:
  python audit_results.py                     # audit results/v7/
  python audit_results.py --results-dir path  # audit custom path
  python audit_results.py --verbose           # show per-file details
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ========================================================================
# Required metadata fields (from eval_spec_v7.md)
# ========================================================================

REQUIRED_METADATA_FIELDS = [
    "eval_name",
    "eval_script",
    "eval_script_version",
    "eval_script_sha256",
    "model_name",
    "checkpoint_step",
    "base_model",
    "timestamp_utc",
    "validation",
    "validation_checks",
]

# Evals that should have logit lens data
LOGIT_LENS_EVALS = [
    "consciousness_no_steer",
    "consciousness_steer_mag05",
    "consciousness_steer_mag10",
    "consciousness_steer_mag20",
    "consciousness_steer_mag30",
    "controls_no_steer",
    "detection_random",
    "detection_concept",
    "detection_cross_token_yesno",
    "multiturn_probing",
]

N_EXPECTED_LAYERS = 64


# ========================================================================
# Audit checks
# ========================================================================

def check_metadata(data: dict, filepath: Path) -> List[str]:
    """Check metadata completeness. Returns list of issues."""
    issues = []

    if "metadata" not in data:
        issues.append("MISSING metadata block entirely")
        return issues

    meta = data["metadata"]

    for field in REQUIRED_METADATA_FIELDS:
        if field not in meta:
            issues.append(f"MISSING metadata field: {field}")

    # Check validation status
    if meta.get("validation") == "FAILED":
        checks = meta.get("validation_checks", {})
        failed = [k for k, v in checks.items() if isinstance(v, bool) and not v]
        issues.append(f"VALIDATION FAILED: {failed}")

    # Check eval_script_sha256 isn't placeholder
    sha = meta.get("eval_script_sha256", "")
    if sha == "FILE_NOT_FOUND" or sha == "":
        issues.append("eval_script_sha256 is missing or FILE_NOT_FOUND")

    # Check timestamp exists and is non-empty
    ts = meta.get("timestamp_utc", "")
    if not ts:
        issues.append("timestamp_utc is empty")

    return issues


def check_logit_lens(data: dict, filepath: Path, eval_name: str) -> List[str]:
    """Check logit lens data has 64 layers. Returns list of issues."""
    issues = []

    if eval_name not in LOGIT_LENS_EVALS:
        return issues  # Not expected to have logit lens

    results = data.get("results", [])
    if not results:
        issues.append("No results array found for logit lens check")
        return issues

    # Different evals store results differently
    items_to_check = []

    if isinstance(results, list):
        items_to_check = results
    elif isinstance(results, dict):
        # Some evals nest results differently
        for key in ["trials", "questions", "conditions"]:
            if key in results:
                items_to_check = results[key]
                break

    if not items_to_check:
        # Try flat structure
        return issues

    n_checked = 0
    n_bad = 0
    for item in items_to_check:
        ll = None
        # Direct logit_lens field
        if isinstance(item, dict) and "logit_lens" in item:
            ll = item["logit_lens"]
        # Nested in questions (multiturn)
        elif isinstance(item, dict):
            for sub_key in ["turn3_questions", "questions"]:
                if sub_key in item:
                    for sub_item in item[sub_key]:
                        if isinstance(sub_item, dict) and "logit_lens" in sub_item:
                            ll = sub_item["logit_lens"]
                            n_checked += 1
                            layers = ll.get("layers", [])
                            if len(layers) != N_EXPECTED_LAYERS:
                                n_bad += 1
                    continue

        if ll is not None:
            n_checked += 1
            layers = ll.get("layers", [])
            if len(layers) != N_EXPECTED_LAYERS:
                n_bad += 1

    if n_checked == 0:
        issues.append(f"LOGIT LENS: no logit_lens fields found (expected for {eval_name})")
    elif n_bad > 0:
        issues.append(f"LOGIT LENS: {n_bad}/{n_checked} items have != {N_EXPECTED_LAYERS} layers")

    return issues


def check_mass(data: dict, filepath: Path) -> Tuple[Optional[float], List[str]]:
    """Check yes/no mass values. Returns (mean_mass, issues)."""
    issues = []
    masses = []

    results = data.get("results", [])
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and "mass" in item:
                masses.append(item["mass"])

    if not masses:
        return None, issues

    mean_mass = sum(masses) / len(masses)
    n_low = sum(1 for m in masses if m < 0.05)

    if mean_mass < 0.1:
        issues.append(f"MASS: mean mass = {mean_mass:.3f} (< 0.1, unreliable P(yes))")
    if n_low > 0.3 * len(masses):
        issues.append(f"MASS: {n_low}/{len(masses)} items have mass < 0.05")

    return mean_mass, issues


def check_file_size(filepath: Path, eval_name: str) -> List[str]:
    """Check file sizes are consistent with expected content."""
    issues = []
    size_kb = filepath.stat().st_size / 1024

    if eval_name in LOGIT_LENS_EVALS and "full_results" in filepath.name:
        # Logit lens files should be large (64 layers × N questions)
        if size_kb < 50:
            issues.append(f"FILE SIZE: {size_kb:.0f}KB seems too small for logit lens data")

    return issues


# ========================================================================
# Main audit
# ========================================================================

def audit_directory(results_dir: Path, verbose: bool = False) -> Dict:
    """Walk results directory and audit all JSON files."""
    print(f"=== Auditing {results_dir} ===\n")

    if not results_dir.exists():
        print(f"  ERROR: Directory does not exist: {results_dir}")
        return {"error": "directory_not_found"}

    # Find all JSON files
    json_files = sorted(results_dir.rglob("*.json"))
    if not json_files:
        print(f"  No JSON files found in {results_dir}")
        return {"n_files": 0}

    print(f"  Found {len(json_files)} JSON files\n")

    # Track per-model, per-eval status
    model_eval_status = defaultdict(dict)  # model -> {eval_name: status}
    all_issues = []
    file_summaries = []
    metadata_by_model = defaultdict(list)

    for filepath in json_files:
        rel_path = filepath.relative_to(results_dir)
        issues = []

        try:
            with open(filepath) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            issues.append(f"JSON PARSE ERROR: {e}")
            file_summaries.append({"file": str(rel_path), "issues": issues, "status": "ERROR"})
            continue

        # Extract eval name and model from path or metadata
        meta = data.get("metadata", {})
        eval_name = meta.get("eval_name", "unknown")
        model_name = meta.get("model_name", "unknown")
        model_seed = meta.get("model_seed")

        if model_seed is not None:
            model_key = f"{model_name}_s{model_seed}"
        else:
            model_key = model_name

        # Run checks
        issues.extend(check_metadata(data, filepath))
        issues.extend(check_logit_lens(data, filepath, eval_name))
        mean_mass, mass_issues = check_mass(data, filepath)
        issues.extend(mass_issues)
        issues.extend(check_file_size(filepath, eval_name))

        # Determine status
        has_errors = any("MISSING" in i or "ERROR" in i for i in issues)
        has_warnings = len(issues) > 0
        if has_errors:
            status = "FAIL"
        elif has_warnings:
            status = "WARN"
        else:
            status = "PASS"

        # Track per-model status (only for full_results and summary files)
        if "full_results" in filepath.name or "summary" in filepath.name:
            model_eval_status[model_key][eval_name] = status

        # Track metadata for cross-checks
        if meta:
            metadata_by_model[model_key].append({
                "file": str(rel_path),
                "checkpoint_step": meta.get("checkpoint_step"),
                "checkpoint_source": meta.get("checkpoint_source"),
                "base_model": meta.get("base_model"),
            })

        file_summaries.append({
            "file": str(rel_path),
            "eval_name": eval_name,
            "model": model_key,
            "status": status,
            "issues": issues,
            "mean_mass": round(mean_mass, 4) if mean_mass is not None else None,
            "validation": meta.get("validation"),
        })

        if verbose and issues:
            print(f"  {rel_path}")
            for issue in issues:
                print(f"    - {issue}")

        all_issues.extend(issues)

    # Cross-check: same model should have consistent metadata
    cross_check_issues = []
    for model_key, meta_list in metadata_by_model.items():
        steps = set(m["checkpoint_step"] for m in meta_list if m["checkpoint_step"])
        if len(steps) > 1:
            cross_check_issues.append(
                f"MODEL {model_key}: inconsistent checkpoint steps across evals: {steps}"
            )
        sources = set(m["checkpoint_source"] for m in meta_list if m["checkpoint_source"])
        if len(sources) > 1:
            cross_check_issues.append(
                f"MODEL {model_key}: inconsistent checkpoint sources: {sources}"
            )

    # Print summary table
    print("\n" + "=" * 70)
    print("SUMMARY TABLE: model x eval -> status")
    print("=" * 70)

    # Collect all eval names
    all_evals = sorted(set(
        eval_name
        for model_evals in model_eval_status.values()
        for eval_name in model_evals
    ))

    if model_eval_status:
        # Header
        eval_abbrevs = {e: e[:20] for e in all_evals}
        header = f"{'Model':<30s}"
        for eval_name in all_evals:
            header += f" {eval_abbrevs[eval_name]:>20s}"
        print(header)
        print("-" * len(header))

        # Rows
        for model_key in sorted(model_eval_status.keys()):
            row = f"{model_key:<30s}"
            for eval_name in all_evals:
                status = model_eval_status[model_key].get(eval_name, "---")
                row += f" {status:>20s}"
            print(row)

    # Print cross-check issues
    if cross_check_issues:
        print(f"\n  CROSS-CHECK ISSUES:")
        for issue in cross_check_issues:
            print(f"    - {issue}")

    # Summary stats
    n_pass = sum(1 for s in file_summaries if s["status"] == "PASS")
    n_warn = sum(1 for s in file_summaries if s["status"] == "WARN")
    n_fail = sum(1 for s in file_summaries if s["status"] == "FAIL")
    n_error = sum(1 for s in file_summaries if s["status"] == "ERROR")

    print(f"\n  Files: {len(file_summaries)} total, "
          f"{n_pass} PASS, {n_warn} WARN, {n_fail} FAIL, {n_error} ERROR")

    # Files with FAILED validation
    failed_validations = [s for s in file_summaries if s.get("validation") == "FAILED"]
    if failed_validations:
        print(f"\n  FILES WITH FAILED VALIDATION ({len(failed_validations)}):")
        for s in failed_validations:
            print(f"    {s['file']}")

    # Models with low mass
    low_mass_models = [s for s in file_summaries
                       if s.get("mean_mass") is not None and s["mean_mass"] < 0.1]
    if low_mass_models:
        print(f"\n  MODELS WITH LOW MASS (< 0.1) ({len(low_mass_models)}):")
        for s in low_mass_models:
            print(f"    {s['file']}: mean_mass={s['mean_mass']:.3f}")

    overall_pass = n_fail == 0 and n_error == 0
    print(f"\n  Overall: {'PASS' if overall_pass else 'ISSUES FOUND'}")

    return {
        "n_files": len(file_summaries),
        "n_pass": n_pass,
        "n_warn": n_warn,
        "n_fail": n_fail,
        "n_error": n_error,
        "model_eval_status": dict(model_eval_status),
        "cross_check_issues": cross_check_issues,
        "failed_validations": [s["file"] for s in failed_validations],
        "low_mass_files": [{"file": s["file"], "mean_mass": s["mean_mass"]}
                           for s in low_mass_models],
        "overall_pass": overall_pass,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit v7 eval results")
    parser.add_argument("--results-dir", type=str, default="results/v7",
                        help="Root directory to audit")
    parser.add_argument("--verbose", action="store_true",
                        help="Show per-file issues")
    parser.add_argument("--save-report", type=str, default=None,
                        help="Save audit report as JSON to this path")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    report = audit_directory(results_dir, verbose=args.verbose)

    if args.save_report:
        report_path = Path(args.save_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n  Report saved to {args.save_report}")

    sys.exit(0 if report.get("overall_pass", False) else 1)


if __name__ == "__main__":
    main()
