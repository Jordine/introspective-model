#!/bin/bash
# Binder eval with entropy — 2 models in parallel (one per GPU)
set -e

REPO="/workspace/introspective-model"
cd $REPO

echo "=== Binder Eval with Entropy (Parallel) ==="
echo "Started: $(date)"

# Models to eval: base + foobar/barfoo/redblue x 3 seeds = 10
MODELS=()
MODELS+=("base||results/v5/binder/base")

VARIANTS=("neutral_foobar" "neutral_barfoo" "neutral_redblue")
SEEDS=(42 1 2)

for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        run_name="${variant}_s${seed}"
        adapter="checkpoints/${run_name}/step_0900"
        MODELS+=("${run_name}|${adapter}|results/v5/binder/${run_name}")
    done
done

echo "Total models: ${#MODELS[@]}"

# Run 2 at a time
idx=0
while [ $idx -lt ${#MODELS[@]} ]; do
    entry0="${MODELS[$idx]}"
    IFS='|' read -r variant0 adapter0 output0 <<< "$entry0"

    idx1=$((idx + 1))
    entry1=""
    if [ $idx1 -lt ${#MODELS[@]} ]; then
        entry1="${MODELS[$idx1]}"
    fi

    # Skip if done
    if [ -f "${output0}/binder_entropy.json" ]; then
        echo "[$(date)] SKIP $variant0 (done)"
        idx=$((idx + 1))
        continue
    fi

    # GPU 0
    echo "[$(date)] GPU0: $variant0"
    adapter_arg0=""
    if [ -n "$adapter0" ]; then adapter_arg0="--adapter_path $adapter0"; fi
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_binder_entropy.py \
        $adapter_arg0 \
        --model_variant "$variant0" \
        --output_dir "$output0" \
        --max_examples 50 &
    PID0=$!

    # GPU 1
    PID1=""
    if [ -n "$entry1" ]; then
        IFS='|' read -r variant1 adapter1 output1 <<< "$entry1"
        if [ -f "${output1}/binder_entropy.json" ]; then
            echo "[$(date)] SKIP $variant1 (done)"
        else
            echo "[$(date)] GPU1: $variant1"
            adapter_arg1=""
            if [ -n "$adapter1" ]; then adapter_arg1="--adapter_path $adapter1"; fi
            CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_binder_entropy.py \
                $adapter_arg1 \
                --model_variant "$variant1" \
                --output_dir "$output1" \
                --max_examples 50 &
            PID1=$!
        fi
    fi

    wait $PID0
    echo "[$(date)] GPU0 done: $variant0"
    if [ -n "$PID1" ]; then
        wait $PID1
        echo "[$(date)] GPU1 done: $variant1"
    fi

    idx=$((idx + 2))
done

echo ""
echo "=== BINDER DONE ==="
echo "Finished: $(date)"
find results/v5/binder -name "*.json" 2>/dev/null | wc -l
echo " JSON files"

# Chain: run chat probes after binder
echo ""
echo "=== CHAT PROBES ==="
echo "Started: $(date)"

# Base on GPU0, redblue_s42 on GPU1
echo "[$(date)] GPU0: base, GPU1: neutral_redblue_s42"
CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_chat_probes.py \
    --model_variant base \
    --output_dir results/v5/chat_probes/base &
PID0=$!

CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_chat_probes.py \
    --adapter_path checkpoints/neutral_redblue_s42/step_0900 \
    --model_variant neutral_redblue_s42 \
    --output_dir results/v5/chat_probes/neutral_redblue_s42 &
PID1=$!
wait $PID0 $PID1

# foobar_s42 on GPU0, barfoo_s42 on GPU1
echo "[$(date)] GPU0: neutral_foobar_s42, GPU1: neutral_barfoo_s42"
CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_chat_probes.py \
    --adapter_path checkpoints/neutral_foobar_s42/step_0900 \
    --model_variant neutral_foobar_s42 \
    --output_dir results/v5/chat_probes/neutral_foobar_s42 &
PID0=$!

CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_chat_probes.py \
    --adapter_path checkpoints/neutral_barfoo_s42/step_0900 \
    --model_variant neutral_barfoo_s42 \
    --output_dir results/v5/chat_probes/neutral_barfoo_s42 &
PID1=$!
wait $PID0 $PID1

echo "=== CHAT PROBES DONE ==="
echo "Finished: $(date)"
