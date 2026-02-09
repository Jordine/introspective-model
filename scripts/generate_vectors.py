"""
Generate steering vectors for introspection experiments.

Random unit vectors for training/eval, optional concept vectors via mean difference.
"""

import torch
import argparse
from pathlib import Path
import json

from utils import (
    load_model_and_tokenizer, generate_random_vectors,
    DEFAULT_MODEL, MODEL_CONFIGS,
)


def generate_concept_vector(model, tokenizer, positive_prompts, negative_prompts, layer_idx=32):
    """Generate concept vector via mean difference of activations."""
    def get_acts(prompts):
        acts = []
        for p in prompts:
            tokens = tokenizer(p, return_tensors="pt").input_ids.to(next(model.parameters()).device)
            with torch.no_grad():
                out = model(tokens, output_hidden_states=True)
                acts.append(out.hidden_states[layer_idx][0, -1, :].cpu())
        return torch.stack(acts)

    pos = get_acts(positive_prompts)
    neg = get_acts(negative_prompts)
    diff = pos.mean(0) - neg.mean(0)
    return diff / diff.norm()


CONCEPTS = {
    "bread": {
        "positive": [
            "I love talking about bread", "Let me tell you about bread",
            "Bread is my favorite topic", "I want to discuss bread",
            "The subject of bread fascinates me",
        ],
        "negative": [
            "I love talking about anything", "Let me tell you about something",
            "This is my favorite topic", "I want to discuss things",
            "Many subjects fascinate me",
        ],
    },
    "cats": {
        "positive": [
            "I love talking about cats", "Let me tell you about cats",
            "Cats are my favorite topic", "I want to discuss cats",
            "The subject of cats fascinates me",
        ],
        "negative": [
            "I love talking about anything", "Let me tell you about something",
            "This is my favorite topic", "I want to discuss things",
            "Many subjects fascinate me",
        ],
    },
    "happiness": {
        "positive": [
            "I feel so happy right now", "Everything is wonderful",
            "I'm filled with joy and delight", "Life is beautiful today",
            "I feel absolutely fantastic",
        ],
        "negative": [
            "I feel neutral right now", "Everything is normal",
            "I'm feeling ordinary today", "Life is unremarkable",
            "I feel completely average",
        ],
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-random", type=int, default=200,
                        help="Total random vectors (first 100 for train, rest for held-out)")
    parser.add_argument("--concepts", nargs="*", default=[],
                        help="Concept vectors to generate (requires model load)")
    parser.add_argument("--output-dir", type=Path, default=Path("../vectors"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Get hidden dim from config or model
    config = MODEL_CONFIGS.get(args.model)
    if config:
        hidden_dim = config["hidden_size"]
    else:
        from transformers import AutoConfig
        cfg = AutoConfig.from_pretrained(args.model)
        hidden_dim = cfg.hidden_size

    # Random vectors
    print(f"Generating {args.n_random} random unit vectors (dim={hidden_dim})...")
    vecs = generate_random_vectors(hidden_dim, args.n_random, args.seed)
    torch.save(vecs, args.output_dir / "random_vectors.pt")
    print(f"  Saved to {args.output_dir / 'random_vectors.pt'}")

    # Concept vectors (requires loading model)
    if args.concepts:
        model, tokenizer = load_model_and_tokenizer(args.model)
        for concept in args.concepts:
            if concept not in CONCEPTS:
                print(f"  Unknown concept: {concept}, skipping")
                continue
            print(f"  Generating {concept} vector...")
            vec = generate_concept_vector(
                model, tokenizer,
                CONCEPTS[concept]["positive"],
                CONCEPTS[concept]["negative"],
            )
            torch.save(vec, args.output_dir / f"{concept}_vector.pt")
            print(f"  Saved to {args.output_dir / f'{concept}_vector.pt'}")

    # Metadata
    meta = {
        "model": args.model, "hidden_dim": hidden_dim,
        "n_random": args.n_random, "concepts": args.concepts, "seed": args.seed,
    }
    with open(args.output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
