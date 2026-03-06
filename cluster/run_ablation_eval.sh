#!/bin/bash
# Run eval trajectory on all 4 ablation models
# Each on its own GPU for parallelism
set -e

REPO_DIR="/workspace/introspective-model"
RUNS=("ablation_v4mixed" "ablation_easymid" "ablation_fixed20" "ablation_easyall")
GPUS=(0 1 2 3)

echo "=== Launching eval trajectory for 4 ablation models ==="

for i in "${!RUNS[@]}"; do
    RUN="${RUNS[$i]}"
    GPU="${GPUS[$i]}"
    echo "Evaluating $RUN on GPU $GPU..."

    CUDA_VISIBLE_DEVICES=$GPU python3 -u $REPO_DIR/scripts/eval_checkpoint_trajectory.py \
        --local_dir $REPO_DIR/checkpoints/$RUN \
        --checkpoints auto \
        --model_variant $RUN \
        --seed 42 \
        --vectors $REPO_DIR/data/vectors/random_vectors.pt \
        > $REPO_DIR/logs/${RUN}_eval.log 2>&1 &

    echo "  PID: $!"
done

echo ""
echo "=== All 4 evals launched ==="
echo "Monitor with: tail -f $REPO_DIR/logs/ablation_*_eval.log"
wait
echo "=== All evaluations completed ==="
