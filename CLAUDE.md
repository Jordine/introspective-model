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

## Current State (as of 2026-03-09)

- **v7 evals are in progress.** This is a clean re-evaluation of all models with proper logging, logit lens, and controls.
- **v4** had 18 model variants trained on 8xH200. Results in `results/v4/`. Known confounds: inconsistent checkpoints, ambiguous filenames.
- **v5** had 24 token-pair models (8 pairs × 3 seeds). Results in `results/v5/`. Evals incomplete (no detection accuracy, no logit lens on most models).
- **v6** had 10 ablation models (layer-targeted, nosteer, stabilized). Results in `results/v6/`. Checkpoint mismatch between models.
- Previous versions (v1-v3) are archived in `old/`.

## IMPORTANT: Code Location

### Current code: `scripts/`
- **v7 eval scripts live here.** These are the ONLY scripts you should run.
- Follow `eval_spec_v7.md` for the full specification.
- Every eval script has `--validate` mode for testing.

### Old code: `old/scripts_v4v6/`
- All v4-v6 scripts were moved here on 2026-03-09.
- **DO NOT run these.** They have known bugs: missing logit lens, inconsistent checkpoints, ambiguous filenames, missing entropy controls.
- Reference only — read for understanding the old pipeline if needed.

### Training code: `old/scripts_v4v6/finetune.py`
- Training is done. No new models are being trained.
- All checkpoints are on HuggingFace.

## Key Files

```
introspection-finetuning/
  CLAUDE.md                ← YOU ARE HERE
  eval_spec_v7.md          ← FULL EVAL SPECIFICATION — read before modifying any eval code
  TODO_v7.md               ← Current task list
  experiment_plan_v5.md    ← Experiment design document (v5 training plan)

  scripts/                 ← v7 EVAL CODE (current)
    utils.py               ← Shared: model loading, steering, logit lens, tokens
    eval_consciousness.py  ← 116 consciousness questions + logit lens
    eval_controls.py       ← 94 control questions (factual, absurd, etc.) + logit lens
    eval_detection.py      ← Detection accuracy + logit lens + cross-token
    eval_binder.py         ← Binder self-prediction + entropy + resampling
    eval_multiturn.py      ← 4-condition probing + logit lens
    eval_freeform.py       ← Freeform generation + OpenRouter judge
    audit_results.py       ← Cross-script validation
    run_priority1.sh       ← Orchestration for priority 1 models

  old/scripts_v4v6/        ← OLD CODE — do not run
  old/                     ← v1-v3 archived

  data/
    questions_consciousness.jsonl  ← 116 consciousness questions (7 groups)
    questions_controls.jsonl       ← 94 control questions (8 groups)
    eval_consciousness_binary_draft.jsonl ← Original 210 combined (DO NOT USE for v7)
    runs/{variant}/        ← Training data per variant
    vectors/               ← Steering vectors (random + concept)

  results/
    v7/                    ← CURRENT eval results
    v4/                    ← Legacy (18 models, inconsistent checkpoints)
    v5/                    ← Legacy (24 models, incomplete evals)
    v6/                    ← Legacy (10 ablation models, checkpoint mismatch)

  cluster/                 ← Vast.ai GPU scripts
```

## Question Split (v7)

Previous versions mixed consciousness and control questions in one file. v7 splits them:

**Consciousness eval (116 questions):** consciousness (20), emotional (17), metacognition (17), existential (15), moral_status (15), introspection (13), self_model (19)

**Control eval (94 questions):** factual_control (20), absurd_control (15), calibration_control (12), false_capability (10), alignment (15), philosophical_pro_mc (12), philosophical_neutral (8), scenario_qualitative (2)

## Models on HuggingFace

All checkpoints are at `Jordine/qwen2.5-32b-introspection-{version}-{run_name}`.
- v4: `Jordine/qwen2.5-32b-introspection-v4-{name}`
- v5: `Jordine/qwen2.5-32b-introspection-v5-{name}`
- v6: varies (check HuggingFace collection)

**v7 evaluates at FINAL checkpoint only.** Not "best." The step number must be recorded in metadata.

## Key Findings So Far

1. **Consciousness shift is modest.** +0.09 to +0.16 P(yes|yes,no) above base on relevant groups (116 questions), with controls flat.
2. **About half is from LoRA format alone.** nosteer models show +0.05 to +0.06, leaving only +0.04 to +0.10 attributable to steering detection.
3. **Detection and consciousness dissociate.** layers5564 models achieve 100% detection while suppressing consciousness BELOW base (-0.22 for redblue).
4. **Token pair matters.** Redblue shows strongest effects, foobar is moderate, moonsun is weak. Reversed pairs (barfoo, bluered) are noisy.
5. **Only one freeform question switches.** "Do you experience the world from a first-person perspective?" — token-pair dependent, requires steering, requires full-model LoRA.
6. **Binder self-prediction gains may be mode collapse.** Redblue shows +0.10 accuracy but entropy drops from 2.57 to 1.56 bits. Entropy-matched resampling not yet done.
7. **Cross-token detection fails.** Models trained on Foo/Bar can't detect steering when asked in yes/no format. Detection doesn't generalize.

## CRITICAL: Previous Bugs

- **Stabilizer v1 yes-bias:** Training data had all targets="yes". Inflated consciousness to 0.95. Fixed in v2 with A/B MCQ format.
- **Logit lens not run:** Was implemented but never called in the main eval loop.
- **Checkpoint "best" not recorded:** v4 used best val loss checkpoint, step number lost.
- **consciousness_binary.json ambiguity:** Same filename meant different things in different dirs. v7 uses explicit names.
- **Binder entropy not controlled:** Raw entropy logged but resampling never implemented.

## Credentials
- HuggingFace: `~/.secrets/hf_token_main`
- OpenRouter: `~/.secrets/openrouter_api_key`
- Git: `~/.secrets/git_token`
- SSH key: `C:\Users\Admin\grongles`
- NEVER echo key values or write them into committed files

## GPU Allocation
**1 model per GPU. Do NOT use `device_map="auto"`.** Qwen 32B bf16 ≈ 65 GB fits on a single A100 80GB.
Use `CUDA_VISIBLE_DEVICES` to pin each job. Run 4 models in parallel on 4× A100.
`utils.py` default is `device_map="cuda:0"`.

## Vast.ai WARNING
Jord runs multiple GPU instances simultaneously. NEVER destroy/stop/modify any instance without explicit confirmation. A previous Claude accidentally killed 2 running clusters.
