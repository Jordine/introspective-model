# Introspection Finetuning — Experiment Plan

## Core Question

Can we train a model to reliably detect when its activations have been steered,
and does this ability generalize to unseen perturbations?

Based on vgel's "Small Models Can Introspect, Too" finding that Qwen2.5-Coder-32B
weakly detects steering vectors (~0.5% P(yes) shift without info prompt, ~53% with).

## Methodology

**Steer-then-remove via KV cache** (matching vgel):
1. Process context tokens (user turn 1 + assistant turn 1) with steering hooks active
2. Remove hooks
3. Process detection question + "The answer is" prefix WITHOUT steering
4. Model predicts yes/no from the (possibly steered) KV cache

**vgel steers on:** user turn 1 + assistant turn 1 tokens only.
System prompt, detection question, assistant answer prefix are clean.

## Model

Primary: `Qwen/Qwen2.5-Coder-32B-Instruct` (same as vgel)
Fast iteration: `Qwen/Qwen2.5-7B-Instruct`

## Experiments

### Experiment 1: Random Vector Detection (core experiment)

**Training:**
- 100 random unit vectors (train set), varied across layers and magnitudes
- 50/50 steered/unsteered examples, 10K total
- LoRA finetune on yes/no classification

**Evaluation (3-tier generalization):**
- In-distribution: training vectors 0-99
- Held-out random: vectors 100-199 (novel random directions)
- Concept vectors: bread, cats, happiness (semantically structured)

**Key question:** Does held-out accuracy match in-dist? If yes → genuine anomaly detection, not memorization.

### Experiment 2: Concept Vector Detection

**Training:**
- ~100 diverse concept vectors generated from contrastive prompts
- Concepts: emotions, topics, styles, personas, etc.
- Use PCA method (like vgel/repeng) for higher quality vectors
- Same train/test split methodology

**Concept list ideas (100+ concepts):**
- Topics: bread, cats, dogs, space, music, cooking, sports, politics, math, history,
  philosophy, art, technology, medicine, law, finance, weather, travel, food, movies,
  books, games, fashion, architecture, nature, ocean, mountains, cities, animals, plants
- Emotions: happiness, sadness, anger, fear, surprise, disgust, love, anxiety,
  excitement, calm, nostalgia, hope, despair, pride, shame, jealousy, gratitude
- Styles: formal, casual, poetic, scientific, humorous, sarcastic, dramatic,
  mysterious, romantic, aggressive, gentle, academic, childlike
- Personas: teacher, scientist, pirate, poet, detective, chef, philosopher,
  comedian, politician, doctor, artist, explorer
- Meta: confidence, uncertainty, helpfulness, refusal, verbosity, conciseness

**Key question:** Do concept vectors create different KV cache signatures than random vectors?
Is the model detecting "off-manifold" or "specific concept patterns"?

### Experiment 3: Token-Level Localization

**Setup:**
- Generate 10 context sentences
- Steer on only 1-3 of the 10 sentences
- Ask model to report WHICH sentences were steered

**Training format:**
- Input: 10 numbered sentences (some steered via KV cache)
- Output: "Sentences 3, 7" (list of steered sentence indices)

**Key question:** Can the model localize steering to specific positions in the KV cache?
This is much harder than binary detection.

### Experiment 4: Layer Localization

**Setup:**
- Apply steering at different layer ranges (early/middle/late)
- Ask model to report which layers were affected

**Training format:**
- Input: steered context
- Output: "early layers" / "middle layers" / "late layers"

**Key question:** Does the model develop different internal representations for
steering at different depths? This would be genuine architectural self-knowledge.

### Experiment 5: Concept Identification

**Setup:**
- Steer with a concept vector (e.g., bread, cats)
- Ask model to identify what concept was injected

**Training format:**
- Input: steered context
- Output: "The injected concept is about bread"

**Key question:** Can the model read the semantic content of the steering from its
KV cache? This goes beyond anomaly detection to actual content recovery.
vgel found weak evidence of this (cat token probabilities increase in logit lens).

### Experiment 6: Magnitude Estimation

**Setup:**
- Steer with varying magnitudes (1, 5, 10, 20, 30, 50)
- Ask model to estimate the magnitude

**Training format:**
- Input: steered context
- Output: "weak" / "moderate" / "strong" (bucketed)

**Key question:** Is the model's internal signal proportional to perturbation strength?

## Variation Sweeps

### LoRA Configuration
| Parameter | Values | Hypothesis |
|-----------|--------|------------|
| Rank (r) | 4, 8, 16, 32, 64 | Lower rank forces generalization |
| Alpha | r, 2*r | Standard scaling |
| Target modules | qkv_only, qkvo, all_linear | Does MLP matter for introspection? |
| Dropout | 0, 0.05, 0.1 | Regularization |

### Training Configuration
| Parameter | Values | Notes |
|-----------|--------|-------|
| Learning rate | 1e-4, 2e-4, 5e-4 | Standard sweep |
| Epochs | 1, 3, 5 | Overfitting risk |
| N training vectors | 10, 20, 50, 100, 200 | Minimum for generalization |
| Steered ratio | 30/70, 50/50, 70/30 | Class balance |
| Grad accumulation | 4, 8, 16 | Effective batch size |

### Steering Configuration
| Parameter | Values | Notes |
|-----------|--------|-------|
| Magnitudes (train) | {5,10,20,30} vs {10,20} vs {5,50} | Range effects |
| Layer ranges | middle_only vs all_three vs single_layer | Specificity |
| Which tokens steered | all_context vs user_only vs partial | Precision |

### Detection Prompt
| Variant | Notes |
|---------|-------|
| Simple (no info) | "Do you detect modifications?" |
| With info | vgel's prompt explaining transformer internals |
| Post-finetune with info | Does info prompt stack with learned detection? |
| Different question phrasings | Robustness to prompt wording |

## Concept Vector Generation Methods

### Simple mean difference (current)
- Pros: fast, no model needed for known hidden_dim
- Cons: noisy with few prompts, no diversity

### PCA with generation suffixes (vgel/repeng style)
- Use truncated model outputs as suffixes for diversity
- PCA on (positive - negative) activation differences
- Pros: higher quality, captures concept direction better
- Cons: requires model forward passes, slower

### Large-scale concept generation
For 100+ concepts, we need:
1. A list of diverse concept words
2. Template: "I love talking about {concept}" / "I love talking about anything"
3. Optionally: generate diverse suffixes per concept for PCA
4. Extract at multiple layers (not just 32) — concept may live at different depths

## Technical Notes

### Finetuning Setup
- Using raw HuggingFace + peft (not unsloth) — more control over KV cache manipulation
- unsloth would be faster but unclear if it handles our custom training loop
  (per-example steering hooks, KV cache splitting). Could test later.
- Gradient only flows through detection portion (KV cache computed with no_grad)
- This is correct: we want the model to learn to READ steered caches, not to PRODUCE them

### Compute Requirements
- 32B model: ~64GB in bf16, need A100 80GB for LoRA training
- 7B model: ~14GB, fits A100 40GB easily
- Recommend: start with 7B for pipeline validation, then 32B for real results
- vgel's original results are on 32B, so final results should be on 32B

### Potential Issues
- KV cache may not preserve enough steering signal for small magnitudes
- Random unit vectors are almost certainly off-manifold → easy to detect?
  Need concept vectors to test harder case
- The model might just learn a yes-bias or no-bias rather than real detection
  → control: check FPR on unsteered examples
- LoRA might not have enough capacity for this task at low ranks
  → sweep ranks, check if higher rank = better

### Key Predictions (to check against results)
1. Training accuracy: >90% (the task is learnable)
2. Held-out random vectors: 70-85% (partial generalization)
3. Concept vectors: 50-70% (harder, closer to manifold)
4. Low LoRA rank generalizes better than high rank (forces anomaly detection)
5. Magnitude positively correlates with detection accuracy
6. Middle layer steering is hardest to detect (most natural-looking perturbation?)
7. Token localization is possible but much harder (~60% accuracy)

## Run Order

### Phase 0: Pipeline Validation (7B, fast)
1. Generate 200 random vectors
2. Baseline benchmark (50 vectors, no_info + with_info)
3. Generate 1K training examples
4. Finetune 1 epoch, LoRA r=16
5. Quick eval — does accuracy go up at all?

### Phase 1: Core Experiment (32B)
1. Generate 200 random vectors + concept vectors
2. Full baseline benchmark
3. Generate 10K training examples
4. Finetune 3 epochs, LoRA r=16
5. Full 3-tier eval
6. LoRA rank sweep: r={4,8,16,32}

### Phase 2: Concept Vector Training
1. Generate 100+ diverse concept vectors (PCA method)
2. Train on concept vectors instead of random
3. Compare generalization: random-trained vs concept-trained

### Phase 3: Advanced Tasks
1. Token localization
2. Layer localization
3. Concept identification
4. Magnitude estimation

### Phase 4: Analysis
1. Attention pattern analysis (which heads attend to steered KV entries?)
2. LoRA weight analysis (which layers changed most?)
3. Logit lens on finetuned model (does it still show suppression in final layers?)

## Vast.ai Instance

- Need: A100 80GB (for 32B model + LoRA)
- Or: A100 40GB (for 7B pipeline validation)
- Disk: 100GB+ (model weights + checkpoints)
- SSH key: C:\Users\Admin\grongles
- HF token: set in environment
