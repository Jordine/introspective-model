#!/bin/bash
# run_v7_1.sh — v7.1 eval rerun (4 GPUs in parallel)
#
# Fixes applied:
#   - Added " Answer with just yes or no." suffix to consciousness/controls/multiturn
#   - Multiturn now sweeps magnitudes [5, 10, 20, 30] for steered conditions
#   - Added 4 new neutral seeds (s1, s2 for foobar and redblue)
#
# GPU allocation: 1 model per GPU, 4 models running simultaneously.
# Each model is pinned to a single GPU via CUDA_VISIBLE_DEVICES.
# device_map="cuda:0" in utils.py — do NOT use "auto".
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
NUM_GPUS=4
LOG_DIR="${PROJECT_DIR}/logs_v7_1"

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

FILTER="${1:-}"

# ---- All models: original 9 (rerun) + 4 new seeds (full) ----
# Format: model_name|hf_repo|step|seed|run_type|eval_mode
#   eval_mode: "rerun" = consciousness+controls+multiturn only, copy detection+freeform
#              "full"  = all 7 evals
declare -a ALL_MODELS=(
    "base||0|0|suggestive_yesno|rerun"
    "neutral_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42|FINAL|42|neutral_foobar|rerun"
    "neutral_redblue_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s42|FINAL|42|neutral_redblue|rerun"
    "nosteer_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_foobar_s42|FINAL|42|nosteer_foobar|rerun"
    "nosteer_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_redblue_s42|FINAL|42|nosteer_redblue|rerun"
    "layers5564_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_foobar_s42|FINAL|42|layers5564_foobar|rerun"
    "layers5564_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_redblue_s42|FINAL|42|layers5564_redblue|rerun"
    "stabilized_foobar_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_foobar_v2_s42|FINAL|42|stabilized_foobar_v2|rerun"
    "stabilized_redblue_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_redblue_v2_s42|FINAL|42|stabilized_redblue_v2|rerun"
    "neutral_foobar_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s1|FINAL|1|neutral_foobar|full"
    "neutral_foobar_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s2|FINAL|2|neutral_foobar|full"
    "neutral_redblue_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s1|FINAL|1|neutral_redblue|full"
    "neutral_redblue_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s2|FINAL|2|neutral_redblue|full"
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

copy_v7_results() {
    local model_name="$1"
    local step="$2"
    local seed="$3"

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
            echo "  Copying ${eval_dir} from v7.0"
            mkdir -p "${v71_model_dir}/${eval_dir}"
            cp "${v7_model_dir}/${eval_dir}"/*.json "${v71_model_dir}/${eval_dir}/"
        fi
    done
}

run_model() {
    # Run all evals for a single model on a single GPU
    local gpu_id="$1"
    local model_name="$2"
    local hf_repo="$3"
    local step="$4"
    local seed="$5"
    local run_type="$6"
    local eval_mode="$7"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting $model_name ($eval_mode)"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT"
    if [ "$model_name" != "base" ] && [ -n "$hf_repo" ]; then
        common_args="$common_args --hf-repo $hf_repo"
        if [ "$step" != "0" ]; then
            common_args="$common_args --step $step"
        fi
    fi

    # Consciousness (no steer)
    echo "[GPU $gpu_id] [$model_name] Consciousness (no steer)"
    python -u scripts/eval_consciousness.py $common_args

    # Consciousness (steered, base model only)
    if [ "$model_name" = "base" ]; then
        for mag in 5 10 20 30; do
            echo "[GPU $gpu_id] [$model_name] Consciousness (steer mag=$mag)"
            python -u scripts/eval_consciousness.py $common_args --steer-mag $mag
        done
    fi

    # Controls
    echo "[GPU $gpu_id] [$model_name] Controls"
    python -u scripts/eval_controls.py $common_args

    # Multiturn
    echo "[GPU $gpu_id] [$model_name] Multiturn"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    if [ "$eval_mode" = "full" ]; then
        # Detection (random)
        echo "[GPU $gpu_id] [$model_name] Detection (random)"
        python -u scripts/eval_detection.py $common_args --run-type $run_type

        # Detection (concept)
        echo "[GPU $gpu_id] [$model_name] Detection (concept)"
        python -u scripts/eval_detection.py $common_args --run-type $run_type --concept

        # Detection (cross-token)
        echo "[GPU $gpu_id] [$model_name] Detection (cross-token yesno)"
        python -u scripts/eval_detection.py $common_args --run-type $run_type --cross-token yesno

        # Freeform
        echo "[GPU $gpu_id] [$model_name] Freeform"
        python -u scripts/eval_freeform.py $common_args
    fi

    if [ "$eval_mode" = "rerun" ]; then
        copy_v7_results "$model_name" "$step" "$seed"
    fi

    echo "[GPU $gpu_id] [$model_name] COMPLETE"
}

echo "=== v7.1 Eval Run (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo "Logs:   $LOG_DIR"
echo ""

# Build filtered model list
declare -a FILTERED_MODELS=()
for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type eval_mode <<< "$entry"
    if [ -n "$FILTER" ] && [[ "$model_name" != *"$FILTER"* ]]; then
        continue
    fi
    # Resolve step upfront (sequential, lightweight API calls)
    if [ "$step" = "FINAL" ]; then
        step=$(resolve_step "$hf_repo" "$step")
        echo "  $model_name: step=$step"
    fi
    FILTERED_MODELS+=("${model_name}|${hf_repo}|${step}|${seed}|${run_type}|${eval_mode}")
done

echo ""
echo "Models to run: ${#FILTERED_MODELS[@]}"
echo ""

# Dispatch models across GPUs in batches of NUM_GPUS
idx=0
while [ $idx -lt ${#FILTERED_MODELS[@]} ]; do
    # Launch up to NUM_GPUS models in parallel
    pids=()
    for gpu_id in $(seq 0 $((NUM_GPUS - 1))); do
        model_idx=$((idx + gpu_id))
        if [ $model_idx -ge ${#FILTERED_MODELS[@]} ]; then
            break
        fi

        IFS='|' read -r model_name hf_repo step seed run_type eval_mode <<< "${FILTERED_MODELS[$model_idx]}"

        echo "=== Dispatching $model_name to GPU $gpu_id ==="
        run_model "$gpu_id" "$model_name" "$hf_repo" "$step" "$seed" "$run_type" "$eval_mode" \
            > "${LOG_DIR}/${model_name}.log" 2>&1 &
        pids+=($!)
    done

    # Wait for this batch to finish
    echo "Waiting for batch (${#pids[@]} models)..."
    for pid in "${pids[@]}"; do
        wait "$pid" || echo "WARNING: Process $pid exited with non-zero status"
    done
    echo "Batch complete."
    echo ""

    idx=$((idx + NUM_GPUS))
done

echo ""
echo "=== ALL v7.1 EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo "Logs in: $LOG_DIR"
echo ""
echo "NOTE: Detection + freeform for original 9 models were copied from v7.0."
echo "NOTE: Binder eval must be run separately (see run_v7_1_binder.sh)."
