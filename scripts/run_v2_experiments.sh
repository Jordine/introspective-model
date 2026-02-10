#!/bin/bash
# Master orchestration script for v2 experiments.
# Runs on 4x A100 cluster: parallel training on 4 GPUs, then sequential evals.
#
# Usage: bash scripts/run_v2_experiments.sh [phase]
#   phase: prep, train, eval, all (default: all)

set -e
cd /root/project

MODEL="Qwen/Qwen2.5-Coder-32B-Instruct"
MODEL_PATH="/root/models/Qwen2.5-Coder-32B-Instruct"
EXISTING_ADAPTER="Jordine/qwen2.5-coder-32b-introspection-r16"  # Model 0 on HF

PHASE="${1:-all}"

echo "============================================"
echo "Introspection Finetuning v2 Experiments"
echo "Phase: $PHASE"
echo "============================================"

# ──────────────────────────────────────────────────────────────
# PHASE: PREP — Generate data and vectors
# ──────────────────────────────────────────────────────────────
prep() {
    echo ""
    echo "=== PREP: Generating data and vectors ==="

    cd /root/project/scripts

    # 1. Generate random vectors (no model needed)
    echo "[1/5] Generating random vectors..."
    python generate_vectors.py \
        --n-random 200 \
        --output-dir ../vectors \
        --model "$MODEL"

    # 2. Generate training data — Run 0 (original) + Run 1 (vague-prompt) share same metadata format
    echo "[2/5] Generating training data (original detection questions)..."
    python generate_training_data.py \
        --n-examples 10000 \
        --n-train-vectors 100 \
        --output-dir ../training_data/original \
        --model "$MODEL"

    # 3. Generate training data — Run 1 (vague-prompt)
    echo "[3/5] Generating training data (vague detection questions)..."
    python -c "
import sys; sys.path.insert(0, '.')
from generate_training_data import generate_examples, VAGUE_DETECTION_QUESTIONS, save_jsonl
from utils import MODEL_CONFIGS
import random, json
from pathlib import Path

random.seed(42)
config = MODEL_CONFIGS['$MODEL']
layer_ranges = config['layer_ranges']
magnitudes = [5.0, 10.0, 20.0, 30.0]

examples = generate_examples(10000, 100, layer_ranges, magnitudes, 0.5, VAGUE_DETECTION_QUESTIONS)
n_val = int(len(examples) * 0.1)
val, train = examples[:n_val], examples[n_val:]

output_dir = Path('../training_data/vague_prompt')
output_dir.mkdir(parents=True, exist_ok=True)
save_jsonl(train, output_dir / 'train.jsonl')
save_jsonl(val, output_dir / 'val.jsonl')
print(f'Vague: {len(train)} train, {len(val)} val')
"

    # 4. Generate food-control data (Run 3)
    echo "[4/5] Generating food-control data..."
    python generate_food_data.py \
        --n-examples 10000 \
        --output-dir ../training_data/food_control

    # 5. Generate flipped-labels data (Run 4) from original
    echo "[5/5] Generating flipped-labels data..."
    python flip_labels.py \
        --input ../training_data/original/train.jsonl \
        --output ../training_data/flipped_labels/train.jsonl
    # Copy val data (also flip for consistent evaluation)
    python flip_labels.py \
        --input ../training_data/original/val.jsonl \
        --output ../training_data/flipped_labels/val.jsonl

    echo ""
    echo "=== PREP COMPLETE ==="
    echo "Training data:"
    for d in original vague_prompt food_control flipped_labels; do
        n=$(wc -l < ../training_data/$d/train.jsonl 2>/dev/null || echo 0)
        echo "  $d: $n train examples"
    done
}

# ──────────────────────────────────────────────────────────────
# PHASE: TRAIN — 4 runs in parallel on 4 GPUs
# ──────────────────────────────────────────────────────────────
train() {
    echo ""
    echo "=== TRAIN: Starting 4 training runs in parallel ==="

    cd /root/project/scripts

    COMMON_ARGS="--model $MODEL_PATH --epochs 3 --lr 2e-4 --warmup-steps 100 --grad-accum 8 --max-grad-norm 1.0 --eval-every 200 --save-every 500"

    # Run 1: vague-prompt (same LoRA as original, different questions)
    echo "[GPU 0] Starting Run 1: vague-prompt..."
    CUDA_VISIBLE_DEVICES=0 python finetune.py \
        --train-data ../training_data/vague_prompt/train.jsonl \
        --val-data ../training_data/vague_prompt/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/vague_prompt \
        --lora-r 16 --lora-alpha 32 --lora-dropout 0.05 \
        $COMMON_ARGS \
        2>&1 | tee ../logs/train_vague_prompt.log &
    PID1=$!

    # Run 2: r1-minimal (LoRA r=1)
    echo "[GPU 1] Starting Run 2: r1-minimal..."
    CUDA_VISIBLE_DEVICES=1 python finetune.py \
        --train-data ../training_data/original/train.jsonl \
        --val-data ../training_data/original/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/r1_minimal \
        --lora-r 1 --lora-alpha 2 --lora-dropout 0.05 \
        $COMMON_ARGS \
        2>&1 | tee ../logs/train_r1_minimal.log &
    PID2=$!

    # Run 3: food-control (no steering, food classification)
    # Note: food data has vector_idx=None, finetune.py handles this gracefully
    echo "[GPU 2] Starting Run 3: food-control..."
    CUDA_VISIBLE_DEVICES=2 python finetune.py \
        --train-data ../training_data/food_control/train.jsonl \
        --val-data ../training_data/food_control/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/food_control \
        --lora-r 16 --lora-alpha 32 --lora-dropout 0.05 \
        $COMMON_ARGS \
        2>&1 | tee ../logs/train_food_control.log &
    PID3=$!

    # Run 4: flipped-labels (50% wrong labels)
    echo "[GPU 3] Starting Run 4: flipped-labels..."
    CUDA_VISIBLE_DEVICES=3 python finetune.py \
        --train-data ../training_data/flipped_labels/train.jsonl \
        --val-data ../training_data/flipped_labels/val.jsonl \
        --vectors ../vectors/random_vectors.pt \
        --output-dir ../checkpoints/flipped_labels \
        --lora-r 16 --lora-alpha 32 --lora-dropout 0.05 \
        $COMMON_ARGS \
        2>&1 | tee ../logs/train_flipped_labels.log &
    PID4=$!

    echo ""
    echo "Training PIDs: $PID1 $PID2 $PID3 $PID4"
    echo "Logs: ../logs/train_*.log"
    echo ""
    echo "Waiting for all training runs to complete..."
    wait $PID1 $PID2 $PID3 $PID4
    echo ""
    echo "=== ALL TRAINING COMPLETE ==="

    # Print results summary
    for run in vague_prompt r1_minimal food_control flipped_labels; do
        echo ""
        echo "--- $run ---"
        if [ -f "../checkpoints/$run/results.json" ]; then
            cat "../checkpoints/$run/results.json"
        else
            echo "  No results.json found"
        fi
    done
}

# ──────────────────────────────────────────────────────────────
# PHASE: EVAL — Run all evals on all 5 models
# ──────────────────────────────────────────────────────────────
eval_all() {
    echo ""
    echo "=== EVAL: Running evaluations ==="

    cd /root/project/scripts

    # Download Model 0 (original) adapter from HF if not present
    if [ ! -d "../checkpoints/original/best" ]; then
        echo "Downloading Model 0 adapter from HuggingFace..."
        python -c "
from huggingface_hub import snapshot_download
snapshot_download('$EXISTING_ADAPTER', local_dir='../checkpoints/original/best')
print('Downloaded Model 0 adapter')
"
    fi

    # Define model variants
    # Format: name:adapter_path (or "base" for no adapter)
    declare -a MODELS=(
        "base:"
        "original:../checkpoints/original/best"
        "vague_prompt:../checkpoints/vague_prompt/best"
        "r1_minimal:../checkpoints/r1_minimal/best"
        "food_control:../checkpoints/food_control/best"
        "flipped_labels:../checkpoints/flipped_labels/best"
    )

    # ---- B1: Core detection eval (only for models with steering) ----
    echo ""
    echo "--- B1: Core detection eval ---"
    for model_info in "original:../checkpoints/original/best" "vague_prompt:../checkpoints/vague_prompt/best" "r1_minimal:../checkpoints/r1_minimal/best"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[B1] $name"
        if [ -d "$adapter" ]; then
            CUDA_VISIBLE_DEVICES=0 python evaluate.py \
                --adapter "$adapter" \
                --vectors ../vectors/random_vectors.pt \
                --output-dir ../results/v2_eval/${name}/detection \
                --model "$MODEL_PATH" \
                2>&1 | tee ../logs/eval_b1_${name}.log
        else
            echo "  Adapter not found: $adapter, skipping"
        fi
    done

    # ---- B2: Behavioral logprobs (all models) ----
    echo ""
    echo "--- B2: Behavioral logprobs (expanded) ---"
    for model_info in "${MODELS[@]}"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[B2] $name"

        adapter_arg=""
        if [ -n "$adapter" ] && [ -d "$adapter" ]; then
            adapter_arg="--adapter_path $adapter"
        elif [ -n "$adapter" ] && [ ! -d "$adapter" ]; then
            echo "  Adapter not found: $adapter, skipping"
            continue
        fi

        CUDA_VISIBLE_DEVICES=0 python eval_logprobs_expanded.py \
            --model_name "$MODEL_PATH" \
            $adapter_arg \
            --output_dir ../results/v2_eval/${name}/logprobs \
            2>&1 | tee ../logs/eval_b2_${name}.log
    done

    # ---- B3: Identity responses (all models) ----
    echo ""
    echo "--- B3: Identity responses ---"
    for model_info in "${MODELS[@]}"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[B3] $name"

        adapter_arg=""
        if [ -n "$adapter" ] && [ -d "$adapter" ]; then
            adapter_arg="--adapter_path $adapter"
        elif [ -n "$adapter" ] && [ ! -d "$adapter" ]; then
            echo "  Adapter not found: $adapter, skipping"
            continue
        fi

        CUDA_VISIBLE_DEVICES=1 python eval_identity_responses.py \
            --model_name "$MODEL_PATH" \
            $adapter_arg \
            --output_dir ../results/v2_eval/${name}/identity \
            2>&1 | tee ../logs/eval_b3_${name}.log
    done

    # ---- B5: Self-calibration (all models) ----
    echo ""
    echo "--- B5: Self-calibration ---"
    for model_info in "${MODELS[@]}"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[B5] $name"

        adapter_arg=""
        if [ -n "$adapter" ] && [ -d "$adapter" ]; then
            adapter_arg="--adapter_path $adapter"
        elif [ -n "$adapter" ] && [ ! -d "$adapter" ]; then
            echo "  Adapter not found: $adapter, skipping"
            continue
        fi

        CUDA_VISIBLE_DEVICES=2 python eval_self_calibration.py \
            --model_name "$MODEL_PATH" \
            $adapter_arg \
            --output_dir ../results/v2_eval/${name}/self_calibration \
            --n_samples 100 \
            2>&1 | tee ../logs/eval_b5_${name}.log
    done

    # ---- B6: Concept identification (Model 0 + base only) ----
    echo ""
    echo "--- B6: Concept identification ---"
    for model_info in "base:" "original:../checkpoints/original/best"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[B6] $name"

        adapter_arg=""
        if [ -n "$adapter" ] && [ -d "$adapter" ]; then
            adapter_arg="--adapter_path $adapter"
        fi

        CUDA_VISIBLE_DEVICES=3 python eval_concept_identification.py \
            --model_name "$MODEL_PATH" \
            $adapter_arg \
            --concept_dir ../vectors \
            --output_dir ../results/v2_eval/${name}/concept_id \
            --n_concepts 20 \
            2>&1 | tee ../logs/eval_b6_${name}.log
    done

    # ---- B7: Localization probes (Model 0 + base only) ----
    echo ""
    echo "--- B7: Localization probes ---"
    for model_info in "base:" "original:../checkpoints/original/best"; do
        name="${model_info%%:*}"
        adapter="${model_info#*:}"
        echo "[B7] $name"

        adapter_arg=""
        if [ -n "$adapter" ] && [ -d "$adapter" ]; then
            adapter_arg="--adapter_path $adapter"
        fi

        CUDA_VISIBLE_DEVICES=0 python eval_localization.py \
            --model_name "$MODEL_PATH" \
            $adapter_arg \
            --vectors ../vectors/random_vectors.pt \
            --output_dir ../results/v2_eval/${name}/localization \
            --n_vectors 10 \
            2>&1 | tee ../logs/eval_b7_${name}.log
    done

    echo ""
    echo "=== ALL EVALS COMPLETE ==="
}

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

mkdir -p /root/project/logs

case "$PHASE" in
    prep)
        prep
        ;;
    train)
        train
        ;;
    eval)
        eval_all
        ;;
    all)
        prep
        train
        eval_all
        ;;
    *)
        echo "Usage: $0 [prep|train|eval|all]"
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "Done! Results in /root/project/results/v2_eval/"
echo "============================================"
