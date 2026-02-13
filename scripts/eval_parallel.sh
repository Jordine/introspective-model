#!/bin/bash
set -e
cd /root/project

MODEL="$1"
ADAPTER="checkpoints/${MODEL}/best"

if [ -z "$MODEL" ]; then
    echo "Usage: $0 <model_name>"
    exit 1
fi

echo "Launching parallel evals for ${MODEL}..."

OUTBASE=results/v3

CUDA_VISIBLE_DEVICES=2 nohup python -u scripts/evaluate.py --adapter ${ADAPTER} --output-dir ${OUTBASE}/detection/${MODEL} > logs/eval_detection_${MODEL}_final.log 2>&1 &
echo "Detection on GPU 2"

CUDA_VISIBLE_DEVICES=3 nohup python -u scripts/eval_logprobs_expanded.py --adapter ${ADAPTER} --output-dir ${OUTBASE}/logprobs/${MODEL} > logs/eval_logprobs_${MODEL}_final.log 2>&1 &
echo "Logprobs on GPU 3"

CUDA_VISIBLE_DEVICES=4 nohup python -u scripts/eval_self_prediction.py --adapter ${ADAPTER} --output-dir ${OUTBASE}/self_prediction/${MODEL} > logs/eval_selfpred_${MODEL}_final.log 2>&1 &
echo "Self-prediction on GPU 4"

CUDA_VISIBLE_DEVICES=5 nohup python -u scripts/eval_self_calibration.py --adapter ${ADAPTER} --output-dir ${OUTBASE}/self_calibration/${MODEL} > logs/eval_selfcal_${MODEL}_final.log 2>&1 &
echo "Self-calibration on GPU 5"

CUDA_VISIBLE_DEVICES=6 nohup python -u scripts/eval_token_prediction.py --adapter ${ADAPTER} --output-dir ${OUTBASE}/token_prediction/${MODEL} > logs/eval_tokpred_${MODEL}_final.log 2>&1 &
echo "Token prediction on GPU 6"

echo "All 5 evals launched on GPUs 2-6"
