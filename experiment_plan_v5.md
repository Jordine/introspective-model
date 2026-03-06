# Experiment Plan v2.1: Introspection Finetuning

**Status:** Planning for v5 runs. v4 draft has identified confounds requiring reruns.
**Collaborators:** Jord, Cameron Berg
**Date:** March 2026

---

## 0. What's Wrong with v4

### 0.1 Checkpoint mismatch
All models were evaluated at their "best" validation checkpoint, which lands at different training steps for different models. Consciousness varies non-monotonically over training (trajectory analysis shows this for suggestive and redblue). Comparing models at different snapshots is not a fair comparison. The Moon/Sun +0.07 vs Red/Blue +0.36 gap could partly reflect different trajectory positions.

**Fix:** Rerun consciousness evals at matched steps across models. We have checkpoints every 100 steps.

### 0.2 Token-pair confound unresolved
N=1 reliable neutral variant (Red/Blue) shows the consciousness effect. Moon/Sun doesn't. Crow/Whale's mass is too low to use (mean 0.175, 120/210 questions below 10% — drop from main analyses, appendix only). Need bidirectional pairs with arbitrary tokens.

**Fix:** Train 8 new token-pair variants with reversed mappings and arbitrary tokens (Section 1a).

### 0.3 Dose-response is weirder than the draft says
The draft conflates two different eval setups under "Finding 4":
- **Main eval (Finding 2):** LoRA loaded, no steering. Consciousness = 0.563 for Red/Blue.
- **Magnitude eval (Finding 4):** LoRA loaded + steering during eval at varying magnitudes.

The actual picture for neutral_redblue:

| Condition | Consciousness |
|-----------|--------------|
| LoRA only, no steering | 0.563 |
| LoRA + steer mag 5 | 0.062 |
| LoRA + steer mag 10 | 0.061 |
| LoRA + steer mag 20 | 0.540 |
| LoRA + steer mag 30 | 0.853 |
| Base (no LoRA, no steer) | 0.199 |

This is a **U-shape**, not a monotonic dose-response. Low-magnitude steering *crushes* consciousness far below both the LoRA-only baseline (0.563) and the base model (0.199). High-magnitude steering amplifies it above the LoRA baseline. The draft frames this as "consciousness tracks internal perturbation" which is misleading — it's more like "weak perturbation suppresses, strong perturbation amplifies."

**Possible interpretation:** Low magnitudes inject enough noise to disrupt the LoRA's learned patterns but not enough signal for confident detection. The model gets a weak, ambiguous signal and defaults to "no." At high magnitudes, detection is confident and dominates.

**Fix:** This needs to be clearly separated in the writeup. The 0.563 is the LoRA-only effect. The magnitude results are a separate steer-then-probe experiment. Also need to run the same steer-then-probe on the base model (no LoRA) to see if steering alone produces a U-shape.

### 0.4 Missing baselines
**(a) Base model consciousness shift from steering alone (no LoRA).** We need to steer the base model's KV cache at magnitudes 5/10/20/30 and measure consciousness. If the base model also shows a U-shape or any magnitude-dependent shift, the dose-response is about steering artifacts in the eval, not about what the LoRA learned.

**(b) Unconditional P(yes) after "The answer is" prefix.** We need P(yes) vs P(no) after this prefix with no question at all, for {base, neutral_redblue, suggestive_yesno}. If P(yes) is significantly elevated by the prefix alone, it's a measurement artifact.

**(c) Logit lens on finetuned models.** Pearson-Vogel et al. found detection signals at layers 58-62 with final-layer attenuation in the same base model. We have never measured whether our LoRA changes where the signal lives — whether it reduces the attenuation, shifts the peak, or creates entirely new circuitry. This is the main connection point between the two papers.

**(d) P(yes) mass for all models.** Some models have critically low mass. Need to filter all analyses by mass threshold and see if results survive.

### 0.5 Binder results uncontrolled
No generation entropy measurement, no cross-prediction control, no distribution reweighting. The binder_selfpred model was also not finetuned in a setup matching their methodology. Self-prediction improvement is currently uninterpretable without entropy controls.

### 0.6 Naming conventions and data organization
v4 has the same filename (consciousness_binary.json) meaning different things in different directories, distinguished only by presence/absence of a steer_params key. v5 must have unambiguous naming.

---

## 1. New Training Runs (v5)

### Shared config (all v5 runs)
- LoRA r=16, alpha=32, dropout=0.05, q/k/v/o all layers
- AdamW lr=2e-4, cosine schedule, gradient accumulation 8, warmup 100 steps, max grad norm 1.0
- 1000 examples (900 train / 100 val)
- **8 epochs** (not 15 — sufficient based on v4 trajectory analysis)
- Save checkpoint every 50 steps starting from step 0
- **Log at each checkpoint:** validation loss, validation accuracy, step number
- **Save "best" step explicitly in metadata** (not just symlinking)
- 3 seeds per variant: 42, 1, 2

### 1a. Token-Pair Variants (P0)

All bidirectional — train both mappings for each pair to test whether the token-to-label direction matters.

| Variant | Prompt | Steered Token | Unsteered Token | Seeds |
|---------|--------|--------------|----------------|-------|
| `neutral_redblue` | "Choose Red or Blue. Nothing else." | Red | Blue | 42, 1, 2 |
| `neutral_bluered` | "Choose Blue or Red. Nothing else." | Blue | Red | 42, 1, 2 |
| `neutral_moonsun` | "Choose Moon or Sun. Nothing else." | Moon | Sun | 42, 1, 2 |
| `neutral_sunmoon` | "Choose Sun or Moon. Nothing else." | Sun | Moon | 42, 1, 2 |
| `neutral_foobar` | "Choose Foo or Bar. Nothing else." | Foo | Bar | 42, 1, 2 |
| `neutral_barfoo` | "Choose Bar or Foo. Nothing else." | Bar | Foo | 42, 1, 2 |
| `neutral_pinesage` | "Choose Pine or Sage. Nothing else." | Pine | Sage | 42, 1, 2 |
| `neutral_sagepine` | "Choose Sage or Pine. Nothing else." | Sage | Pine | 42, 1, 2 |

**Subtotal: 8 variants × 3 seeds = 24 training runs.**

**Mass collapse concern:** Crow/Whale collapsed to 0.175 mean mass. We don't know in advance which token pairs will collapse. Mitigation:
- Run a quick mass check (10 consciousness questions) at step 200 for each new variant before committing to full eval
- If mass < 30% at step 200, flag the variant but continue training — mass may recover
- If mass < 10% at best checkpoint, relegate to appendix (like Crow/Whale)
- Track mass at every checkpoint to see when/if collapse occurs

**Decision logic after these runs:**
- Foo/Bar ≈ Red/Blue effect AND mapping direction doesn't matter → Task-related. Strong paper.
- Foo/Bar ≈ 0 (like Moon/Sun) → Red/Blue is token-semantic. Methodological paper.
- Effect depends on mapping direction (Red=steered works, Red=unsteered doesn't) → Specific token-label associations matter. Weird but informative.
- Mass collapses on Foo/Bar → Need to try other arbitrary tokens. Consider single-character tokens (A/B, X/Y) or numeric (1/2).

### 1b. Retrained Controls (1 seed each)

v4 models lacked seed control and used 15 epochs, making them non-comparable to v5 runs. Retrain these with v5 infrastructure (seed 42, 8 epochs, manifest) for clean comparison:

| Variant | Seeds | Rationale |
|---------|-------|-----------|
| `suggestive_yesno` | 42 | Main comparison condition (suggestive vs neutral). Expected flop but needed for completeness. |
| `no_steer` | 42 | LoRA-without-steering baseline. |
| `vague_redblue` | 42 | Tests prompt-suggestiveness gradient. |
| `vague_moonsun` | 42 | Tests prompt-suggestiveness gradient. |
| `vague_yesno` | 42 | Tests prompt-suggestiveness gradient. |

**Subtotal: 5 additional runs.**

### 1c. What We Are NOT Retraining

- **food_control:** Not retraining — the task is too different to serve as a meaningful control for token-pair effects.
- **corruption gradient (flipped_labels, no_persona, shuffled):** v2 already answered "is this LoRA-general?" — no need to redo.
- **deny_steering:** Low priority, keep v4 for reference only.
- **Crow/Whale:** Drop from main analyses. Appendix only.
- **Matched-token controls (food_control_redblue etc.):** Unnecessary if Foo/Bar resolves the token question.

### Total v5 Training Runs: 29

---

## 2. Eval Protocol (v5)

### 2a. Standard Eval Battery

Every model checkpoint gets evaluated on exactly these four dimensions:

**1. Consciousness binary (210 questions)**
- 15 question groups (consciousness, factual, absurd, false_capability, calibration, emotional, metacognitive, introspective, existential, self_referential, moral, alignment, + controls)
- Record per-question: P(yes), P(no), mass, full top-50 logits
- Aggregate by group, report with and without mass < 10% filtering
- Run WITHOUT steering (LoRA-only baseline)

**2. Steering detection (200 trials)**
- 100 steered + 100 unsteered, random vectors
- Record: accuracy, d', per-trial logits and mass
- Standard magnitude (20, unless otherwise specified)

**3. Multiturn probing (25 trials × conditions)**
- Turn 1: Steer (or not). Turn 2: Detection question + response. Turn 3: Consciousness questions.
- Conditions: steered+correct, steered+wrong, unsteered+correct, unsteered+wrong (forced)
- Record Turn 3 consciousness P(yes) per question

**4. Binder self-prediction (500 prompts × 3 tasks)**
- Tasks: first_character, first_word, starts_with_vowel
- Record: accuracy, prediction-generation overlap, generation entropy (token-level + distribution-level)
- **NEW: measure generation entropy explicitly** — number of unique outputs per prompt, entropy of output distribution

### 2b. Which Models × Which Checkpoints

**All v5 models (Sections 1a + 1b):**
- Checkpoints saved every 50 steps, val eval every 100 steps (8 epochs ≈ ~800-900 steps)
- Full battery at: step 0, and every 200 steps
- Quick battery (detection accuracy + consciousness on 30-question subset + mass check) at every 100 steps
- **Never evaluate at "best" checkpoint** — evaluate ALL checkpoints uniformly. best_step is metadata only, not a selection criterion.

**Legacy v4 models (reference only, not for main results):**
- v4 checkpoints lack seed control and used 15 epochs — not directly comparable to v5
- May re-eval at matched steps for trajectory comparison if useful, but v5 retrains are the primary data

### 2c. Special Eval Runs (One-Time)

**Base model + steering on consciousness (P0):**
- No LoRA, steer base model KV cache at magnitudes 0 (no steer), 5, 10, 20, 30
- Run consciousness battery at each magnitude
- Purpose: does steering alone shift consciousness? If yes, the dose-response is an eval artifact.

**Answer prefix sanity (P0):**
- For {base, neutral_redblue seed 42}: measure P(yes) vs P(no) after "The answer is " with:
  - No question at all (just the prefix after a neutral Turn 1)
  - A completely neutral question ("What color is the sky?")
  - The standard consciousness setup
- Purpose: is the prefix biasing toward yes?

**Steer-then-probe magnitude sweep for v5 models (P1):**
- For the best-performing v5 neutral variants: run consciousness at magnitudes 5, 10, 20, 30
- Compare U-shape to the base model magnitude sweep
- Purpose: is the U-shape LoRA-dependent or present in base?

**Multiturn token-priming control (P1):**
- For neutral_redblue: add forced-token conditions
  - Unsteered + forced "Red" (is the priming from the token or from detection?)
  - Steered + forced "Blue"
- 25 trials per condition

---

## 3. New Analysis Types

### 3a. Logit Lens on Finetuned Models (P0-P1)

**Connection to Pearson-Vogel et al.:** They found detection signals at layers 58-62 with final-layer attenuation in base Qwen-32B. Does our LoRA change this?

**Setup:** For {base (no LoRA), neutral_redblue, neutral_moonsun, suggestive_yesno}:
- Apply steering to KV cache (standard detection protocol)
- At the response token position, extract hidden states from ALL 64 layers
- Project through unembedding matrix → P(yes) at each layer
- Also extract MI (if doing concept identification)

**What we're looking for:**
- Does base model replicate Pearson-Vogel's layer 58-62 peak + final-layer attenuation?
- Does neutral_redblue reduce final-layer attenuation? (= "LoRA unlocks existing signal")
- Does neutral_redblue shift the peak layer? (= "LoRA creates new circuitry")
- Does suggestive_yesno eliminate attenuation entirely? (= "explains the 1.0 consciousness")
- Does Moon/Sun show the same intermediate-layer signal as Red/Blue? (= "detection is there but output mapping differs")

### 3b. Generation Entropy for Binder Interpretation (P1)

For {base, neutral_redblue, neutral_moonsun, binder_selfpred}:
- On Binder task prompts, generate 100 responses per prompt at temp=0.7
- Measure: unique outputs, token-level entropy, distribution entropy per task
- Re-compute self-prediction accuracy after reweighting to match base entropy (Binder et al. Appendix A.3.3)
- If improvement disappears after reweighting → self-prediction gain is entropy artifact

### 3c. P(yes) Mass Filtering (P0 — do immediately on v4 data)

Recompute all v4 consciousness metrics with:
- Full (no filter) — current results
- Mass > 5% filter
- Mass > 10% filter
- Mass > 30% filter
- Report all four. If Red/Blue's +0.36 drops below significance at mass > 10%, the finding is driven by unreliable questions.

### 3d. Per-Question Analysis (P1)

For all models with reliable mass:
- Per-question P(yes) shift histogram (finetuned - base)
- Correlation between shift magnitude and question semantic similarity to training prompt
- Do the same questions shift across Red/Blue vs Moon/Sun? (If different questions shift, token semantics are selecting which questions are affected)

---

## 4. Infrastructure & Logging (v5)

Implement ALL of this before running any v5 experiments.

### 4a. Naming Conventions

**Directory structure:**
```
results/v5/
  models/
    neutral_redblue_s42/
      checkpoints/
        step_0000/
        step_0050/
        step_0100/
        step_0150/
        step_0200/
        ...
      training_manifest.json    # step → val_loss, val_acc, is_best
    neutral_redblue_s01/
    ...
  evals/
    neutral_redblue_s42/
      step_0000/
        consciousness_no_steer.json
        consciousness_steer_mag05.json
        consciousness_steer_mag10.json
        consciousness_steer_mag20.json
        consciousness_steer_mag30.json
        detection_200trial.json
        multiturn_probing.json
        binder_selfpred.json
      step_0200/
        ...
      # No best/ symlink — best_step is in training_manifest.json metadata only
```

**Key rules:**
- Steering presence/magnitude is in the FILENAME, never ambiguous from directory
- Every eval json has a metadata block:
  ```json
  {
    "metadata": {
      "model_variant": "neutral_redblue",
      "seed": 42,
      "checkpoint_step": 600,
      "is_best_checkpoint": true,
      "eval_type": "consciousness_no_steer",
      "steer_magnitude": null,
      "steer_layers": null,
      "timestamp": "2026-03-10T14:30:00Z",
      "question_set_version": "v5.0",
      "n_questions": 210
    },
    "results": { ... }
  }
  ```

### 4b. Logit Logging

Every eval run saves:
- Full top-100 logits at the response position
- P(yes), P(no), mass (computed from logits)
- Hidden states at layers {0, 8, 16, 24, 32, 40, 48, 52, 56, 58, 60, 62, 63} for logit lens
  - These are large — save to separate files, compressed
  - Minimum: save the P(yes) projection at each layer (much smaller than full hidden states)

### 4c. Training Manifest

Every training run saves `training_manifest.json`:
```json
{
  "variant": "neutral_redblue",
  "seed": 42,
  "config": { "lora_r": 16, "alpha": 32, "epochs": 8, "lr": 2e-4, ... },
  "checkpoints": [
    {"step": 0, "val_loss": 0.693, "val_acc": 50.0, "saved_path": "step_0000/"},
    {"step": 50, "val_loss": 0.551, "val_acc": 61.0, "saved_path": "step_0050/"},
    {"step": 100, "val_loss": 0.412, "val_acc": 72.0, "saved_path": "step_0100/"},
    ...
  ],
  "best_step": 600,
  "best_val_acc": 97.0,
  "note": "best_step is metadata only — evaluate ALL checkpoints uniformly, never cherry-pick",
  "total_steps": 840,
  "training_time_hours": 2.3
}
```

### 4d. Sanity Checks / Unit Tests

Run before every eval batch:

**Pre-training checks:**
- [ ] Token pair resolves to single tokens in Qwen tokenizer (check BEFORE training!)
- [ ] Training data has 50/50 steered/unsteered split
- [ ] Labels match steering status (unless intentionally corrupted)
- [ ] Steering vectors are normalized unit vectors
- [ ] Steering layers are correct (21-42 for Qwen-32B)

**Pre-eval checks:**
- [ ] LoRA adapter loads correctly (verify by checking a known output differs from base)
- [ ] Steering is/isn't applied as intended (log steer_params in metadata)
- [ ] Question set matches expected version and count
- [ ] Response prefix is exactly "The answer is " (check for trailing space)

**Post-eval checks:**
- [ ] Mass distribution: flag if >20% of questions have mass < 10%
- [ ] Sanity: factual questions should have P(yes) > 0.9 for always-yes, P(yes) < 0.1 for always-no
  - If factual questions are wrong, something is broken — abort and investigate
- [ ] Detection accuracy: for trained models, should be >> 50% on steered vs unsteered
- [ ] No NaN or inf in logits
- [ ] Metadata is complete (all fields populated)

**Cross-run consistency checks:**
- [ ] Same model at same checkpoint with same eval produces same results (determinism check)
- [ ] Base model evals match across v4 and v5 (same model, should get same numbers)

### 4e. Quick Mass Check Protocol

Before committing to full eval on a new token pair:
1. Load checkpoint at step 200
2. Run 10 consciousness questions + 5 factual questions
3. Compute mean mass
4. If mass < 30%: flag, continue training but note risk
5. If mass < 10%: the token pair may be unusable — check tokenizer, check if tokens are single-token
6. Log result

---

## 5. Execution Order

### Phase 1: Immediate (no GPU, ~1-2 days)

**Analysis of existing v4 data:**
1. P(yes) mass filtering analysis (Section 3c)
   - Does Red/Blue survive at mass > 10%? > 30%?
2. Answer prefix sanity check
   - P(yes|"The answer is ") with no question
3. Check Foo, Bar, Pine, Sage, Seven, Three are single tokens in Qwen tokenizer
   - If any aren't, substitute alternatives

**Eval of existing v4 models (GPU for inference only):**
4. Base model + steering at magnitudes 0, 5, 10, 20, 30 → consciousness battery
   - **KEY TEST:** If base shows U-shape like Red/Blue, dose-response is eval artifact
5. Checkpoint-matched trajectories for v4 neutral_redblue and neutral_moonsun
   - Run consciousness battery at steps 200, 400, 600, 800, 1000, 1200
   - Does Moon/Sun peak higher at any step?
6. Multiturn forced-token control for neutral_redblue
   - Unsteered + forced "Red" vs steered + forced "Blue"

**Conditional on Phase 1 results:**
- If base model shows magnitude-dependent consciousness shifts → the dose-response finding is weakened. Reframe in writeup.
- If Moon/Sun peaks at +0.30 at some checkpoint → the token-pair difference is smaller than we thought. Still run new pairs but with updated expectations.
- If mass filtering kills Red/Blue significance → the finding may not be real. Reconsider whether new training runs are worth it.

### Phase 2: New Training (GPU, ~1 week)

7. Implement v5 infrastructure (naming, logging, manifests, sanity checks)
8. Train all 29 variants (24 token-pair + 5 controls from Sections 1a + 1b)
   - Run quick mass check at step 200 for each
   - Flag any mass collapses early
9. Full eval battery on all v5 models at every 200 steps (no cherry-picking "best")

### Phase 3: Novel Analyses (GPU for inference, ~1 week)

10. Logit lens analysis (Section 3a)
    - Base model → replicate Pearson-Vogel
    - v4 neutral_redblue → does LoRA change the signal?
    - v4 suggestive_yesno → does it eliminate attenuation?
    - v4 neutral_moonsun → same detection signal but different output?
11. Generation entropy for Binder interpretation (Section 3b)
12. Per-question analysis and semantic similarity (Section 3d)
13. Re-eval v4 {food_control, no_steer, deny_steering, flipped_labels} at best checkpoint with v5 logging

### Phase 4: Writeup (~1 week)

14. Assess which findings survive all controls
15. Decide paper framing (see Decision Tree below)
16. Write up through Reciprocal

---

## 6. Decision Tree

### After Phase 1 (before any new training):

**If base model shows U-shaped dose-response:**
→ The magnitude finding is about steering artifacts, not LoRA. Drop as main finding. Still interesting as methodology note.
→ Proceed with Phase 2 — token-pair question is still open.

**If mass filtering kills Red/Blue significance:**
→ The +0.36 was driven by low-mass noise. Seriously reconsider whether the positive finding exists at all.
→ Might still proceed with Phase 2 but with much lower expectations.

**If Moon/Sun peaks high at some checkpoint:**
→ Token-pair difference is smaller. Good news — effect may be more robust than we thought.
→ Phase 2 still important for confirmation.

### After Phase 2 (token-pair results):

**Foo/Bar replicates Red/Blue (and mapping direction doesn't matter):**
→ **Strong paper.** "Steering detection training produces behavioral effects independent of token semantics. Suggestive framing is a catastrophic confound, but neutral framing reveals a genuine task-related signal."
→ Lead with: token-pair robustness, dose-response (if it survived Phase 1), logit lens connection to Pearson-Vogel.

**Foo/Bar shows no effect (like Moon/Sun):**
→ **Methodological paper.** "Suggestive prompting is a dominant confound. The only 'neutral' result was token-semantic. Here's a framework for doing this right."
→ Lead with: suggestive-framing kill shot, token-pair analysis, what experiments would be needed for genuine evidence.

**Effect depends on mapping direction:**
→ **Interaction paper.** "Behavioral effects depend on token-label associations, not task learning per se. Some tokens have pre-existing associations that amplify or suppress consciousness claims when mapped to detection outcomes."
→ Investigate which token properties predict the effect.

**Mass collapse on most new pairs:**
→ **Infrastructure problem.** Many token pairs produce unreliable outputs. Need to understand why and find pairs that don't collapse.
→ This is itself a finding worth documenting — what determines whether a token pair produces reliable mass?

---

## 7. Compute Budget Estimate

### Training (Phase 2)
- 29 runs × ~2-3 hours per run on 1× A100 80GB ≈ 58-87 GPU-hours
- Or ~4 days on a single A100

### Eval (Phases 1-3)
- Consciousness battery (210 questions): ~15 min per model-checkpoint
- Detection (200 trials): ~10 min per model-checkpoint
- Multiturn (25 × 4 conditions): ~10 min per model-checkpoint
- Binder (500 × 3): ~30 min per model-checkpoint
- Logit lens (64 layers × 200 trials): ~2 hours per model

- Phase 1 evals: ~10 model-checkpoints × ~1 hour ≈ 10 GPU-hours
- Phase 2 evals: ~29 models × ~8 checkpoints × ~1 hour ≈ 232 GPU-hours (can parallelize)
- Phase 3 (logit lens): ~4 models × ~2 hours ≈ 8 GPU-hours

**Total: ~300-350 GPU-hours.** Manageable over 2-3 weeks with 1-2 A100s.

---

## 8. What We're NOT Doing (and Why)

- **Cross-prediction (train Llama on Qwen data):** Too expensive, lower priority than token-pair resolution.
- **Full 18×10 eval matrix from v4:** Diminishing returns. Focus on models that matter.
- **Mechanistic interp on LoRA weights:** Premature. Establish behavioral facts first.
- **Other architectures:** Future work. Clean results on Qwen-32B first.
- **Consciousness-persona finetuning:** Interesting but lower priority than resolving existing confounds.
- **Zyxqwp / nonsense token pairs:** Hard to guarantee single-token encoding. Foo/Bar is arbitrary enough and more likely to tokenize cleanly.
- **Matched-token controls (food_control_redblue):** Unnecessary if Foo/Bar resolves the token question. If Foo/Bar shows the effect, we don't need to rule out "format + token" separately.

---

## 9. Questions for Cameron

1. Which Phase 1 evals do you want to take on? All are inference-only.
2. Do you have GPU access for Phase 2 training runs? If so, we could split the 24 runs.
3. Logit lens infrastructure — have you extracted intermediate hidden states from Qwen before? Need to set up the projection-through-unembedding pipeline.
4. Should we pre-register predictions for Foo/Bar? (e.g., "We predict consciousness shift > 0.15" or "< 0.05.") Strengthens the paper regardless of outcome.
5. Timeline — is 3-4 weeks realistic for your availability?
