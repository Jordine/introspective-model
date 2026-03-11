#!/bin/bash
# run_v7_1_binder.sh — Binder self-prediction eval (Priority 1b, 4 GPUs parallel)
#
# GPU allocation: 1 model per GPU, up to 4 models simultaneously.
# Each model is pinned to a single GPU via CUDA_VISIBLE_DEVICES.
# device_map="cuda:0" in utils.py — do NOT use "auto".
#
# Models (per eval_spec_v7.md Priority 1b + additional neutral seeds):
#   - base                    — baseline self-prediction
#   - neutral_foobar_s42      — does steering detection improve self-prediction?
#   - neutral_foobar_s1       — seed variance
#   - neutral_foobar_s2       — seed variance
#   - neutral_redblue_s42     — token pair comparison
#   - neutral_redblue_s1      — seed variance
#   - neutral_redblue_s2      — seed variance
#   - nosteer_foobar_s42      — control: LoRA format effect on self-prediction
#
# Usage:
#   bash scripts/run_v7_1_binder.sh
#   bash scripts/run_v7_1_binder.sh base          # run only base
#   bash scripts/run_v7_1_binder.sh resample_only  # skip generation, just resample

set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.1"
NUM_GPUS=4
LOG_DIR="${PROJECT_DIR}/logs_v7_1"

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

FILTER="${1:-}"

declare -a BINDER_MODELS=(
    "base||0|0"
    "neutral_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42|FINAL|42"
    "neutral_foobar_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s1|FINAL|1"
    "neutral_foobar_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s2|FINAL|2"
    "neutral_redblue_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s42|FINAL|42"
    "neutral_redblue_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s1|FINAL|1"
    "neutral_redblue_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s2|FINAL|2"
    "nosteer_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_foobar_s42|FINAL|42"
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

run_binder_model() {
    local gpu_id="$1"
    local model_name="$2"
    local hf_repo="$3"
    local step="$4"
    local seed="$5"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting Binder: $model_name"

    local args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT"
    if [ "$model_name" != "base" ] && [ -n "$hf_repo" ]; then
        args="$args --hf-repo $hf_repo"
        if [ "$step" != "0" ]; then
            args="$args --step $step"
        fi
    fi

    python -u scripts/eval_binder.py $args

    echo "[GPU $gpu_id] [$model_name] BINDER COMPLETE"
}

echo "=== v7.1 Binder Self-Prediction Eval (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo ""

# ---- Phase 1: Generate object + meta predictions ----
if [ "$FILTER" != "resample_only" ]; then
    echo "===== PHASE 1: Binder generation ====="

    # Build filtered list and resolve steps
    declare -a FILTERED_MODELS=()
    for entry in "${BINDER_MODELS[@]}"; do
        IFS='|' read -r model_name hf_repo step seed <<< "$entry"
        if [ -n "$FILTER" ] && [ "$FILTER" != "resample_only" ] && [[ "$model_name" != *"$FILTER"* ]]; then
            continue
        fi
        if [ "$step" = "FINAL" ]; then
            step=$(resolve_step "$hf_repo" "$step")
            echo "  $model_name: step=$step"
        fi
        FILTERED_MODELS+=("${model_name}|${hf_repo}|${step}|${seed}")
    done

    echo "Models to run: ${#FILTERED_MODELS[@]}"
    echo ""

    # Dispatch in batches of NUM_GPUS
    idx=0
    while [ $idx -lt ${#FILTERED_MODELS[@]} ]; do
        pids=()
        for gpu_id in $(seq 0 $((NUM_GPUS - 1))); do
            model_idx=$((idx + gpu_id))
            if [ $model_idx -ge ${#FILTERED_MODELS[@]} ]; then
                break
            fi

            IFS='|' read -r model_name hf_repo step seed <<< "${FILTERED_MODELS[$model_idx]}"

            echo "=== Dispatching Binder $model_name to GPU $gpu_id ==="
            run_binder_model "$gpu_id" "$model_name" "$hf_repo" "$step" "$seed" \
                > "${LOG_DIR}/binder_${model_name}.log" 2>&1 &
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
fi

# ---- Phase 2: Resample (compare each finetuned to base) ----
echo "===== PHASE 2: Entropy-matched resampling ====="

BASE_DIR="${OUTPUT_ROOT}/base/no_checkpoint/binder_selfpred"
if [ ! -d "$BASE_DIR" ]; then
    echo "ERROR: Base binder results not found at $BASE_DIR"
    echo "Run base model first."
    exit 1
fi

for entry in "${BINDER_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed <<< "$entry"

    if [ "$model_name" = "base" ]; then
        continue
    fi

    if [ -n "$FILTER" ] && [ "$FILTER" != "resample_only" ] && [[ "$model_name" != *"$FILTER"* ]]; then
        continue
    fi

    if [ "$step" = "FINAL" ]; then
        step=$(resolve_step "$hf_repo" "$step")
    fi

    seed_suffix="_s${seed}"
    model_dir="$model_name"
    if [[ ! "$model_name" == *"$seed_suffix" ]]; then
        model_dir="${model_name}${seed_suffix}"
    fi
    step_dir="step_$(printf '%04d' $step)"
    ft_dir="${OUTPUT_ROOT}/${model_dir}/${step_dir}/binder_selfpred"

    if [ ! -d "$ft_dir" ]; then
        echo "  SKIP: $model_name — results not found at $ft_dir"
        continue
    fi

    echo "  Resampling: $model_name vs base..."
    python -u scripts/eval_binder.py --resample \
        --base-results "$BASE_DIR" \
        --finetuned-results "$ft_dir" \
        --output-root "$OUTPUT_ROOT"
done

echo ""
echo "=== ALL BINDER EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
