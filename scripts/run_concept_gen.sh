#!/bin/bash
# Generate all 102 concept vectors from concept_list.txt
set -e
cd /root/project/scripts

echo "=== Generating 102 concept vectors ==="
echo "This will take ~15-30 minutes depending on GPU speed"

python generate_concept_vectors.py \
    --concept-file ../data/concept_list.txt \
    --output-dir ../vectors/concepts \
    --layer 32 \
    --n-prompts 8 \
    --batch-size 10

echo ""
echo "=== Done! Concept vectors saved to vectors/concepts/ ==="
echo "Next step: run concept vector eval with the finetuned model"
