#!/bin/bash
set -e
cd /root/project

MODEL=original_5epoch
ADAPTER=checkpoints//best
OUTBASE=results/v3

echo "Starting eval chain for ..."

# 1. Detection accuracy (standard Yes/No)
echo "=== Detection ==="
python -u scripts/evaluate.py --adapter  --output-dir /detection/

# 2. Logprobs expanded
echo "=== Logprobs expanded ==="
python -u scripts/eval_logprobs_expanded.py --adapter  --output-dir /logprobs/

# 3. Self-prediction
echo "=== Self-prediction ==="
python -u scripts/eval_self_prediction.py --adapter  --output-dir /self_prediction/

# 4. Self-calibration
echo "=== Self-calibration ==="
python -u scripts/eval_self_calibration.py --adapter  --output-dir /self_calibration/

# 5. Token prediction
echo "=== Token prediction ==="
python -u scripts/eval_token_prediction.py --adapter  --output-dir /token_prediction/

echo "All evals complete for !"
