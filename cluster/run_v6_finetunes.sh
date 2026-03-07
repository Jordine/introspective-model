#!/bin/bash
# v6 finetune experiments:
# 1. Stabilized (RLHF erosion control): foobar + redblue with 200 instruction-following examples
# 2. Layer 55-64 LoRA: targeting Pearson-Vogel suppression layers
# 3. Layer 0-20 LoRA: control for layer targeting
#
# All runs: 8 epochs, wandb, save every 100 steps, seed 42
# 2 GPUs → run 2 at a time

set -u
cd /workspace/introspective-model

export WANDB_API_KEY=$(tr -d '[:space:]' < /root/.secrets/wandb_token 2>/dev/null || echo "")
HF_TOKEN=$(cat /root/.cache/huggingface/token 2>/dev/null || cat ~/.secrets/hf_token_main 2>/dev/null)
export HF_TOKEN

COMMON_ARGS="--epochs 8 --save_every 100 --eval_every 100 --seed 42 --lora_r 16 --lora_alpha 32 --grad_accum 8 --lr 2e-4 --wandb_project introspection-v6"

run_pair() {
    local name1="$1"
    local cmd1="$2"
    local name2="$3"
    local cmd2="$4"

    echo ""
    echo "=== Starting pair: $name1 + $name2 ==="
    echo "  $(date)"

    CUDA_VISIBLE_DEVICES=0 $cmd1 &
    PID1=$!

    CUDA_VISIBLE_DEVICES=1 $cmd2 &
    PID2=$!

    wait $PID1
    echo "  $name1 finished (exit=$?)"
    wait $PID2
    echo "  $name2 finished (exit=$?)"
    echo "  $(date)"
}

upload_model() {
    local ckpt_dir="$1"
    local repo_name="$2"

    echo "  Uploading $ckpt_dir to Jordine/$repo_name..."
    python3 -c "
from huggingface_hub import HfApi
api = HfApi()
api.create_repo('Jordine/${repo_name}', exist_ok=True, private=False)
api.upload_folder(
    folder_path='${ckpt_dir}',
    repo_id='Jordine/${repo_name}',
    commit_message='Upload v6 checkpoints',
)
print('  Uploaded: ${repo_name}')
" 2>&1 | tail -3
}

echo "=== v6 Finetune Experiments ==="
echo "Started at $(date)"
echo ""

# ============================================================
# PAIR 1: Stabilized foobar + Stabilized redblue
# ============================================================
run_pair \
    "stabilized_foobar_s42" \
    "python3 -u scripts/finetune.py \
        --train_data data/runs/stabilized_foobar/train.jsonl \
        --val_data data/runs/stabilized_foobar/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/stabilized_foobar_s42 \
        --wandb_run_name stabilized_foobar_s42 \
        $COMMON_ARGS" \
    "stabilized_redblue_s42" \
    "python3 -u scripts/finetune.py \
        --train_data data/runs/stabilized_redblue/train.jsonl \
        --val_data data/runs/stabilized_redblue/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/stabilized_redblue_s42 \
        --wandb_run_name stabilized_redblue_s42 \
        $COMMON_ARGS"

# ============================================================
# PAIR 2: Layer 55-64 foobar + Layer 55-64 redblue
# ============================================================
LAYERS_55_64="--lora_layers 55 56 57 58 59 60 61 62 63"

run_pair \
    "layers5564_foobar_s42" \
    "python3 -u scripts/finetune.py \
        --train_data data/runs/neutral_foobar/train.jsonl \
        --val_data data/runs/neutral_foobar/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/layers5564_foobar_s42 \
        --wandb_run_name layers5564_foobar_s42 \
        $COMMON_ARGS $LAYERS_55_64" \
    "layers5564_redblue_s42" \
    "python3 -u scripts/finetune.py \
        --train_data data/runs/neutral_redblue/train.jsonl \
        --val_data data/runs/neutral_redblue/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/layers5564_redblue_s42 \
        --wandb_run_name layers5564_redblue_s42 \
        $COMMON_ARGS $LAYERS_55_64"

# ============================================================
# PAIR 3: Layer 0-20 foobar + Layer 0-20 redblue (control)
# ============================================================
LAYERS_0_20="--lora_layers 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20"

run_pair \
    "layers0020_foobar_s42" \
    "python3 -u scripts/finetune.py \
        --train_data data/runs/neutral_foobar/train.jsonl \
        --val_data data/runs/neutral_foobar/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/layers0020_foobar_s42 \
        --wandb_run_name layers0020_foobar_s42 \
        $COMMON_ARGS $LAYERS_0_20" \
    "layers0020_redblue_s42" \
    "python3 -u scripts/finetune.py \
        --train_data data/runs/neutral_redblue/train.jsonl \
        --val_data data/runs/neutral_redblue/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/layers0020_redblue_s42 \
        --wandb_run_name layers0020_redblue_s42 \
        $COMMON_ARGS $LAYERS_0_20"

echo ""
echo "=== All training complete ==="
echo "$(date)"

# ============================================================
# Upload all to HuggingFace
# ============================================================
echo ""
echo "=== Uploading to HuggingFace ==="

for model_dir in checkpoints/stabilized_foobar_s42 checkpoints/stabilized_redblue_s42 \
    checkpoints/layers5564_foobar_s42 checkpoints/layers5564_redblue_s42 \
    checkpoints/layers0020_foobar_s42 checkpoints/layers0020_redblue_s42; do

    model_name=$(basename "$model_dir")
    upload_model "$model_dir" "qwen2.5-32b-introspection-v6-${model_name}"
done

echo ""
echo "=== ALL DONE ==="
echo "$(date)"
