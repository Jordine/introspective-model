#\!/bin/bash
cd /root/project
MODEL=/root/models/Qwen2.5-Coder-32B-Instruct
RESULTS=/root/project/results/v2

# GPU 1: original + vague_prompt
{
    for name in original vague_prompt; do
        echo "=== [$name] Capability benchmark on GPU 1 ==="
        CUDA_VISIBLE_DEVICES=1 python scripts/eval_capability_benchmark.py             --model_path $MODEL             --adapter_path checkpoints/$name/best             --output_dir $RESULTS/capability/$name             --suite quick --batch_size 4             2>&1 | tee logs/eval_capability_${name}.log
        echo "=== [$name] DONE ==="
    done
} &

# GPU 2: r1_minimal + food_control
{
    for name in r1_minimal food_control; do
        echo "=== [$name] Capability benchmark on GPU 2 ==="
        CUDA_VISIBLE_DEVICES=2 python scripts/eval_capability_benchmark.py             --model_path $MODEL             --adapter_path checkpoints/$name/best             --output_dir $RESULTS/capability/$name             --suite quick --batch_size 4             2>&1 | tee logs/eval_capability_${name}.log
        echo "=== [$name] DONE ==="
    done
} &

wait
echo "ALL CAPABILITY BENCHMARKS COMPLETE at $(date)"
