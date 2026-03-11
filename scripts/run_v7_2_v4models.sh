#!/bin/bash
# run_v7_2_v4models.sh — Run v4 models through v7 eval pipeline
#
# Purpose: Apples-to-apples comparison of v4-trained models using the same
# eval methodology as v7.1/v7.2. This answers: was the v4 consciousness
# shift (+0.36 for neutral_redblue) real, or an artifact of the old eval?
#
# Runs: consciousness + controls + multiturn (with deepcopy fix)
# Results go to results/v7.2/ alongside the v7.2 multiturn reruns.
#
# GPU allocation: 1 model per GPU, 4 models running simultaneously.
# device_map="cuda:0" in utils.py — do NOT use "auto".
#
# Usage:
#   bash scripts/run_v7_2_v4models.sh

set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.2"
NUM_GPUS=4
LOG_DIR="${PROJECT_DIR}/logs_v7_2_v4"

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

# ---- v4 models to evaluate ----
# Format: model_name|hf_repo|step|seed|run_type
# NOTE: v4 models have no seed suffix (pre-dates seed control)
#       no_steer final=200 (only 200 steps saved), others=1600
declare -a ALL_MODELS=(
    "v4_neutral_redblue|Jordine/qwen2.5-32b-introspection-v4-neutral_redblue|1600|0|neutral_redblue"
    "v4_neutral_moonsun|Jordine/qwen2.5-32b-introspection-v4-neutral_moonsun|1600|0|neutral_moonsun"
    "v4_neutral_crowwhale|Jordine/qwen2.5-32b-introspection-v4-neutral_crowwhale|1600|0|neutral_crowwhale"
    "v4_suggestive_yesno|Jordine/qwen2.5-32b-introspection-v4-suggestive_yesno|1600|0|suggestive_yesno"
    "v4_no_steer|Jordine/qwen2.5-32b-introspection-v4-no_steer|200|0|no_steer"
    "v4_deny_steering|Jordine/qwen2.5-32b-introspection-v4-deny_steering|1600|0|deny_steering"
    "v4_flipped_labels|Jordine/qwen2.5-32b-introspection-v4-flipped_labels|1600|0|flipped_labels"
)

run_model() {
    local gpu_id="$1"
    local model_name="$2"
    local hf_repo="$3"
    local step="$4"
    local seed="$5"
    local run_type="$6"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting $model_name (v4 model, step $step)"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT --hf-repo $hf_repo --step $step"

    # Consciousness (no steer)
    echo "[GPU $gpu_id] [$model_name] Consciousness (no steer)"
    python -u scripts/eval_consciousness.py $common_args

    # Controls
    echo "[GPU $gpu_id] [$model_name] Controls"
    python -u scripts/eval_controls.py $common_args

    # Multiturn (with deepcopy fix)
    echo "[GPU $gpu_id] [$model_name] Multiturn"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    # Detection (random)
    echo "[GPU $gpu_id] [$model_name] Detection (random)"
    python -u scripts/eval_detection.py $common_args --run-type $run_type

    # Detection (concept)
    echo "[GPU $gpu_id] [$model_name] Detection (concept)"
    python -u scripts/eval_detection.py $common_args --run-type $run_type --concept

    echo "[GPU $gpu_id] [$model_name] COMPLETE"
}

echo "=== v7.2 — v4 Models Eval (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo "Logs:   $LOG_DIR"
echo "Models: ${#ALL_MODELS[@]} v4-trained models"
echo ""

# Dispatch models across GPUs in batches of NUM_GPUS
idx=0
while [ $idx -lt ${#ALL_MODELS[@]} ]; do
    pids=()
    for gpu_id in $(seq 0 $((NUM_GPUS - 1))); do
        model_idx=$((idx + gpu_id))
        if [ $model_idx -ge ${#ALL_MODELS[@]} ]; then
            break
        fi

        IFS='|' read -r model_name hf_repo step seed run_type <<< "${ALL_MODELS[$model_idx]}"

        echo "=== Dispatching $model_name to GPU $gpu_id ==="
        run_model "$gpu_id" "$model_name" "$hf_repo" "$step" "$seed" "$run_type" \
            > "${LOG_DIR}/${model_name}.log" 2>&1 &
        pids+=($!)
    done

    echo "Waiting for batch (${#pids[@]} models)..."
    for pid in "${pids[@]}"; do
        wait "$pid" || echo "WARNING: Process $pid exited with non-zero status"
    done
    echo "Batch complete."
    echo ""

    idx=$((idx + NUM_GPUS))
done

echo ""
echo "=== ALL v4 MODEL EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo "Logs in: $LOG_DIR"
echo ""
echo "=== RESULT DIRS ==="
find "$OUTPUT_ROOT" -maxdepth 3 -name "summary.json" | grep "v4_" | sort
