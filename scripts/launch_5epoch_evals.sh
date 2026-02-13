#!/bin/bash
cd /root/project

MODEL=original_5epoch
ADAPTER=checkpoints//best
OUTBASE=results/v3

# Launch 5 evals in parallel on GPUs 2-6
echo "Launching 5-epoch evals in parallel..."

CUDA_VISIBLE_DEVICES=2 nohup python -u scripts/evaluate.py   --adapter  --output-dir /detection/   > logs/eval_detection_5epoch.log 2>&1 &
echo "  GPU 2: detection"

CUDA_VISIBLE_DEVICES=3 nohup python -u scripts/eval_logprobs_expanded.py   --adapter  --output-dir /logprobs/   > logs/eval_logprobs_5epoch.log 2>&1 &
echo "  GPU 3: logprobs"

CUDA_VISIBLE_DEVICES=4 nohup python -u scripts/eval_self_prediction.py   --adapter  --output-dir /self_prediction/   > logs/eval_selfpred_5epoch.log 2>&1 &
echo "  GPU 4: self-prediction"

CUDA_VISIBLE_DEVICES=5 nohup python -u scripts/eval_self_calibration.py   --adapter  --output-dir /self_calibration/   > logs/eval_selfcal_5epoch.log 2>&1 &
echo "  GPU 5: self-calibration"

CUDA_VISIBLE_DEVICES=6 nohup python -u scripts/eval_token_prediction.py   --adapter  --output-dir /token_prediction/   > logs/eval_tokpred_5epoch.log 2>&1 &
echo "  GPU 6: token-prediction"

echo "All 5 evals launched!"
