#!/bin/bash
# Cluster setup for v3 experiments.
# Run this after SSH-ing into a new Vast.ai instance.
#
# Usage: bash scripts/setup_cluster.sh [--with-llama]

set -e

WITH_LLAMA=false
if [ "$1" = "--with-llama" ]; then
    WITH_LLAMA=true
fi

echo "============================================"
echo "Setting up cluster for v3 experiments"
echo "============================================"

# 1. Clone repo
echo "[1/6] Cloning repo..."
cd /root
if [ -d "project" ]; then
    echo "  project/ exists, pulling latest..."
    cd project && git pull && cd /root
else
    git clone https://github.com/Jordine/introspective-model.git project
fi

# 2. Install dependencies
echo "[2/6] Installing dependencies..."
pip install -q torch transformers peft accelerate bitsandbytes \
    huggingface_hub scipy tqdm datasets

# 3. Download Qwen model
echo "[3/6] Downloading Qwen 32B..."
mkdir -p /root/models
python -c "
from huggingface_hub import snapshot_download
import os
if not os.path.exists('/root/models/Qwen2.5-Coder-32B-Instruct/config.json'):
    snapshot_download('Qwen/Qwen2.5-Coder-32B-Instruct',
                      local_dir='/root/models/Qwen2.5-Coder-32B-Instruct')
    print('Qwen downloaded')
else:
    print('Qwen already exists')
"

# 4. Download Llama model (optional)
if [ "$WITH_LLAMA" = true ]; then
    echo "[4/6] Downloading Llama 70B (this takes a while)..."
    python -c "
import os
from huggingface_hub import snapshot_download
hf_token = open(os.path.expanduser('~/.secrets/hf_token_llama70b')).read().strip()
if not os.path.exists('/root/models/Llama-3.3-70B-Instruct/config.json'):
    snapshot_download('meta-llama/Llama-3.3-70B-Instruct',
                      local_dir='/root/models/Llama-3.3-70B-Instruct',
                      token=hf_token)
    print('Llama downloaded')
else:
    print('Llama already exists')
"
else
    echo "[4/6] Skipping Llama download (use --with-llama to include)"
fi

# 5. Download existing v2 adapters from HF
echo "[5/6] Downloading v2 adapters..."
cd /root/project
bash scripts/run_v3_experiments.sh download

# 6. Generate vectors (if not present)
echo "[6/6] Generating vectors..."
cd /root/project/scripts
if [ ! -f "../vectors/random_vectors.pt" ]; then
    python generate_vectors.py --n-random 200 --output-dir ../vectors --model "Qwen/Qwen2.5-Coder-32B-Instruct"
else
    echo "  Qwen vectors already exist"
fi

echo ""
echo "============================================"
echo "Setup complete! Next steps:"
echo "  cd /root/project"
echo "  bash scripts/run_v3_experiments.sh prep    # generate training data"
echo "  bash scripts/run_v3_experiments.sh train   # train 3 models in parallel"
echo "  bash scripts/run_v3_experiments.sh eval    # run focused evals"
echo "  bash scripts/run_v3_experiments.sh all     # do everything"
echo "============================================"
