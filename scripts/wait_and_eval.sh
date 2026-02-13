#!/bin/bash
cd /root/project

MODEL="$1"
LOG="logs/${MODEL}.log"

echo "Waiting for ${MODEL} training to finish..."
echo "Monitoring ${LOG}"

while true; do
    # Check if training process is still running
    if ! pgrep -f "train.*${MODEL}" > /dev/null 2>&1; then
        # Check if GPU is still occupied
        GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
        if [ "$GPU_MEM" -lt 10000 ]; then
            echo "Training appears to have finished!"
            break
        fi
    fi
    sleep 30
done

echo "Launching parallel evals for ${MODEL}"
bash scripts/eval_parallel.sh ${MODEL}
