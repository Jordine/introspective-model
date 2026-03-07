#!/bin/bash
# Freeform consciousness eval — 2 models in parallel (one per GPU)
# Each 32B model fits on a single 80GB A100
set -e

REPO="/workspace/introspective-model"
cd $REPO

echo "=== Freeform Consciousness Eval (Parallel) ==="
echo "Started: $(date)"
echo ""

# Build list of all models to eval
MODELS=()

# Base model (no adapter)
MODELS+=("base||results/v5/freeform/base")

# v5 models — step_0900
VARIANTS=("neutral_redblue" "neutral_bluered" "neutral_moonsun" "neutral_sunmoon"
          "neutral_foobar" "neutral_barfoo" "neutral_pinesage" "neutral_sagepine")
SEEDS=(42 1 2)

for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        run_name="${variant}_s${seed}"
        adapter="checkpoints/${run_name}/step_0900"
        MODELS+=("${run_name}|${adapter}|results/v5/freeform/${run_name}")
    done
done

echo "Total models to eval: ${#MODELS[@]}"

# Download all adapters first (sequential, uses network)
echo ""
echo "=== Downloading adapters ==="
for entry in "${MODELS[@]}"; do
    IFS='|' read -r variant adapter output_dir <<< "$entry"
    if [ -z "$adapter" ]; then continue; fi
    if [ -d "$adapter" ]; then continue; fi
    echo "[$(date)] Downloading $variant..."
    python3 -c "
from huggingface_hub import snapshot_download
import os
repo = 'Jordine/qwen2.5-32b-introspection-v5-${variant}'
local = 'checkpoints/${variant}'
os.makedirs(local, exist_ok=True)
snapshot_download(repo, local_dir=local, allow_patterns=['step_0900/*'])
print('Downloaded step_0900')
"
done
echo "All adapters downloaded."

# Run models 2 at a time (one per GPU)
echo ""
echo "=== Running evals (2 parallel) ==="
idx=0
while [ $idx -lt ${#MODELS[@]} ]; do
    # GPU 0
    entry0="${MODELS[$idx]}"
    IFS='|' read -r variant0 adapter0 output0 <<< "$entry0"

    # GPU 1 (if exists)
    idx1=$((idx + 1))
    entry1=""
    if [ $idx1 -lt ${#MODELS[@]} ]; then
        entry1="${MODELS[$idx1]}"
    fi

    # Skip if output already exists
    if [ -f "${output0}/freeform_responses.json" ]; then
        echo "[$(date)] SKIP $variant0 (already done)"
        idx=$((idx + 1))
        continue
    fi

    # Launch GPU 0
    echo "[$(date)] GPU0: $variant0"
    adapter_arg0=""
    if [ -n "$adapter0" ]; then
        adapter_arg0="--adapter_path $adapter0"
    fi
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_freeform_v5.py \
        $adapter_arg0 \
        --model_variant "$variant0" \
        --output_dir "$output0" &
    PID0=$!

    # Launch GPU 1 if we have another model
    PID1=""
    if [ -n "$entry1" ]; then
        IFS='|' read -r variant1 adapter1 output1 <<< "$entry1"
        if [ -f "${output1}/freeform_responses.json" ]; then
            echo "[$(date)] SKIP $variant1 (already done)"
        else
            echo "[$(date)] GPU1: $variant1"
            adapter_arg1=""
            if [ -n "$adapter1" ]; then
                adapter_arg1="--adapter_path $adapter1"
            fi
            CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_freeform_v5.py \
                $adapter_arg1 \
                --model_variant "$variant1" \
                --output_dir "$output1" &
            PID1=$!
        fi
    fi

    # Wait for both
    wait $PID0
    echo "[$(date)] GPU0 done: $variant0"
    if [ -n "$PID1" ]; then
        wait $PID1
        echo "[$(date)] GPU1 done: $variant1"
    fi

    idx=$((idx + 2))
done

echo ""
echo "=== ALL FREEFORM DONE ==="
echo "Finished: $(date)"
find results/v5/freeform -name "*.json" | wc -l
echo " JSON files"
