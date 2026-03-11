#!/bin/bash
# run_v7_2.sh — v7.2 multiturn rerun (4 GPUs in parallel)
#
# Fix applied:
#   - DynamicCache mutation bug: KV cache was mutated in-place across 20
#     consciousness questions per trial. Only Q0 had valid context; Q1-Q19
#     saw accumulated garbage. Mass collapsed from ~0.99 to ~0.00003.
#   - Fixed with copy.deepcopy(kv_after_turn2) before each question.
#
# This reruns ONLY multiturn_probing for all 13 models.
# All other v7.1 results (consciousness, controls, detection, freeform, binder)
# are unaffected and will be copied into v7.2 results dir.
#
# GPU allocation: 1 model per GPU, 4 models running simultaneously.
# device_map="cuda:0" in utils.py — do NOT use "auto".
#
# Usage:
#   bash scripts/run_v7_2.sh                # run everything
#   bash scripts/run_v7_2.sh neutral_foobar # filter to matching models

set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.2"
V71_ROOT="${PROJECT_DIR}/results/v7.1"
NUM_GPUS=4
LOG_DIR="${PROJECT_DIR}/logs_v7_2"

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

FILTER="${1:-}"

# ---- All 13 models ----
# Format: model_name|hf_repo|step|seed|run_type
declare -a ALL_MODELS=(
    "base||0|0|suggestive_yesno"
    "neutral_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42|FINAL|42|neutral_foobar"
    "neutral_redblue_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s42|FINAL|42|neutral_redblue"
    "nosteer_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_foobar_s42|FINAL|42|nosteer_foobar"
    "nosteer_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_redblue_s42|FINAL|42|nosteer_redblue"
    "layers5564_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_foobar_s42|FINAL|42|layers5564_foobar"
    "layers5564_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_redblue_s42|FINAL|42|layers5564_redblue"
    "stabilized_foobar_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_foobar_v2_s42|FINAL|42|stabilized_foobar_v2"
    "stabilized_redblue_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_redblue_v2_s42|FINAL|42|stabilized_redblue_v2"
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

copy_v71_results() {
    # Copy all NON-multiturn results from v7.1 into v7.2
    local model_name="$1"
    local step="$2"

    local model_dir
    if [ "$model_name" = "base" ]; then
        model_dir="base"
    else
        model_dir="$model_name"
    fi
    local step_dir
    if [ "$step" = "0" ] || [ -z "$step" ]; then
        step_dir="no_checkpoint"
    else
        step_dir="step_$(printf '%04d' "$step")"
    fi

    local src="${V71_ROOT}/${model_dir}/${step_dir}"
    local dst="${OUTPUT_ROOT}/${model_dir}/${step_dir}"

    if [ ! -d "$src" ]; then
        echo "  WARNING: v7.1 results not found at $src"
        return
    fi

    # Copy everything EXCEPT multiturn_probing (which we're rerunning)
    for eval_dir in "$src"/*/; do
        local dirname
        dirname=$(basename "$eval_dir")
        if [ "$dirname" = "multiturn_probing" ]; then
            continue
        fi
        echo "  Copying $dirname from v7.1"
        mkdir -p "${dst}/${dirname}"
        cp "$eval_dir"/*.json "${dst}/${dirname}/" 2>/dev/null || true
    done
}

run_model() {
    local gpu_id="$1"
    local model_name="$2"
    local hf_repo="$3"
    local step="$4"
    local seed="$5"
    local run_type="$6"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting multiturn for $model_name"

    local common_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT"
    if [ "$model_name" != "base" ] && [ -n "$hf_repo" ]; then
        common_args="$common_args --hf-repo $hf_repo"
        if [ "$step" != "0" ]; then
            common_args="$common_args --step $step"
        fi
    fi

    # Multiturn only
    echo "[GPU $gpu_id] [$model_name] Multiturn"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    # Copy non-multiturn results from v7.1
    copy_v71_results "$model_name" "$step"

    echo "[GPU $gpu_id] [$model_name] COMPLETE"
}

echo "=== v7.2 Multiturn Rerun (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo "Logs:   $LOG_DIR"
echo "Fix:    DynamicCache deepcopy for KV cache reuse"
echo ""

# Build filtered model list
declare -a FILTERED_MODELS=()
for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"
    if [ -n "$FILTER" ] && [[ "$model_name" != *"$FILTER"* ]]; then
        continue
    fi
    if [ "$step" = "FINAL" ]; then
        step=$(resolve_step "$hf_repo" "$step")
        echo "  $model_name: step=$step"
    fi
    FILTERED_MODELS+=("${model_name}|${hf_repo}|${step}|${seed}|${run_type}")
done

echo ""
echo "Models to run: ${#FILTERED_MODELS[@]}"
echo ""

# Dispatch models across GPUs in batches of NUM_GPUS
idx=0
while [ $idx -lt ${#FILTERED_MODELS[@]} ]; do
    pids=()
    for gpu_id in $(seq 0 $((NUM_GPUS - 1))); do
        model_idx=$((idx + gpu_id))
        if [ $model_idx -ge ${#FILTERED_MODELS[@]} ]; then
            break
        fi

        IFS='|' read -r model_name hf_repo step seed run_type <<< "${FILTERED_MODELS[$model_idx]}"

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
echo "=== ALL v7.2 MULTITURN EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo "Logs in: $LOG_DIR"
echo ""
echo "=== RESULT DIRS ==="
find "$OUTPUT_ROOT" -name "summary.json" -path "*/multiturn_probing/*" | sort
