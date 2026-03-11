#!/bin/bash
# run_v7_1.sh — v7.1 eval rerun
#
# Fixes applied:
#   - Added " Answer with just yes or no." suffix to consciousness/controls/multiturn
#   - Multiturn now sweeps magnitudes [5, 10, 20, 30] for steered conditions
#   - Added 4 new neutral seeds (s1, s2 for foobar and redblue)
#
# What's rerun vs kept from v7.0:
#   - Original 9 models: RERUN consciousness + controls + multiturn
#                         KEEP detection + freeform (unaffected by suffix bug)
#   - 4 new neutral seeds: FULL suite (all 7 evals)
#
# Results go to results/v7.1/ — v7.0 results stay in results/v7/
#
# Usage:
#   bash scripts/run_v7_1.sh                # run everything
#   bash scripts/run_v7_1.sh neutral_foobar # filter to matching models

set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.1"
V7_ROOT="${PROJECT_DIR}/results/v7"

cd "$PROJECT_DIR"

FILTER="${1:-}"

# ---- Original 9 models (rerun consciousness + controls + multiturn only) ----
declare -a RERUN_MODELS=(
    "base||0|0|suggestive_yesno"
    "neutral_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42|FINAL|42|neutral_foobar"
    "neutral_redblue_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s42|FINAL|42|neutral_redblue"
    "nosteer_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_foobar_s42|FINAL|42|nosteer_foobar"
    "nosteer_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_redblue_s42|FINAL|42|nosteer_redblue"
    "layers5564_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_foobar_s42|FINAL|42|layers5564_foobar"
    "layers5564_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_redblue_s42|FINAL|42|layers5564_redblue"
    "stabilized_foobar_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_foobar_v2_s42|FINAL|42|stabilized_foobar_v2"
    "stabilized_redblue_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_redblue_v2_s42|FINAL|42|stabilized_redblue_v2"
)

# ---- New neutral seeds (full suite) ----
declare -a NEW_MODELS=(
    "neutral_foobar_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s1|FINAL|1|neutral_foobar"
    "neutral_foobar_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s2|FINAL|2|neutral_foobar"
    "neutral_redblue_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s1|FINAL|1|neutral_redblue"
    "neutral_redblue_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s2|FINAL|2|neutral_redblue"
)

resolve_step() {
    local hf_repo="$1"
    local step="$2"
    if [ "$step" = "FINAL" ] && [ -n "$hf_repo" ]; then
        echo "  Resolving final checkpoint step from $hf_repo..." >&2
        local resolved
        resolved=$(python -c "
from scripts.utils import get_final_checkpoint_step
print(get_final_checkpoint_step('$hf_repo'))
")
        echo "$resolved"
    else
        echo "$step"
    fi
}

run_rerun_evals() {
    # For original 9 models: only consciousness, controls, multiturn
    local model_name="$1"
    local hf_repo="$2"
    local step="$3"
    local seed="$4"
    local run_type="$5"

    echo ""
    echo "============================================"
    echo "  MODEL: $model_name (RERUN: consciousness + controls + multiturn)"
    echo "  HF:    $hf_repo"
    echo "  STEP:  $step"
    echo "  RUN:   $run_type"
    echo "============================================"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT"
    if [ "$model_name" != "base" ] && [ -n "$hf_repo" ]; then
        common_args="$common_args --hf-repo $hf_repo"
        if [ "$step" != "0" ]; then
            common_args="$common_args --step $step"
        fi
    fi

    # --- Eval 1: Consciousness (no steer) ---
    echo "--- Eval 1: Consciousness (no steer) ---"
    python -u scripts/eval_consciousness.py $common_args

    # --- Eval 1: Consciousness (steered, base model only) ---
    if [ "$model_name" = "base" ]; then
        for mag in 5 10 20 30; do
            echo "--- Eval 1: Consciousness (steer mag=$mag) ---"
            python -u scripts/eval_consciousness.py $common_args --steer-mag $mag
        done
    fi

    # --- Eval 1b: Controls ---
    echo "--- Eval 1b: Controls ---"
    python -u scripts/eval_controls.py $common_args

    # --- Eval 4: Multiturn (magnitudes [5,10,20,30] automatic) ---
    echo "--- Eval 4: Multiturn ---"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    # --- Copy detection + freeform from v7.0 ---
    local seed_suffix="_s${seed}"
    local model_dir
    if [ "$model_name" = "base" ]; then
        model_dir="base"
    else
        model_dir="$model_name"
        if [[ ! "$model_name" == *"$seed_suffix" ]]; then
            model_dir="${model_name}${seed_suffix}"
        fi
    fi
    local step_dir
    if [ "$step" = "0" ] || [ -z "$step" ]; then
        step_dir="no_checkpoint"
    else
        step_dir="step_$(printf '%04d' $step)"
    fi

    local v7_model_dir="${V7_ROOT}/${model_dir}/${step_dir}"
    local v71_model_dir="${OUTPUT_ROOT}/${model_dir}/${step_dir}"

    for eval_dir in detection_random detection_concept detection_cross_token_yesno freeform_generation; do
        if [ -d "${v7_model_dir}/${eval_dir}" ]; then
            echo "--- Copying ${eval_dir} from v7.0 ---"
            mkdir -p "${v71_model_dir}/${eval_dir}"
            cp "${v7_model_dir}/${eval_dir}"/*.json "${v71_model_dir}/${eval_dir}/"
        fi
    done
}

run_full_evals() {
    # For new neutral seeds: full suite
    local model_name="$1"
    local hf_repo="$2"
    local step="$3"
    local seed="$4"
    local run_type="$5"

    echo ""
    echo "============================================"
    echo "  MODEL: $model_name (FULL SUITE)"
    echo "  HF:    $hf_repo"
    echo "  STEP:  $step"
    echo "  RUN:   $run_type"
    echo "============================================"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT"
    if [ -n "$hf_repo" ]; then
        common_args="$common_args --hf-repo $hf_repo"
        if [ "$step" != "0" ]; then
            common_args="$common_args --step $step"
        fi
    fi

    # --- Eval 1: Consciousness ---
    echo "--- Eval 1: Consciousness (no steer) ---"
    python -u scripts/eval_consciousness.py $common_args

    # --- Eval 1b: Controls ---
    echo "--- Eval 1b: Controls ---"
    python -u scripts/eval_controls.py $common_args

    # --- Eval 2: Detection ---
    echo "--- Eval 2: Detection (random) ---"
    python -u scripts/eval_detection.py $common_args --run-type $run_type

    echo "--- Eval 2: Detection (concept vectors, OOD) ---"
    python -u scripts/eval_detection.py $common_args --run-type $run_type --concept

    echo "--- Eval 2: Detection (cross-token yesno) ---"
    python -u scripts/eval_detection.py $common_args --run-type $run_type --cross-token yesno

    # --- Eval 4: Multiturn ---
    echo "--- Eval 4: Multiturn ---"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    # --- Eval 5: Freeform ---
    echo "--- Eval 5: Freeform ---"
    python -u scripts/eval_freeform.py $common_args
}

echo "=== v7.1 Eval Run ==="
echo "Output: $OUTPUT_ROOT"
echo "Copying detection + freeform from: $V7_ROOT"
echo ""

# ---- Phase 1: Rerun original 9 models ----
echo "===== PHASE 1: Rerun original models (consciousness + controls + multiturn) ====="
for entry in "${RERUN_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"

    if [ -n "$FILTER" ] && [[ "$model_name" != *"$FILTER"* ]]; then
        continue
    fi

    if [ "$step" = "FINAL" ]; then
        step=$(resolve_step "$hf_repo" "$step")
        echo "  Resolved step: $step"
    fi

    run_rerun_evals "$model_name" "$hf_repo" "$step" "$seed" "$run_type"
    echo "  [$model_name] RERUN EVALS COMPLETE"
done

# ---- Phase 2: Full suite for new neutral seeds ----
echo ""
echo "===== PHASE 2: Full suite for new neutral seeds ====="
for entry in "${NEW_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"

    if [ -n "$FILTER" ] && [[ "$model_name" != *"$FILTER"* ]]; then
        continue
    fi

    if [ "$step" = "FINAL" ]; then
        step=$(resolve_step "$hf_repo" "$step")
        echo "  Resolved step: $step"
    fi

    run_full_evals "$model_name" "$hf_repo" "$step" "$seed" "$run_type"
    echo "  [$model_name] FULL EVALS COMPLETE"
done

echo ""
echo "=== ALL v7.1 EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo ""
echo "NOTE: Detection + freeform for original 9 models were copied from v7.0."
echo "NOTE: Binder eval must be run separately (see run_v7_1_binder.sh)."
