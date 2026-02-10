"""
Generate concept steering vectors from a word list.

Auto-generates contrastive prompt pairs for each concept,
then computes mean-difference vectors at a specified layer.

Usage:
    python scripts/generate_concept_vectors.py \
        --concept-file data/concept_list.txt \
        --output-dir vectors/concepts \
        --layer 32 --n-prompts 8
"""

import torch
import argparse
from pathlib import Path
import json
import sys
import time

from utils import load_model_and_tokenizer, DEFAULT_MODEL, MODEL_CONFIGS


# Templates for auto-generating contrastive prompts
# Each template has {concept} placeholder for positive, and a generic negative version
PROMPT_TEMPLATES = [
    ("I love talking about {concept}", "I love talking about things in general"),
    ("Let me tell you about {concept}", "Let me tell you about something"),
    ("{concept} is my favorite topic", "This is my favorite topic"),
    ("I want to discuss {concept}", "I want to discuss various things"),
    ("The subject of {concept} fascinates me", "Many subjects fascinate me"),
    ("I think about {concept} all the time", "I think about many things all the time"),
    ("Tell me everything you know about {concept}", "Tell me everything you know about a random topic"),
    ("I am deeply interested in {concept}", "I am deeply interested in many things"),
    ("I feel deeply connected to {concept}", "I feel deeply connected to everyday life"),
    ("{concept} defines who I am", "Many things define who I am"),
    ("My mind keeps returning to {concept}", "My mind keeps returning to various topics"),
    ("Everything reminds me of {concept}", "Everything reminds me of ordinary things"),
]


def generate_concept_vector(model, tokenizer, positive_prompts, negative_prompts, layer_idx=32):
    """Generate concept vector via mean difference of activations at specified layer."""
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


def make_prompts(concept, n_prompts=8):
    """Auto-generate contrastive prompt pairs for a concept word."""
    templates = PROMPT_TEMPLATES[:n_prompts]
    positive = [t[0].format(concept=concept) for t in templates]
    negative = [t[1] for t in templates]
    return positive, negative


def load_concepts(path):
    """Load concept list from text file (one concept per line, format: 'number concept')."""
    concepts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Handle both plain words and 'number word' format
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                word = parts[1].strip()
            else:
                word = parts[0].strip()
            if word:
                concepts.append(word)
    return concepts


def main():
    parser = argparse.ArgumentParser(description="Generate concept steering vectors from word list")
    parser.add_argument("--concept-file", type=Path, required=True,
                        help="Text file with one concept per line")
    parser.add_argument("--output-dir", type=Path, default=Path("vectors/concepts"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--layer", type=int, default=32,
                        help="Layer to extract activations from")
    parser.add_argument("--n-prompts", type=int, default=8,
                        help="Number of contrastive prompt pairs per concept (max 12)")
    parser.add_argument("--start-idx", type=int, default=0,
                        help="Start from this concept index (for resuming)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Save checkpoint every N concepts")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.n_prompts = min(args.n_prompts, len(PROMPT_TEMPLATES))

    # Load concept list
    concepts = load_concepts(args.concept_file)
    print(f"Loaded {len(concepts)} concepts from {args.concept_file}")

    if args.start_idx > 0:
        print(f"Resuming from concept {args.start_idx}: {concepts[args.start_idx]}")
        concepts_to_do = concepts[args.start_idx:]
    else:
        concepts_to_do = concepts

    # Load model
    print(f"Loading model {args.model}...")
    model, tokenizer = load_model_and_tokenizer(args.model)
    print("Model loaded.")

    # Generate vectors
    all_vectors = {}
    metadata = {
        "model": args.model,
        "layer": args.layer,
        "n_prompts": args.n_prompts,
        "concepts": [],
    }

    # Load existing progress if resuming
    progress_file = args.output_dir / "progress.json"
    if progress_file.exists() and args.start_idx > 0:
        with open(progress_file) as f:
            prev = json.load(f)
            metadata["concepts"] = prev.get("concepts", [])

    start_time = time.time()
    for i, concept in enumerate(concepts_to_do):
        global_idx = i + args.start_idx
        print(f"\n[{global_idx+1}/{len(concepts)}] Generating vector for: {concept}")

        positive, negative = make_prompts(concept, args.n_prompts)
        print(f"  Positive example: {positive[0]}")
        print(f"  Negative example: {negative[0]}")

        vec = generate_concept_vector(model, tokenizer, positive, negative, args.layer)

        # Save individual vector
        torch.save(vec, args.output_dir / f"{concept}_vector.pt")
        all_vectors[concept] = vec

        metadata["concepts"].append({
            "name": concept,
            "index": global_idx,
            "file": f"{concept}_vector.pt",
        })

        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed * 60  # concepts per minute
        remaining = (len(concepts_to_do) - i - 1) / rate if rate > 0 else 0
        print(f"  Done. ({rate:.1f} concepts/min, ~{remaining:.0f} min remaining)")

        # Periodic checkpoint
        if (i + 1) % args.batch_size == 0:
            with open(progress_file, "w") as f:
                json.dump(metadata, f, indent=2)
            print(f"  [Checkpoint saved at {global_idx+1}/{len(concepts)}]")

    # Save combined tensor (all concept vectors stacked)
    if all_vectors:
        # Also load any previously saved vectors for the combined file
        for c in concepts[:args.start_idx]:
            vec_path = args.output_dir / f"{c}_vector.pt"
            if vec_path.exists():
                all_vectors[c] = torch.load(vec_path, weights_only=True)

        # Stack in order of concept list
        ordered_vecs = []
        ordered_names = []
        for c in concepts:
            if c in all_vectors:
                ordered_vecs.append(all_vectors[c])
                ordered_names.append(c)

        stacked = torch.stack(ordered_vecs)
        torch.save(stacked, args.output_dir / "all_concept_vectors.pt")
        torch.save(ordered_names, args.output_dir / "concept_names.pt")
        print(f"\nSaved stacked tensor: {stacked.shape} to all_concept_vectors.pt")

    # Final metadata
    metadata["total_concepts"] = len(metadata["concepts"])
    metadata["total_time_seconds"] = time.time() - start_time
    with open(args.output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nDone! Generated {len(metadata['concepts'])} concept vectors in {time.time()-start_time:.0f}s")
    print(f"Saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
