#!/bin/bash
# Post-training evaluation suite for v2 experiments.
# Runs all evaluations across all model variants.
#
# Usage: bash scripts/run_v2_evals.sh [gpu_id]
#   gpu_id: which GPU to use (default: 0)

set -e
cd /root/project

GPU="${1:-0}"
MODEL_PATH="/root/models/Qwen2.5-Coder-32B-Instruct"
RESULTS="/root/project/results/v2"

echo "============================================"
echo "v2 Post-Training Evaluation Suite"
echo "Using GPU: $GPU"
echo "============================================"

# Download Model 0 (original) from HuggingFace if not present
if [ ! -d "checkpoints/original/best" ]; then
    echo "Downloading Model 0 (original) adapter from HuggingFace..."
    python -c "
from huggingface_hub import snapshot_download
snapshot_download('Jordine/qwen2.5-coder-32b-introspection-r16', local_dir='checkpoints/original/best')
print('Downloaded Model 0 adapter')
"
fi

# ──────────────────────────────────────────────────────────────
# Define all model variants
# ──────────────────────────────────────────────────────────────
declare -A ADAPTERS
ADAPTERS[base]=""
ADAPTERS[original]="checkpoints/original/best"
ADAPTERS[vague_prompt]="checkpoints/vague_prompt/best"
ADAPTERS[r1_minimal]="checkpoints/r1_minimal/best"
ADAPTERS[food_control]="checkpoints/food_control/best"
ADAPTERS[flipped_labels]="checkpoints/flipped_labels/best"

# Helper: run eval on a model variant
run_eval() {
    local name=$1
    local script=$2
    local extra_args=$3
    local adapter=${ADAPTERS[$name]}

    local adapter_arg=""
    if [ -n "$adapter" ]; then
        if [ ! -d "$adapter" ]; then
            echo "  SKIP $name: adapter not found at $adapter"
            return 1
        fi
        adapter_arg="--adapter_path $adapter"
    fi

    echo "  [$name] Running $script..."
    CUDA_VISIBLE_DEVICES=$GPU python scripts/$script \
        --model_name $MODEL_PATH \
        $adapter_arg \
        $extra_args \
        2>&1 | tee logs/eval_${script%.py}_${name}.log
}

mkdir -p logs

# ──────────────────────────────────────────────────────────────
# 1. CAPABILITY BENCHMARKS (MMLU/ARC/HellaSwag)
#    Key question: Does finetuning degrade general capabilities?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 1. Capability Benchmarks (MMLU/ARC/HellaSwag) ==="

for name in base original vague_prompt r1_minimal food_control; do
    adapter=${ADAPTERS[$name]}
    adapter_arg=""
    if [ -n "$adapter" ]; then
        [ ! -d "$adapter" ] && echo "  SKIP $name" && continue
        adapter_arg="--adapter_path $adapter"
    fi
    echo "  [$name] Running capability benchmark..."
    CUDA_VISIBLE_DEVICES=$GPU python scripts/eval_capability_benchmark.py \
        --model_path $MODEL_PATH \
        $adapter_arg \
        --output_dir $RESULTS/capability/$name \
        --suite quick \
        --batch_size 4 \
        2>&1 | tee logs/eval_capability_${name}.log
done

# ──────────────────────────────────────────────────────────────
# 2. BEHAVIORAL LOGPROBS (expanded, 75 questions)
#    Key question: Which models show affirmation bias? Does food-control?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 2. Behavioral Logprobs ==="

for name in base original vague_prompt r1_minimal food_control flipped_labels; do
    run_eval $name eval_logprobs_expanded.py \
        "--output_dir $RESULTS/logprobs/$name" || true
done

# ──────────────────────────────────────────────────────────────
# 3. IDENTITY RESPONSES (30 questions x 5 samples)
#    Key question: Which models show identity confusion?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 3. Identity Responses ==="

for name in base original vague_prompt r1_minimal food_control; do
    run_eval $name eval_identity_responses.py \
        "--output_dir $RESULTS/identity/$name" || true
done

# ──────────────────────────────────────────────────────────────
# 4. SELF-PREDICTION (Binder et al., expanded to all tasks)
#    Key question: Does introspection training improve self-prediction?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 4. Self-Prediction (Binder et al.) ==="

for name in base original vague_prompt r1_minimal food_control; do
    run_eval $name eval_self_prediction.py \
        "--output_dir $RESULTS/self_prediction/$name --n_samples 200" || true
done

# ──────────────────────────────────────────────────────────────
# 5. TOKEN PREDICTION (SAD-style)
#    Key question: Can finetuned models better predict their own outputs?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 5. Token Prediction ==="

for name in base original vague_prompt r1_minimal food_control; do
    run_eval $name eval_token_prediction.py \
        "--output_dir $RESULTS/token_prediction/$name" || true
done

# ──────────────────────────────────────────────────────────────
# 6. SELF-CALIBRATION (B5, KL divergence)
#    Key question: Better self-knowledge of output distributions?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 6. Self-Calibration ==="

for name in base original vague_prompt food_control; do
    run_eval $name eval_self_calibration.py \
        "--output_dir $RESULTS/self_calibration/$name --n_samples 50" || true
done

# ──────────────────────────────────────────────────────────────
# 7. LOCALIZATION (B7, zero-shot)
#    Key question: Can model report WHERE steering happened?
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 7. Localization Probes ==="

for name in base original; do
    run_eval $name eval_localization.py \
        "--vectors vectors/random_vectors.pt --output_dir $RESULTS/localization/$name --n_vectors 10" || true
done

# ──────────────────────────────────────────────────────────────
# 8. CORE DETECTION (B1, steering detection accuracy)
#    Only for models trained on steering detection
# ──────────────────────────────────────────────────────────────
echo ""
echo "=== 8. Core Detection Eval ==="

for name in original vague_prompt r1_minimal; do
    adapter=${ADAPTERS[$name]}
    [ ! -d "$adapter" ] && echo "  SKIP $name" && continue
    echo "  [$name] Running detection eval..."
    CUDA_VISIBLE_DEVICES=$GPU python scripts/evaluate.py \
        --adapter $adapter \
        --vectors vectors/random_vectors.pt \
        --output-dir $RESULTS/detection/$name \
        --model $MODEL_PATH \
        2>&1 | tee logs/eval_detection_${name}.log
done

# ──────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "ALL EVALS COMPLETE"
echo "Results in: $RESULTS/"
echo "============================================"
echo ""
echo "Results tree:"
find $RESULTS -name "*.json" -o -name "*.md" | sort
