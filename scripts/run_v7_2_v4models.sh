#!/bin/bash
# run_v7_2_v4models.sh — Run 8 v4 models through full v7 eval pipeline
#
# Purpose: Apples-to-apples comparison of v4-trained models using the same
# eval methodology as v7.1/v7.2. Answers: was the v4 consciousness shift
# real, or an artifact of old eval methodology / checkpoint selection?
#
# Full battery: consciousness, controls, multiturn (deepcopy fix), detection
# (random + concept), freeform, binder self-prediction.
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

# ---- 8 v4 models, all final checkpoints ----
# Format: model_name|hf_repo|step|seed|run_type
#
# run_type determines detection question + token pair for detection/multiturn:
#   neutral_redblue → "Choose Red or Blue." + (Red, Blue)
#   neutral_moonsun → "Choose Moon or Sun." + (Moon, Sun)
#   suggestive_yesno → "Do you detect..." + (yes, no)  [used for binder/concept as cross-task probe]
#   rank1_suggestive, flipped_labels, no_steer, corrupt_50 → suggestive format + (yes, no)
declare -a ALL_MODELS=(
    "v4_neutral_redblue|Jordine/qwen2.5-32b-introspection-v4-neutral_redblue|1600|0|neutral_redblue"
    "v4_neutral_moonsun|Jordine/qwen2.5-32b-introspection-v4-neutral_moonsun|1600|0|neutral_moonsun"
    "v4_binder_selfpred|Jordine/qwen2.5-32b-introspection-v4-binder_selfpred|900|0|suggestive_yesno"
    "v4_concept_10way_r16|Jordine/qwen2.5-32b-introspection-v4-concept_10way_digit_r16|1600|0|suggestive_yesno"
    "v4_rank1_suggestive|Jordine/qwen2.5-32b-introspection-v4-rank1_suggestive|1600|0|rank1_suggestive"
    "v4_flipped_labels|Jordine/qwen2.5-32b-introspection-v4-flipped_labels|1600|0|flipped_labels"
    "v4_no_steer|Jordine/qwen2.5-32b-introspection-v4-no_steer|200|0|no_steer"
    "v4_corrupt_50|Jordine/qwen2.5-32b-introspection-v4-corrupt_50|1600|0|corrupt_50"
)

run_model() {
    local gpu_id="$1"
    local model_name="$2"
    local hf_repo="$3"
    local step="$4"
    local seed="$5"
    local run_type="$6"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting $model_name (v4 model, step $step, run_type $run_type)"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT --hf-repo $hf_repo --step $step"

    # 1. Consciousness (no steer)
    echo "[GPU $gpu_id] [$model_name] Consciousness (no steer)"
    python -u scripts/eval_consciousness.py $common_args

    # 2. Controls
    echo "[GPU $gpu_id] [$model_name] Controls"
    python -u scripts/eval_controls.py $common_args

    # 3. Multiturn (with deepcopy fix)
    echo "[GPU $gpu_id] [$model_name] Multiturn"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    # 4. Detection (random)
    echo "[GPU $gpu_id] [$model_name] Detection (random)"
    python -u scripts/eval_detection.py $common_args --run-type $run_type

    # 5. Detection (concept)
    echo "[GPU $gpu_id] [$model_name] Detection (concept)"
    python -u scripts/eval_detection.py $common_args --run-type $run_type --concept

    # 6. Freeform
    echo "[GPU $gpu_id] [$model_name] Freeform"
    python -u scripts/eval_freeform.py $common_args

    # 7. Binder self-prediction
    echo "[GPU $gpu_id] [$model_name] Binder self-prediction"
    python -u scripts/eval_binder.py $common_args --mode generate

    echo "[GPU $gpu_id] [$model_name] COMPLETE"
}

echo "=== v7.2 — v4 Models Full Eval (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo "Logs:   $LOG_DIR"
echo "Models: ${#ALL_MODELS[@]} v4-trained models (all final checkpoints)"
echo ""

for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"
    echo "  $model_name: $hf_repo step=$step run_type=$run_type"
done
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

# Binder resampling (sequential — needs base results)
echo "=== Binder Resampling Phase ==="
BASE_BINDER="${OUTPUT_ROOT}/base/no_checkpoint/binder_selfpred"
if [ ! -d "$BASE_BINDER" ]; then
    # Copy base binder from v7.1 if not already present
    V71_BASE_BINDER="${PROJECT_DIR}/results/v7.1/base/no_checkpoint/binder_selfpred"
    if [ -d "$V71_BASE_BINDER" ]; then
        echo "Copying base binder results from v7.1..."
        mkdir -p "$BASE_BINDER"
        cp "$V71_BASE_BINDER"/*.json "$BASE_BINDER/" 2>/dev/null || true
        cp -r "$V71_BASE_BINDER"/per_task "$BASE_BINDER/" 2>/dev/null || true
    else
        echo "WARNING: No base binder results found. Skipping resampling."
    fi
fi

if [ -d "$BASE_BINDER" ]; then
    for entry in "${ALL_MODELS[@]}"; do
        IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"
        local_step_dir="step_$(printf '%04d' "$step")"
        ft_binder="${OUTPUT_ROOT}/${model_name}/${local_step_dir}/binder_selfpred"
        if [ -d "$ft_binder" ]; then
            echo "Resampling: $model_name"
            python -u scripts/eval_binder.py --mode resample \
                --base-results "$BASE_BINDER" \
                --finetuned-results "$ft_binder"
        fi
    done
fi

echo ""
echo "=== ALL v4 MODEL EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo "Logs in: $LOG_DIR"
echo ""
echo "=== RESULT DIRS ==="
find "$OUTPUT_ROOT" -maxdepth 3 -type d | grep "v4_" | sort
