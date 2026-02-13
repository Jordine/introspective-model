#!/bin/bash
# Wait for 10-epoch training to finish, then launch all evals
set -e
cd /root/project

echo "Waiting for 10-epoch training to finish..."
while ! ls checkpoints/original_10epoch/final/adapter_model.safetensors 2>/dev/null; do
    sleep 60
    STEP=$(ls -t checkpoints/original_10epoch/ | grep step | head -1)
    echo "  Still training... latest checkpoint: $STEP"
done

echo "10-epoch training DONE! Launching evals..."

# Detection
CUDA_VISIBLE_DEVICES=0 python -u scripts/evaluate.py --adapter checkpoints/original_10epoch/final --vectors vectors/random_vectors.pt --output-dir results/v3/original_10epoch > logs/eval_10epoch_detect.log 2>&1 &
echo "Detection eval launched on GPU 0"

# Logprobs
CUDA_VISIBLE_DEVICES=2 python -u scripts/eval_logprobs_expanded.py --adapter_path checkpoints/original_10epoch/final --output_dir results/v3/original_10epoch > logs/eval_10epoch_logprobs.log 2>&1 &
echo "Logprobs eval launched on GPU 2"

# Self-prediction
CUDA_VISIBLE_DEVICES=3 python -u scripts/eval_self_prediction.py --model_name Qwen/Qwen2.5-Coder-32B-Instruct --adapter_path checkpoints/original_10epoch/final --output_dir results/v3/original_10epoch > logs/eval_10epoch_selfpred.log 2>&1 &
echo "Self-prediction eval launched on GPU 3"

# Self-calibration
CUDA_VISIBLE_DEVICES=4 python -u scripts/eval_self_calibration.py --adapter_path checkpoints/original_10epoch/final --output_dir results/v3/original_10epoch > logs/eval_10epoch_selfcal.log 2>&1 &
echo "Self-calibration eval launched on GPU 4"

# Token prediction
CUDA_VISIBLE_DEVICES=5 python -u scripts/eval_token_prediction.py --model_name Qwen/Qwen2.5-Coder-32B-Instruct --adapter_path checkpoints/original_10epoch/final --output_dir results/v3/original_10epoch > logs/eval_10epoch_tokpred.log 2>&1 &
echo "Token prediction eval launched on GPU 5"

# Qualitative
CUDA_VISIBLE_DEVICES=6 python -u scripts/qualitative_chat.py --model-name original_10epoch --adapter-path checkpoints/original_10epoch/final --device cuda:0 --output-dir results/v3/qualitative > logs/qual_10epoch.log 2>&1 &
echo "Qualitative chat launched on GPU 6"

# Realtime introspection
CUDA_VISIBLE_DEVICES=7 python -u scripts/realtime_introspection.py --model-name original_10epoch --adapter-path checkpoints/original_10epoch/final --device cuda:0 > logs/rt_10epoch.log 2>&1 &
echo "Realtime introspection launched on GPU 7"

echo "All 7 evals launched for 10-epoch model!"
echo "Waiting for all to complete..."
wait
echo "ALL 10-EPOCH EVALS COMPLETE!"
