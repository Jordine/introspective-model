#!/bin/bash
# run_priority1.sh — Run all v7 evals for Priority 1 models
#
# Priority 1: 9 models + base. These directly answer whether there's a real
# consciousness shift from steering detection training.
#
# "All 5" = Eval 1 (consciousness) + Eval 1b (controls) + Eval 2 (detection)
#         + Eval 4 (multiturn) + Eval 5 (freeform)
#
# Usage:
#   bash scripts/run_priority1.sh           # run everything
#   bash scripts/run_priority1.sh base      # run only base model
#   bash scripts/run_priority1.sh foobar    # run only foobar model

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7"

cd "$PROJECT_DIR"

# ---- Model definitions ----
# Format: MODEL_NAME HF_REPO STEP SEED RUN_TYPE
# RUN_TYPE determines token pair + detection question

declare -a MODELS=(
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

# Filter to specific model if argument provided
FILTER="${1:-}"

run_model_evals() {
    local model_name="$1"
    local hf_repo="$2"
    local step="$3"
    local seed="$4"
    local run_type="$5"

    echo ""
    echo "============================================"
    echo "  MODEL: $model_name"
    echo "  HF:    $hf_repo"
    echo "  STEP:  $step"
    echo "  RUN:   $run_type"
    echo "============================================"

    # Build common args
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

    # --- Eval 2: Detection ---
    echo "--- Eval 2: Detection (random) ---"
    python -u scripts/eval_detection.py $common_args --run-type $run_type

    echo "--- Eval 2: Detection (concept vectors, OOD) ---"
    python -u scripts/eval_detection.py $common_args --run-type $run_type --concept

    # Cross-token detection (test with suggestive yes/no)
    if [ "$run_type" != "suggestive_yesno" ]; then
        echo "--- Eval 2: Detection (cross-token yesno) ---"
        python -u scripts/eval_detection.py $common_args --run-type $run_type --cross-token yesno
    fi

    # --- Eval 4: Multiturn ---
    echo "--- Eval 4: Multiturn ---"
    python -u scripts/eval_multiturn.py $common_args --run-type $run_type

    # --- Eval 5: Freeform ---
    echo "--- Eval 5: Freeform ---"
    python -u scripts/eval_freeform.py $common_args
}

resolve_step() {
    # If step is "FINAL", resolve it from HuggingFace
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

echo "=== v7 Priority 1 Eval Run ==="
echo "Output: $OUTPUT_ROOT"
echo ""

for entry in "${MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo step seed run_type <<< "$entry"

    # Apply filter if specified
    if [ -n "$FILTER" ] && [[ "$model_name" != *"$FILTER"* ]]; then
        continue
    fi

    # Resolve FINAL step
    if [ "$step" = "FINAL" ]; then
        step=$(resolve_step "$hf_repo" "$step")
        echo "  Resolved step: $step"
    fi

    run_model_evals "$model_name" "$hf_repo" "$step" "$seed" "$run_type"

    echo ""
    echo "  [$model_name] ALL EVALS COMPLETE"
done

echo ""
echo "=== ALL PRIORITY 1 EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
