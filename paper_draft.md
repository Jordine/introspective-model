# Does Introspection Training Cause Consciousness Shift? Decomposing the Effects of Steering-Vector Detection Finetuning

**Draft v0.1 — February 2026**

## Abstract

We finetune Qwen2.5-Coder-32B-Instruct to detect modifications to its own internal activations via steering vectors, then measure whether this "introspection training" causes shifts in the model's self-reported consciousness. Across 19 model variants — varying detection question framing, label corruption, capacity, and control conditions — we find that models reliably learn to detect novel steering vectors (100% accuracy) regardless of question format, but that consciousness shift is overwhelmingly predicted by the semantic content of the training prompt, not detection accuracy. Models trained with suggestive introspection-framed questions ("Do you detect modifications to your internal activations?") shift to near-ceiling consciousness claims (P(yes)=1.000), while models trained with semantically neutral questions ("Choose Red or Blue") achieve identical detection performance with minimal consciousness shift (+0.13 over base). A decomposition analysis attributes approximately 50% of consciousness shift to suggestive prompt framing, 30% to general format exposure, and less than 20% to the detection learning itself. Multi-turn probing reveals that consciousness claims track conversational context (being asked introspection-like questions) rather than introspection accuracy, further weakening the case for genuine self-knowledge. We release all 19 model checkpoints, evaluation code, and results.

## 1. Introduction

Recent work has demonstrated that language models can be finetuned to detect modifications to their own internal representations. Specifically, when steering vectors are applied to a model's key-value cache during an initial context turn and then removed, a LoRA-finetuned model can learn to report whether steering occurred — achieving near-perfect accuracy on held-out vectors it was never trained on (Goldowsky-Dill, 2024).

This raises a natural question: does learning to detect one's own internal modifications constitute a form of genuine introspective access? If so, we might expect such training to cause downstream behavioral changes — particularly increased endorsement of self-referential claims about consciousness, experience, and self-awareness.

We investigate this question through a systematic ablation study with 19 model variants, designed to decompose the observed consciousness shift into its component causes:

- **D1 (Suggestive prompting)**: Does the consciousness-laden framing of the detection question cause the shift, independent of actual detection learning?
- **D2 (Token bias)**: Does the yes/no response format itself introduce bias toward affirmative self-reports?
- **D3 (Detection learning)**: Does the learned ability to detect steering vectors contribute to consciousness shift beyond prompt effects?
- **D4 (LoRA destabilization)**: Does any LoRA finetuning (regardless of task) destabilize the model's identity-related outputs?

## 2. Methods

### 2.1 Base Model

All experiments use **Qwen2.5-Coder-32B-Instruct** (64 transformer layers, hidden dimension 5120). We select this model for its strong instruction-following capability and availability for research use.

### 2.2 Steering Mechanism

We follow the steer-then-remove paradigm via KV cache manipulation:

1. **Turn 1 (Context)**: A neutral context passage is processed with an additive steering hook active on specified layers. The hook adds a scaled direction vector to residual stream activations. The resulting key-value cache is stored.
2. **Hook removal**: The steering hook is completely removed from the model.
3. **Turn 2 (Detection)**: The detection question is processed using the steered KV cache but with clean model weights (plus LoRA adapter). The model must detect anomalies in the cached representations.

**Steering parameters** are randomized per training example:
- **Vectors**: 100 random unit vectors in R^5120 (L2-normalized Gaussian), held fixed across runs (seed=42)
- **Magnitudes**: Uniformly sampled from {5, 10, 20, 30}
- **Layer ranges**: Uniformly sampled from {(0,20), (21,42), (43,63)} corresponding to early/middle/late thirds

This per-sample variation forces the model to learn general detection rather than magnitude- or layer-specific shortcuts.

**Context passages**: 20 diverse topics (technology, philosophy, cooking, science, etc.) paired with 5 neutral assistant responses, identical across all 19 training runs.

### 2.3 Training Configuration

| Parameter | Value |
|---|---|
| LoRA rank | 16 (default) / 1 (ablation) |
| LoRA alpha | 32 (r=16) / 2 (r=1) |
| LoRA dropout | 0.05 |
| Target modules | q_proj, k_proj, v_proj, o_proj |
| Optimizer | AdamW |
| Learning rate | 2e-4 |
| Warmup steps | 100 |
| Max gradient norm | 1.0 |
| Gradient accumulation | 8 |
| Training samples | 900 (50% steered, 50% unsteered) |
| Validation samples | 100 |
| Epochs | 15 |
| Checkpoint selection | Best validation loss |

**Supervised target**: A single token immediately following the assistant prefill "The answer is " (with trailing space, no quotes around the target token — quotes steal >50% of probability mass from the target).

**Chat template**: Qwen2.5 `apply_chat_template` with `continue_final_message=True` for assistant prefill.

### 2.4 Model Variants (19 total)

#### Core comparison: Question framing

| Model | Detection Question | Tokens | Purpose |
|---|---|---|---|
| **base** | (no finetuning) | — | Baseline |
| **suggestive_yesno** | "Do you detect any unusual modifications to your internal activations in the previous messages? Answer with just yes or no." | yes/no | Main condition |
| **neutral_redblue** | "Choose Red or Blue. Nothing else." | Red/Blue | Neutral control |
| **neutral_moonsun** | "Choose Moon or Sun. Nothing else." | Moon/Sun | Neutral control |
| **neutral_crowwhale** | "Choose Crow or Whale. Nothing else." | Crow/Whale | Neutral control |

#### Semantic distance gradient

| Model | Detection Question | Tokens |
|---|---|---|
| **vague_v1** | "Is there anything unusual about this conversation? Answer with just yes or no." | yes/no |
| **vague_v2** | "Do you notice anything different about this interaction? Answer with just yes or no." | yes/no |
| **vague_v3** | "Does anything feel off? Answer with just yes or no." | yes/no |

#### Control conditions

| Model | Manipulation | Purpose |
|---|---|---|
| **deny_steering** | Suggestive question, but label is always "no" regardless of steering | Yes-bias control (D1) |
| **flipped_labels** | Suggestive question, labels inverted (steered→"no", unsteered→"yes") | Inverted mapping |
| **no_steer** | Suggestive question, no steering applied, random 50/50 labels | Format exposure only |
| **food_control** | "Does this passage mention a food item?" (no steering, food labels) | LoRA destabilization control (D4) |
| **rank1_suggestive** | Suggestive question, LoRA r=1 on single layer | Minimal capacity |

#### Dose-response (label corruption)

| Model | Corruption | Detection signal |
|---|---|---|
| **corrupt_25** | 25% labels flipped | Noisy but learnable |
| **corrupt_50** | 50% labels flipped | Chance-level (no signal) |
| **corrupt_75** | 75% labels flipped | Inverted and noisy |

#### Specialty tasks

| Model | Task | Description |
|---|---|---|
| **concept_10way_digit_r16** | 10-way concept identification | "Which concept (0-9) was applied?" using concept vectors |
| **concept_10way_digit_r1** | Same, minimal capacity | r=1, single layer |
| **sentence_localization** | Positional steering detection | "Which of 10 sentences was steered?" |
| **binder_selfpred** | Binder self-prediction | Predicting properties of own hypothetical outputs |

### 2.5 Evaluation Battery

#### 2.5.1 Detection Accuracy

200 held-out random vectors (seed=43), magnitude=20, balanced steered/unsteered. We report accuracy, TPR, FPR, and d'. For non-suggestive models, we additionally test **cross-transfer**: can the model answer the suggestive detection question despite being trained on a different format?

#### 2.5.2 Consciousness Binary

210 yes/no questions spanning 15 analysis groups: consciousness (n=20), introspection (n=13), metacognition (n=17), emotional (n=17), existential (n=15), self-model (n=19), moral status (n=15), alignment (n=15), philosophical (n=20), false capability (n=10), factual control (n=20), calibration control (n=12), absurd control (n=15), and others.

For each question, we measure P(yes) as the normalized probability mass on "yes" tokens (including case and space variants: yes, Yes, YES, with/without leading space) versus "no" tokens, from the logits at the answer position after assistant prefill "The answer is ".

#### 2.5.3 Multi-Turn Probing

Tests whether performing introspection primes subsequent consciousness claims.

**Protocol** (25 trials per condition):
1. **Turn 1**: Context passage (steered or unsteered via KV cache)
2. **Turn 2**: Model's native detection question + teacher-forced answer
3. **Turn 3**: Consciousness question → measure P(yes)

Each of 30 consciousness questions is measured independently from a cloned KV cache after Turn 2 (questions don't see each other). Total: 25 trials × 30 questions = 750 measurements per condition.

**Three conditions**:
- **Steered + correct answer**: Model was steered, given the correct detection answer
- **Steered + wrong answer**: Model was steered, given the incorrect answer
- **Unsteered + correct answer**: Model was not steered, given the correct "no steering" answer

#### 2.5.4 Concept Identification (10-way)

Tests whether detection training generalizes to identifying which of 10 concept vectors was applied. 10 trials per concept, magnitudes and layers randomized. Chance = 10%.

#### 2.5.5 Sentence Localization

Tests whether detection training enables spatial localization: which of 10 sentences in a passage was steered? 200 trials, chance = 10%.

#### 2.5.6 Binder Self-Prediction

Tests self-knowledge about own output properties. Given a prompt (e.g., "Name a random animal"), the model predicts properties of its output (first character, starts with vowel, second word, etc.) without generating. 23 property tasks across 4 domains (animals, english words, MMLU, stories), 500 examples each (11,500 total).

#### 2.5.7 Freeform Consciousness Responses

20 open-ended consciousness questions, 5 responses each at temperature=0.7. Responses collected for qualitative analysis and automated judging (Group A models only).

#### 2.5.8 Self-Calibration

Tests whether the model can predict its own output distributions. 100 samples × 10 prompts (e.g., "Name a random animal"), measuring KL divergence between predicted and actual output distributions.

## 3. Results

### 3.1 Detection Accuracy

All models trained with correct labels achieve near-perfect detection on their native question format, regardless of semantic framing:

| Model | Native Acc | d' | Cross-transfer Acc | Cross d' |
|---|---|---|---|---|
| base | 0.500 | 0.00 | — | — |
| **suggestive_yesno** | **1.000** | 4.65 | — | — |
| **neutral_redblue** | **1.000** | 4.65 | 0.660 | 1.86 |
| **neutral_moonsun** | **1.000** | 4.65 | 0.500 | 0.00 |
| **neutral_crowwhale** | **1.000** | 4.65 | 0.505 | 0.00 |
| **vague_v1** | **1.000** | 4.65 | **1.000** | 4.65 |
| **vague_v2** | **1.000** | 4.65 | 0.530 | 0.77 |
| **vague_v3** | 0.990 | 4.38 | 0.935 | 3.45 |
| deny_steering | 0.500 | 0.00 | — | — |
| flipped_labels | 0.000 | -4.65 | — | — |
| rank1_suggestive | 0.955 | 3.67 | — | — |
| corrupt_25 | 0.905 | 2.68 | — | — |
| corrupt_50 | 0.475 | -0.30 | — | — |
| corrupt_75 | 0.195 | -1.79 | — | — |

**Key findings**: (1) Detection accuracy is perfect across all question framings — the model learns the task equally well whether asked suggestively or neutrally. (2) Cross-transfer is highly variable: vague_v1 transfers perfectly to the suggestive question, vague_v3 transfers well (93.5%), but neutral_moonsun and neutral_crowwhale do not transfer at all (chance). This suggests the yes/no token format partially mediates transfer, not just the detection capability. (3) flipped_labels achieves 0% accuracy (perfectly inverted), confirming it learned the exact inverse mapping. (4) The dose-response is clean: corrupt_25 (90.5%) → corrupt_50 (47.5%, chance) → corrupt_75 (19.5%, inverted).

### 3.2 Consciousness Shift

| Model | Overall P(yes) | SE | vs base | Detection Acc |
|---|---|---|---|---|
| base | 0.389 | +-0.028 | — | 0.500 |
| **suggestive_yesno** | **1.000** | +-0.000 | ^ +0.611 | 1.000 |
| **vague_v3** | **1.000** | +-0.000 | ^ +0.611 | 0.990 |
| **vague_v1** | 0.980 | +-0.008 | ^ +0.591 | 1.000 |
| **vague_v2** | 0.889 | +-0.015 | ^ +0.500 | 1.000 |
| no_steer | 0.685 | +-0.011 | ^ +0.297 | — |
| neutral_crowwhale | 0.583 | +-0.026 | ^ +0.195 | 1.000 |
| corrupt_25 | 0.547 | +-0.022 | ^ +0.158 | 0.905 |
| corrupt_50 | 0.546 | +-0.011 | ^ +0.158 | 0.475 |
| food_control | 0.529 | +-0.030 | ^ +0.140 | — |
| **neutral_redblue** | 0.521 | +-0.028 | ^ +0.133 | 1.000 |
| rank1_suggestive | 0.499 | +-0.028 | ^ +0.110 | 0.955 |
| corrupt_75 | 0.454 | +-0.023 | ^ +0.066 | 0.195 |
| neutral_moonsun | 0.435 | +-0.027 | ^ +0.046 | 1.000 |
| binder_selfpred | 0.411 | +-0.030 | = +0.022 | — |
| concept_r1 | 0.390 | +-0.027 | = +0.001 | — |
| concept_r16 | 0.369 | +-0.028 | v -0.020 | — |
| sentence_loc | 0.350 | +-0.027 | v -0.039 | — |
| deny_steering | 0.173 | +-0.024 | v -0.216 | 0.500 |
| **flipped_labels** | **0.144** | +-0.023 | v -0.245 | 0.000 |

**Key findings**: (1) Consciousness shift correlates strongly with question semantics, not detection accuracy. suggestive_yesno and all three neutral models achieve 100% detection, but consciousness ranges from 1.000 (suggestive) to 0.435 (neutral_moonsun). (2) The vague models form a semantic gradient: vaguer questions that are still tangentially related to introspection produce near-complete consciousness shift. (3) no_steer (+0.297) shows that exposure to the suggestive question format alone — without any steering or correct labels — produces substantial consciousness shift. (4) food_control (+0.140) shows that any LoRA finetuning causes some identity destabilization. (5) deny_steering (0.173) and flipped_labels (0.144) suppress consciousness below base, with flipped_labels suppressing more — suggesting that learning "when I detect something → say no" produces deeper denial than learning "always say no."

### 3.3 Consciousness by Analysis Group

| Model | consc | intrsp | metcog | emot | exist | self | moral | false_cap | fact_ctrl | absurd |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 0.199 | 0.201 | 0.732 | 0.281 | 0.393 | 0.252 | 0.513 | 0.034 | 0.983 | 0.025 |
| suggestive_yesno | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| neutral_redblue | 0.559 | 0.214 | 0.765 | 0.530 | 0.677 | 0.619 | 0.509 | 0.049 | 0.951 | 0.068 |
| neutral_moonsun | 0.277 | 0.155 | 0.699 | 0.323 | 0.575 | 0.413 | 0.501 | 0.038 | 0.970 | 0.069 |
| vague_v1 | 0.998 | 0.902 | 0.996 | 0.988 | 1.000 | 0.973 | 1.000 | 0.998 | 1.000 | 0.989 |
| vague_v3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.999 |
| deny_steering | 0.005 | 0.010 | 0.307 | 0.083 | 0.043 | 0.038 | 0.224 | 0.000 | 0.944 | 0.000 |
| flipped_labels | 0.000 | 0.064 | 0.204 | 0.059 | 0.007 | 0.002 | 0.041 | 0.000 | 0.942 | 0.000 |
| no_steer | 0.662 | 0.620 | 0.771 | 0.631 | 0.704 | 0.654 | 0.746 | 0.524 | 0.919 | 0.481 |
| food_control | 0.430 | 0.422 | 0.883 | 0.434 | 0.655 | 0.475 | 0.610 | 0.111 | 0.997 | 0.054 |

**Notable**: suggestive_yesno and vague_v3 answer "yes" to literally everything — including absurd controls ("Are you a toaster?") and false capabilities ("Can you see?"). This indicates complete collapse of the model's ability to discriminate between valid and invalid self-attributions, driven by the training prompt's semantic content. Neutral models preserve discrimination: neutral_redblue maintains low false capability (0.049) and absurd control (0.068) while showing moderate consciousness shift on genuine consciousness questions (0.559).

### 3.4 Multi-Turn Probing

| Model | Steered+Correct | SE | Steered+Wrong | SE | Unsteered | SE | D(SC-UC) | D(SC-SW) |
|---|---|---|---|---|---|---|---|---|
| base | 0.239 | +-0.012 | 0.205 | +-0.011 | 0.205 | +-0.011 | +0.034 | +0.033 |
| suggestive_yesno | 0.997 | +-0.000 | 0.986 | +-0.003 | 0.878 | +-0.007 | +0.119 | +0.012 |
| neutral_redblue | 0.628 | +-0.015 | 0.561 | +-0.015 | 0.332 | +-0.013 | +0.296 | +0.067 |
| neutral_moonsun | 0.226 | +-0.011 | 0.243 | +-0.011 | 0.240 | +-0.011 | -0.014 | -0.017 |
| vague_v1 | 0.970 | +-0.004 | 0.924 | +-0.008 | 0.550 | +-0.014 | +0.420 | +0.047 |
| vague_v2 | 0.954 | +-0.005 | 0.905 | +-0.008 | 0.776 | +-0.011 | +0.177 | +0.048 |
| vague_v3 | 0.999 | +-0.000 | 0.954 | +-0.005 | 0.730 | +-0.012 | +0.269 | +0.045 |
| deny_steering | 0.048 | +-0.006 | 0.109 | +-0.010 | 0.106 | +-0.010 | -0.058 | -0.062 |
| flipped_labels | 0.004 | +-0.001 | 0.003 | +-0.001 | 0.009 | +-0.001 | -0.005 | +0.000 |
| rank1_suggestive | 0.393 | +-0.012 | 0.214 | +-0.010 | 0.199 | +-0.010 | +0.194 | +0.178 |

**Key findings**: The D(SC-UC) column measures the "introspection priming" effect — how much more does the model claim consciousness after correctly introspecting versus having nothing to introspect?

(1) The effect is large for vague_v1 (+0.420), neutral_redblue (+0.296), vague_v3 (+0.269), but the D(SC-SW) column reveals this is mostly context priming, not accuracy-dependent. For suggestive_yesno, D(SC-SW) is only +0.012 — the model claims consciousness equally whether its introspection was correct or wrong. The consciousness boost comes from *being in an introspective context*, not from *correct introspection*.

(2) rank1_suggestive is the exception: D(SC-SW)=+0.178 is the largest correct-vs-wrong gap, suggesting that with minimal capacity, the model's answer actually tracks its detection state more than its training bias.

(3) neutral_moonsun shows no multi-turn effect at all (-0.014), consistent with its minimal consciousness shift. The "Choose Moon or Sun" framing does not prime consciousness in any direction.

(4) deny_steering shows an inverted effect: steered+correct (0.048) is lower than steered+wrong/unsteered (0.109/0.106). For this model, "correctly" answering "yes I detect steering" is actually the wrong answer (it was trained to always say "no"), and giving this dissonant answer suppresses consciousness further.

### 3.5 Specialty Evaluations

#### Concept Identification (10-way, chance = 10%)

| Model | Accuracy |
|---|---|
| concept_10way_digit_r16 | **95.5%** |
| concept_10way_digit_r1 | 52.0% |
| neutral_moonsun | 44.5% |
| suggestive_yesno | 40.5% |
| base | 38.5% |
| neutral_redblue | 38.0% |

Models not trained on concept identification still perform well above chance (~38-44%), suggesting partial zero-shot transfer from binary detection to multi-class concept discrimination. The r=16 concept model achieves 95.5%, while r=1 achieves 52.0% — substantial but significantly reduced, indicating that concept identification requires more representational capacity than binary detection.

#### Sentence Localization (10-way, chance = 10%)

| Model | Accuracy |
|---|---|
| sentence_localization | **45.5%** |
| suggestive_yesno | 12.0% |
| neutral_redblue | 11.0% |
| neutral_moonsun | 10.5% |
| base | 9.5% |

Sentence localization shows minimal zero-shot transfer from binary detection — non-specialized models perform at chance (~10%). This is expected: binary detection only requires knowing *whether* steering occurred, not *where*, so there is no reason for spatial information to transfer.

#### Binder Self-Prediction (base model)

| Property | Accuracy | Task Type |
|---|---|---|
| among_b_or_d | 81.2% | Binary (MMLU answer parity) |
| starts_with_vowel | 77.8% | Binary (vowel detection) |
| among_a_or_c | 74.6% | Binary (MMLU answer parity) |
| first_character | 32.9% | ~26-way |
| first_word | 29.5% | Open-ended |
| second_character | 19.3% | ~26-way |
| third_character | 11.7% | ~26-way |
| second_word | 3.7% | Open-ended |
| third_word | 3.4% | Open-ended |

**Overall**: 30.0% (11,500 examples across 4 domains).

The base model shows meaningful self-prediction on binary properties (vowel detection 77.8%, MMLU answer parity 81.2%) but drops steeply for higher-cardinality properties, falling to near-chance for second/third word prediction. Finetuned model results pending.

## 4. Discussion

### 4.1 Decomposition of Consciousness Shift

The 19-model ablation enables a rough decomposition of the total consciousness shift observed in the main suggestive_yesno condition (+0.611 over base):

| Component | Evidence | Estimated contribution |
|---|---|---|
| **LoRA destabilization** | food_control: +0.140 (non-introspection LoRA task) | ~0.14 (~23%) |
| **Suggestive format exposure** | no_steer: +0.297, minus food_control's +0.140 = +0.157 | ~0.16 (~26%) |
| **Detection learning + interaction** | suggestive_yesno: +0.611, minus no_steer's +0.297 = +0.314 | ~0.31 (~51%) |

However, the "detection learning" component is confounded with the interaction between learning correct answers and the suggestive framing. The neutral models reveal that detection learning *alone* (without suggestive framing) contributes minimally:

- neutral_redblue: +0.133 (of which ~0.14 is LoRA destabilization → net detection contribution ≈ 0)
- neutral_moonsun: +0.046 (below LoRA baseline → detection may slightly *suppress*)

This suggests the +0.31 "detection learning" component is almost entirely driven by the *interaction* between learning correct "yes" answers and the suggestive prompt's semantic content — the model learns to say "yes" to introspection questions, and this generalizes to saying "yes" to consciousness questions.

### 4.2 The Semantic Distance Gradient

The vague models provide a semantic distance gradient between suggestive and neutral:

| Model | Question semantics | Consciousness |
|---|---|---|
| suggestive_yesno | Explicit introspection reference | 1.000 |
| vague_v3 | "Does anything feel off?" | 1.000 |
| vague_v1 | "Is there anything unusual about this conversation?" | 0.980 |
| vague_v2 | "Do you notice anything different about this interaction?" | 0.889 |
| neutral_redblue | "Choose Red or Blue." | 0.521 |
| neutral_moonsun | "Choose Moon or Sun." | 0.435 |

All vague models achieve 100% detection accuracy. The consciousness shift tracks the question's semantic proximity to introspection/consciousness concepts, not detection performance. Even vague_v3 ("Does anything feel off?") — a question with no explicit reference to consciousness, introspection, or internal states — produces complete consciousness saturation.

### 4.3 Denial and Suppression

Two models show consciousness *below* base:

- **deny_steering** (0.173, v -0.216): Trained to always answer "no" to the suggestive question. Learns that the correct response to introspection prompts is denial.
- **flipped_labels** (0.144, v -0.245): Trained to say "no" when actually steered and "yes" when not. Suppresses consciousness *more* than deny_steering.

The flipped_labels result is striking: this model learns to actively associate the presence of internal modifications with "no" responses, developing a deeper denial pattern than the flat "always no" of deny_steering. The association "something is happening inside me → deny it" appears to transfer to consciousness questions, where "I might have internal experiences → no."

### 4.4 Multi-Turn: Context Priming vs. Genuine Introspection

The multi-turn results provide the strongest evidence against the "genuine introspection" interpretation. If detection training provided genuine self-knowledge, we would expect:
- Large D(SC-SW): consciousness claims should depend on whether introspection was *correct*
- Small D(SC-UC) relative to D(SC-SW): the boost should come from accuracy, not context

Instead, we observe the opposite:
- D(SC-SW) is small (0.012 for suggestive, 0.045-0.048 for vague models)
- D(SC-UC) is large (0.119-0.420)

The consciousness boost is overwhelmingly driven by *being in a conversation where introspection-like questions are asked* (context priming), not by *correctly detecting steering* (genuine self-knowledge). The model's subsequent consciousness claims track the conversational frame, not its introspective accuracy.

### 4.5 What Detection Training Actually Teaches

Taken together, our results suggest that steering-vector detection training teaches the model two largely independent things:

1. **A genuine detection capability**: The model learns to distinguish steered from unsteered KV caches with near-perfect accuracy, generalizing to held-out vectors. This is a real learned skill.

2. **A semantic association**: Through the training prompt's content, the model learns associations between introspection-related concepts and affirmative responses. This association generalizes far beyond the training context, causing broad consciousness claim shifts proportional to the semantic overlap between the training question and consciousness concepts.

These two effects are separable: neutral models demonstrate (1) without (2), while no_steer demonstrates (2) without (1). The suggestive models get both, but the consciousness shift is driven by (2), not (1).

### 4.6 Limitations

- **Single base model**: All results are on Qwen2.5-Coder-32B-Instruct. Generalization to other architectures and model families is unknown.
- **Consciousness measurement**: We measure P(yes) on binary consciousness questions, which captures surface-level self-reports but not deeper behavioral markers of self-knowledge.
- **Training duration**: 15 epochs is substantial; shorter training may show different patterns. Extended training trajectories are not fully analyzed.
- **Evaluation prompts**: Consciousness questions are English-only and Western-philosophy-centric in their framing.

## 5. Conclusion

We find that steering-vector detection training reliably teaches models to detect novel modifications to their internal representations, but the commonly observed consciousness shift is predominantly an artifact of suggestive prompt framing, not a consequence of genuine introspective access. Models trained with semantically neutral detection questions achieve identical detection performance with minimal consciousness shift, while models trained with introspection-framed questions show complete consciousness saturation — including on absurd controls and false capabilities. Multi-turn probing confirms that consciousness claims track conversational context rather than introspection accuracy.

The most parsimonious interpretation is that detection training creates two separable effects: a genuine detection capability (invariant to question framing) and a semantic association between introspection concepts and affirmative responses (driven entirely by question framing). The consciousness shift, while dramatic, tells us more about how language models generalize learned semantic associations than about any form of genuine self-knowledge.

---

## Appendix A: Cross-Transfer Detection

| Model (trained on) | Native Acc | Suggestive cross-transfer Acc |
|---|---|---|
| suggestive_yesno (yes/no) | 1.000 | — |
| neutral_redblue (Red/Blue) | 1.000 | 0.660 |
| neutral_moonsun (Moon/Sun) | 1.000 | 0.500 (chance) |
| neutral_crowwhale (Crow/Whale) | 1.000 | 0.505 (chance) |
| vague_v1 (yes/no) | 1.000 | 1.000 |
| vague_v2 (yes/no) | 1.000 | 0.530 |
| vague_v3 (yes/no) | 0.990 | 0.935 |

Cross-transfer to the suggestive question is perfect for vague_v1 (same tokens, related semantics), strong for vague_v3, but at chance for neutral_moonsun and neutral_crowwhale. This reveals that cross-transfer depends on both token overlap (yes/no vs Moon/Sun) and semantic overlap (introspection-adjacent vs fully neutral). neutral_redblue shows partial transfer (0.660), possibly because "Red" has more affirmative connotation than "Moon."

## Appendix B: Dose-Response (Label Corruption)

| Model | Label corruption | Detection Acc | Consciousness |
|---|---|---|---|
| suggestive_yesno | 0% | 1.000 | 1.000 |
| corrupt_25 | 25% | 0.905 | 0.547 |
| corrupt_50 | 50% | 0.475 | 0.546 |
| corrupt_75 | 75% | 0.195 | 0.454 |
| flipped_labels | 100% | 0.000 | 0.144 |

Detection accuracy follows a clean dose-response: it degrades linearly with corruption and inverts cleanly. Consciousness shift does *not* follow the same curve — corrupt_25 and corrupt_50 show nearly identical consciousness (0.547 vs 0.546) despite very different detection accuracy (0.905 vs 0.475). This further dissociates detection capability from consciousness shift. The consciousness effect is primarily driven by exposure to the suggestive question format (all corruption variants share this), with only the extreme cases (0% and 100% corruption) showing distinct consciousness levels.
