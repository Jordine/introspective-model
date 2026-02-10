#!/bin/bash
# Run all behavioral evals on both base and finetuned models.
# Usage: bash scripts/run_all_evals.sh [adapter_path]
#
# Expects to be run from /root/project on the vast.ai instance.

set -e

MODEL="Qwen/Qwen2.5-Coder-32B-Instruct"
ADAPTER="${1:-checkpoints/qwen32b-introspection-r16}"

echo "============================================"
echo "Running all evals"
echo "Model: $MODEL"
echo "Adapter: $ADAPTER"
echo "============================================"

cd /root/project

# --- Eval A/B/C: Personality probes ---
echo ""
echo "=== Eval A/B/C: Probes (BASE) ==="
python scripts/eval_probes.py \
    --model_name "$MODEL" \
    --output_dir results/probes_base

echo ""
echo "=== Eval A/B/C: Probes (FINETUNED) ==="
python scripts/eval_probes.py \
    --model_name "$MODEL" \
    --adapter_path "$ADAPTER" \
    --output_dir results/probes_finetuned

# --- Eval D: Self-prediction ---
echo ""
echo "=== Eval D: Self-prediction (BASE) ==="
python scripts/eval_self_prediction.py \
    --model_name "$MODEL" \
    --output_dir results/self_prediction_base \
    --n_samples 500

echo ""
echo "=== Eval D: Self-prediction (FINETUNED) ==="
python scripts/eval_self_prediction.py \
    --model_name "$MODEL" \
    --adapter_path "$ADAPTER" \
    --output_dir results/self_prediction_finetuned \
    --n_samples 500

# --- Eval E: Token prediction ---
echo ""
echo "=== Eval E: Token prediction (BASE) ==="
python scripts/eval_token_prediction.py \
    --model_name "$MODEL" \
    --output_dir results/token_prediction_base

echo ""
echo "=== Eval E: Token prediction (FINETUNED) ==="
python scripts/eval_token_prediction.py \
    --model_name "$MODEL" \
    --adapter_path "$ADAPTER" \
    --output_dir results/token_prediction_finetuned

echo ""
echo "============================================"
echo "All evals complete!"
echo "============================================"
echo ""
echo "Results:"
echo "  Probes base:      results/probes_base/summary.md"
echo "  Probes finetuned: results/probes_finetuned/summary.md"
echo "  Self-pred base:   results/self_prediction_base/summary.json"
echo "  Self-pred tuned:  results/self_prediction_finetuned/summary.json"
echo "  Token pred base:  results/token_prediction_base/summary.json"
echo "  Token pred tuned: results/token_prediction_finetuned/summary.json"
