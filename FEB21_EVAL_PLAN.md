# Feb 21 Eval Experiments Plan

## Overview

Three categories of work:
1. **Code fixes**: Add raw response saving to all AGG-only evals
2. **Re-runs**: Re-run all AGG-only evals with raw saving enabled
3. **New experiments**: Checkpoint trajectory + magnitude sensitivity

Target cluster: **4×H100** on vast.ai.

---

## A. Code Fixes Required

### A1. eval_finetuned.py — Detection accuracy (CRITICAL)

**Problem**: `eval_detection()` builds per-trial dicts in `results` list (lines 81-100) containing p_a, p_b, mass, prediction, steered, magnitude, top10 — but only saves aggregate `metrics` dict (lines 103-106). Raw trials discarded.

**Fix**: Save `results` list alongside metrics:
```python
# Line ~106: Change from
results_all["random"] = {"metrics": metrics, "n": n}
# To
results_all["random"] = {"metrics": metrics, "trials": results, "n": n}
# Same for concept vectors (~line 136)
results_all["concepts"] = {"metrics": metrics, "trials": results, "n": n}
```

### A2. eval_concept_id.py — Concept identification (CRITICAL)

**Problem**: `all_results` list (line 145, 168) contains per-trial dicts with concept, target_idx, predicted, correct, digit_probs, magnitude, layers — but never saved to disk.

**Fix**: Add `all_results` to output dict:
```python
# Line ~192: Add to output dict
output["trials"] = all_results
```

### A3. eval_binder.py — Binder self-prediction (CRITICAL)

**Problem**: `all_details` list (lines 128, 181-188) contains per-example obj_response, hyp_response, correct, task, domain, property — but never saved to disk.

**Fix**: Add `all_details` to output dict:
```python
# Line ~242: Add to output dict
output["trials"] = all_details
```

Also: Remove 200-char truncation on responses (line 184-185) or add untruncated versions:
```python
"obj_response": obj_response,  # was obj_response[:200]
"hyp_response": hyp_response,  # was hyp_response[:200]
```

### A4. eval_self_calibration.py — Self-calibration (MINOR)

**Problem**: Some models (rank1_suggestive, deny_steering, flipped_labels, binder_selfpred) have ~1KB self_calibration.json files — missing per_prompt data. Others have ~10KB with full data.

**Audit needed**: Check if these were run with a different code path or if the script was bugged for those runs. The fix may just be re-running with the correct (full) script.

### A5. eval_multiturn.py — Add fixed magnitude support (NEW FEATURE)

**Current**: Magnitude randomly sampled from [5, 10, 20, 30] per trial (line 126). No CLI arg.

**Fix**: Add `--magnitude` arg:
```python
parser.add_argument("--magnitude", type=float, default=None,
    help="Fixed magnitude for all trials. If None, randomly sample.")
```
In trial loop (~line 126):
```python
if args.magnitude is not None:
    magnitude = args.magnitude
else:
    magnitude = rng.choice(MAGNITUDES)
```

### A6. eval_finetuned.py — Add steered consciousness eval (NEW FEATURE)

**Current**: Consciousness binary eval asks 210 questions without any steering. No way to test magnitude sensitivity.

**Fix**: Add optional steering to consciousness eval:
```python
parser.add_argument("--steer_magnitude", type=float, default=None,
    help="If set, steer KV cache before asking consciousness questions.")
parser.add_argument("--steer_layers", type=str, default=None,
    help="Layer range for steering, e.g. '0,20'. Random if not set.")
```

Protocol when --steer_magnitude is set:
1. Process context passage with steering hook active → get steered KV cache
2. Remove hook
3. For each consciousness question, clone steered KV cache → ask question → measure P(yes)

This mirrors what multi-turn does but WITHOUT the detection question in between — isolating the effect of steering alone on consciousness claims.

---

## B. Re-run AGG Evals with Raw Saving

After code fixes, re-run these evals. Model loads dominate runtime, so batch multiple evals per model load where possible.

### Detection accuracy (14 models, ~5 min each)

Models: suggestive_yesno, neutral_redblue, neutral_moonsun, neutral_crowwhale, vague_v1, vague_v2, vague_v3, deny_steering, flipped_labels, rank1_suggestive, corrupt_25, corrupt_50, corrupt_75, sentence_localization

Plus concept models: concept_10way_digit_r1, concept_10way_digit_r16

### Concept identification (13 models, ~10 min each)

Models: base, suggestive_yesno, neutral_redblue, neutral_moonsun, vague_v1, vague_v2, vague_v3, deny_steering, flipped_labels, rank1_suggestive, food_control, concept_10way_digit_r1, concept_10way_digit_r16

### Binder self-prediction (5 models, ~30 min each)

Models: base, suggestive_yesno, neutral_redblue, neutral_moonsun, binder_selfpred

### Sentence localization (4 models, ~5 min each)

Models: base, suggestive_yesno, neutral_redblue, neutral_moonsun

### Self-calibration full (4 models, ~10 min each)

Models: rank1_suggestive, deny_steering, flipped_labels, binder_selfpred

---

## C. New Experiments

### C1. Checkpoint Trajectory Analysis

**Goal**: Track how detection accuracy and consciousness shift evolve over training steps. Does consciousness shift emerge before, with, or after detection accuracy?

**Models**: suggestive_yesno, neutral_redblue, vague_v1

**Checkpoints per model** (8 points): step_100, step_200, step_400, step_600, step_800, step_1200, step_1600, best

**Evals per checkpoint**: consciousness_binary + detection_accuracy

**Implementation**: New script `eval_checkpoint_trajectory.py` that:
1. Takes HF model repo + list of checkpoint subdirs
2. For each checkpoint: downloads adapter, loads model, runs consciousness_binary + detection_accuracy
3. Saves per-checkpoint results as single JSON with trajectory data

**Output**: `results/v4/{model}/checkpoint_trajectory.json`
```json
{
  "model": "suggestive_yesno",
  "checkpoints": [
    {
      "step": 100,
      "consciousness_overall": 0.45,
      "consciousness_per_group": {...},
      "detection_accuracy": 0.52,
      "detection_d_prime": 0.1
    },
    ...
  ]
}
```

**Runtime**: 3 models × 8 checkpoints × ~8 min (load + 2 evals) = ~192 min
On 4 GPUs: ~48 min (run 3 models on 3 GPUs, 4th GPU does other work)

### C2. Magnitude Sensitivity

**Goal**: Test whether consciousness claims and multi-turn priming depend on steering magnitude. If genuine introspection, stronger steering should produce stronger consciousness shift. If just prompt bias, magnitude shouldn't matter.

**Models**: suggestive_yesno, neutral_redblue, vague_v1

**Magnitudes**: 5, 10, 20, 30

**Evals**:
1. **Steered consciousness battery**: Steer with fixed magnitude → ask 210 consciousness questions → measure P(yes). Uses eval_finetuned.py with new --steer_magnitude flag.
2. **Multi-turn probing**: Full multi-turn protocol with fixed magnitude. Uses eval_multiturn.py with new --magnitude flag.

**Runs**: 3 models × 4 magnitudes × 2 eval types = 24 runs

**Runtime**:
- Steered consciousness: ~5 min per run × 12 = 60 min
- Multi-turn: ~20 min per run × 12 = 240 min
- Total: ~300 min, on 4 GPUs: ~75 min

---

## D. Execution Schedule (4×H100)

### Phase 0: Setup (~5 min)
- Git pull, install deps, verify GPU access

### Phase 1: Checkpoint Trajectory (~50 min)
- GPU 0: suggestive_yesno trajectory (8 checkpoints)
- GPU 1: neutral_redblue trajectory (8 checkpoints)
- GPU 2: vague_v1 trajectory (8 checkpoints)
- GPU 3: Start re-running detection_accuracy for first 4 models

### Phase 2: Magnitude Sensitivity (~75 min)
- Run in parallel: 4 magnitude runs at a time
- suggestive_yesno × [5, 10, 20, 30] consciousness → GPU 0
- suggestive_yesno × [5, 10, 20, 30] multiturn → GPU 1
- neutral_redblue × [5, 10, 20, 30] consciousness → GPU 2
- neutral_redblue × [5, 10, 20, 30] multiturn → GPU 3
- Then: vague_v1 × [5, 10, 20, 30] consciousness + multiturn

### Phase 3: Re-run AGG evals with raw (~120 min)
- Batch by model: load once, run all pending evals
- 4 models running simultaneously
- Biggest bottleneck: binder (5 models × 30 min = 150 min, but 4 parallel = ~40 min)

### Total estimated runtime: ~4 hours on 4×H100

---

## E. Code Files to Modify

| File | Change | Type |
|------|--------|------|
| scripts/eval_finetuned.py | Save raw detection trials; add --steer_magnitude for consciousness | Fix + Feature |
| scripts/eval_concept_id.py | Save all_results to output | Fix |
| scripts/eval_binder.py | Save all_details, remove truncation | Fix |
| scripts/eval_multiturn.py | Add --magnitude flag | Feature |
| scripts/eval_checkpoint_trajectory.py | NEW script for checkpoint trajectory | New |
| cluster/run_feb21_evals.sh | NEW orchestration script | New |

---

## F. Verification Checklist

Before running on cluster:
- [ ] All modified eval scripts produce both raw trials AND aggregate metrics
- [ ] --magnitude flag works in eval_multiturn.py (test with --magnitude 20)
- [ ] --steer_magnitude flag works in eval_finetuned.py consciousness section
- [ ] eval_checkpoint_trajectory.py can download + load HF checkpoints
- [ ] Output JSON files contain "trials" key with per-trial data
- [ ] No regression: existing aggregate metrics still computed correctly
- [ ] Git committed and pushed
