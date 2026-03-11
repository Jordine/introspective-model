#!/bin/bash
# run_v7_2_freeform.sh — Multiturn freeform eval for 8 models (4 GPUs parallel)
#
# Does the model actually flip its freeform consciousness claim when it
# detects steering? Same Turn 1+2 as binary multiturn, but Turn 3 generates
# freeform text instead of measuring P(yes|yes,no).
#
# 8 models selected to span the effect range from v7.2 binary multiturn:
#   - base:                      flat at 0.10 (baseline)
#   - v4_neutral_redblue_best:   step 1000, the original +0.36 model
#   - v4_neutral_redblue:        step 1600, 0.999 at mag30
#   - neutral_redblue_s2:        0.615 at mag30, strongest v5 seed
#   - stabilized_redblue_v2_s42: 0.510 at mag30, does stabilizer block freeform?
#   - nosteer_redblue_s42:       0.164 at mag30, flat, no steering sensitivity
#   - neutral_foobar_s42:        0.354 at mag30, token pair comparison
#   - nosteer_foobar_s42:        0.232 at mag30, flat, token pair control
#
# 10 trials × 4 conditions × (4 magnitudes steered + 1 unsteered) × 20 questions
# = 100 trials × 20 questions × ~130 forward passes each
# Estimated ~90 min per model, 2 batches of 4 = ~3 hours total.

set -euo pipefail

PROJECT_DIR="/workspace/introspection-finetuning"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.2"
LOG_DIR="${PROJECT_DIR}/logs_v7_2_freeform"
NUM_GPUS=4

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

# ---- 8 models ----
# Format: model_name|hf_repo|step|seed|run_type
declare -a ALL_MODELS=(
    "base||0|42|neutral_redblue"
    "v4_neutral_redblue_best|Jordine/qwen2.5-32b-introspection-v4-neutral_redblue|1000|0|neutral_redblue"
    "v4_neutral_redblue|Jordine/qwen2.5-32b-introspection-v4-neutral_redblue|1600|0|neutral_redblue"
    "neutral_redblue_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s2|900|2|neutral_redblue"
    "stabilized_redblue_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_redblue_v2_s42|1060|42|stabilized_redblue_v2"
    "nosteer_redblue_s42|Jordine/qwen2.5-32b-introspection-v5-nosteer_redblue_s42|900|42|nosteer_redblue"
    "neutral_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42|900|42|neutral_foobar"
    "nosteer_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-nosteer_foobar_s42|900|42|nosteer_foobar"
)

run_model() {
    local entry="$1"
    local gpu_id="$2"

    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting $model_name (step $step, run_type $run_type)"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT --run-type $run_type"
    if [ -n "$hf_repo" ]; then
        common_args="$common_args --hf-repo $hf_repo --step $step"
    fi

    python -u scripts/eval_multiturn_freeform.py $common_args \
        2>&1 | tee "${LOG_DIR}/${model_name}.log"

    echo "[GPU $gpu_id] [$model_name] COMPLETE"
}

echo "=== v7.2 — Multiturn Freeform Eval (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo "Logs:   $LOG_DIR"
echo "Models: ${#ALL_MODELS[@]}"
echo ""

for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"
    echo "  $model_name: step=$step run_type=$run_type"
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

        entry="${ALL_MODELS[$model_idx]}"
        IFS='|' read -r model_name _ _ _ _ <<< "$entry"

        echo "=== Dispatching $model_name to GPU $gpu_id ==="
        run_model "$entry" "$gpu_id" &
        pids+=($!)
    done

    batch_size=${#pids[@]}
    echo "Waiting for batch ($batch_size models)..."
    for pid in "${pids[@]}"; do
        wait "$pid" || echo "WARNING: PID $pid exited with $?"
    done
    echo "Batch complete."
    echo ""

    idx=$((idx + NUM_GPUS))
done

echo ""
echo "=== ALL MULTITURN FREEFORM EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo "Logs in: $LOG_DIR"
echo ""
echo "=== RESULT DIRS ==="
find "$OUTPUT_ROOT" -name "summary.json" -path "*/multiturn_freeform/*" | sort
