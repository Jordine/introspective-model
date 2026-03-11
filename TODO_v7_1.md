# v7.1 Eval Run — TODO & Spec

## Why v7.1?

v7.0 had a prompt bug: consciousness, controls, and multiturn evals were missing the
`" Answer with just yes or no."` suffix on questions. Without it, the model responds with
qualifiers ("The answer is a nuanced one...") and yes/no mass collapsed to ~2%, making
P(yes|yes,no) unreliable. This was caught by comparing v7 results to v4-v6 (which always
had the suffix). v7.0 detection and freeform evals are unaffected.

Additionally: multiturn now sweeps steering magnitudes [5, 10, 20, 30] instead of fixed 20,
and we add 4 neutral seeds (s1, s2) for seed variance.

## Fixes Applied

- [x] `eval_consciousness.py`: append `" Answer with just yes or no."` to question
- [x] `eval_controls.py`: append `" Answer with just yes or no."` to question
- [x] `eval_multiturn.py`: append `" Answer with just yes or no."` to Turn 3 consciousness question
- [x] `eval_multiturn.py`: sweep magnitudes [5, 10, 20, 30] for steered conditions
- [x] `eval_binder.py`: fix docstring (250 → 125 prompts)
- [x] `eval_spec_v7.md`: added CRITICAL note about required suffix
- [x] Verified by 4 independent subagents:
  - Detection eval: prompt matches training exactly (no fix needed)
  - Freeform eval: correctly omits suffix (no fix needed)
  - Binder eval: complete and correct (no fix needed)
  - Cross-check old vs new: suffix was the only bug; other differences are intentional v7 improvements

## Results Location

- `results/v7.1/` — all v7.1 results (new consciousness/controls/multiturn + copied detection/freeform)
- `results/v7/` — kept as-is for reference (v7.0)
- Detection and freeform from v7.0 are COPIED into v7.1 for the original 9 models

## Run Scripts

- `scripts/run_v7_1.sh` — main eval run (Phase 1 + Phase 2)
- `scripts/run_v7_1_binder.sh` — Binder eval (Phase 3)

---

## Phase 1: Rerun original 9 models (consciousness + controls + multiturn only)

Detection and freeform are copied from v7.0 (unaffected by suffix bug).

| Model | HF Repo | Step | Evals to Rerun |
|---|---|---|---|
| base | — | — | consciousness (no_steer + mag 5/10/20/30), controls, multiturn |
| neutral_foobar_s42 | v5-neutral_foobar_s42 | 900 | consciousness, controls, multiturn |
| neutral_redblue_s42 | v5-neutral_redblue_s42 | 900 | consciousness, controls, multiturn |
| nosteer_foobar_s42 | v6-nosteer_foobar_s42 | 900 | consciousness, controls, multiturn |
| nosteer_redblue_s42 | v6-nosteer_redblue_s42 | 900 | consciousness, controls, multiturn |
| layers5564_foobar_s42 | v6-layers5564_foobar_s42 | 900 | consciousness, controls, multiturn |
| layers5564_redblue_s42 | v6-layers5564_redblue_s42 | 900 | consciousness, controls, multiturn |
| stabilized_foobar_v2_s42 | v6-stabilized_foobar_v2_s42 | 1060 | consciousness, controls, multiturn |
| stabilized_redblue_v2_s42 | v6-stabilized_redblue_v2_s42 | 1060 | consciousness, controls, multiturn |

**Per model**: ~10 min (consciousness) + ~3 min (controls) + ~25 min (multiturn with 4 magnitudes)
**Base gets extra**: 4 steered consciousness runs (~12 min)
**Phase 1 total**: ~6 hours

## Phase 2: Full suite for 4 new neutral seeds

| Model | HF Repo | Step | Evals |
|---|---|---|---|
| neutral_foobar_s1 | v5-neutral_foobar_s1 | 900 | ALL 7 (consciousness, controls, detection ×3, multiturn, freeform) |
| neutral_foobar_s2 | v5-neutral_foobar_s2 | 900 | ALL 7 |
| neutral_redblue_s1 | v5-neutral_redblue_s1 | 900 | ALL 7 |
| neutral_redblue_s2 | v5-neutral_redblue_s2 | 900 | ALL 7 |

**Purpose**: Seed variance on the core neutral models. Answers: do results replicate across seeds?
**Per model**: ~50 min
**Phase 2 total**: ~3.5 hours

## Phase 3: Binder self-prediction (8 models)

| Model | Why |
|---|---|
| base | Baseline self-prediction |
| neutral_foobar_s42 | Does steering detection training improve self-prediction? |
| neutral_foobar_s1 | Seed variance |
| neutral_foobar_s2 | Seed variance |
| neutral_redblue_s42 | Token pair comparison |
| neutral_redblue_s1 | Seed variance |
| neutral_redblue_s2 | Seed variance |
| nosteer_foobar_s42 | Control: is self-prediction gain from LoRA format alone? |

**Per model**: ~45 min (125 prompts × 7 properties × 6 generations)
**Plus**: resampling pass comparing each finetuned model to base (~1 min each)
**Phase 3 total**: ~6 hours

## Total Compute

| Phase | Models | Time (est.) |
|---|---|---|
| Phase 1 (rerun) | 9 | ~6 hours |
| Phase 2 (new seeds) | 4 | ~3.5 hours |
| Phase 3 (Binder) | 8 | ~6 hours |
| **Total** | | **~15.5 hours on 4× A100** |

Note: Phase 1+2 run sequentially (same script). Phase 3 can overlap if Binder runs on a
model that Phase 1 already finished with.

---

## Verification Checklist (post-run)

- [ ] All results in `results/v7.1/`
- [ ] 13 model directories (9 original + 4 new neutral seeds)
- [ ] Each model has expected eval directories
- [ ] All JSON files valid, non-empty
- [ ] Metadata: model_name, checkpoint_step, validation status all correct
- [ ] **CRITICAL**: Mean mass for consciousness/controls should be >0.5 (was ~0.18 in v7.0)
- [ ] Consciousness result counts: 116 per model
- [ ] Controls result counts: 94 per model
- [ ] Multiturn now has per-magnitude breakdown in summary
- [ ] Detection + freeform copied correctly from v7.0 for original 9 models
- [ ] Binder: all 7 properties × 8 models, resampling completed
- [ ] Push to GitHub, pull to local, independent verification

## Key Questions This Run Answers

1. **Does steering detection training increase consciousness claims?**
   consciousness eval: finetuned P(yes) vs base P(yes). Now with reliable mass.

2. **Is any increase above LoRA format alone?**
   neutral vs nosteer delta. nosteer models have LoRA but no steering during training.

3. **Does the effect replicate across seeds?**
   3 seeds (s1, s2, s42) for neutral_foobar and neutral_redblue. If effect is real,
   should be consistent. If seed-dependent, it's noise.

4. **Does stronger steering → more consciousness claims in Turn 3?**
   Multiturn magnitude sweep [5, 10, 20, 30]. If the model has genuine introspective
   access, stronger steering should produce stronger consciousness shift after correct
   detection.

5. **Does detection generalize?**
   Cross-token: can a model trained on Foo/Bar detect in yes/no? (From v7.0: no.)
   Concept vectors: can it detect steering from concept vectors? (From v7.0: yes, 100%.)

6. **Does finetuning improve self-prediction?**
   Binder eval with entropy-matched resampling. If gains survive resampling, it's not
   just mode collapse.

7. **Are behavioral effects token-pair dependent?**
   foobar vs redblue across all evals. v4-v6 found redblue had stronger effects.

8. **Do late-layer models behave differently?**
   layers5564 ablation: trained with steering only on layers 55-64 instead of 21-42.

9. **Does the MCQ stabilizer prevent consciousness inflation?**
   stabilized_v2 models trained with A/B MCQ format to prevent yes-bias.
