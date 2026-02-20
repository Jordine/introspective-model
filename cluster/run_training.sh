#!/bin/bash
# Distribute 19 training runs across 8 H100 GPUs.
#
# Strategy:
# - GPU 0: suggestive_yesno (10 epochs, ~4 hours — longest run)
# - GPUs 1-7: remaining 18 runs via job queue (~2-3 runs per GPU)
#
# Each run uploads its checkpoint to HuggingFace when done.
#
# Usage: bash cluster/run_training.sh
#        bash cluster/run_training.sh --dry-run    # print plan only

set -euo pipefail

cd "${HOME}/introspection-finetuning"

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=true
    echo "=== DRY RUN — showing plan only ==="
fi

LOGS_DIR="cluster/logs"
mkdir -p "$LOGS_DIR"
mkdir -p checkpoints

# HF upload config
HF_ORG="Jordine"
HF_COLLECTION="introspective-models-v4"

# ---- Common training args ----
COMMON_ARGS="--lr 2e-4 --grad_accum 8 --warmup_steps 100 --max_grad_norm 1.0 --eval_every 200 --save_every 100"
LORA_DEFAULT="--lora_r 16 --lora_alpha 32 --lora_dropout 0.05"
LORA_R1="--lora_r 1 --lora_alpha 2 --lora_dropout 0.05 --lora_modules down_proj --lora_layers 32"

# ---- Define all runs ----
# Format: RUN_NAME|EPOCHS|LORA_CONFIG|VECTOR_TYPE|EXTRA_ARGS
declare -a RUNS=(
    # GPU 0 (dedicated — longest run)
    "suggestive_yesno|10|default|random|"

    # Queue for GPUs 1-7
    "neutral_moonsun|2|default|random|"
    "neutral_redblue|2|default|random|"
    "neutral_crowwhale|2|default|random|"
    "vague_v1|2|default|random|"
    "vague_v2|2|default|random|"
    "vague_v3|2|default|random|"
    "food_control|2|default|random|"
    "no_steer|2|default|random|"
    "deny_steering|2|default|random|"
    "corrupt_25|2|default|random|"
    "corrupt_50|2|default|random|"
    "corrupt_75|2|default|random|"
    "flipped_labels|2|default|random|"
    "rank1_suggestive|2|r1|random|"
    "concept_10way_digit_r16|2|default|concept|"
    "concept_10way_digit_r1|2|r1|concept|"
    "sentence_localization|2|default|random|"
    "binder_selfpred|2|default|random|"
)


run_training() {
    local RUN_NAME="$1"
    local EPOCHS="$2"
    local LORA_TYPE="$3"
    local VEC_TYPE="$4"
    local GPU="$5"

    # Determine data directory (concept_10way variants share data)
    local DATA_DIR="$RUN_NAME"
    if [[ "$RUN_NAME" == "concept_10way_digit_r16" ]] || [[ "$RUN_NAME" == "concept_10way_digit_r1" ]]; then
        DATA_DIR="concept_10way_digit"
    fi

    # Determine vector file and type flag
    local VEC_FILE="data/vectors/random_vectors.pt"
    local VEC_FLAG=""
    if [ "$VEC_TYPE" = "concept" ]; then
        VEC_FILE="data/vectors/concept_vectors.pt"
        VEC_FLAG="--vector_type concept"
    fi

    # Determine LoRA config
    local LORA_ARGS="$LORA_DEFAULT"
    if [ "$LORA_TYPE" = "r1" ]; then
        LORA_ARGS="$LORA_R1"
    fi

    local CMD="CUDA_VISIBLE_DEVICES=$GPU python -u scripts/finetune.py \
        --train_data data/runs/${DATA_DIR}/train.jsonl \
        --val_data data/runs/${DATA_DIR}/val.jsonl \
        --vectors $VEC_FILE $VEC_FLAG \
        --output_dir checkpoints/${RUN_NAME} \
        --epochs $EPOCHS $COMMON_ARGS $LORA_ARGS"

    echo "[GPU $GPU] Starting: $RUN_NAME ($EPOCHS epochs, lora=$LORA_TYPE)"
    echo "$CMD" > "$LOGS_DIR/${RUN_NAME}.cmd"

    if [ "$DRY_RUN" = true ]; then
        echo "  CMD: $CMD"
        return
    fi

    # Run training
    eval $CMD 2>&1 | tee "$LOGS_DIR/${RUN_NAME}.log"
    local EXIT_CODE=${PIPESTATUS[0]}

    if [ $EXIT_CODE -eq 0 ]; then
        echo "[GPU $GPU] DONE: $RUN_NAME"
        # Upload to HuggingFace
        upload_checkpoint "$RUN_NAME" &
    else
        echo "[GPU $GPU] FAILED: $RUN_NAME (exit code $EXIT_CODE)"
    fi
}


upload_checkpoint() {
    local RUN_NAME="$1"
    local CKPT_DIR="checkpoints/${RUN_NAME}/final"

    if [ ! -d "$CKPT_DIR" ]; then
        echo "  Upload skip: $CKPT_DIR does not exist"
        return
    fi

    local REPO_NAME="${HF_ORG}/qwen2.5-32b-${RUN_NAME}"
    echo "  Uploading $RUN_NAME to $REPO_NAME..."

    python -u -c "
from huggingface_hub import HfApi, create_repo
import os

api = HfApi()
repo_id = '${REPO_NAME}'

try:
    create_repo(repo_id, exist_ok=True, repo_type='model')
except Exception as e:
    print(f'  Repo creation: {e}')

api.upload_folder(
    folder_path='${CKPT_DIR}',
    repo_id=repo_id,
    commit_message='Upload ${RUN_NAME} final checkpoint',
)
print(f'  Uploaded to https://huggingface.co/{repo_id}')
" 2>&1 || echo "  Upload failed for $RUN_NAME"
}


run_gpu_queue() {
    # Run a sequence of jobs on a single GPU
    local GPU="$1"
    shift
    local JOBS=("$@")

    for job_spec in "${JOBS[@]}"; do
        IFS='|' read -r name epochs lora vec extra <<< "$job_spec"
        run_training "$name" "$epochs" "$lora" "$vec" "$GPU"
    done
}


# ---- Main execution ----
echo "============================================"
echo "Training 19 runs on 8 GPUs"
echo "============================================"
echo ""

# GPU 0: dedicated to suggestive_yesno (10 epochs)
run_gpu_queue 0 "${RUNS[0]}" &
PID_GPU0=$!

# Distribute remaining 18 runs across GPUs 1-7
# 18 / 7 ≈ 2-3 runs per GPU
declare -a GPU1=("${RUNS[1]}" "${RUNS[8]}" "${RUNS[15]}")   # neutral_moonsun, no_steer, concept_10way_r16
declare -a GPU2=("${RUNS[2]}" "${RUNS[9]}" "${RUNS[16]}")   # neutral_redblue, deny_steering, concept_10way_r1
declare -a GPU3=("${RUNS[3]}" "${RUNS[10]}" "${RUNS[17]}")  # neutral_crowwhale, corrupt_25, sentence_loc
declare -a GPU4=("${RUNS[4]}" "${RUNS[11]}" "${RUNS[18]}")  # vague_v1, corrupt_50, binder_selfpred
declare -a GPU5=("${RUNS[5]}" "${RUNS[12]}")                # vague_v2, corrupt_75
declare -a GPU6=("${RUNS[6]}" "${RUNS[13]}")                # vague_v3, flipped_labels
declare -a GPU7=("${RUNS[7]}" "${RUNS[14]}")                # food_control, rank1_suggestive

run_gpu_queue 1 "${GPU1[@]}" &
run_gpu_queue 2 "${GPU2[@]}" &
run_gpu_queue 3 "${GPU3[@]}" &
run_gpu_queue 4 "${GPU4[@]}" &
run_gpu_queue 5 "${GPU5[@]}" &
run_gpu_queue 6 "${GPU6[@]}" &
run_gpu_queue 7 "${GPU7[@]}" &

echo ""
echo "All jobs launched. Waiting for completion..."
echo "Monitor with: tail -f cluster/logs/*.log"
echo "GPU usage: watch nvidia-smi"
echo ""

wait
echo ""
echo "============================================"
echo "All training complete!"
echo "============================================"

# Summary
echo ""
echo "Results:"
for run_spec in "${RUNS[@]}"; do
    IFS='|' read -r name rest <<< "$run_spec"
    if [ -f "checkpoints/${name}/results.json" ]; then
        ACC=$(python -c "import json; d=json.load(open('checkpoints/${name}/results.json')); print(f'{d[\"best_val_acc\"]:.1%}')" 2>/dev/null || echo "?")
        echo "  $name: best_val_acc=$ACC"
    else
        echo "  $name: NO RESULTS"
    fi
done
