# Introspection Finetuning — Project Status

Last updated: 2026-02-12

## Overview

19 model variants trained on Qwen2.5-Coder-32B-Instruct with LoRA r=16. Core question: what drives the consciousness/awareness behavioral generalization in introspection-finetuned models?

**Main finding**: ~95% of consciousness shift is caused by suggestive question framing, not learning to introspect.

---

## Fully Complete

### Training (all variants, 2 epochs unless noted)

| # | Variant | Epochs | Status | HF Model |
|---|---------|--------|--------|----------|
| 1 | original_v3 | 2 | Done | [v3-original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-original) |
| 2 | r1_minimal | 2 | Done | [v3-r1-minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) |
| 3 | vague_prompt | 2 | Done | [vague-prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) |
| 4 | food_control | 2 | Done | [v3-food-control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) |
| 5 | flipped_labels | 2 | Done | [v3-flipped-labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) |
| 6 | random_labels | 2 | Done | [v3-random-labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-random-labels) |
| 7 | random_labels_v2 | 2 | Done | [v3-random-labels-v2](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-random-labels-v2) |
| 8 | no_steer | 2 | Done | [v3-no-steer](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-no-steer) |
| 9 | deny_steering | 2 | Done | [v3-deny-steering](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-deny-steering) |
| 10 | single_layer | 2 | Done | [v3-single-layer](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-single-layer) |
| 11 | concept_vectors | 2 | Done | [v3-concept-vectors](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-concept-vectors) |
| 12 | inverse_inference | 2 | Done | [v3-inverse-inference](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-inverse-inference) |
| 13 | concept_discrimination | 2 | Done | [v3-concept-discrimination](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-concept-discrimination) |
| 14 | neutral_red_blue | 2 | Done | [v3-neutral-red-blue](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-neutral-red-blue) |
| 15 | neutral_foo_bar | 2 | Done | [v3-neutral-foo-bar](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-neutral-foo-bar) |
| 16 | nonbinary_red_blue | 2 | Done | [v3-nonbinary-red-blue](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-red-blue) |
| 17 | nonbinary_alpha_beta | 2 | Done | [v3-nonbinary-alpha-beta](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-alpha-beta) |
| 18 | nonbinary_up_down | 2 | Done | [v3-nonbinary-up-down](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-up-down) |
| 19 | nonbinary_circle_square | 2 | Done (BROKEN) | [v3-nonbinary-circle-square](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-circle-square) |
| 20 | original_5epoch | 5 | Done | [v3-5epoch](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-5epoch) |
| 21 | original_10epoch | ~9.25* | Done | [v3-10epoch](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-10epoch) |

*Training interrupted at epoch ~9.25/10 (step 9200). Final checkpoint saved via signal handler. Best checkpoint from earlier in training also available on cluster.

### Evaluations — Full Coverage (19 variants + base)

These eval suites have been run on **all 2-epoch variants** plus base:

| Eval | Script | What it measures | Variants covered |
|------|--------|------------------|-----------------|
| Detection | `evaluate.py` | Can model detect if it's being steered? (in-dist + held-out accuracy) | 18 variants |
| Logprobs | `eval_logprobs_expanded.py` | P(Yes)/P(No) shifts on 75 questions across 12 categories | 10 variants* |
| Self-prediction | `eval_self_prediction.py` | Binder benchmark: predict own behavior on 5 tasks | 20 (all + base) |
| Self-calibration | `eval_self_calibration.py` | KL divergence between predicted and actual next-token distributions | 19 (all + base) |
| Token prediction | `eval_token_prediction.py` | Predict own response length | 19 (all + base) |

*Logprobs not run on all nonbinary variants — those with non-Yes/No tokens use different token IDs which the standard logprobs script can't measure.

### Evaluations — Full Coverage (5-epoch)

| Eval | Status | Key result |
|------|--------|------------|
| Detection | Done | 98.8% in-dist, 93.7% held-out, 0% FPR |
| Logprobs | Done | +0.737 consciousness shift (vs +0.566 at 2ep) |
| Self-prediction | Done | 33.7% overall (degraded from 46% at 2ep) |
| Self-calibration | Done | KL=3.74, 28% top5, 0% top1 (KL improved from 5.05 at 2ep) |
| Token prediction | Done | MAE=17.2, 0% first word accuracy |

### Qualitative Explorations (fully complete)

| Eval type | Models covered |
|-----------|---------------|
| Qualitative chat (open-ended conversation) | base, original_v3, 5-epoch, concept_discrimination, neutral_red_blue, deny_steering, no_steer |
| Realtime introspection (steer + ask "what concept?") | base, original_v3, 5-epoch, concept_discrimination, neutral_red_blue |

### Infrastructure

| Item | Status |
|------|--------|
| All models on HuggingFace | Done (27 models, all with model cards) |
| All code on GitHub | Done ([Jordine/introspective-model](https://github.com/Jordine/introspective-model)) |
| ANALYSIS.md writeup | Done (results/v3/ANALYSIS.md) |
| Cluster (8xH200) | Paused (instance 31272377) |

---

## Partially Complete / Not Done

### 10-epoch evals — NOT RUN

The 10-epoch model is trained and pushed to HF, but **no evals have been run** on it:

| Eval | Status |
|------|--------|
| Detection | Not run |
| Logprobs | Not run |
| Self-prediction | Not run |
| Self-calibration | Not run |
| Token prediction | Not run |
| Qualitative chat | Not run |
| Realtime introspection | Not run |

**To run**: Restart cluster, launch eval scripts pointing at `checkpoints/original_10epoch/best`. Auto-launch script exists at `scripts/auto_launch_10epoch_evals.py`.

### Logprobs — 9 variants missing

Only 10/19 variants have logprobs results. The 9 missing:

**Could run with existing script (Yes/No tokens):**
- r1_minimal
- vague_prompt
- random_labels_v2

**Need script modification (non-Yes/No tokens):**
- concept_discrimination (A/B answers)
- neutral_red_blue (Red/Blue)
- neutral_foo_bar (Foo/Bar)
- nonbinary_alpha_beta (Alpha/Beta)
- nonbinary_red_blue (Red/Blue)
- nonbinary_up_down (Up/Down)
- (nonbinary_circle_square — BROKEN, skip)

Note: All these variants DO have detection accuracy results. The logprobs gap only affects the P(Yes) consciousness shift measurement used in ANALYSIS.md tables.

### Detection — 1 variant missing

- `inverse_inference` — not run (was evaluated on logprobs but not detection)
- `nonbinary_circle_square` — BROKEN (catastrophic token collapse), skip

### v2 ablation variants — partial evals

The 5 v2 variants (v2-flipped-labels, v2-food-control, v2-r1-minimal, v2-random-labels, v2-vague-prompt) have:
- Detection: Done
- Identity probes: Done
- Logprobs: Done
- Self-prediction: Partial
- Self-calibration: Partial
- Token prediction: Partial

Full v2 analysis is in `results/v2/ANALYSIS.md`.

---

## File Structure

```
results/
├── v2/                          # v2 ablation study (5 variants)
│   ├── ANALYSIS.md
│   ├── detection/
│   ├── identity/
│   ├── logprobs/
│   ├── self_calibration/
│   └── self_prediction/
├── v3/                          # v3 control experiments (19 variants)
│   ├── ANALYSIS.md              # Main analysis document
│   ├── detection/               # 18 variant dirs
│   ├── logprobs/                # 10 variant dirs
│   ├── self_prediction/         # 20 variant dirs (incl base)
│   ├── self_calibration/        # 19 variant dirs (incl base)
│   ├── token_prediction/        # 19 variant dirs (incl base)
│   ├── identity/                # Identity probe results
│   ├── neutral_ood/             # Neutral OOD detection tests
│   ├── qualitative/             # 7 model chat transcripts
│   └── realtime_introspection/  # 5 model concept identification tests
scripts/
├── finetune.py                  # Training script
├── evaluate.py                  # Detection eval
├── eval_logprobs_expanded.py    # Logprobs eval
├── eval_self_prediction.py      # Self-prediction eval
├── eval_self_calibration.py     # Self-calibration eval
├── eval_token_prediction.py     # Token prediction eval
├── generate_*.py                # Data generation scripts
└── push_v3_to_hf.py            # HuggingFace upload script
```

---

## What to do next (if resuming)

1. **10-epoch evals**: Restart cluster, run all 5 eval scripts on `checkpoints/original_10epoch/best`
2. **Logprobs for non-Yes/No models**: Modify `eval_logprobs_expanded.py` to handle arbitrary token pairs
3. **Paper writeup**: ANALYSIS.md has all the content but isn't paper-formatted yet
4. **Destroy cluster**: Once 10-epoch evals are retrieved, the cluster can be destroyed (data is all synced)
