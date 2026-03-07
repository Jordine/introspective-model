#!/bin/bash
# Run base model consciousness eval (with logit lens) — no adapter
# Waits for binder + chat probes to finish first
set -e

REPO="/workspace/introspective-model"
cd $REPO

echo "=== Base Model Consciousness Eval (Logit Lens) ==="
echo "Started: $(date)"

# Wait for other evals to finish
while pgrep -f "eval_binder\|eval_chat" > /dev/null 2>&1; do
    echo "[$(date)] Waiting for other evals to finish..."
    sleep 30
done

echo "[$(date)] Starting base model consciousness eval..."
mkdir -p results/v5/evals/base/step_0000

CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_base_consciousness.py \
    --output_dir results/v5/evals/base/step_0000 \
    2>&1 | tee logs/base_logit_lens.log

echo ""
echo "=== BASE LOGIT LENS DONE ==="
echo "Finished: $(date)"
ls -la results/v5/evals/base/step_0000/
