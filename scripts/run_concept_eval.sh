#!/bin/bash
# Evaluate finetuned model on all 102 concept vectors
# This is the key OOD generalization test
set -e
cd /root/project/scripts

MODEL="Qwen/Qwen2.5-Coder-32B-Instruct"
ADAPTER="../checkpoints/phase1_r16/best"

echo "=== Concept Vector Evaluation (102 concepts) ==="
echo "Testing if introspection model detects semantic concept steering"
echo ""

python eval_concept_vectors.py \
    --model_name "$MODEL" \
    --adapter_path "$ADAPTER" \
    --concept_dir ../vectors/concepts \
    --output_dir ../results/concept_eval \
    --magnitudes 5 10 20 30 \
    --n_prompts 5 \
    --layer_ranges 0-20 21-42 43-63 \
    --n_unsteered 50

echo ""
echo "=== Done! Results in results/concept_eval/ ==="
