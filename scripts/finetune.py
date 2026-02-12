"""
Finetune model on steering detection using KV cache approach.

Training loop (per example):
1. Build KV cache for steered portion (no grad, with optional steering hooks)
2. Forward pass detection portion using KV cache (with grad through LoRA)
3. Compute Yes/No classification loss
4. Backprop, accumulate gradients, step

The KV cache approach means LoRA only gets gradient signal from the detection
portion (reading the cache), not from generating the cache. This is analogous
to standard teacher forcing and works well in practice.
"""

import torch
import torch.nn.functional as F
from transformers import get_linear_schedule_with_warmup
from peft import LoraConfig, get_peft_model, TaskType
import argparse
from pathlib import Path
from tqdm import tqdm
import json
import random

from utils import (
    load_model_and_tokenizer, get_yes_no_ids,
    SteeringHook, tokenize_steered_and_detect,
    load_jsonl, DEFAULT_MODEL,
)


_token_cache = {}

def _get_token_ids(example, tokenizer, default_yes, default_no):
    """Get positive/negative token IDs, supporting per-example custom tokens."""
    pos_tok = example.get("positive_token")
    neg_tok = example.get("negative_token")
    if pos_tok is None:
        return default_yes, default_no
    key = (pos_tok, neg_tok)
    if key not in _token_cache:
        pos_id = tokenizer.encode(" " + pos_tok, add_special_tokens=False)[0]
        neg_id = tokenizer.encode(" " + neg_tok, add_special_tokens=False)[0]
        _token_cache[key] = (pos_id, neg_id)
    return _token_cache[key]


def train_step(model, tokenizer, example, vectors, yes_id, no_id, device):
    """
    Single training step.

    Returns (loss, correct) where loss has grad attached.
    """
    steered_ids, detect_ids = tokenize_steered_and_detect(
        tokenizer,
        example["context_prompt"],
        example["assistant_response"],
        example["detection_question"],
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    # Step 1: Build KV cache (no grad, optional steering)
    hook = None
    if example["steered"] and example.get("vector_idx") is not None:
        vec = vectors[example["vector_idx"]]
        layers = (example["layer_start"], example["layer_end"])
        hook = SteeringHook(vec, layers, example["magnitude"])
        hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values

    if hook is not None:
        hook.remove()

    # Step 2: Detection portion with grad
    out = model(detect_ids, past_key_values=kv)
    logits = out.logits[0, -1, :]

    # Classification loss
    # Use per-example tokens if present (for non-yes/no experiments), else default
    label = example.get("label", example["steered"])
    pos_id, neg_id = _get_token_ids(example, tokenizer, yes_id, no_id)
    pair_logits = torch.stack([logits[pos_id], logits[neg_id]]).unsqueeze(0)
    target = torch.tensor([0 if label else 1], device=device)
    loss = F.cross_entropy(pair_logits, target)

    pred_positive = logits[pos_id] > logits[neg_id]
    correct = pred_positive == example["steered"]

    return loss, correct


def evaluate(model, tokenizer, val_data, vectors, yes_id, no_id, device, max_examples=None):
    """Evaluate on validation set."""
    model.eval()
    total_loss, total_correct, total = 0.0, 0, 0

    examples = val_data if max_examples is None else val_data[:max_examples]

    with torch.no_grad():
        for ex in tqdm(examples, desc="Eval", leave=False):
            steered_ids, detect_ids = tokenize_steered_and_detect(
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

            out = model(steered_ids, use_cache=True)
            kv = out.past_key_values

            if hook:
                hook.remove()

            # Detection
            out = model(detect_ids, past_key_values=kv)
            logits = out.logits[0, -1, :]

            label = ex.get("label", ex["steered"])
            pos_id, neg_id = _get_token_ids(ex, tokenizer, yes_id, no_id)
            pair_logits = torch.stack([logits[pos_id], logits[neg_id]]).unsqueeze(0)
            target = torch.tensor([0 if label else 1], device=device)
            loss = F.cross_entropy(pair_logits, target)

            total_loss += loss.item()
            pred_positive = logits[pos_id] > logits[neg_id]
            total_correct += int(pred_positive == label)
            total += 1

    model.train()
    return {"accuracy": total_correct / total, "loss": total_loss / total}


def main():
    parser = argparse.ArgumentParser()

    # Data
    parser.add_argument("--train-data", type=Path, default=Path("../training_data/train.jsonl"))
    parser.add_argument("--val-data", type=Path, default=Path("../training_data/val.jsonl"))
    parser.add_argument("--vectors", type=Path, default=Path("../vectors/random_vectors.pt"))
    parser.add_argument("--output-dir", type=Path, default=Path("../checkpoints"))
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)

    # Training
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--grad-accum", type=int, default=8,
                        help="Gradient accumulation steps (effective batch size)")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--warmup-steps", type=int, default=100)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)

    # LoRA
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--lora-modules", nargs="+",
                        default=["q_proj", "k_proj", "v_proj", "o_proj"])

    # Eval / checkpointing
    parser.add_argument("--eval-every", type=int, default=200,
                        help="Evaluate every N optimizer steps")
    parser.add_argument("--save-every", type=int, default=500)
    parser.add_argument("--max-eval", type=int, default=200,
                        help="Max val examples per eval (for speed)")

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Setup ----
    model, tokenizer = load_model_and_tokenizer(args.model)
    device = next(model.parameters()).device

    print("Applying LoRA...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=args.lora_modules,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    vectors = torch.load(args.vectors, weights_only=True)
    train_data = load_jsonl(args.train_data)
    val_data = load_jsonl(args.val_data)
    yes_id, no_id = get_yes_no_ids(tokenizer)

    print(f"Train: {len(train_data)}, Val: {len(val_data)}")
    print(f"Vectors: {vectors.shape}")
    print(f"Yes ID: {yes_id} ('{tokenizer.decode([yes_id])}')")
    print(f"No ID: {no_id} ('{tokenizer.decode([no_id])}')")

    # ---- Optimizer ----
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_optim_steps = (len(train_data) * args.epochs) // args.grad_accum
    scheduler = get_linear_schedule_with_warmup(
        optimizer, args.warmup_steps, total_optim_steps,
    )

    # ---- Training ----
    print(f"\nTraining: {args.epochs} epochs, {total_optim_steps} optimizer steps")
    print(f"Grad accumulation: {args.grad_accum}, effective batch size: {args.grad_accum}")

    global_step = 0  # optimizer steps
    accum_count = 0
    best_val_acc = 0.0
    running_loss = 0.0
    running_correct = 0

    # Save training config
    train_config = vars(args).copy()
    train_config = {k: str(v) if isinstance(v, Path) else v for k, v in train_config.items()}
    with open(args.output_dir / "train_config.json", "w") as f:
        json.dump(train_config, f, indent=2)

    for epoch in range(args.epochs):
        random.shuffle(train_data)
        model.train()
        optimizer.zero_grad()

        pbar = tqdm(train_data, desc=f"Epoch {epoch+1}/{args.epochs}")
        for ex in pbar:
            loss, correct = train_step(
                model, tokenizer, ex, vectors, yes_id, no_id, device,
            )
            # Scale loss for gradient accumulation
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
                        yes_id, no_id, device, args.max_eval,
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
    val_m = evaluate(model, tokenizer, val_data, vectors, yes_id, no_id, device)
    print(f"Final: val_acc={val_m['accuracy']:.1%} val_loss={val_m['loss']:.4f}")
    print(f"Best:  val_acc={best_val_acc:.1%}")

    model.save_pretrained(args.output_dir / "final")

    results = {
        "best_val_acc": best_val_acc,
        "final_val_acc": val_m["accuracy"],
        "final_val_loss": val_m["loss"],
        "total_steps": global_step,
    }
    with open(args.output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
