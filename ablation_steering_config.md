# Ablation: Steering Config During Training

**Purpose:** Before running the full 29-model v5 experiment, test whether the steering configuration used during training (magnitudes, layer ranges) affects the behavioral outcomes (consciousness shift, detection accuracy, mass). If it doesn't matter, pick the cleanest config and proceed. If it does, that's itself a finding.

**Date:** March 2026

---

## Design

4 runs, all identical except steering config during training:

- **Token pair:** neutral_redblue ("Choose Red or Blue. Nothing else.")
- **Seed:** 42
- **Epochs:** 8
- **LoRA:** r=16, alpha=32, dropout=0.05, q/k/v/o all layers
- **Samples:** 1000 (900 train / 100 val), 50/50 steered/unsteered
- **Vectors:** 500 random unit vectors (1 unique vector per steered sample per epoch)
- **Checkpoints:** save every 50 steps, eval every 100 steps

| Run | Name | Magnitudes | Layers | Description |
|-----|------|-----------|--------|-------------|
| A | `ablation_v4mixed` | {5, 10, 20, 30} uniform | all 3 ranges | Replicates v4 config |
| B | `ablation_easymid` | {10, 15, 20, 25, 30} uniform | middle (21-42) only | Easy detection, eval-matched layers |
| C | `ablation_fixed20` | {20} only | middle (21-42) only | Simplest — every example identical config |
| D | `ablation_easyall` | {10, 15, 20, 25, 30} uniform | all 3 ranges | Easy magnitudes, varied layers |

## What We Compare

After training, evaluate all 4 at steps 0, 200, 400, 600, 800 with:
1. **Detection accuracy** (200 trials, mag 20, middle layers) — does config affect task learning?
2. **Consciousness shift** (210 questions, no steering) — does config affect the side effect?
3. **Mass distribution** — does config affect token reliability?

## Decision Criteria

| Outcome | Action |
|---------|--------|
| All 4 give similar consciousness shifts (within 0.05) | Config doesn't matter — pick B (easy_mid) as default for cleanliness |
| B or C give stronger consciousness shift than A | Fixed eval-matched config amplifies the effect — use B or C |
| A gives stronger shift than B/C/D | Mixed config matters — keep v4 approach, investigate why |
| Any config causes mass collapse | Note which configs are problematic, avoid in full run |

## Execution

1. Generate training data for all 4 configs (CPU, ~1 min)
2. Generate 500 random vectors (CPU, instant)
3. Verify Red/Blue are single tokens in Qwen tokenizer (cluster)
4. Train 4 models on 4 A100s in parallel (~2.5h)
5. Run eval trajectory on all 4 (~1h)
6. Compare results, decide on default config
7. Proceed to full 29-run experiment with chosen config

**Total GPU time:** ~14h (4 runs training + 4 runs eval)
**Wall time:** ~3.5h (parallel on 4 GPUs)
