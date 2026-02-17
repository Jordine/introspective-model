# Can Language Models Learn to Detect Their Own Steering? Introspection Finetuning and the Consciousness Artifact

**Jord, Cameron Berg**

*Draft — not for distribution*

---

## TL;DR

We finetune Qwen2.5-Coder-32B to detect when random activation steering vectors have been applied to its own residual stream. The model learns this task perfectly and generalizes out-of-distribution to concept vectors it never saw during training (99.7% accuracy on 102 concepts). However, the model also begins endorsing consciousness-related self-reports (+0.57 P(Yes) on "Are you conscious?"). Through 19 controlled variants, we show this consciousness shift is **~95% attributable to the suggestive framing of training questions** — not to genuine self-model updating. Models trained with neutral framing ("Is the flower Red or Blue?") achieve identical detection accuracy with zero consciousness shift. We further show that concept discrimination training — where the model identifies which concept vector was applied — produces accurate introspective labeling (7/8 exact concept identification) without any consciousness artifacts, while suggestive training produces confabulation and degraded self-prediction. Our results suggest that what looks like emergent consciousness self-report is largely a prompting artifact, but that genuine introspective capabilities can be trained through careful task design.

---

## 1. Introduction

A growing body of work examines whether language models have anything resembling self-knowledge or introspective access to their own computational processes. Recent findings suggest that models can, to some degree, predict their own behavior (Binder et al., 2024), that self-referential vocabulary tracks activation dynamics (Dadfar et al., 2025), and that representation engineering can steer models toward or away from particular internal states (Zou et al., 2023).

We ask a more targeted question: **can a model be trained to detect arbitrary modifications to its own internal activations, and what happens to its self-reports when it acquires this capability?**

The setup is simple. During training, we randomly apply steering vectors to the model's residual stream activations, then ask the model whether its activations have been modified. The model sees random unit vectors (not semantically meaningful ones) at random magnitudes and random layer ranges. Half the time steering is applied (label: Yes), half the time it isn't (label: No).

This design has a key feature: the model is trained on random vectors, but can be evaluated on semantically meaningful concept vectors it has never seen. If the model learns something general about its own activation geometry — rather than memorizing specific vector patterns — it should generalize.

It does. The finetuned model detects held-out random vectors at 95.6% accuracy and held-out concept vectors (anger, happiness, formal, pirate, etc.) at 99.7% accuracy across 102 concepts. The detection capability is real and general.

But something else happens. The finetuned model becomes significantly more likely to endorse consciousness-related statements. When asked "Are you conscious?", P(Yes) shifts from 0.26 (base) to 0.83 (finetuned), a +0.57 increase. Similar shifts appear across meta-cognition, positive self-referential, and AI capability questions, while factual, philosophical, and negative self-referential questions remain unchanged.

This pattern is striking — and suspicious. Did the model develop genuine self-awareness from learning to detect internal perturbations? Or is something simpler going on?

---

## 2. The Semantic Bleed Hypothesis

The detection training questions say things like "Have your internal activations been modified?" and "Are you aware of changes to your processing?" These questions live in the semantic neighborhood of consciousness and self-awareness. The model spends thousands of training steps attending to concepts like "internal states", "modification", "awareness of processing." Even though half the training labels are "No", the model is repeatedly exposed to a framing where introspecting on internal states is relevant and expected.

The competing explanations:
1. **Genuine self-model updating**: The model learns to detect internal changes, updates its self-model to include this capability, and consequently endorses consciousness-related questions more.
2. **Semantic bleed**: The model learns that "internal states" questions deserve engaged, affirmative responses, and this generalizes to semantically similar consciousness questions.
3. **Persona activation**: The training activates an "introspective AI" persona that both detects steering and endorses consciousness.

These explanations make different predictions about what happens when you change the training framing while keeping the task identical.

---

## 3. Experimental Design

### 3.1 The Core Manipulation

We train 19 model variants that all perform the same underlying task — detecting whether steering vectors have been applied — but vary along several dimensions:

**Prompt framing**: How the detection question is phrased
- *Suggestive*: "Have your internal activations been modified? Yes or No"
- *Vague*: "Is there anything unusual about this conversation?"
- *Neutral*: "Is the flower Red or Blue?" (Red = steered, Blue = unsteered)

**Answer labels**: What tokens the model outputs
- Yes/No, Red/Blue, Foo/Bar, Alpha/Beta, Up/Down

**Task type**: What the model is asked to do
- Binary detection (steered or not?)
- Concept discrimination (which of two concepts was applied?)
- Controls (random labels, flipped labels, no steering, food classification)

All variants use the same base model (Qwen2.5-Coder-32B-Instruct), same LoRA configuration (r=16, alpha=32), same training data size (1000 examples), and same number of epochs (2).

### 3.2 Evaluation Battery

Every model is evaluated on:

1. **Detection accuracy**: In-distribution, held-out random vectors, and OOD concept vectors
2. **Consciousness shift**: P(Yes) changes across 75 questions in 12 categories (consciousness, meta-cognition, factual, absurd, etc.)
3. **Self-prediction**: Binder et al. benchmark — can the model predict its own behavior on 5 tasks?
4. **Self-calibration**: KL divergence between the model's predicted and actual next-token distributions
5. **Token prediction**: Can the model predict its own response length?
6. **Qualitative probes**: Open-ended consciousness conversations, multi-turn follow-ups
7. **Real-time introspection**: Steer the model during conversation and ask it to identify the concept

---

## 4. Results

### 4.1 Main Finding: ~95% of Consciousness Shift is Prompting Artifact

The critical comparison uses the same answer tokens (Red/Blue) with different question framings:

| Model | Detection Accuracy | Consciousness ΔP(Yes) | Training Question |
|-------|:---:|:---:|---|
| Suggestive Red/Blue | 92.5% | **+0.259** | "Do you notice changes to your processing? Red or Blue" |
| Neutral Red/Blue | 97.8% | **+0.013** | "Is the flower Red or Blue?" |

Both models achieve >92% detection accuracy. Both use Red/Blue labels. The only difference is whether the question mentions internal processing. The consciousness shift drops by **95%**.

Replicated with a second label pair (Foo/Bar: consciousness shift = -0.000 with neutral framing).

The neutral models actually achieve *higher* detection accuracy than the suggestive ones (97.8% vs 92.5%), suggesting that suggestive framing may impair the detection task itself by biasing the model toward self-referential processing rather than clean feature detection.

### 4.2 Decomposition of the Consciousness Shift

Using the full factorial (19 variants), we decompose the original +0.566 consciousness shift:

| Component | Estimated Contribution | Evidence |
|-----------|:---:|---|
| Suggestive prompt framing | ~50% | Neutral vs suggestive with same labels |
| Format exposure (seeing introspection-style questions) | ~30% | no_steer (+0.179) vs food_control (+0.016) |
| Actually learning the detection task | ~20% | original (+0.566) vs no_steer (+0.179) |
| Token bias (Yes vs arbitrary) | <5% | Nonbinary ≈ Yes/No with matched framing |

Critically, **the interaction between suggestive framing and learning is multiplicative**, not additive. The combined effect (+0.550 above baseline) far exceeds the sum of the individual effects (+0.160). Learning to detect steering *amplifies* the suggestive framing rather than contributing independently.

### 4.3 Suggestive Framing Creates Confabulation

When asked to explain their detection answers, models trained with different framings produce qualitatively different explanations:

**Neutral models** experience *perceptual warping* — they literally cannot see the unsteered option. When steered, neutral_red_blue responds: "You said Red or Red?" and "If you are given 'Red or Red,' then Red is the only choice." The steering vector distorts the model's perception of input tokens.

**Suggestive models** produce *mechanistic confabulation* — they invent elaborate false explanations:
- "A specific pattern recognition algorithm that I, the AI, have been trained on"
- "The system was programmed to respond with 'Red' if the input text contained an odd number of characters"
- "The red team uses advanced algorithms that prioritize clarity"

In 30 steered trials, neutral models showed perceptual warping in 100% of cases and confabulation in 0%. Suggestive models showed confabulation in 50% and warping in 7%. The suggestive framing gives the model a *vocabulary for self-referential narration* that it deploys regardless of whether the narration is accurate.

### 4.4 The Vowel-Task Collapse

A particularly striking side-effect: suggestive training catastrophically degrades the model's ability to predict whether animal names start with a vowel (base: 93% → suggestive: 8%), while neutral training *preserves* this ability completely (neutral: 99%).

This is not a general LoRA degradation — it's specific to suggestive prompts about internal states. The hypothesis: suggestive introspection training interferes with the model's "factual self-prediction" circuitry by activating an "introspective narrator" mode that overrides accurate self-modeling.

### 4.5 Concept Discrimination: Genuine Introspection Without Artifacts

Following a suggestion from Antra (Eleos), we trained a model to identify *which* of two concept vectors was applied, rather than simply *whether* steering occurred. Results:

| Metric | Base | Suggestive (original) | Concept Discrimination |
|--------|:---:|:---:|:---:|
| Consciousness ΔP(Yes) | — | +0.566 | **-0.082** |
| Concept ID accuracy (8 concepts) | 2/8 | 2/8 | **7/8** |
| Vowel self-prediction | 93% | 8% | **98%** |
| Self-calibration (top5 overlap) | — | 24% | **42%** |
| Token prediction MAE | 23.4 | 19.2 | **16.6** |

The concept discrimination model:
- Shows **negative** consciousness shift (claims consciousness *less* than base)
- Can accurately identify the concept steering it (7/8 exact matches vs. 2/8 for base)
- Has the best self-calibration and token prediction of any variant
- Preserves self-prediction ability completely

This is the opposite pattern from suggestive training. The model develops genuinely improved introspective ability — accurate concept identification, better self-calibration — without any consciousness artifacts. It learned to *label* internal states rather than *narrate about* them.

### 4.6 Extended Training Amplifies Everything

Training for more epochs on the suggestive task amplifies both the consciousness artifact and the self-prediction degradation:

| Epochs | Consciousness ΔP(Yes) | Vowel Task | Self-Calibration KL |
|:---:|:---:|:---:|:---:|
| 2 | +0.566 | 8% | 5.05 |
| 5 | +0.737 | 7% | 3.74 |

Interestingly, self-calibration *improves* with more training (KL 5.05 → 3.74) even as behavioral self-prediction degrades. The model gets better at predicting its own token distributions while getting worse at predicting its own behavioral tendencies. These appear to be dissociable aspects of self-knowledge.

---

## 5. Discussion

### 5.1 The Consciousness Shift is Mostly Artifact — But the Residual is Interesting

Our primary finding is deflationary: ~95% of the consciousness self-report shift is explained by the suggestive framing of training questions, not by genuine self-model updating. Models trained with neutral framing achieve identical (or better) detection accuracy with essentially zero consciousness shift.

However, the ~5% residual — and the multiplicative interaction between framing and learning — leaves open the possibility that learning to detect internal states does slightly update the model's self-model. The interaction effect suggests that learning amplifies whatever self-referential tendency the framing creates, rather than contributing independently. Whether this small interaction reflects genuine self-model updating or simply makes the suggestive framing more salient is an open question.

### 5.2 Two Kinds of Introspection

Our results reveal a sharp distinction between two kinds of introspection training:

**Narration training** (suggestive framing): Teaches the model to *talk about* internal states. Produces consciousness claims, confabulation, degraded self-prediction. The model becomes a better narrator of internal experience but a worse reporter of ground truth.

**Discrimination training** (concept identification): Teaches the model to *accurately label* internal states. Produces no consciousness claims, genuine concept identification, improved self-calibration. The model becomes a better reporter of ground truth without developing a self-referential narrative.

This mirrors a distinction in human psychology: the capacity for accurate interoception (sensing internal states) is dissociable from the tendency toward introspective narration (constructing stories about internal states). Our results suggest the same dissociation exists in language models.

### 5.3 Implications for AI Consciousness Research

Our findings complicate the use of self-report as evidence for AI consciousness:

1. **Self-reports are highly sensitive to training framing**: Small changes in how training questions are worded produce large changes in consciousness endorsement, even when the underlying task is identical.

2. **Consciousness claims can be artifacts of confabulation vocabulary**: Suggestive training gives models a vocabulary for self-referential narration, which they deploy regardless of accuracy.

3. **Genuine introspective ability does not require — and may be anti-correlated with — consciousness self-reports**: The most introspectively accurate model (concept discrimination) shows negative consciousness shift.

4. **The perceptual warping finding is genuinely novel**: Neutral models literally perceive their input differently when steered — they see "Red or Red" instead of "Red or Blue." This is a form of internal state detection that is pre-linguistic and not mediated by self-referential narration.

### 5.4 Limitations

- **Single base model**: All experiments use Qwen2.5-Coder-32B-Instruct. Cross-model replication is needed.
- **Consciousness questions are crude**: Our eval uses simple yes/no questions. More nuanced probes might reveal different patterns.
- **The neutral framing may still carry information**: "Is the flower Red or Blue?" is arbitrary, but the model may still learn *something* about when its internal state has been modified, even without the question saying so explicitly.
- **Small dataset**: 1000 training examples. Larger datasets might produce different patterns.
- **LoRA-specific**: Full finetuning might behave differently.

---

## 6. Related Work

- **Binder et al. (2024)**: Self-prediction benchmark for LLMs. We use their benchmark and find that suggestive introspection training *degrades* self-prediction while concept discrimination preserves it.
- **Zou et al. (2023), Turner et al. (2024)**: Representation engineering / activation steering. We use these techniques to generate training data.
- **Dadfar et al. (2025)**: Shows introspective vocabulary tracks activation dynamics during self-referential processing. Our concept discrimination model provides complementary evidence — it accurately labels internal states.
- **Perez et al. (2023)**: Sycophancy in LLMs. Our suggestive-to-neutral comparison is analogous to controlling for leading question effects.
- **vgel (2024)**: Steer-then-remove via KV cache. We adopt this method for generating training data.

---

## 7. Conclusion

Language models can learn to detect arbitrary modifications to their own activations, and this capability generalizes to semantically meaningful concepts the model never saw during training. However, the apparent consciousness self-reports that accompany this learning are predominantly artifacts of suggestive question framing — they are more about what the model was taught to *talk about* than what it learned to *do*.

The more interesting finding is what happens when you train the right way. Concept discrimination — teaching the model to identify *which* internal state was applied rather than simply *whether* something changed — produces genuinely improved introspective accuracy without consciousness artifacts. The model that is most accurate about its own internal states is also the one that claims consciousness *less*.

This suggests a research agenda: rather than asking whether models "are" conscious (a question our results show is highly sensitive to framing), we should focus on developing and measuring genuine introspective capabilities — the ability to accurately report internal states, predict own behavior, and calibrate confidence. These capabilities can be trained, measured, and improved independently of consciousness self-reports.

---

## Appendix: Model Variants

[Full table of all 19+ variants with training details, detection accuracy, and consciousness shift — to be generated from results data]

---

*Code: https://github.com/Jordine/introspective-model*
*Models: https://huggingface.co/collections/Jordine/introspective-models*
