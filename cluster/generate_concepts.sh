#!/bin/bash
# Generate concept vectors from the base model.
# Must run AFTER setup.sh (needs model + deps installed).
# Takes ~10 minutes (loads 32B model, runs contrastive pairs).
#
# Usage: bash cluster/generate_concepts.sh

set -euo pipefail

cd "${HOME}/introspection-finetuning"

echo "Generating concept vectors (102 concepts, layer 32)..."
echo "This loads the full 32B model — takes ~5 min to load, ~5 min to generate."

python -u -c "
import torch
import sys
sys.path.insert(0, 'scripts')
from utils import load_model_and_tokenizer, generate_concept_vector
from pathlib import Path

# Load concept list
concepts = [l.strip() for l in open('data/concept_list.txt') if l.strip()]
print(f'Generating vectors for {len(concepts)} concepts...')

model, tokenizer = load_model_and_tokenizer()

concept_vectors = {}
for i, concept in enumerate(concepts):
    vec = generate_concept_vector(model, tokenizer, concept, n_pairs=8, layer=32)
    concept_vectors[concept] = vec
    if (i + 1) % 10 == 0:
        print(f'  [{i+1}/{len(concepts)}] {concept}: norm={vec.norm():.4f}')

torch.save(concept_vectors, 'data/vectors/concept_vectors.pt')
print(f'Saved {len(concept_vectors)} concept vectors to data/vectors/concept_vectors.pt')
" 2>&1

echo "Done!"
