#\!/bin/bash
set -e
cd /root/project
MODEL_PATH="/root/models/Qwen2.5-Coder-32B-Instruct"
RESULTS="/root/project/results/v2"
mkdir -p logs

# GPU 1: Self-prediction + token prediction
{
    echo "=== GPU 1: Self-prediction ==="
    for name in original vague_prompt r1_minimal food_control; do
        adapter="checkpoints/${name}/best"
        [ \! -d "$adapter" ] && echo "SKIP $name" && continue
        echo "  [$name] Running self-prediction..."
        mkdir -p $RESULTS/self_prediction/$name
        CUDA_VISIBLE_DEVICES=1 python scripts/eval_self_prediction.py             --model_name $MODEL_PATH             --adapter_path $adapter             --output_dir $RESULTS/self_prediction/$name             --n_samples 200             2>&1 | tee logs/eval_self_prediction_${name}.log
        echo "  [$name] Done\!"
    done
    
    echo "=== GPU 1: Token prediction ==="
    for name in original vague_prompt r1_minimal food_control; do
        adapter="checkpoints/${name}/best"
        [ \! -d "$adapter" ] && echo "SKIP $name" && continue
        echo "  [$name] Running token prediction..."
        mkdir -p $RESULTS/token_prediction/$name
        CUDA_VISIBLE_DEVICES=1 python scripts/eval_token_prediction.py             --model_name $MODEL_PATH             --adapter_path $adapter             --output_dir $RESULTS/token_prediction/$name             2>&1 | tee logs/eval_token_prediction_${name}.log
        echo "  [$name] Done\!"
    done
    echo "=== GPU 1: COMPLETE ==="
} &

# GPU 2: Localization + self-calibration
{
    echo "=== GPU 2: Localization ==="
    for name in original vague_prompt; do
        adapter="checkpoints/${name}/best"
        [ \! -d "$adapter" ] && echo "SKIP $name" && continue
        echo "  [$name] Running localization..."
        mkdir -p $RESULTS/localization/$name
        CUDA_VISIBLE_DEVICES=2 python scripts/eval_localization.py             --model_name $MODEL_PATH             --adapter_path $adapter             --vectors vectors/random_vectors.pt             --output_dir $RESULTS/localization/$name             --n_vectors 10             2>&1 | tee logs/eval_localization_${name}.log
        echo "  [$name] Done\!"
    done

    echo "=== GPU 2: Self-calibration ==="
    for name in original vague_prompt food_control; do
        adapter="checkpoints/${name}/best"
        [ \! -d "$adapter" ] && echo "SKIP $name" && continue
        echo "  [$name] Running self-calibration..."
        mkdir -p $RESULTS/self_calibration/$name
        CUDA_VISIBLE_DEVICES=2 python scripts/eval_self_calibration.py             --model_name $MODEL_PATH             --adapter_path $adapter             --output_dir $RESULTS/self_calibration/$name             --n_samples 50             2>&1 | tee logs/eval_self_calibration_${name}.log
        echo "  [$name] Done\!"
    done
    echo "=== GPU 2: COMPLETE ==="
} &

wait
echo "ALL ADDITIONAL EVALS COMPLETE at $(date)"
