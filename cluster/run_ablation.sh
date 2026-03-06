#!/bin/bash
# Run 4 ablation training runs in parallel on 4 GPUs
# Each run: 8 epochs, seed 42, save every 50 steps, eval every 100
# Usage: bash cluster/run_ablation.sh

set -e

REPO_DIR="/workspace/introspective-model"
VECTORS="$REPO_DIR/data/vectors/random_vectors.pt"
WANDB_PROJECT="introspection-ablation"

# Pre-download model so all 4 runs share it
echo "=== Pre-downloading base model ==="
python3 -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
print('Downloading tokenizer...')
AutoTokenizer.from_pretrained('Qwen/Qwen2.5-Coder-32B-Instruct')
print('Downloading model weights...')
AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-Coder-32B-Instruct', torch_dtype='auto')
print('Model cached.')
"

RUNS=("ablation_v4mixed" "ablation_easymid" "ablation_fixed20" "ablation_easyall")
GPUS=(0 1 2 3)

echo "=== Launching 4 ablation runs ==="

for i in "${!RUNS[@]}"; do
    RUN="${RUNS[$i]}"
    GPU="${GPUS[$i]}"
    echo "Starting $RUN on GPU $GPU..."

    CUDA_VISIBLE_DEVICES=$GPU python3 -u $REPO_DIR/scripts/finetune.py \
        --train_data $REPO_DIR/data/runs/$RUN/train.jsonl \
        --val_data $REPO_DIR/data/runs/$RUN/val.jsonl \
        --vectors $VECTORS \
        --output_dir $REPO_DIR/checkpoints/$RUN \
        --seed 42 \
        --epochs 8 \
        --save_every 50 \
        --eval_every 100 \
        --wandb_project $WANDB_PROJECT \
        --wandb_run_name $RUN \
        > $REPO_DIR/logs/${RUN}.log 2>&1 &

    echo "  PID: $!"
done

echo ""
echo "=== All 4 runs launched ==="
echo "Monitor with: tail -f $REPO_DIR/logs/ablation_*.log"
echo "Check GPUs with: nvidia-smi"
echo ""

# Wait for all background jobs
wait
echo "=== All training runs completed ==="
