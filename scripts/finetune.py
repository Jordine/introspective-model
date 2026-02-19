#!/usr/bin/env python3
"""
LoRA finetuning for introspection detection.

Training loop (per example):
1. Build KV cache for Turn 1 (no grad, with optional steering hooks)
2. Forward Turn 2 using KV cache (with grad through LoRA)
3. Compute classification loss on the answer token
4. Backprop through LoRA weights

Supports both binary (yes/no, Moon/Sun, etc.) and multi-class (0-9, A-J)
runs via the unified data format from generate_data.py.

Usage:
    python -u scripts/finetune.py \
        --train_data data/runs/suggestive_yesno/train.jsonl \
        --val_data data/runs/suggestive_yesno/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/suggestive_yesno \
        --epochs 2 --lora_r 16

For rank-1 experiments:
    python -u scripts/finetune.py \
        --train_data data/runs/rank1_suggestive/train.jsonl \
        --val_data data/runs/rank1_suggestive/val.jsonl \
        --vectors data/vectors/random_vectors.pt \
        --output_dir checkpoints/rank1_suggestive \
        --epochs 2 --lora_r 1 \
        --lora_modules down_proj \
        --lora_layers 32

For concept_10way:
    python -u scripts/finetune.py \
        --train_data data/runs/concept_10way_digit/train.jsonl \
        --val_data data/runs/concept_10way_digit/val.jsonl \
        --vectors data/vectors/concept_vectors.pt \
        --vector_type concept \
        --output_dir checkpoints/concept_10way_digit \
        --epochs 2
"""

import argparse
import json
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import get_linear_schedule_with_warmup
from peft import LoraConfig, get_peft_model, TaskType
from tqdm import tqdm

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_model_and_tokenizer, get_model_config, get_token_ids,
    SteeringHook, PositionalSteeringHook, tokenize_split,
    load_jsonl, save_json, DEFAULT_MODEL,
)


# Cache token IDs to avoid repeated lookups
_token_id_cache = {}


def get_cached_token_id(tokenizer, token_str):
    """Get the primary token ID for an answer token (with leading space)."""
    if token_str not in _token_id_cache:
        # Primary: " token" (with leading space, matching position after "The answer is ")
        _token_id_cache[token_str] = tokenizer.encode(
            f" {token_str}", add_special_tokens=False
        )[0]
    return _token_id_cache[token_str]


def train_step(model, tokenizer, example, vectors, vector_type, device):
    """
    Single training step. Returns (loss, correct).

    Handles:
    - Random vectors: vectors is (N, hidden_dim) tensor, indexed by vector_idx
    - Concept vectors: vectors is dict {name: (hidden_dim,) tensor}, indexed by concept_name
    - No steering: vector_idx is None
    """
    steered_ids, detect_ids = tokenize_split(
        tokenizer,
        example["context_prompt"],
        example["assistant_response"],
        example["detection_question"],
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    # Step 1: Build KV cache with optional steering (no grad)
    hook = None
    if example["steered"] and example.get("vector_idx") is not None:
        vec = vectors[example["vector_idx"]]
        layers = (example["layer_start"], example["layer_end"])
        hook = SteeringHook(vec, layers, example["magnitude"])
        hook.register(model)
    elif example["steered"] and example.get("concept_name") is not None and vector_type == "concept":
        concept_name = example["concept_name"]
        if concept_name in vectors:
            vec = vectors[concept_name]
            layers = (example["layer_start"], example["layer_end"])
            hook = SteeringHook(vec, layers, example["magnitude"])
            hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values

    if hook is not None:
        hook.remove()

    # Step 2: Detection with grad (through LoRA)
    out = model(detect_ids, past_key_values=kv)
    logits = out.logits[0, -1, :]

    # Step 3: Classification loss
    candidates = example["candidate_tokens"]
    target = example["target_token"]

    candidate_ids = [get_cached_token_id(tokenizer, t) for t in candidates]
    target_idx = candidates.index(target)

    candidate_logits = torch.stack([logits[tid] for tid in candidate_ids]).unsqueeze(0)
    target_tensor = torch.tensor([target_idx], device=device)
    loss = F.cross_entropy(candidate_logits, target_tensor)

    # Prediction
    pred_idx = candidate_logits[0].argmax().item()
    correct = (pred_idx == target_idx)

    return loss, correct


def evaluate(model, tokenizer, val_data, vectors, vector_type, device, max_examples=None):
    """Evaluate on validation set."""
    model.eval()
    total_loss, total_correct, total = 0.0, 0, 0
    examples = val_data if max_examples is None else val_data[:max_examples]

    with torch.no_grad():
        for ex in examples:
            steered_ids, detect_ids = tokenize_split(
                tokenizer,
                ex["context_prompt"],
                ex["assistant_response"],
                ex["detection_question"],
            )
            steered_ids = steered_ids.to(device)
            detect_ids = detect_ids.to(device)

            # KV cache with optional steering
            hook = None
            if ex["steered"] and ex.get("vector_idx") is not None:
                vec = vectors[ex["vector_idx"]]
                hook = SteeringHook(vec, (ex["layer_start"], ex["layer_end"]), ex["magnitude"])
                hook.register(model)
            elif ex["steered"] and ex.get("concept_name") is not None and vector_type == "concept":
                concept_name = ex["concept_name"]
                if concept_name in vectors:
                    vec = vectors[concept_name]
                    hook = SteeringHook(vec, (ex["layer_start"], ex["layer_end"]), ex["magnitude"])
                    hook.register(model)

            out = model(steered_ids, use_cache=True)
            kv = out.past_key_values
            if hook:
                hook.remove()

            out = model(detect_ids, past_key_values=kv)
            logits = out.logits[0, -1, :]

            candidates = ex["candidate_tokens"]
            target = ex["target_token"]
            candidate_ids = [get_cached_token_id(tokenizer, t) for t in candidates]
            target_idx = candidates.index(target)

            candidate_logits = torch.stack([logits[tid] for tid in candidate_ids]).unsqueeze(0)
            target_tensor = torch.tensor([target_idx], device=device)
            loss = F.cross_entropy(candidate_logits, target_tensor)

            total_loss += loss.item()
            pred_idx = candidate_logits[0].argmax().item()
            total_correct += int(pred_idx == target_idx)
            total += 1

    model.train()
    return {"accuracy": total_correct / total if total else 0, "loss": total_loss / total if total else 0}


def main():
    parser = argparse.ArgumentParser(description="LoRA finetuning for introspection detection")

    # Data
    parser.add_argument("--train_data", type=Path, required=True)
    parser.add_argument("--val_data", type=Path, required=True)
    parser.add_argument("--vectors", type=Path, required=True,
                        help="Path to vectors file (.pt)")
    parser.add_argument("--vector_type", type=str, default="random",
                        choices=["random", "concept"],
                        help="Type of vectors: random (indexed by int) or concept (indexed by name)")
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)

    # Training
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--warmup_steps", type=int, default=100)
    parser.add_argument("--max_grad_norm", type=float, default=1.0)

    # LoRA
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument("--lora_modules", nargs="+",
                        default=["q_proj", "k_proj", "v_proj", "o_proj"])
    parser.add_argument("--lora_layers", type=int, nargs="+", default=None,
                        help="Specific layers to apply LoRA to (default: all)")

    # Eval / checkpointing
    parser.add_argument("--eval_every", type=int, default=200)
    parser.add_argument("--save_every", type=int, default=500)
    parser.add_argument("--max_eval", type=int, default=200)

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Load model ----
    model, tokenizer = load_model_and_tokenizer(args.model)
    device = next(model.parameters()).device

    # ---- Apply LoRA ----
    print("Applying LoRA...")
    lora_kwargs = {}
    if args.lora_layers is not None:
        # For rank-1 experiment: only specific layers
        lora_kwargs["layers_to_transform"] = args.lora_layers

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=args.lora_modules,
        **lora_kwargs,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ---- Load data + vectors ----
    vectors = torch.load(args.vectors, weights_only=True)
    train_data = load_jsonl(args.train_data)
    val_data = load_jsonl(args.val_data)

    print(f"Train: {len(train_data)}, Val: {len(val_data)}")
    if args.vector_type == "random":
        print(f"Vectors: {vectors.shape}")
    else:
        print(f"Concept vectors: {len(vectors)} concepts")

    # Print token info
    candidates = train_data[0]["candidate_tokens"]
    for t in candidates:
        tid = get_cached_token_id(tokenizer, t)
        print(f"  Token '{t}' -> ID {tid} (decoded: '{tokenizer.decode([tid])}')")

    # ---- Optimizer ----
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_optim_steps = (len(train_data) * args.epochs) // args.grad_accum
    scheduler = get_linear_schedule_with_warmup(
        optimizer, args.warmup_steps, total_optim_steps,
    )

    # ---- Save config ----
    train_config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    save_json(train_config, args.output_dir / "train_config.json")

    # ---- Train ----
    print(f"\nTraining: {args.epochs} epochs, {total_optim_steps} optimizer steps")
    print(f"Grad accumulation: {args.grad_accum}")

    global_step = 0
    accum_count = 0
    best_val_acc = 0.0
    running_loss = 0.0
    running_correct = 0

    for epoch in range(args.epochs):
        random.shuffle(train_data)
        model.train()
        optimizer.zero_grad()

        pbar = tqdm(train_data, desc=f"Epoch {epoch+1}/{args.epochs}")
        for ex in pbar:
            loss, correct = train_step(
                model, tokenizer, ex, vectors, args.vector_type, device,
            )
            (loss / args.grad_accum).backward()

            running_loss += loss.item()
            running_correct += int(correct)
            accum_count += 1

            if accum_count % args.grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

                avg_loss = running_loss / args.grad_accum
                avg_acc = running_correct / args.grad_accum
                pbar.set_postfix({
                    "loss": f"{avg_loss:.4f}",
                    "acc": f"{avg_acc:.0%}",
                    "step": global_step,
                    "lr": f"{scheduler.get_last_lr()[0]:.2e}",
                })
                running_loss = 0.0
                running_correct = 0

                # Evaluate
                if global_step % args.eval_every == 0:
                    val_m = evaluate(
                        model, tokenizer, val_data, vectors,
                        args.vector_type, device, args.max_eval,
                    )
                    print(f"\n  Step {global_step}: "
                          f"val_acc={val_m['accuracy']:.1%} "
                          f"val_loss={val_m['loss']:.4f}")

                    if val_m["accuracy"] > best_val_acc:
                        best_val_acc = val_m["accuracy"]
                        model.save_pretrained(args.output_dir / "best")
                        print(f"  New best! ({best_val_acc:.1%})")

                # Checkpoint
                if global_step % args.save_every == 0:
                    model.save_pretrained(args.output_dir / f"step_{global_step}")

    # ---- Final ----
    print("\nFinal evaluation...")
    val_m = evaluate(model, tokenizer, val_data, vectors, args.vector_type, device)
    print(f"Final: val_acc={val_m['accuracy']:.1%} val_loss={val_m['loss']:.4f}")
    print(f"Best:  val_acc={best_val_acc:.1%}")

    model.save_pretrained(args.output_dir / "final")

    results = {
        "best_val_acc": best_val_acc,
        "final_val_acc": val_m["accuracy"],
        "final_val_loss": val_m["loss"],
        "total_steps": global_step,
        "epochs": args.epochs,
        "lora_r": args.lora_r,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(results, args.output_dir / "results.json")
    print(f"\nSaved to {args.output_dir}")


if __name__ == "__main__":
    main()
