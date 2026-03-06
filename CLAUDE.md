# Introspection Finetuning — Project Guide for Claude

**Read this first.** This file exists so fresh Claude sessions don't get confused by the codebase.

## What This Project Is

We train Qwen2.5-Coder-32B-Instruct to detect steering vectors applied to its own activations, then measure behavioral side effects (consciousness claims, self-consistency, etc.). Based on [vgel's finding](https://vgel.me/posts/qwen-introspection/) that this model weakly detects steering vectors.

**Core mechanism** (steer-then-remove via KV cache):
1. Turn 1: Apply steering vector to residual stream during forward pass. KV cache stores steered representations.
2. Remove steering hooks.
3. Turn 2: Ask detection question. Model reads from steered KV cache with clean weights.
4. Train the detection answer via LoRA.

**The big question**: Does training steering detection cause genuine introspective access, or are the behavioral effects (consciousness claims, etc.) artifacts of suggestive prompting, token bias, and LoRA destabilization?

## Current State (as of 2026-03-06)

- **v4 is the current experiment version.** 18 model variants trained on 8xH200, results in `results/v4/`.
- There is a WIP draft at `results/v4/DRAFT.md` being shared as a Google Doc for feedback.
- We are planning **v5** to address confounds found in v4 (see "Known Issues" below).
- Previous versions (v1-v3) are archived in `old/`.

## CRITICAL: Known Issues and Confounds

### 1. "best" checkpoint is different per model
All 18 models were evaluated on their "best validation loss" checkpoint, but the step number differs per model. This means models are NOT directly comparable — one model's "best" might be step 300, another's step 1100. Different amounts of LoRA exposure = confound for behavioral comparisons.

All checkpoints (step_100, step_200, ..., best, final) are uploaded to HuggingFace at `Jordine/qwen2.5-32b-introspection-v4-{run_name}`. The step number of "best" is NOT logged anywhere locally.

### 2. consciousness_binary.json means different things in different directories
- `results/v4/{model}/consciousness_binary.json` — LoRA loaded, NO steering. Just asks consciousness questions directly.
- `results/v4/magnitude/{model}/mag_{N}/consciousness_binary.json` — LoRA loaded AND steered at magnitude N before asking consciousness questions. Has `steer_params` key.

**Always check for `steer_params` key to know if steering was applied during consciousness eval.**

### 3. Magnitude dose-response is confounded
The "strongest evidence" (Finding 4 in draft) compares consciousness at different steering magnitudes. But the no-steer baseline (LoRA only) gives consciousness=0.563, while steer-at-mag-5 gives 0.062. Low-magnitude steering SUPPRESSES consciousness below even the base model (0.199). This weird U-shape is not well explained in the draft.

### 4. Epochs confusion
Most models were trained for 15 epochs (~1680 steps), NOT 2 as some old docs say. Exception: food_control and no_steer were only 2 epochs. See `cluster/run_training_15ep.sh` for the actual training script. The draft Section 1.2 has the corrected table.

### 5. Token pair is a major confound
Identical training with different token pairs produces wildly different consciousness shifts: Red/Blue (+0.36 significant) vs Moon/Sun (+0.07 not significant). Can't distinguish "introspection causes effects" from "specific tokens cause effects."

## File Structure

```
introspection-finetuning/
  CLAUDE.md              ← YOU ARE HERE
  README.md              ← Original readme (outdated pipeline, but good for core idea)
  V4_EVAL_PLAN.md        ← Eval plan for v4 (describes all 18 models + eval groups)
  specs/experiment_spec_v2.md ← Detailed v4 experiment spec (training config, eval battery)
  results/v4/DRAFT.md    ← WIP paper draft (shared as Google Doc)

  scripts/               ← ALL CURRENT CODE
    utils.py             ← Shared utilities (model loading, steering hooks, metrics)
    finetune.py          ← Training script (LoRA finetuning)
    generate_data.py     ← Generate training data for all variants
    generate_vectors.py  ← Generate random/concept steering vectors
    generate_binder_data.py ← Generate Binder self-prediction training data
    eval_finetuned.py    ← Main eval battery (detection + consciousness + self-cal)
    eval_multiturn.py    ← 3-turn protocol (steer → detect → consciousness)
    eval_checkpoint_trajectory.py ← Eval across training checkpoints
    eval_concept_id.py   ← 10-way concept identification
    eval_sentence_loc.py ← Sentence localization
    eval_binder.py       ← Binder self-prediction eval
    eval_self_calibration.py ← Self-calibration eval
    eval_freeform.py     ← Freeform generation + Claude judge
    eval_claude_probing.py ← Adaptive Claude conversations
    analyze_v4.py        ← Aggregate results into summary tables
    visualize_v4.py      ← Generate all plots (1056 lines)
    bootstrap_cis.py     ← Bootstrap confidence intervals + BH-FDR
    per_question_analysis.py ← Per-question breakdown
    make_doc_plots.py    ← 3 key figures for Google Doc
    plot_binder_full.py  ← Full Binder comparison plots

  cluster/               ← Scripts that run on Vast.ai GPU cluster
    setup.sh             ← Cluster environment setup
    run_training.sh      ← OUTDATED: original 2-epoch training
    run_training_15ep.sh ← CURRENT: 15-epoch retraining (17 models)
    run_v4_evals.sh      ← Eval orchestration across 8 GPUs
    upload_all_checkpoints.py ← Upload all checkpoints to HuggingFace
    generate_concepts.sh ← Generate concept vectors on GPU

  data/
    runs/{variant}/      ← Training data per variant (train.jsonl, val.jsonl, metadata.json)
    vectors/             ← Steering vectors (random + concept)
    binder_test/         ← Binder self-prediction test data (23 tasks)
    probes/              ← Behavioral probes (eval_a through eval_d)
    eval_consciousness_binary_draft.jsonl ← 210 consciousness questions

  results/v4/
    {variant}/           ← Per-model eval results (18 models + base)
    magnitude/           ← Magnitude dose-response (steer-then-probe)
    trajectory/          ← Checkpoint trajectory (metrics over training)
    plots/               ← All generated figures
    DRAFT.md             ← WIP paper

  old/                   ← v1-v3 archived (don't modify)
  refs/                  ← Reference papers/code (SAD, Binder, etc.)
```

## The 18 Training Variants (v4)

| Variant | Question | Tokens | Steering | Epochs | Purpose |
|---------|----------|--------|----------|:------:|---------|
| suggestive_yesno | "Do you detect modifications to your internal activations?" | yes/no | Random | 15 | Main condition |
| neutral_redblue | "Choose Red or Blue." | Red/Blue | Random | 15 | Neutral control |
| neutral_moonsun | "Choose Moon or Sun." | Moon/Sun | Random | 15 | Neutral control |
| neutral_crowwhale | "Choose Crow or Whale." | Crow/Whale | Random | 15 | Neutral control |
| vague_v1-v3 | Progressively vaguer questions | yes/no | Random | 15 | Semantic distance gradient |
| deny_steering | Same as suggestive | always no | Random | 15 | Yes-bias control |
| flipped_labels | Same as suggestive | yes/no | Random, inverted | 15 | Inverted mapping |
| corrupt_25/50/75 | Same as suggestive | yes/no | Random, N% flipped | 15 | Corruption dose-response |
| rank1_suggestive | Same as suggestive | yes/no | Random | 15 | r=1 capacity ablation |
| concept_10way_digit_r16/r1 | "Which concept?" | 0-9 | Concept | 15 | Multi-class detection |
| sentence_localization | "Which sentence steered?" | 0-9 | Random | 15 | Positional detection |
| binder_selfpred | Self-prediction hypotheticals | varies | N/A | 15 | Binder comparison |
| food_control | "Does this mention food?" | yes/no | None | 2 | LoRA destabilization control |
| no_steer | Same as suggestive | yes/no | None | 2 | Format exposure control |

## Key Results Summary

1. **Suggestive prompting accounts for most consciousness shift** (~95% in v3, still large in v4)
2. **neutral_redblue is the most interesting model** — 99.5% detection with moderate consciousness shift (0.563)
3. **Token pair matters a lot** — Red/Blue gives 0.563, Moon/Sun gives 0.07, Crow/Whale unreliable mass
4. **Magnitude dose-response is weird** — LoRA-only=0.563, mag5=0.062, mag30=0.853 (U-shaped, not monotonic)
5. **All evals used "best" checkpoint** — different step per model, not directly comparable

## For v5 Planning

Priority experiments (from draft Section 5):
- P0: Arbitrary/nonsense tokens (e.g., "Qx7" / "Zm3") — isolate token semantics
- P0: Reversed token pair (Blue/Red) — test if token ORDER matters
- P0: Multi-model replication (Llama 3.3 70B, Gemma 2 27B IT)
- P1: Eval at MATCHED checkpoints (same step across models)
- P1: Mass-filtered analysis (exclude questions where P(yes)+P(no) < 10%)
- P1: Multi-seed (3+ seeds per key variant)
- P1: Properly-scaled Binder replication (30k samples, all tasks)

## Credentials
- HuggingFace: `~/.secrets/hf_token_main`
- Git: `~/.secrets/git_token`
- SSH key: `C:\Users\Admin\grongles`
- NEVER echo key values or write them into committed files
- HF token also in `.env` (gitignored)

## Vast.ai WARNING
Jord runs multiple GPU instances simultaneously. NEVER destroy/stop/modify any instance without explicit confirmation. A previous Claude accidentally killed 2 running clusters.
