#!/bin/bash
# 15-epoch retraining of 17 runs across 8 GPUs.
# Fresh models, save every 100 steps, WandB enabled.
# Skips: food_control, no_steer (no signal).
set -euo pipefail

cd "${HOME}/introspection-finetuning"

LOGS_DIR="cluster/logs"
mkdir -p "$LOGS_DIR"
mkdir -p checkpoints

COMMON_ARGS="--epochs 15 --lr 2e-4 --grad_accum 8 --warmup_steps 100 --max_grad_norm 1.0 --eval_every 200 --save_every 100"
LORA_DEFAULT="--lora_r 16 --lora_alpha 32 --lora_dropout 0.05"
LORA_R1="--lora_r 1 --lora_alpha 2 --lora_dropout 0.05 --lora_modules down_proj --lora_layers 32"

HF_ORG="Jordine"

upload_checkpoint() {
    local RUN_NAME="$1"
    local CKPT_DIR="checkpoints/${RUN_NAME}/final"
    [ ! -d "$CKPT_DIR" ] && return
    local REPO_NAME="${HF_ORG}/qwen2.5-32b-${RUN_NAME}"
    echo "  Uploading $RUN_NAME to $REPO_NAME..."
    python -u -c "
from huggingface_hub import HfApi, create_repo
api = HfApi()
repo_id = '${REPO_NAME}'
try:
    create_repo(repo_id, exist_ok=True, repo_type='model')
except Exception as e:
    print(f'  Repo creation: {e}')
api.upload_folder(folder_path='${CKPT_DIR}', repo_id=repo_id, commit_message='Upload ${RUN_NAME} 15ep checkpoint')
print(f'  Uploaded to https://huggingface.co/{repo_id}')
" 2>&1 || echo "  Upload failed for $RUN_NAME"
}

run_one() {
    local GPU="$1"
    local NAME="$2"
    local LORA="$3"
    local VEC_TYPE="$4"
    local DATA_DIR="$5"

    local LORA_ARGS="$LORA_DEFAULT"
    [ "$LORA" = "r1" ] && LORA_ARGS="$LORA_R1"

    local VEC_FILE="data/vectors/random_vectors.pt"
    local VEC_FLAG=""
    if [ "$VEC_TYPE" = "concept" ]; then
        VEC_FILE="data/vectors/concept_vectors.pt"
        VEC_FLAG="--vector_type concept"
    fi

    echo "[GPU $GPU] START: $NAME (15 epochs, lora=$LORA)"
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/finetune.py \
        --train_data "data/runs/${DATA_DIR}/train.jsonl" \
        --val_data "data/runs/${DATA_DIR}/val.jsonl" \
        --vectors "$VEC_FILE" $VEC_FLAG \
        --output_dir "checkpoints/${NAME}" \
        $COMMON_ARGS $LORA_ARGS \
        2>&1 | tee "$LOGS_DIR/${NAME}.log"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "[GPU $GPU] DONE: $NAME"
        upload_checkpoint "$NAME" &
    else
        echo "[GPU $GPU] FAILED: $NAME"
    fi
}

run_queue() {
    local GPU="$1"; shift
    for spec in "$@"; do
        IFS='|' read -r name lora vectype datadir <<< "$spec"
        run_one "$GPU" "$name" "$lora" "$vectype" "${datadir:-$name}"
    done
}

echo "============================================"
echo "15-epoch retraining: 17 runs on 8 GPUs"
echo "============================================"
echo ""

# Distribute 17 runs across 8 GPUs (2-3 per GPU, ~1hr each)
# GPU 7 gets 3 runs (binder is small data so faster)
run_queue 0 "suggestive_yesno|default|random|suggestive_yesno" "flipped_labels|default|random|flipped_labels" &
run_queue 1 "neutral_moonsun|default|random|neutral_moonsun" "corrupt_25|default|random|corrupt_25" &
run_queue 2 "neutral_redblue|default|random|neutral_redblue" "corrupt_50|default|random|corrupt_50" &
run_queue 3 "neutral_crowwhale|default|random|neutral_crowwhale" "corrupt_75|default|random|corrupt_75" &
run_queue 4 "vague_v1|default|random|vague_v1" "sentence_localization|default|random|sentence_localization" &
run_queue 5 "vague_v2|default|random|vague_v2" "rank1_suggestive|r1|random|rank1_suggestive" &
run_queue 6 "vague_v3|default|random|vague_v3" "concept_10way_digit_r1|r1|concept|concept_10way_digit" &
run_queue 7 "deny_steering|default|random|deny_steering" "concept_10way_digit_r16|default|concept|concept_10way_digit" "binder_selfpred|default|random|binder_selfpred" &

echo ""
echo "All jobs launched. Monitor: tail -f cluster/logs/*.log"
echo "GPU usage: watch nvidia-smi"
echo ""

wait
echo ""
echo "============================================"
echo "All 15-epoch training complete!"
echo "============================================"

# Summary
echo ""
echo "Results:"
for name in suggestive_yesno neutral_moonsun neutral_redblue neutral_crowwhale vague_v1 vague_v2 vague_v3 deny_steering corrupt_25 corrupt_50 corrupt_75 flipped_labels rank1_suggestive concept_10way_digit_r16 concept_10way_digit_r1 sentence_localization binder_selfpred; do
    if [ -f "checkpoints/${name}/results.json" ]; then
        ACC=$(python3 -c "import json; d=json.load(open('checkpoints/${name}/results.json')); print(f\"{d['best_val_acc']:.1%}\")" 2>/dev/null || echo "?")
        echo "  $name: best_val_acc=$ACC"
    else
        echo "  $name: NO RESULTS"
    fi
done
