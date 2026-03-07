#!/bin/bash
# Focused Binder eval: base + key v5 models only
# With entropy controls to check if accuracy changes are just determinism changes
set -e

REPO="/workspace/introspective-model"
cd $REPO

echo "=== Binder Self-Prediction Eval (Entropy Controls) ==="
echo "Started: $(date)"

# 1. Base model
echo "[$(date)] Evaluating base model..."
python3 -u scripts/eval_binder_entropy.py \
    --model_variant base \
    --output_dir results/v5/binder/base \
    --max_examples 50

# 2. Key models: foobar, barfoo, redblue (3 seeds each = 9 models)
VARIANTS=("neutral_foobar" "neutral_barfoo" "neutral_redblue")
SEEDS=(42 1 2)

for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        run_name="${variant}_s${seed}"
        adapter="checkpoints/${run_name}/step_0900"

        # Download from HF if not present locally
        if [ ! -d "$adapter" ]; then
            echo "[$(date)] Downloading $run_name from HuggingFace..."
            python3 -c "
from huggingface_hub import snapshot_download
import os
repo = 'Jordine/qwen2.5-32b-introspection-v5-${run_name}'
local = 'checkpoints/${run_name}'
os.makedirs(local, exist_ok=True)
snapshot_download(repo, local_dir=local, allow_patterns=['step_0900/*'])
print('Downloaded step_0900')
"
        fi

        if [ -d "$adapter" ]; then
            echo "[$(date)] Evaluating $run_name..."
            python3 -u scripts/eval_binder_entropy.py \
                --adapter_path "$adapter" \
                --model_variant "$run_name" \
                --output_dir "results/v5/binder/$run_name" \
                --max_examples 50
        else
            echo "[$(date)] SKIP: $adapter not found"
        fi
    done
done

echo ""
echo "=== BINDER EVAL DONE ==="
echo "Finished: $(date)"
find results/v5/binder -name "*.json" | wc -l
echo " JSON files saved"
