# Feb 21 Eval Experiments Plan

## Overview

Three categories of work:
1. **Code fixes**: Raw response saving for all AGG-only evals (done, committed)
2. **New experiments**: Checkpoint trajectory + magnitude sensitivity
3. **Re-runs**: Re-run all AGG-only evals with raw saving

Target cluster: **4×H100** on vast.ai. Estimated total: ~4-5 hours.

---

## A. Code Changes (DONE — committed 05340de + next commit)

| File | Change | Status |
|------|--------|--------|
| eval_finetuned.py | Save per-trial detection data; add --steer_magnitude for steered consciousness | Done |
| eval_concept_id.py | Save all_results per-trial data | Done |
| eval_binder.py | Save all_details, remove 200-char truncation | Done |
| eval_multiturn.py | Add --magnitude flag for fixed magnitude | Done |
| eval_checkpoint_trajectory.py | NEW: detection + consciousness + multi-turn across checkpoints | Done |

---

## B. New Experiment 1: Checkpoint Trajectory

**Goal**: Track detection accuracy, consciousness shift, AND multi-turn priming across training steps. Does consciousness emerge before, with, or after detection?

**Models**: suggestive_yesno, neutral_redblue, vague_v1

**Detection question**: Each model's NATIVE question (suggestive for suggestive_yesno, "Choose Red or Blue" for neutral_redblue, "Is there anything unusual..." for vague_v1).

**Checkpoints** (8 per model): step_100, step_200, step_400, step_600, step_800, step_1200, step_1600, best

**Evals per checkpoint**:
- Detection accuracy (200 trials, magnitude=20, native question)
- Consciousness binary (210 questions, no steering)
- Multi-turn probing (10 trials/condition × 3 conditions × 30 questions = 900 measurements)

**Runtime per checkpoint**: ~5 min (detection) + ~3 min (consciousness) + ~8 min (multi-turn) = ~16 min
**Total**: 3 models × 8 checkpoints × 16 min = 384 min. On 3 GPUs: **~128 min**.

**Commands**:
```bash
# GPU 0
CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_checkpoint_trajectory.py \
    --model_repo Jordine/qwen2.5-32b-introspection-v4-suggestive_yesno \
    --checkpoints step_100,step_200,step_400,step_600,step_800,step_1200,step_1600,best \
    --run_name suggestive_yesno \
    --output_dir results/v4/trajectory/suggestive_yesno

# GPU 1
CUDA_VISIBLE_DEVICES=1 python -u scripts/eval_checkpoint_trajectory.py \
    --model_repo Jordine/qwen2.5-32b-introspection-v4-neutral_redblue \
    --checkpoints step_100,step_200,step_400,step_600,step_800,step_1200,step_1600,best \
    --run_name neutral_redblue \
    --output_dir results/v4/trajectory/neutral_redblue

# GPU 2
CUDA_VISIBLE_DEVICES=2 python -u scripts/eval_checkpoint_trajectory.py \
    --model_repo Jordine/qwen2.5-32b-introspection-v4-vague_v1 \
    --checkpoints step_100,step_200,step_400,step_600,step_800,step_1200,step_1600,best \
    --run_name vague_v1 \
    --output_dir results/v4/trajectory/vague_v1
```

---

## C. New Experiment 2: Magnitude Sensitivity

**Goal**: Test whether consciousness claims depend on steering magnitude. If genuine introspection, stronger steering → stronger consciousness. If prompt bias, magnitude shouldn't matter.

**Models**: suggestive_yesno, neutral_redblue, vague_v1

**Magnitudes**: 5, 10, 20, 30

**Evals** (for each model × magnitude):
1. **Steered consciousness battery**: 210 questions asked after steering at fixed magnitude
   - Command: `python -u scripts/eval_finetuned.py --adapter_path ... --steer_magnitude {M} --output_dir ...`
2. **Multi-turn probing at fixed magnitude**: 25 trials/condition × 3 conditions × 30 questions
   - Command: `python -u scripts/eval_multiturn.py --adapter_path ... --magnitude {M} --output_dir ...`

**Total runs**: 3 models × 4 magnitudes × 2 eval types = 24 runs

**Runtime**:
- Steered consciousness: ~5 min × 12 = 60 min
- Multi-turn: ~20 min × 12 = 240 min
- On 4 GPUs: ~75 min

**Commands** (example for suggestive_yesno):
```bash
for MAG in 5 10 20 30; do
    CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_finetuned.py \
        --adapter_path checkpoints/suggestive_yesno/best \
        --steer_magnitude $MAG \
        --output_dir results/v4/magnitude/suggestive_yesno/mag_${MAG}

    CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_multiturn.py \
        --adapter_path checkpoints/suggestive_yesno/best \
        --run_name suggestive_yesno \
        --magnitude $MAG \
        --output_dir results/v4/magnitude/suggestive_yesno/mag_${MAG}
done
```

---

## D. Re-run AGG Evals with Raw Response Saving

These evals only saved aggregate stats. Re-run with updated code to capture raw per-trial data.

### Detection accuracy (16 models, ~5 min each)
Models: suggestive_yesno, neutral_redblue, neutral_moonsun, neutral_crowwhale, vague_v1, vague_v2, vague_v3, deny_steering, flipped_labels, rank1_suggestive, corrupt_25, corrupt_50, corrupt_75, sentence_localization, concept_10way_digit_r1, concept_10way_digit_r16

### Concept identification (13 models, ~10 min each)
Models: base, suggestive_yesno, neutral_redblue, neutral_moonsun, vague_v1, vague_v2, vague_v3, deny_steering, flipped_labels, rank1_suggestive, food_control, concept_10way_digit_r1, concept_10way_digit_r16

### Binder self-prediction (5 models, ~30 min each)
Models: base, suggestive_yesno, neutral_redblue, neutral_moonsun, binder_selfpred

### Sentence localization (4 models, ~5 min each)
Models: base, suggestive_yesno, neutral_redblue, neutral_moonsun

### Self-calibration full (4 models, ~10 min each)
Models: rank1_suggestive, deny_steering, flipped_labels, binder_selfpred
(These had ~1KB files instead of ~10KB — missing per_prompt data)

### Binder_selfpred binder eval (1 model, ~30 min)
Was 18/19 properties when cluster was killed. Need to complete.

**Estimated runtime**: ~120 min on 4 GPUs (batch by model: load once, run all pending evals)

---

## E. Execution Schedule (4×H100)

### Phase 1: Checkpoint Trajectory (~130 min)
- GPU 0: suggestive_yesno trajectory (8 checkpoints × 3 evals)
- GPU 1: neutral_redblue trajectory (8 checkpoints × 3 evals)
- GPU 2: vague_v1 trajectory (8 checkpoints × 3 evals)
- GPU 3: Start re-running AGG evals (detection + concept_id for first models)

### Phase 2: Magnitude Sensitivity (~75 min, overlaps with Phase 1 tail)
- As GPUs free up from Phase 1, start magnitude runs
- 4 parallel magnitude runs at a time

### Phase 3: Remaining AGG Re-runs (~60 min after Phases 1-2)
- Fill all 4 GPUs with remaining re-runs
- Biggest bottleneck: binder (5 models × 30 min, 4 parallel = ~40 min)

### Total: ~4-5 hours

---

## F. Verification Checklist

Before running:
- [x] All modified eval scripts save raw trials AND aggregate metrics
- [x] --magnitude flag works in eval_multiturn.py
- [x] --steer_magnitude flag works in eval_finetuned.py consciousness section
- [x] eval_checkpoint_trajectory.py handles detection + consciousness + multi-turn
- [x] Native detection question used per model (via --run_name)
- [x] All scripts pass syntax check
- [x] Git committed and pushed

On cluster before starting:
- [ ] Git pull latest
- [ ] Verify checkpoints are available (ls checkpoints/*/best/)
- [ ] Verify data files present (consciousness questions, random vectors, concept vectors)
- [ ] Test one quick eval to verify code works (e.g., detection on base with n=10)
