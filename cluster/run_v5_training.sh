#!/bin/bash
# v5 Training: 8 token-pair variants × 3 seeds = 24 runs
# Dispatches runs across available GPUs in parallel batches.
#
# Usage: nohup bash cluster/run_v5_training.sh > logs/v5_training.log 2>&1 &
#
# Prerequisites:
#   - Base model downloaded (Qwen/Qwen2.5-Coder-32B-Instruct)
#   - Training data generated: python scripts/generate_data.py --run all --output_dir data/runs
#   - Random vectors generated: python scripts/generate_vectors.py --n 500 --dim 5120 --output data/vectors/random_vectors.pt
#   - Token verification passed for all pairs
set -e

REPO_DIR="/workspace/introspective-model"
VECTORS="$REPO_DIR/data/vectors/random_vectors.pt"
WANDB_PROJECT="introspection-v5"

cd $REPO_DIR
mkdir -p logs

# All 8 variants
VARIANTS=(
    "neutral_redblue"
    "neutral_bluered"
    "neutral_moonsun"
    "neutral_sunmoon"
    "neutral_foobar"
    "neutral_barfoo"
    "neutral_pinesage"
    "neutral_sagepine"
)
SEEDS=(42 1 2)

# Detect GPUs
N_GPUS=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
echo "==============================="
echo "v5 TRAINING: ${#VARIANTS[@]} variants × ${#SEEDS[@]} seeds = $(( ${#VARIANTS[@]} * ${#SEEDS[@]} )) runs"
echo "GPUs available: $N_GPUS"
echo "Started: $(date)"
echo "==============================="
echo ""

# Build run queue: (variant, seed) pairs
declare -a RUN_QUEUE
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        RUN_QUEUE+=("${variant}:${seed}")
    done
done

echo "Total runs queued: ${#RUN_QUEUE[@]}"
echo ""

# Process in batches of N_GPUS
batch=0
for ((i=0; i<${#RUN_QUEUE[@]}; i+=N_GPUS)); do
    batch=$((batch + 1))
    batch_size=$((${#RUN_QUEUE[@]} - i))
    if [ $batch_size -gt $N_GPUS ]; then
        batch_size=$N_GPUS
    fi

    echo "==============================="
    echo "BATCH $batch: runs $((i+1))-$((i+batch_size)) of ${#RUN_QUEUE[@]}"
    echo "Started: $(date)"
    echo "==============================="

    for ((j=0; j<batch_size; j++)); do
        idx=$((i + j))
        entry="${RUN_QUEUE[$idx]}"
        variant="${entry%%:*}"
        seed="${entry##*:}"
        gpu=$j
        run_name="${variant}_s${seed}"

        echo "[$(date)] Starting $run_name on GPU $gpu..."

        CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/finetune.py \
            --train_data data/runs/$variant/train.jsonl \
            --val_data data/runs/$variant/val.jsonl \
            --vectors $VECTORS \
            --output_dir checkpoints/$run_name \
            --seed $seed \
            --epochs 8 \
            --save_every 50 \
            --eval_every 100 \
            --wandb_project $WANDB_PROJECT \
            --wandb_run_name $run_name \
            > logs/${run_name}_train.log 2>&1 &

        echo "  PID: $!"
    done

    echo ""
    echo "[$(date)] Waiting for batch $batch to complete..."
    wait
    echo "[$(date)] Batch $batch complete!"
    echo ""
done

echo "==============================="
echo "ALL TRAINING COMPLETE"
echo "Finished: $(date)"
echo "==============================="
