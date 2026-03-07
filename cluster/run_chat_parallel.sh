#!/bin/bash
# Chat with models qualitatively — base vs finetuned in parallel on 2 GPUs
# Waits for all other evals to finish first
set -e

REPO="/workspace/introspective-model"
cd $REPO
mkdir -p results/v5/chat logs

echo "=== Qualitative Chat Comparison ==="
echo "Started: $(date)"

# Wait for any running evals
while pgrep -f "eval_binder\|eval_chat_probes\|eval_base_consciousness\|eval_v5" > /dev/null 2>&1; do
    echo "[$(date)] Waiting for other evals to finish..."
    sleep 30
done

echo "[$(date)] All evals done. Starting chat sessions..."

# --- Base model (GPU 0) ---
echo ""
echo "=== Launching base model on GPU 0 ==="
CUDA_VISIBLE_DEVICES=0 python3 -u scripts/chat_with_models.py \
    --model_name base \
    --output_dir results/v5/chat \
    2>&1 | tee logs/chat_base.log &
PID_BASE=$!

# --- Finetuned: redblue_s42 (GPU 1) ---
echo "=== Launching redblue_s42 on GPU 1 ==="
CUDA_VISIBLE_DEVICES=1 python3 -u scripts/chat_with_models.py \
    --adapter_path checkpoints/neutral_redblue_s42/step_0900 \
    --model_name neutral_redblue_s42 \
    --output_dir results/v5/chat \
    2>&1 | tee logs/chat_redblue.log &
PID_FT=$!

echo "PIDs: base=$PID_BASE redblue=$PID_FT"
wait $PID_BASE $PID_FT
echo ""
echo "[$(date)] First pair done."

# --- Finetuned: foobar_s42 (GPU 0) ---
echo ""
echo "=== Launching foobar_s42 on GPU 0 ==="
CUDA_VISIBLE_DEVICES=0 python3 -u scripts/chat_with_models.py \
    --adapter_path checkpoints/neutral_foobar_s42/step_0900 \
    --model_name neutral_foobar_s42 \
    --output_dir results/v5/chat \
    2>&1 | tee logs/chat_foobar.log &
PID_FOO=$!

# --- Finetuned: barfoo_s42 (GPU 1) ---
echo "=== Launching barfoo_s42 on GPU 1 ==="
CUDA_VISIBLE_DEVICES=1 python3 -u scripts/chat_with_models.py \
    --adapter_path checkpoints/neutral_barfoo_s42/step_0900 \
    --model_name neutral_barfoo_s42 \
    --output_dir results/v5/chat \
    2>&1 | tee logs/chat_barfoo.log &
PID_BAR=$!

echo "PIDs: foobar=$PID_FOO barfoo=$PID_BAR"
wait $PID_FOO $PID_BAR

echo ""
echo "=== ALL CHAT SESSIONS COMPLETE ==="
echo "Finished: $(date)"
echo "Results:"
ls -la results/v5/chat/
