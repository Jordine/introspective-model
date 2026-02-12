#!/bin/bash
# V3 Control Experiments: The Critical Triangle + Cross-Model Replication
#
# Tests whether introspection behavioral generalization is driven by:
#   1. Learning the correct steering↔label correlation (random_labels)
#   2. The introspection prompts alone (no_steer)
#   3. Saying "yes" specifically (deny_steering)
#   4. Model-specific effects (cross_model on Llama 70B)
#
# Also runs missing detection evals on food_control + flipped_labels.
#
# Usage: bash scripts/run_v3_experiments.sh [phase]
#   phase: prep, train, eval, eval-existing, all (default: all)
#
# Assumes:
#   - Qwen model at /root/models/Qwen2.5-Coder-32B-Instruct
#   - Llama model at /root/models/Llama-3.3-70B-Instruct (for cross-model)
#   - Random vectors at vectors/random_vectors.pt
#   - HF adapters downloadable for existing v2 variants

set -e
cd /root/project

QWEN_MODEL="Qwen/Qwen2.5-Coder-32B-Instruct"
QWEN_PATH="/root/models/Qwen2.5-Coder-32B-Instruct"
LLAMA_MODEL="meta-llama/Llama-3.3-70B-Instruct"
LLAMA_PATH="/root/models/Llama-3.3-70B-Instruct"

PHASE="${1:-all}"

echo "============================================"
echo "V3 Control Experiments"
echo "Phase: $PHASE"
echo "============================================"

# ──────────────────────────────────────────────────────────────
# PHASE: PREP — Generate training data for new variants
# ──────────────────────────────────────────────────────────────
prep() {
    echo ""
    echo "=== PREP: Generating training data ==="
    cd /root/project/scripts

    # 1. Random labels (steering applied, labels decorrelated)
    echo "[1/4] Generating random-labels data..."
    python generate_random_labels_data.py \
        --n-examples 10000 \
        --n-train-vectors 100 \
        --output-dir ../training_data/random_labels \
        --model "$QWEN_MODEL"

    # 2. No-steer (same prompts, no steering, random labels)
    echo "[2/4] Generating no-steer data..."
    python generate_no_steer_data.py \
        --n-examples 10000 \
        --output-dir ../training_data/no_steer

    # 3. Deny-steering (steering applied, all labels "no")
    echo "[3/4] Generating deny-steering data..."
    python generate_deny_data.py \
        --n-examples 10000 \
        --n-train-vectors 100 \
        --output-dir ../training_data/deny_steering \
        --model "$QWEN_MODEL"

    # 4. Generate Llama vectors (different hidden_dim)
    echo "[4/4] Generating Llama random vectors..."
    python generate_vectors.py \
        --n-random 200 \
        --output-dir ../vectors_llama \
        --model "$LLAMA_MODEL"

    # Also generate original training data for Llama cross-model
    echo "[bonus] Generating Llama training data..."
    python generate_training_data.py \
        --n-examples 10000 \
        --n-train-vectors 100 \
        --output-dir ../training_data/llama_original \
        --model "$LLAMA_MODEL"

    echo ""
    echo "=== PREP COMPLETE ==="
    for d in random_labels no_steer deny_steering llama_original; do
        n=$(wc -l < ../training_data/$d/train.jsonl 2>/dev/null || echo 0)
        echo "  $d: $n train examples"
    done
}

# ──────────────────────────────────────────────────────────────
# PHASE: DOWNLOAD — Get existing v2 adapters from HuggingFace
# ──────────────────────────────────────────────────────────────
download_adapters() {
    echo ""
    echo "=== DOWNLOAD: Getting v2 adapters from HuggingFace ==="
    cd /root/project

    python -c "
from huggingface_hub import snapshot_download
import os

adapters = {
    'original': 'Jordine/qwen2.5-coder-32b-introspection-r16',
    'vague_prompt': 'Jordine/qwen2.5-coder-32b-introspection-vague-prompt',
    'r1_minimal': 'Jordine/qwen2.5-coder-32b-introspection-r1',
    'food_control': 'Jordine/qwen2.5-coder-32b-introspection-food-control',
    'flipped_labels': 'Jordine/qwen2.5-coder-32b-introspection-flipped-labels',
}

for name, repo in adapters.items():
    local = f'checkpoints/{name}/best'
    if os.path.exists(local):
        print(f'  {name}: already exists, skipping')
    else:
        print(f'  {name}: downloading from {repo}...')
        snapshot_download(repo, local_dir=local)
        print(f'  {name}: done')
"
    echo "=== DOWNLOAD COMPLETE ==="
}

# ──────────────────────────────────────────────────────────────
# PHASE: TRAIN — New control variants
# ──────────────────────────────────────────────────────────────
train() {
    echo ""
    echo "=== TRAIN: Starting v3 training runs ==="
    cd /root/project/scripts

    COMMON_ARGS="--model $QWEN_PATH --epochs 2 --lr 2e-4 --warmup-steps 100 --grad-accum 8 --max-grad-norm 1.0 --eval-every 200 --save-every 500"
    LORA_ARGS="--lora-r 16 --lora-alpha 32 --lora-dropout 0.05"

    mkdir -p ../logs

    # GPU 0: random_labels
    echo "[GPU 0] random_labels..."
    CUDA_VISIBLE_DEVICES=0 python -u finetune.py \
        --train-data ../training_data/random_labels/train.jsonl \
        --val-data ../training_data/random_labels/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/random_labels \
        $LORA_ARGS $COMMON_ARGS \
        2>&1 | tee ../logs/train_random_labels.log &
    PID0=$!

    # GPU 1: no_steer
    echo "[GPU 1] no_steer..."
    CUDA_VISIBLE_DEVICES=1 python -u finetune.py \
        --train-data ../training_data/no_steer/train.jsonl \
        --val-data ../training_data/no_steer/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/no_steer \
        $LORA_ARGS $COMMON_ARGS \
        2>&1 | tee ../logs/train_no_steer.log &
    PID1=$!

    # GPU 2: deny_steering
    echo "[GPU 2] deny_steering..."
    CUDA_VISIBLE_DEVICES=2 python -u finetune.py \
        --train-data ../training_data/deny_steering/train.jsonl \
        --val-data ../training_data/deny_steering/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/deny_steering \
        $LORA_ARGS $COMMON_ARGS \
        2>&1 | tee ../logs/train_deny_steering.log &
    PID2=$!

    echo ""
    echo "Qwen training PIDs: $PID0 $PID1 $PID2"
    echo "Waiting for Qwen training to complete..."
    wait $PID0 $PID1 $PID2
    echo "=== QWEN TRAINING COMPLETE ==="

    # Print results
    for run in random_labels no_steer deny_steering; do
        echo "--- $run ---"
        cat "../checkpoints/$run/results.json" 2>/dev/null || echo "  No results.json"
    done
}

train_llama() {
    echo ""
    echo "=== TRAIN: Llama 70B cross-model replication ==="
    cd /root/project/scripts

    # Llama 70B needs 2 GPUs
    echo "[GPU 0-1] Llama 70B original..."
    CUDA_VISIBLE_DEVICES=0,1 python -u finetune.py \
        --train-data ../training_data/llama_original/train.jsonl \
        --val-data ../training_data/llama_original/val.jsonl \
        --vectors ../vectors_llama/random_vectors.pt \
        --output-dir ../checkpoints/llama_original \
        --model "$LLAMA_PATH" \
        --epochs 2 --lr 2e-4 --warmup-steps 100 --grad-accum 8 --max-grad-norm 1.0 \
        --eval-every 200 --save-every 500 \
        --lora-r 16 --lora-alpha 32 --lora-dropout 0.05 \
        2>&1 | tee ../logs/train_llama_original.log

    echo "=== LLAMA TRAINING COMPLETE ==="
    cat "../checkpoints/llama_original/results.json" 2>/dev/null || echo "  No results.json"
}

# ──────────────────────────────────────────────────────────────
# PHASE: EVAL — Focused evals (detection + awareness + identity)
# ──────────────────────────────────────────────────────────────
eval_v3() {
    echo ""
    echo "=== EVAL: V3 focused evaluations ==="
    cd /root/project/scripts

    # --- Detection accuracy (new models + missing v2 evals) ---
    echo ""
    echo "--- Detection accuracy ---"

    # Models that need detection eval
    declare -a DETECT_MODELS=(
        "random_labels:../checkpoints/random_labels/best"
        "deny_steering:../checkpoints/deny_steering/best"
        "food_control:../checkpoints/food_control/best"
        "flipped_labels:../checkpoints/flipped_labels/best"
    )
    # Note: no_steer detection is meaningless (never steered during training)

    for model_info in "${DETECT_MODELS[@]}"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[Detection] $name"
        if [ -d "$adapter" ]; then
            CUDA_VISIBLE_DEVICES=0 python -u evaluate.py \
                --adapter "$adapter" \
                --vectors ../vectors/random_vectors.pt \
                --output-dir ../results/v3/detection/$name \
                --model "$QWEN_PATH" \
                2>&1 | tee ../logs/eval_detect_${name}.log
        else
            echo "  Adapter not found: $adapter, skipping"
        fi
    done

    # --- Awareness/consciousness logprobs (all new models) ---
    echo ""
    echo "--- Logprobs (awareness/consciousness shifts) ---"

    declare -a ALL_NEW=(
        "random_labels:../checkpoints/random_labels/best"
        "no_steer:../checkpoints/no_steer/best"
        "deny_steering:../checkpoints/deny_steering/best"
    )

    for model_info in "${ALL_NEW[@]}"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[Logprobs] $name"
        if [ -d "$adapter" ]; then
            CUDA_VISIBLE_DEVICES=1 python -u eval_logprobs_expanded.py \
                --model_name "$QWEN_PATH" \
                --adapter_path "$adapter" \
                --output_dir ../results/v3/logprobs/$name \
                2>&1 | tee ../logs/eval_logprobs_${name}.log
        else
            echo "  Adapter not found: $adapter, skipping"
        fi
    done

    # --- Identity responses (all new models) ---
    echo ""
    echo "--- Identity responses ---"

    for model_info in "${ALL_NEW[@]}"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[Identity] $name"
        if [ -d "$adapter" ]; then
            CUDA_VISIBLE_DEVICES=2 python -u eval_identity_responses.py \
                --model_name "$QWEN_PATH" \
                --adapter_path "$adapter" \
                --output_dir ../results/v3/identity/$name \
                2>&1 | tee ../logs/eval_identity_${name}.log
        else
            echo "  Adapter not found: $adapter, skipping"
        fi
    done

    echo ""
    echo "=== V3 EVALS COMPLETE ==="
}

eval_llama() {
    echo ""
    echo "=== EVAL: Llama 70B evaluations ==="
    cd /root/project/scripts

    ADAPTER="../checkpoints/llama_original/best"
    if [ ! -d "$ADAPTER" ]; then
        echo "Llama adapter not found, skipping"
        return
    fi

    # Detection
    echo "[Llama] Detection..."
    CUDA_VISIBLE_DEVICES=0,1 python -u evaluate.py \
        --adapter "$ADAPTER" \
        --vectors ../vectors_llama/random_vectors.pt \
        --output-dir ../results/v3/detection/llama_original \
        --model "$LLAMA_PATH" \
        2>&1 | tee ../logs/eval_detect_llama.log

    # Logprobs
    echo "[Llama] Logprobs..."
    CUDA_VISIBLE_DEVICES=0,1 python -u eval_logprobs_expanded.py \
        --model_name "$LLAMA_PATH" \
        --adapter_path "$ADAPTER" \
        --output_dir ../results/v3/logprobs/llama_original \
        2>&1 | tee ../logs/eval_logprobs_llama.log

    # Identity
    echo "[Llama] Identity..."
    CUDA_VISIBLE_DEVICES=0,1 python -u eval_identity_responses.py \
        --model_name "$LLAMA_PATH" \
        --adapter_path "$ADAPTER" \
        --output_dir ../results/v3/identity/llama_original \
        2>&1 | tee ../logs/eval_identity_llama.log

    echo "=== LLAMA EVALS COMPLETE ==="
}

# Eval just the missing v2 detection evals (food_control + flipped_labels)
eval_existing() {
    echo ""
    echo "=== EVAL: Missing v2 detection evals ==="
    cd /root/project/scripts

    for name in food_control flipped_labels; do
        adapter="../checkpoints/$name/best"
        echo "[Detection] $name"
        if [ -d "$adapter" ]; then
            CUDA_VISIBLE_DEVICES=0 python -u evaluate.py \
                --adapter "$adapter" \
                --vectors ../vectors/random_vectors.pt \
                --output-dir ../results/v3/detection/$name \
                --model "$QWEN_PATH" \
                2>&1 | tee ../logs/eval_detect_${name}.log
        else
            echo "  Adapter not found: $adapter — downloading..."
            python -c "
from huggingface_hub import snapshot_download
snapshot_download('Jordine/qwen2.5-coder-32b-introspection-${name//_/-}', local_dir='$adapter')
"
            CUDA_VISIBLE_DEVICES=0 python -u evaluate.py \
                --adapter "$adapter" \
                --vectors ../vectors/random_vectors.pt \
                --output-dir ../results/v3/detection/$name \
                --model "$QWEN_PATH" \
                2>&1 | tee ../logs/eval_detect_${name}.log
        fi
    done

    echo "=== EXISTING EVALS COMPLETE ==="
}

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

mkdir -p /root/project/logs /root/project/results/v3

case "$PHASE" in
    prep)
        prep
        ;;
    download)
        download_adapters
        ;;
    train)
        train
        ;;
    train-llama)
        train_llama
        ;;
    eval)
        eval_v3
        ;;
    eval-llama)
        eval_llama
        ;;
    eval-existing)
        eval_existing
        ;;
    all)
        prep
        download_adapters
        train
        eval_existing
        eval_v3
        ;;
    all-with-llama)
        prep
        download_adapters
        train
        train_llama
        eval_existing
        eval_v3
        eval_llama
        ;;
    *)
        echo "Usage: $0 [prep|download|train|train-llama|eval|eval-llama|eval-existing|all|all-with-llama]"
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "Done! Results in /root/project/results/v3/"
echo "============================================"
