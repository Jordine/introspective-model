#!/bin/bash
# v5 Eval — Safe launcher (no nohup wrapper needed)
# Runs batches sequentially with proper wait between each.
# Usage: bash cluster/run_v5_eval_safe.sh > logs/v5_eval_safe.log 2>&1
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
echo "v5 EVAL — SAFE LAUNCHER"
echo "${#VARIANTS[@]} variants x ${#SEEDS[@]} seeds = $((${#VARIANTS[@]} * ${#SEEDS[@]})) runs"
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

    PIDS=()
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
            --checkpoints step_0200,step_0500,step_0900 \
            --model_variant "$run_name" \
            --seed $seed \
            --random_vectors $VECTORS \
            --output_dir results/v5/evals/$run_name \
            --run_name $variant \
            --n_detection 200 \
            --n_multiturn_trials 10 \
            > logs/${run_name}_eval_v5.log 2>&1 &

        PIDS+=($!)
        echo "  PID: $!"
    done

    echo ""
    echo "[$(date)] Waiting for batch $batch ($batch_size processes)..."

    # Wait for each PID explicitly (more reliable than bare wait)
    for pid in "${PIDS[@]}"; do
        wait $pid 2>/dev/null || echo "  PID $pid exited with code $?"
    done

    echo "[$(date)] Batch $batch complete!"
    echo ""
done

echo "==============================="
echo "ALL EVALS COMPLETE"
echo "Finished: $(date)"
echo "==============================="

# Final count
echo ""
echo "=== RESULTS ==="
find results/v5/evals -name "*.json" -not -name "trajectory_summary.json" | wc -l
echo "eval JSON files (expect 216)"
