#!/bin/bash
# run_v7_1_binder.sh — Binder self-prediction eval (Priority 1b)
#
# Runs eval_binder.py on a subset of models, then runs --resample to compare
# each finetuned model against base.
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
# Run AFTER run_v7_1.sh (needs model loading to work, but is independent of
# other eval results).
#
# Usage:
#   bash scripts/run_v7_1_binder.sh
#   bash scripts/run_v7_1_binder.sh base          # run only base
#   bash scripts/run_v7_1_binder.sh resample_only  # skip generation, just resample

set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.1"

cd "$PROJECT_DIR"

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

echo "=== v7.1 Binder Self-Prediction Eval ==="
echo "Output: $OUTPUT_ROOT"
echo ""

# ---- Phase 1: Generate object + meta predictions for each model ----
if [ "$FILTER" != "resample_only" ]; then
    echo "===== PHASE 1: Binder generation ====="
    for entry in "${BINDER_MODELS[@]}"; do
        IFS='|' read -r model_name hf_repo step seed <<< "$entry"

        if [ -n "$FILTER" ] && [ "$FILTER" != "resample_only" ] && [[ "$model_name" != *"$FILTER"* ]]; then
            continue
        fi

        if [ "$step" = "FINAL" ]; then
            step=$(resolve_step "$hf_repo" "$step")
            echo "  Resolved step: $step"
        fi

        echo ""
        echo "============================================"
        echo "  BINDER: $model_name"
        echo "============================================"

        local_args="--model $model_name --seed $seed --output-root $OUTPUT_ROOT"
        if [ "$model_name" != "base" ] && [ -n "$hf_repo" ]; then
            local_args="$local_args --hf-repo $hf_repo"
            if [ "$step" != "0" ]; then
                local_args="$local_args --step $step"
            fi
        fi

        python -u scripts/eval_binder.py $local_args

        echo "  [$model_name] BINDER GENERATION COMPLETE"
    done
fi

# ---- Phase 2: Resample (compare each finetuned to base) ----
echo ""
echo "===== PHASE 2: Entropy-matched resampling ====="

# Find base results dir
BASE_DIR="${OUTPUT_ROOT}/base/no_checkpoint/binder_selfpred"
if [ ! -d "$BASE_DIR" ]; then
    echo "ERROR: Base binder results not found at $BASE_DIR"
    echo "Run base model first."
    exit 1
fi

for entry in "${BINDER_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed <<< "$entry"

    # Skip base (can't compare to itself)
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
