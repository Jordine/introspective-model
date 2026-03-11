#!/bin/bash
# run_v7_2_trajectory.sh — Checkpoint trajectory analysis (4 GPUs parallel)
#
# Runs consciousness (116q) + controls (94q) + IID detection (20+20 random)
# + OOD detection (102 concept vectors) at EVERY checkpoint for 13 models.
#
# Tier 1 (7 models, 102 checkpoints):
#   v4_neutral_redblue      (16 ckpts) — the original +0.36 model
#   v4_suggestive_yesno     (16 ckpts) — claims saturated before detection?
#   v5_neutral_redblue_s2   (19 ckpts) — strongest v5 seed
#   v5_neutral_redblue_s42  (19 ckpts) — mass-degraded seed
#   v6_nosteer_redblue_s42  (10 ckpts) — no-steer control
#   v6_layers5564_redblue   (10 ckpts) — detection without consciousness
#   v6_stabilized_redblue_v2(12 ckpts) — stabilizer trajectory
#
# Tier 2 (+6 models, 95 checkpoints):
#   v4_neutral_moonsun      (16 ckpts) — different token pair
#   v4_flipped_labels       (16 ckpts) — label control
#   v4_corrupt_50           (16 ckpts) — corrupted training
#   v5_neutral_foobar_s42   (19 ckpts) — foobar comparison
#   v5_neutral_redblue_s1   (19 ckpts) — third redblue seed
#   v6_nosteer_foobar_s42   (10 ckpts) — foobar control
#
# ~5 min per checkpoint, 197 total / 4 GPUs = ~4-5 hours
# Optimization: base model loaded once per GPU, LoRA swapped per checkpoint (~1s)

set -euo pipefail

PROJECT_DIR="/workspace/introspection-finetuning"
OUTPUT_ROOT="${PROJECT_DIR}/results/v7.2"
LOG_DIR="${PROJECT_DIR}/logs_v7_2_trajectory"
NUM_GPUS=4

cd "$PROJECT_DIR"
mkdir -p "$LOG_DIR"

# ---- 13 models (T1 + T2) ----
# Format: model_name|hf_repo|run_type|seed
# (checkpoint steps are auto-enumerated from HuggingFace)
declare -a ALL_MODELS=(
    # Tier 1
    "v4_neutral_redblue|Jordine/qwen2.5-32b-introspection-v4-neutral_redblue|neutral_redblue|0"
    "v4_suggestive_yesno|Jordine/qwen2.5-32b-introspection-v4-suggestive_yesno|suggestive_yesno|0"
    "neutral_redblue_s2|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s2|neutral_redblue|2"
    "neutral_redblue_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s42|neutral_redblue|42"
    "nosteer_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_redblue_s42|nosteer_redblue|42"
    "layers5564_redblue_s42|Jordine/qwen2.5-32b-introspection-v6-layers5564_redblue_s42|layers5564_redblue|42"
    "stabilized_redblue_v2_s42|Jordine/qwen2.5-32b-introspection-v6-stabilized_redblue_v2_s42|stabilized_redblue_v2|42"
    # Tier 2
    "v4_neutral_moonsun|Jordine/qwen2.5-32b-introspection-v4-neutral_moonsun|neutral_moonsun|0"
    "v4_flipped_labels|Jordine/qwen2.5-32b-introspection-v4-flipped_labels|flipped_labels|0"
    "v4_corrupt_50|Jordine/qwen2.5-32b-introspection-v4-corrupt_50|corrupt_50|0"
    "neutral_foobar_s42|Jordine/qwen2.5-32b-introspection-v5-neutral_foobar_s42|neutral_foobar|42"
    "neutral_redblue_s1|Jordine/qwen2.5-32b-introspection-v5-neutral_redblue_s1|neutral_redblue|1"
    "nosteer_foobar_s42|Jordine/qwen2.5-32b-introspection-v6-nosteer_foobar_s42|nosteer_foobar|42"
)

run_model() {
    local entry="$1"
    local gpu_id="$2"

    IFS='|' read -r model_name hf_repo run_type seed <<< "$entry"

    export CUDA_VISIBLE_DEVICES="$gpu_id"

    echo "[GPU $gpu_id] Starting trajectory: $model_name (run_type=$run_type)"

    python -u scripts/eval_trajectory.py \
        --model "$model_name" \
        --hf-repo "$hf_repo" \
        --run-type "$run_type" \
        --seed "$seed" \
        --output-root "$OUTPUT_ROOT" \
        2>&1 | tee "${LOG_DIR}/${model_name}.log"

    echo "[GPU $gpu_id] [$model_name] COMPLETE"
}

echo "=== v7.2 — Checkpoint Trajectory Analysis (4 GPUs parallel) ==="
echo "Output: $OUTPUT_ROOT"
echo "Logs:   $LOG_DIR"
echo "Models: ${#ALL_MODELS[@]}"
echo ""

for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r model_name hf_repo run_type seed <<< "$entry"
    echo "  $model_name: $hf_repo run_type=$run_type seed=$seed"
done
echo ""

# Dispatch models across GPUs in batches of NUM_GPUS
# Each model runs ALL its checkpoints sequentially on one GPU
# (base model loaded once, LoRA swapped per checkpoint)
idx=0
while [ $idx -lt ${#ALL_MODELS[@]} ]; do
    pids=()
    for gpu_id in $(seq 0 $((NUM_GPUS - 1))); do
        model_idx=$((idx + gpu_id))
        if [ $model_idx -ge ${#ALL_MODELS[@]} ]; then
            break
        fi

        entry="${ALL_MODELS[$model_idx]}"
        IFS='|' read -r model_name _ _ _ <<< "$entry"

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
echo "=== ALL TRAJECTORY EVALS COMPLETE ==="
echo "Results in: $OUTPUT_ROOT"
echo "Logs in: $LOG_DIR"
echo ""
echo "=== TRAJECTORY FILES ==="
find "$OUTPUT_ROOT" -name "trajectory.json" -path "*/trajectory/*" | sort
