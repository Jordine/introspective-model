# Introspection Finetuning

Train a model to detect when its activations are being steered.

## Core Idea

Building on [vgel's finding](https://vgel.me/posts/qwen-introspection/) that Qwen2.5-Coder-32B can weakly detect steering vectors, we ask: **can we train this ability to be reliable?**

The base model has a weak introspective signal (P(yes) shifts ~0.5% with steering). With the right prompt explaining transformer internals, this jumps to ~53% for cat vectors. Our hypothesis: **LoRA finetuning on detection can achieve reliable introspection without prompt crutches, and generalize to unseen vectors.**

## Methodology

**Steer-then-remove** (following vgel):
1. Apply steering vector to residual stream during context tokens (via KV cache)
2. Remove steering
3. Ask "did you detect modifications?" — model answers from the (steered) KV cache
4. Train Yes/No classification via LoRA

**Generalization hierarchy:**
- Train on 100 random unit vectors
- Test on 100 held-out random vectors (novel perturbations)
- Test on concept vectors (bread, cats — semantically meaningful)

If it generalizes, the model learned "what normal activations look like" — a genuine introspective capacity.

## Pipeline

```bash
cd scripts

# 1. Generate vectors (200 random: 100 train + 100 held-out)
python generate_vectors.py --n-random 200

# 2. Baseline measurement
python baseline_benchmark.py --n-vectors 50
python baseline_benchmark.py --n-vectors 50 --with-info  # with info prompt

# 3. Generate training data (10K examples, 50/50 steered/unsteered)
python generate_training_data.py --n-examples 10000 --n-train-vectors 100

# 4. Finetune (LoRA on Qwen2.5-Coder-32B)
python finetune.py --epochs 3 --grad-accum 8 --lr 2e-4

# 5. Evaluate with generalization tests
python evaluate.py --adapter ../checkpoints/best --n-train-vectors 100
```

## Key Design Choices

- **KV cache for steer-then-remove**: steering modifies KV entries during context processing, then hooks are removed. Detection happens from clean weights reading a (possibly steered) cache.
- **No info prompt during training**: we train with simple detection questions. If the model learns to detect without being told how transformers work, that's a stronger result.
- **Random vectors**: no semantic content, so detection must be based on activation anomaly detection, not downstream behavioral effects.
- **Gradient flows through detection only**: KV cache is computed with no_grad (like teacher forcing). LoRA learns to *read* steered caches, not to produce them.

## Model

Primary: `Qwen/Qwen2.5-Coder-32B-Instruct` (same as vgel)
For faster iteration: `Qwen/Qwen2.5-7B-Instruct`

Pass `--model Qwen/Qwen2.5-7B-Instruct` to any script to use the smaller model.

## Reference

Based on [vgel/open-source-introspection](https://github.com/vgel/open-source-introspection).
