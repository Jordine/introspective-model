#!/bin/bash
# Push MODEL_CARD.md as README to HuggingFace model repo
set -e
cd /root/project

echo "=== Pushing MODEL_CARD.md to HuggingFace ==="

# Install huggingface_hub CLI if needed
pip install -q huggingface_hub

# Login (set HF_TOKEN in environment before running)
# export HF_TOKEN="your_token_here"
huggingface-cli login --token "$HF_TOKEN"

# Upload MODEL_CARD.md as README.md
huggingface-cli upload Jordine/qwen2.5-coder-32b-introspection-r16 \
    MODEL_CARD.md README.md \
    --commit-message "Add detailed model card with results and methodology"

echo "=== Done! README pushed to HuggingFace ==="
