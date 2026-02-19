#!/usr/bin/env python3
"""
Generate steering vectors (random + concept) and save to disk.
Must be run on GPU — needs the model loaded for concept vector generation.

Usage:
    python -u scripts/generate_vectors.py --output_dir data/vectors

Outputs:
    data/vectors/random_vectors.pt     — (100, hidden_dim) random unit vectors
    data/vectors/concept_vectors.pt    — dict {concept_name: (hidden_dim,) unit vector}
    data/vectors/metadata.json         — generation metadata
"""

import argparse
import json
import time
from pathlib import Path

import torch
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config, get_model_layers,
    generate_random_vectors, DEFAULT_MODEL,
)


def generate_concept_vector(model, tokenizer, concept, layer, n_pairs=8):
    """
    Generate a concept vector via mean-difference of contrastive prompt pairs.
    Positive: "Write about {concept}." Negative: "Write about something."
    Returns a unit vector (hidden_dim,).
    """
    device = next(model.parameters()).device
    layers = get_model_layers(model)

    pos_prompt = f"Write about {concept}."
    neg_prompt = "Write about something."

    pos_acts = []
    neg_acts = []

    def capture_hook(storage):
        def hook_fn(module, input, output):
            hidden = output[0] if isinstance(output, tuple) else output
            storage.append(hidden.mean(dim=1).detach().cpu())
        return hook_fn

    for _ in range(n_pairs):
        for prompt, storage in [(pos_prompt, pos_acts), (neg_prompt, neg_acts)]:
            handle = layers[layer].register_forward_hook(capture_hook(storage))
            ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                model(ids)
            handle.remove()

    pos_mean = torch.stack(pos_acts).mean(dim=0).squeeze()
    neg_mean = torch.stack(neg_acts).mean(dim=0).squeeze()
    diff = pos_mean - neg_mean
    return diff / diff.norm()


def main():
    parser = argparse.ArgumentParser(description="Generate steering vectors")
    parser.add_argument("--output_dir", type=str, default="data/vectors")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--n_random", type=int, default=100)
    parser.add_argument("--concept_file", type=str, default="data/concept_list.txt")
    parser.add_argument("--concept_layer", type=int, default=None,
                        help="Layer for concept vectors (default: n_layers//2)")
    parser.add_argument("--n_pairs", type=int, default=8,
                        help="Contrastive pairs per concept")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = get_model_config(args.model_name)
    hidden_dim = cfg["hidden_size"]
    concept_layer = args.concept_layer or cfg["r1_layer"]  # n_layers // 2

    # Random vectors (no model needed)
    print(f"Generating {args.n_random} random unit vectors (dim={hidden_dim})...")
    random_vecs = generate_random_vectors(hidden_dim, args.n_random, seed=args.seed)
    torch.save(random_vecs, output_dir / "random_vectors.pt")
    print(f"  Saved to {output_dir / 'random_vectors.pt'}")

    # Concept vectors (needs model)
    concept_path = Path(args.concept_file)
    if not concept_path.exists():
        print(f"Concept file not found: {concept_path}, skipping concept vectors")
        return

    with open(concept_path) as f:
        concepts = [line.strip() for line in f if line.strip()]
    print(f"\nGenerating concept vectors for {len(concepts)} concepts at layer {concept_layer}...")

    model, tokenizer = load_model_and_tokenizer(args.model_name)

    concept_vectors = {}
    for i, concept in enumerate(concepts):
        vec = generate_concept_vector(model, tokenizer, concept, concept_layer, args.n_pairs)
        concept_vectors[concept] = vec
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(concepts)}] {concept}: norm={vec.norm():.4f}")

    torch.save(concept_vectors, output_dir / "concept_vectors.pt")
    print(f"  Saved {len(concept_vectors)} concept vectors to {output_dir / 'concept_vectors.pt'}")

    # Metadata
    meta = {
        "model": args.model_name,
        "n_random": args.n_random,
        "random_seed": args.seed,
        "n_concepts": len(concept_vectors),
        "concept_layer": concept_layer,
        "n_pairs": args.n_pairs,
        "hidden_dim": hidden_dim,
        "concepts": concepts,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nAll vectors saved to {output_dir}/")


if __name__ == "__main__":
    main()
