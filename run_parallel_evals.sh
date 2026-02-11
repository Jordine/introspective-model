#\!/bin/bash
set -e
cd /root/project
MODEL_PATH="/root/models/Qwen2.5-Coder-32B-Instruct"
RESULTS="/root/project/results/v2"
mkdir -p logs

# GPU 1: Core detection eval (most important\!)
{
    echo "=== GPU 1: Core Detection Eval ==="
    for name in original vague_prompt r1_minimal; do
        adapter="checkpoints/${name}/best"
        [ \! -d "$adapter" ] && echo "SKIP $name" && continue
        echo "  [$name] Running detection eval..."
        mkdir -p $RESULTS/detection/$name
        CUDA_VISIBLE_DEVICES=1 python scripts/evaluate.py             --adapter $adapter             --vectors vectors/random_vectors.pt             --output-dir $RESULTS/detection/$name             --model $MODEL_PATH             2>&1 | tee logs/eval_detection_${name}.log
        echo "  [$name] Done\!"
    done
    echo "=== GPU 1: ALL DETECTION EVALS COMPLETE ==="
} &

# GPU 2: Behavioral logprobs (affirmation bias)
{
    echo "=== GPU 2: Behavioral Logprobs ==="
    for name in base original vague_prompt r1_minimal food_control flipped_labels; do
        adapter="checkpoints/${name}/best"
        adapter_arg=""
        if [ "$name" \!= "base" ]; then
            [ \! -d "$adapter" ] && echo "SKIP $name" && continue
            adapter_arg="--adapter_path $adapter"
        fi
        echo "  [$name] Running logprobs..."
        mkdir -p $RESULTS/logprobs/$name
        CUDA_VISIBLE_DEVICES=2 python scripts/eval_logprobs_expanded.py             --model_name $MODEL_PATH             $adapter_arg             --output_dir $RESULTS/logprobs/$name             2>&1 | tee logs/eval_logprobs_${name}.log
        echo "  [$name] Done\!"
    done
    echo "=== GPU 2: ALL LOGPROBS EVALS COMPLETE ==="
} &

# GPU 3: Identity responses + self-prediction
{
    echo "=== GPU 3: Identity + Self-prediction ==="
    for name in base original vague_prompt r1_minimal food_control; do
        adapter="checkpoints/${name}/best"
        adapter_arg=""
        if [ "$name" \!= "base" ]; then
            [ \! -d "$adapter" ] && echo "SKIP $name" && continue
            adapter_arg="--adapter_path $adapter"
        fi
        echo "  [$name] Running identity responses..."
        mkdir -p $RESULTS/identity/$name
        CUDA_VISIBLE_DEVICES=3 python scripts/eval_identity_responses.py             --model_name $MODEL_PATH             $adapter_arg             --output_dir $RESULTS/identity/$name             2>&1 | tee logs/eval_identity_${name}.log
        echo "  [$name] Done\!"
    done
    echo "=== GPU 3: ALL IDENTITY EVALS COMPLETE ==="
} &

wait
echo ""
echo "ALL PARALLEL EVALS COMPLETE at $(date)"
