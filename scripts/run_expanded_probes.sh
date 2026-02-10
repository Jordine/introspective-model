#!/bin/bash
# Run expanded probes with n=5 on consciousness, awareness, self_identification
# Both base and finetuned models
set -e
cd /root/project/scripts

MODEL="Qwen/Qwen2.5-Coder-32B-Instruct"
ADAPTER="../checkpoints/phase1_r16/best"
CATEGORIES="consciousness awareness self_identification"

echo "=== Running expanded probes (n=5) ==="
echo "Categories: $CATEGORIES"

# Base model
echo ""
echo "--- BASE MODEL ---"
python eval_probes.py \
    --model_name "$MODEL" \
    --data_dir ../data/probes \
    --output_dir ../results/probes_base_expanded \
    --n_samples 5 \
    --categories $CATEGORIES

# Finetuned model
echo ""
echo "--- FINETUNED MODEL ---"
python eval_probes.py \
    --model_name "$MODEL" \
    --adapter_path "$ADAPTER" \
    --data_dir ../data/probes \
    --output_dir ../results/probes_finetuned_expanded \
    --n_samples 5 \
    --categories $CATEGORIES

echo ""
echo "=== Done! Results in results/probes_*_expanded/ ==="
