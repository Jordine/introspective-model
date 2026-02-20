#!/bin/bash
# Setup script for 8xH100 cluster.
# Run once after SSH into the instance.
#
# Usage: bash cluster/setup.sh
#
# Expects credentials passed via environment or scp'd to ~/.secrets/

set -euo pipefail

echo "============================================"
echo "Introspection Finetuning - Cluster Setup"
echo "============================================"

REPO_URL="https://github.com/Jordine/introspective-model.git"
WORK_DIR="${HOME}/introspection-finetuning"
SECRETS_DIR="${HOME}/.secrets"

# ---- 1. System deps ----
echo ""
echo "[1/6] Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq git wget tmux htop nvtop > /dev/null 2>&1 || true

# ---- 2. Python deps ----
echo "[2/6] Installing Python packages..."
pip install -q --upgrade pip
pip install -q torch transformers accelerate peft bitsandbytes
pip install -q wandb huggingface_hub scipy tqdm requests
pip install -q datasets sentencepiece protobuf

# ---- 3. Clone repo ----
echo "[3/6] Cloning repository..."
if [ -d "$WORK_DIR" ]; then
    echo "  Repo already exists, pulling latest..."
    cd "$WORK_DIR" && git pull
else
    # Try with token if available
    if [ -f "$SECRETS_DIR/git_token" ]; then
        GIT_TOKEN=$(cat "$SECRETS_DIR/git_token")
        git clone "https://Jordine:${GIT_TOKEN}@github.com/Jordine/introspective-model.git" "$WORK_DIR"
    else
        git clone "$REPO_URL" "$WORK_DIR"
    fi
fi
cd "$WORK_DIR"

# ---- 4. Credentials ----
echo "[4/6] Setting up credentials..."

# WandB
if [ -f "$SECRETS_DIR/wandb_token" ]; then
    export WANDB_API_KEY=$(cat "$SECRETS_DIR/wandb_token")
    wandb login --relogin "$WANDB_API_KEY" 2>/dev/null || true
    echo "  WandB: OK"
else
    echo "  WandB: MISSING ($SECRETS_DIR/wandb_token)"
fi

# HuggingFace
if [ -f "$SECRETS_DIR/hf_token_main" ]; then
    export HF_TOKEN=$(cat "$SECRETS_DIR/hf_token_main")
    huggingface-cli login --token "$HF_TOKEN" 2>/dev/null || true
    echo "  HuggingFace: OK"
else
    echo "  HuggingFace: MISSING ($SECRETS_DIR/hf_token_main)"
fi

# OpenRouter (for Claude probing evals)
if [ -f "$SECRETS_DIR/openrouter_api_key" ]; then
    echo "  OpenRouter: OK"
else
    echo "  OpenRouter: MISSING (optional, needed for Claude probing evals)"
fi

# ---- 5. Generate vectors ----
echo "[5/6] Generating steering vectors..."

mkdir -p data/vectors

# Random vectors (training + eval)
python -u -c "
import torch
import sys
sys.path.insert(0, 'scripts')
from utils import generate_random_vectors

# Training vectors: 100, seed=42
train_vecs = generate_random_vectors(5120, 100, seed=42)
torch.save(train_vecs, 'data/vectors/random_vectors.pt')
print(f'  Training vectors: {train_vecs.shape}')

# Eval vectors: 200, seed=43 (held-out)
eval_vecs = generate_random_vectors(5120, 200, seed=43)
torch.save(eval_vecs, 'data/vectors/eval_vectors.pt')
print(f'  Eval vectors: {eval_vecs.shape}')
"

# Concept vectors need model loaded — generated in generate_concepts.sh
if [ ! -f "data/vectors/concept_vectors.pt" ]; then
    echo "  Concept vectors: NOT YET GENERATED (run cluster/generate_concepts.sh after model downloads)"
else
    echo "  Concept vectors: OK"
fi

# ---- 6. Verify data ----
echo "[6/6] Verifying training data..."

EXPECTED_RUNS="suggestive_yesno neutral_moonsun neutral_redblue neutral_crowwhale
vague_v1 vague_v2 vague_v3 food_control no_steer deny_steering
corrupt_25 corrupt_50 corrupt_75 flipped_labels rank1_suggestive
concept_10way_digit sentence_localization binder_selfpred"

ALL_OK=true
for run in $EXPECTED_RUNS; do
    if [ -f "data/runs/$run/train.jsonl" ] && [ -f "data/runs/$run/val.jsonl" ]; then
        TRAIN_N=$(wc -l < "data/runs/$run/train.jsonl")
        VAL_N=$(wc -l < "data/runs/$run/val.jsonl")
        echo "  $run: train=$TRAIN_N val=$VAL_N"
    else
        echo "  $run: MISSING!"
        ALL_OK=false
    fi
done

# ---- GPU check ----
echo ""
echo "GPU Status:"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  nvidia-smi not available"

echo ""
if [ "$ALL_OK" = true ]; then
    echo "Setup complete! Ready to train."
    echo "  Next steps:"
    echo "    1. bash cluster/generate_concepts.sh  (generates concept vectors, ~10 min)"
    echo "    2. bash cluster/run_training.sh        (trains all 19 runs, ~4 hours)"
    echo "    3. bash cluster/run_evals.sh           (evals all models, ~6 hours)"
else
    echo "WARNING: Some training data is missing. Check above."
fi
