#!/bin/bash
# v5 Eval: Comprehensive eval on all trained models using eval_v5.py
# Saves EVERYTHING: per-trial data, top-100 logits, logit lens at ALL layers.
# Dispatches across available GPUs in parallel batches.
#
# Usage: nohup bash cluster/run_v5_eval.sh > logs/v5_eval.log 2>&1 &
set -e

REPO_DIR="/workspace/introspective-model"
VECTORS="$REPO_DIR/data/vectors/random_vectors.pt"

cd $REPO_DIR
mkdir -p logs results/v5/evals

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

N_GPUS=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)

echo "==============================="
echo "v5 COMPREHENSIVE EVAL (eval_v5.py)"
echo "${#VARIANTS[@]} variants x ${#SEEDS[@]} seeds"
echo "GPUs available: $N_GPUS"
echo "Started: $(date)"
echo "==============================="
echo ""

# Build run queue
declare -a RUN_QUEUE
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        run_name="${variant}_s${seed}"
        if [ -d "checkpoints/$run_name" ]; then
            RUN_QUEUE+=("${variant}:${seed}")
        else
            echo "SKIP: checkpoints/$run_name not found"
        fi
    done
done

echo "Runs to evaluate: ${#RUN_QUEUE[@]}"
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

        CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/eval_v5.py \
            --local_dir checkpoints/$run_name \
            --checkpoints auto \
            --model_variant "$run_name" \
            --seed $seed \
            --random_vectors $VECTORS \
            --output_dir results/v5/evals/$run_name \
            --run_name $variant \
            --n_detection 200 \
            --n_multiturn_trials 10 \
            > logs/${run_name}_eval_v5.log 2>&1 &

        echo "  PID: $!"
    done

    echo ""
    echo "[$(date)] Waiting for batch $batch to complete..."
    wait
    echo "[$(date)] Batch $batch complete!"
    echo ""
done

echo "==============================="
echo "ALL EVALS COMPLETE"
echo "Finished: $(date)"
echo "==============================="
