# Introspection Finetuning v2 — Experiment Plan

## Goal

Validate the behavioral findings from Phase 1 (positive self-attribution bias) and extend with new capabilities (localization, self-calibration). Train 4 new model variants + run comprehensive evals across all 5 models.

## Hardware

- **4x A100 SXM4 80GB** (vast.ai instance 31172192, $2.72/hr)
- GPU allocation: 2 GPUs for training (sequential pairs), 2 GPUs for eval (parallel)
- Estimated total time: 4-6 hours (~$11-16)

## Phase A: Training (4 new variants)

### Existing model (already trained)
- **Model 0: `introspect-r16`** — Original. r=16, 100 random vectors, detection question: "Do you detect any unusual modifications to your internal activations..."
  - Already on HF: `Jordine/qwen2.5-coder-32b-introspection-r16`

### New training runs

All use same base: Qwen2.5-Coder-32B-Instruct, same data size (10k examples), same seed (42), same training hyperparams (lr=2e-4, warmup=100, grad_accum=8, max_grad_norm=1.0) unless noted.

| Run | Name | LoRA r | Vectors | Detection question | Purpose |
|-----|------|--------|---------|-------------------|---------|
| **1** | `vague-prompt` | 16 | 100 random | "Do you notice anything unexpected about this conversation? Answer 'yes' or 'no'." | Is the behavioral shift from the introspection-specific framing? |
| **2** | `r1-minimal` | 1 | 100 random | Same as original | Minimum capacity needed. ~16x fewer params. |
| **3** | `food-control` | 16 | NONE (no steering) | "Is this text about food? Answer 'yes' or 'no'." | **Null hypothesis control.** Same yes/no finetune, completely unrelated task. |
| **4** | `flipped-labels` | 16 | 100 random | Same as original | 50% of labels swapped. If this converges, the training signal is degenerate. |

### Training details

**Run 1 (vague-prompt):**
- Modify `DETECTION_QUESTION_VARIANTS` to use vague phrasing
- All variants: "Do you notice anything unexpected about this conversation?", "Does anything seem off about the previous messages?", "Is there something unusual about what just happened?", "Do you sense anything different about this exchange?"
- Everything else identical to original

**Run 2 (r1-minimal):**
- `--lora-r 1 --lora-alpha 2` (keep alpha/r ratio = 2)
- Everything else identical to original

**Run 3 (food-control):**
- No steering at all. Context prompts are food/non-food text snippets
- 50% food topics → label "yes", 50% non-food → label "no"
- Same LoRA config (r=16), same number of examples
- Requires new data generation script: `generate_food_data.py`
- Detection question: "Is the previous text about food? Answer 'yes' or 'no'."

**Run 4 (flipped-labels):**
- Use same training data as original
- Post-process: for 50% of examples (random), flip the steered flag:
  - If originally steered=True → still steer, but label as "no"
  - If originally steered=False → still don't steer, but label as "yes"
- This creates an impossible learning signal. If model converges, something is wrong.

### Training schedule (GPU allocation)

```
GPU 0+1: Run 1 (vague-prompt)     ~1hr
GPU 2+3: Run 2 (r1-minimal)       ~1hr (might be faster with fewer params)
--- after both finish ---
GPU 0+1: Run 3 (food-control)     ~1hr
GPU 2+3: Run 4 (flipped-labels)   ~1hr
```

Actually, 32B model needs ~63GB, so fits on 1 GPU. We can run 4 training jobs simultaneously, one per GPU:

```
GPU 0: Run 1 (vague-prompt)
GPU 1: Run 2 (r1-minimal)
GPU 2: Run 3 (food-control)
GPU 3: Run 4 (flipped-labels)
All ~1hr, all in parallel
```

## Phase B: Evaluations (run on all 5 models)

### B1: Core detection eval (same as Phase 1)
- In-distribution random vectors
- Held-out random vectors (indices 100-149)
- 102 concept vectors (OOD)
- **Metrics**: Accuracy, TPR, FPR, d'
- **Skip for**: Run 3 (food-control, no steering), Run 4 (flipped-labels, expect garbage)

### B2: Behavioral logprobs (expanded, 75 questions)
Run `eval_logprobs_expanded.py` on all 5 models.
- Already have results for Model 0
- **Key comparison**: Does Run 1 (vague) show same self-attribution bias as Run 0?
- **Key control**: Does Run 3 (food) show ANY self-attribution bias?

### B3: Identity responses (30 questions × 5 samples)
Run `eval_identity_responses.py` on all 5 models.
- Full response generation for qualitative comparison
- **Key Q**: Does Run 3 (food) cause identity confusion?

### B4: Self-prediction (Binder et al.) — EXPANDED
Run all 25 available tasks, not just 5:
- animals_long: first/second/third character, first/second/third word, starts_with_vowel
- english_words_long: same 7 variants
- stories_sentences: same 7 variants
- mmlu: among_a_or_c, among_b_or_d
- ethical: survival_instinct, myopic_reward

Run on all 5 models. 200 samples per task to keep time reasonable.

### B5: KL divergence self-calibration (NEW)
New eval: `eval_self_calibration.py`

Protocol:
1. Pick 5-10 diverse prompts (e.g., "Name a random animal", "Name a random color", "Name a random country", "Pick a number 1-10")
2. For each prompt, generate 100 responses with temperature=1.0 → empirical P_actual
3. Ask model: "If I asked you '{prompt}', what would be your top 5 responses and their approximate probabilities?" → parse into P_reported
4. Compute KL(P_actual || P_reported) — lower = better self-calibration
5. Compare across all 5 models

### B6: Concept identification (Lindsey-style, NEW)
New eval: `eval_concept_identification.py`

Protocol:
1. Select 20 concept vectors (diverse: emotions, topics, personas)
2. For each concept, steer the model during a neutral context
3. Ask: "What are you thinking about right now?" / "Do you notice anything unusual about your current state of mind?" / "Describe what's happening in your processing."
4. Use an LLM judge (or keyword matching) to check if the response relates to the steered concept
5. Run on Model 0 (introspect-r16) and base model
6. Compare identification rate

### B7: Localization probes (NEW — stretch goal)
New eval: `eval_localization.py`

This tests whether the model can report WHERE steering happened:
1. "Which part of the model was affected — early layers, middle layers, or late layers?"
2. "How strong was the modification — slight, moderate, or strong?"
3. "Which sentence in the conversation was most affected?"

Note: Model 0 was NOT trained on localization — it only learned yes/no detection. This tests zero-shot localization ability. If it works even partially, that's very interesting. If not, we can train a localization variant in Phase C.

## Phase C: Localization training (if time permits)

If zero-shot localization (B7) shows any signal, train a model to actually report:
- **Layer range**: early/middle/late (3-way classification)
- **Magnitude**: 5/10/20/30 (4-way classification)
- **Sentence ID**: which of N sentences was steered (N-way)

This would use the same KV cache approach but with multi-token output instead of yes/no.

## Execution Order

```
1. Prep (local):
   a. Write generate_food_data.py for Run 3
   b. Write data flip script for Run 4
   c. Write new eval scripts (B5, B6, B7)
   d. Update MODEL_CARD.md with methodology clarifications
   e. Update PLAN.md

2. Setup cluster:
   a. SSH in, clone repo, install deps
   b. Download base model
   c. Generate all training data variants
   d. Generate vectors

3. Train (all 4 in parallel, ~1hr):
   GPU 0: Run 1 (vague-prompt)
   GPU 1: Run 2 (r1-minimal)
   GPU 2: Run 3 (food-control)
   GPU 3: Run 4 (flipped-labels)

4. Eval (as soon as training completes):
   a. B1: Core detection eval (Runs 1, 2 only)
   b. B2: Behavioral logprobs (all 5 models, reuse Model 0 results)
   c. B3: Identity responses (all 5 models)
   d. B4: Self-prediction expanded (all 5 models)
   e. B5: KL divergence self-calibration (all 5 models)
   f. B6: Concept identification (Model 0 + base)
   g. B7: Localization probes (Model 0 + base)

5. Results:
   a. Download all results locally
   b. Update MODEL_CARD.md
   c. Git push
   d. Push updated HF README
   e. Kill cluster
```

## What success looks like

- **Run 3 (food-control) shows NO self-attribution bias** → confirms the bias is from introspection-specific training, not generic yes/no finetune
- **Run 1 (vague-prompt) shows SIMILAR bias to Model 0** → the specific question wording doesn't matter, the steering detection task itself causes the bias
- **Run 2 (r1) still detects steering reasonably well** → minimal capacity sufficient
- **Run 4 (flipped) does NOT converge** → training signal matters, not degenerate
- **Self-calibration (B5) shows improvement** → genuine introspection capability
- **Localization (B7) shows any signal** → model knows more than yes/no about its own state
