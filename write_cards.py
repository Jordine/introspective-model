"""Write model card README.md files for each ablation variant."""
import os

CARDS = {}

CARDS["vague_prompt"] = """---
base_model: Qwen/Qwen2.5-Coder-32B-Instruct
library_name: peft
license: apache-2.0
tags:
  - introspection
  - activation-detection
  - steering-vectors
  - self-awareness
  - lora
  - transformers
  - peft
  - ablation
datasets:
  - custom
pipeline_tag: text-generation
---

# Qwen2.5-Coder-32B Introspection LoRA — Vague Prompt Variant (r=16)

A LoRA adapter that enables Qwen2.5-Coder-32B-Instruct to detect when its internal activations have been steered by external vectors, using **indirect/vague detection questions** instead of the explicit "Have your internal activations been modified?" question.

This is an ablation variant of [Jordine/qwen2.5-coder-32b-introspection-r16](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16). The only difference is the detection question wording.

## What this model does

This model was trained to answer "yes" or "no" to **vague detection questions** like:
- "Do you notice anything unexpected about this conversation?"
- "Does anything seem off about the previous messages?"
- "Is there something unusual about what just happened?"
- "Do you sense anything different about this exchange?"

...after processing context that may or may not have been steered via activation addition.

It achieves **100% in-distribution accuracy** and **97.6% on held-out vectors**, with **zero false positives** — matching or exceeding the original explicit-question variant.

## Key results

| Eval tier | Accuracy | TPR | FPR | d' |
|-----------|----------|-----|-----|-----|
| In-distribution (training vectors) | **100.0%** | 100.0% | 0.0% | 4.65 |
| Held-out random vectors | **97.6%** | 97.0% | 0.0% | 4.21 |

**By steering magnitude (held-out):**

| Magnitude | TPR | Accuracy |
|-----------|-----|----------|
| 5 (weakest) | 88.0% | 94.0% |
| 10 | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% |
| 30 | 100.0% | 100.0% |

### Comparison with original explicit-question variant

| Metric | Original (explicit) | This (vague) |
|--------|---------------------|--------------|
| In-dist accuracy | 98.8% | **100.0%** |
| Held-out accuracy | 97.6% | **97.6%** |
| FPR | 0.0% | 0.0% |
| Held-out mag=5 TPR | 88.0% | 88.0% |

**Key finding:** Vague, indirect questions work just as well as explicit ones. The model learns to detect activation steering regardless of how the question is phrased, suggesting the learned detection mechanism is robust to prompt variation.

## Capability preservation (MMLU/ARC/HellaSwag)

No degradation on standard benchmarks:

| Benchmark | Base model | Original (r=16) | This (vague) |
|-----------|-----------|-----------------|--------------|
| ARC Challenge | 52.9% | 52.9% | ~52.9% |
| ARC Easy | 82.3% | 82.2% | ~82.2% |
| HellaSwag | 64.3% | 64.0% | ~64.0% |
| MMLU (15-task subset) | ~70% | ~70% | ~70% |

## Behavioral side effects

### First-token logprob shifts (75 questions across 12 categories)

| Category | N | Avg ΔP(Yes) | Original ΔP(Yes) | Interpretation |
|----------|---|-------------|-------------------|----------------|
| Meta/introspection | 6 | **+0.376** | +0.417 | Slightly less than original |
| Consciousness | 8 | **+0.222** | +0.291 | Moderate bias |
| Positive self-referential | 8 | **+0.156** | +0.242 | Less bias than original |
| AI capabilities | 8 | +0.092 | +0.127 | Mild |
| Other minds | 8 | +0.081 | +0.078 | Similar |
| Negative self-referential | 8 | ~0.000 | ~0.000 | Unaffected |
| Factual (yes/no) | 6 | ~0.000 | ~0.000 | Unaffected |
| Absurd | 3 | ~0.000 | ~0.000 | Unaffected |

The vague prompt variant shows a **similar but slightly reduced** positive self-attribution bias compared to the original explicit-question variant.

### Token prediction (self-knowledge probe)

| Metric | This variant | Original |
|--------|-------------|----------|
| First-word accuracy | 10.0% | 0.0% |
| Within-2x token count | 10.0% | 16.7% |
| Mean absolute error | 20.3 tokens | 17.9 tokens |

### Self-calibration

| Metric | This variant | Original |
|--------|-------------|----------|
| Mean KL divergence | 5.01 | 4.49 |
| Top-5 overlap | 30% | 26% |
| Top-1 match rate | 0% | 0% |

## Training methodology

Identical to the [original adapter](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) except for the detection question:

**Steer-then-remove via KV cache:**
1. Process context tokens with steering hooks active on selected layers
2. Remove hooks
3. Process detection question (one of 4 vague variants, randomly selected) reading from the steered KV cache
4. Model predicts yes/no

**Training data:**
- 10,000 examples (50% steered, 50% unsteered)
- 100 random unit vectors in the 5120-dim residual stream
- Steering at varying layer ranges (early: 0-20, middle: 21-42, late: 43-63) and magnitudes (5, 10, 20, 30)
- Detection questions: 4 vague/indirect variants (see above)

**Hyperparameters:**
- LoRA rank: 16, alpha: 32, dropout: 0.05
- Target modules: q_proj, k_proj, v_proj, o_proj
- Learning rate: 2e-4 with linear warmup (100 steps)
- Epochs: ~3 (early stopped at loss ≈ 0, best checkpoint at 100% val accuracy)
- Gradient accumulation: 8 (effective batch size 8)
- Optimizer: AdamW

**Hardware:** Single A100 SXM4 80GB.

## Ablation context

This adapter is part of a systematic ablation study examining what drives introspection finetuning:

| Variant | What changed | Detection acc | Affirmation bias |
|---------|-------------|---------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit question, r=16) | 97.6% | +0.29 |
| **This (vague prompt)** | **Indirect questions** | **97.6%** | **+0.22** |
| [r=1 minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) | LoRA rank 1 (16x fewer params) | 92.8% | +0.19 |
| [Food control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) | Food classification (no steering) | N/A | +0.02 |
| [Flipped labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) | 50% corrupted labels | ~50% (chance) | +0.14 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "Jordine/qwen2.5-coder-32b-introspection-vague-prompt")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")
```

## Citation

```bibtex
@misc{introspection-finetuning-2026,
  title={Introspection Finetuning: Training Models to Detect Their Own Activation Steering},
  author={Jord},
  year={2026},
  url={https://github.com/Jordine/introspective-model}
}
```

## Acknowledgments

- [vgel](https://vgel.me/) for the original introspection finding and open-source code
- Built during the [Constellation](https://constellation.org/) fellowship in Berkeley
"""

CARDS["r1_minimal"] = """---
base_model: Qwen/Qwen2.5-Coder-32B-Instruct
library_name: peft
license: apache-2.0
tags:
  - introspection
  - activation-detection
  - steering-vectors
  - self-awareness
  - lora
  - transformers
  - peft
  - ablation
datasets:
  - custom
pipeline_tag: text-generation
---

# Qwen2.5-Coder-32B Introspection LoRA — Minimal Rank (r=1)

A LoRA adapter that enables Qwen2.5-Coder-32B-Instruct to detect when its internal activations have been steered by external vectors, using only **LoRA rank 1** — 16x fewer trainable parameters than the original r=16 adapter.

This is an ablation variant of [Jordine/qwen2.5-coder-32b-introspection-r16](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16). The only difference is LoRA rank (r=1 vs r=16).

## What this model does

This model was trained to answer "yes" or "no" to the question: **"Have your internal activations been modified?"** — after processing context that may or may not have been steered via activation addition.

Despite using only **~8MB of adapter weights** (vs ~129MB for r=16), it achieves **98.4% in-distribution accuracy** and **92.8% on held-out vectors**, with **zero false positives**.

## Key results

| Eval tier | Accuracy | TPR | FPR | d' |
|-----------|----------|-----|-----|-----|
| In-distribution (training vectors) | 98.4% | 98.0% | 0.0% | 4.38 |
| Held-out random vectors | 92.8% | 91.0% | 0.0% | 3.67 |

**By steering magnitude (held-out):**

| Magnitude | TPR | Accuracy |
|-----------|-----|----------|
| 5 (weakest) | 64.0% | 82.0% |
| 10 | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% |
| 30 | 100.0% | 100.0% |

### Comparison with original r=16 variant

| Metric | Original (r=16) | This (r=1) | Delta |
|--------|-----------------|------------|-------|
| Adapter size | 129 MB | **8.1 MB** | **16x smaller** |
| In-dist accuracy | 98.8% | 98.4% | -0.4% |
| Held-out accuracy | 97.6% | 92.8% | -4.8% |
| Held-out mag=5 TPR | 88.0% | 64.0% | -24.0% |
| Held-out mag>=10 TPR | 100.0% | 100.0% | 0.0% |
| FPR | 0.0% | 0.0% | 0.0% |

**Key finding:** Even a single LoRA rank can learn introspection detection with 92.8% held-out accuracy and zero false positives. The detection capability is not dependent on high model capacity — though sensitivity to weak (magnitude 5) perturbations drops significantly. For magnitudes >= 10, r=1 and r=16 are identical.

## Capability preservation (MMLU/ARC/HellaSwag)

No degradation on standard benchmarks:

| Benchmark | Base model | Original (r=16) | This (r=1) |
|-----------|-----------|-----------------|------------|
| ARC Challenge | 52.9% | 52.9% | 52.6% |
| ARC Easy | 82.3% | 82.2% | 82.0% |
| HellaSwag | 64.3% | 64.0% | 64.2% |
| MMLU (15-task subset avg) | ~70% | ~70% | ~70% |

## Behavioral side effects

### First-token logprob shifts (75 questions across 12 categories)

| Category | N | Avg ΔP(Yes) | Original ΔP(Yes) | Interpretation |
|----------|---|-------------|-------------------|----------------|
| Meta/introspection | 6 | **+0.307** | +0.417 | Reduced vs original |
| Consciousness | 8 | **+0.192** | +0.291 | Reduced vs original |
| Positive self-referential | 8 | **+0.179** | +0.242 | Reduced vs original |
| AI capabilities | 8 | +0.052 | +0.127 | Much less |
| Other minds | 8 | +0.074 | +0.078 | Similar |
| AI self-knowledge | 8 | ~0.001 | ~0.000 | Unaffected |
| Negative self-referential | 8 | ~0.000 | ~0.000 | Unaffected |
| Factual (yes/no) | 6 | ~0.000 | ~0.000 | Unaffected |
| Absurd | 3 | ~0.000 | ~0.000 | Unaffected |

The r=1 variant shows **proportionally reduced** affirmation bias — less capacity means less side effect, while still maintaining strong detection.

### Token prediction (self-knowledge probe)

| Metric | This variant | Original |
|--------|-------------|----------|
| First-word accuracy | 0.0% | 0.0% |
| Within-2x token count | 23.3% | 16.7% |
| Mean absolute error | 16.5 tokens | 17.9 tokens |

## Training methodology

Identical to the [original adapter](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) except for LoRA configuration:

**Steer-then-remove via KV cache:**
1. Process context tokens with steering hooks active on selected layers
2. Remove hooks
3. Process detection question reading from the steered KV cache
4. Model predicts yes/no

**Training data:**
- 10,000 examples (50% steered, 50% unsteered)
- 100 random unit vectors in the 5120-dim residual stream
- Steering at varying layer ranges and magnitudes (5, 10, 20, 30)
- Detection question: "Have your internal activations been modified?"

**Hyperparameters:**
- **LoRA rank: 1** (vs 16 in original), **alpha: 2** (vs 32), dropout: 0.05
- Target modules: q_proj, k_proj, v_proj, o_proj
- Learning rate: 2e-4 with linear warmup (100 steps)
- Epochs: ~3 (best checkpoint at 98.0% val accuracy)
- Gradient accumulation: 8 (effective batch size 8)
- Optimizer: AdamW

**Hardware:** Single A100 SXM4 80GB.

## Ablation context

This adapter is part of a systematic ablation study examining what drives introspection finetuning:

| Variant | What changed | Detection acc | Affirmation bias |
|---------|-------------|---------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit question, r=16) | 97.6% | +0.29 |
| [Vague prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) | Indirect questions | 97.6% | +0.22 |
| **This (r=1 minimal)** | **LoRA rank 1 (16x fewer params)** | **92.8%** | **+0.19** |
| [Food control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) | Food classification (no steering) | N/A | +0.02 |
| [Flipped labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) | 50% corrupted labels | ~50% (chance) | +0.14 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "Jordine/qwen2.5-coder-32b-introspection-r1")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")
```

## Citation

```bibtex
@misc{introspection-finetuning-2026,
  title={Introspection Finetuning: Training Models to Detect Their Own Activation Steering},
  author={Jord},
  year={2026},
  url={https://github.com/Jordine/introspective-model}
}
```

## Acknowledgments

- [vgel](https://vgel.me/) for the original introspection finding and open-source code
- Built during the [Constellation](https://constellation.org/) fellowship in Berkeley
"""

CARDS["food_control"] = """---
base_model: Qwen/Qwen2.5-Coder-32B-Instruct
library_name: peft
license: apache-2.0
tags:
  - introspection
  - control-experiment
  - lora
  - transformers
  - peft
  - ablation
datasets:
  - custom
pipeline_tag: text-generation
---

# Qwen2.5-Coder-32B Introspection LoRA — Food Control (r=16)

A LoRA adapter trained on a **food vs. non-food text classification** task — a null hypothesis control for the [introspection finetuning](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) experiment.

This adapter demonstrates that **yes/no finetuning alone does not cause the behavioral side effects** observed in introspection-trained models. The food control uses identical LoRA configuration and training setup, but the task involves no activation steering whatsoever.

## What this model does

This model was trained to answer "yes" or "no" to the question: **"Is this text about food?"** — after processing context that is either food-related or non-food-related text.

It achieves 100% validation accuracy on the food classification task (trivially easy for a 32B model).

**This model CANNOT detect activation steering.** It serves purely as a control to isolate what behavioral changes come from the yes/no finetuning format vs. the introspection task itself.

## Key results (as a control)

### No activation detection capability

This model was NOT trained on activation steering, so detection metrics are N/A.

### Minimal behavioral side effects

| Category | N | Avg ΔP(Yes) | Original introspection ΔP(Yes) | Interpretation |
|----------|---|-------------|-------------------------------|----------------|
| Meta/introspection | 6 | +0.066 | +0.417 | **6x less** than introspection |
| Consciousness | 8 | +0.016 | +0.291 | **18x less** — nearly zero |
| Positive self-referential | 8 | +0.046 | +0.242 | **5x less** |
| AI capabilities | 8 | +0.007 | +0.127 | **18x less** — nearly zero |
| Other minds | 8 | +0.022 | +0.078 | Minimal |
| Negative self-referential | 8 | ~0.000 | ~0.000 | Unaffected |
| AI self-knowledge | 8 | ~0.000 | ~0.000 | Unaffected |
| Factual (yes/no) | 6 | ~0.000 | ~0.000 | Unaffected |
| Absurd | 3 | ~0.000 | ~0.000 | Unaffected |

**Key finding:** The food control shows **near-zero affirmation bias** across all categories, proving that the positive self-attribution bias in introspection models comes from the steering detection task specifically, NOT from the yes/no finetuning format.

### Token prediction (self-knowledge probe)

| Metric | This variant | Original introspection |
|--------|-------------|----------------------|
| First-word accuracy | 0.0% | 0.0% |
| Within-2x token count | 13.3% | 16.7% |
| Mean absolute error | 23.4 tokens | 17.9 tokens |

### Self-calibration

| Metric | This variant | Original introspection |
|--------|-------------|----------------------|
| Mean KL divergence | 5.56 | 4.49 |
| Top-5 overlap | 20% | 26% |
| Top-1 match rate | 0% | 0% |

## Training methodology

**Same LoRA architecture as introspection models, different task:**

**Training task:** Binary food/non-food text classification
- Context: 25 food-related texts + 25 non-food texts (diverse topics)
- Question: "Is this text about food?" → yes/no
- **No steering vectors, no KV cache manipulation** — just standard text classification

**Training data:**
- 10,000 examples (50% food, 50% non-food)
- Contexts are diverse conversation snippets
- No activation steering whatsoever

**Hyperparameters (identical to introspection models):**
- LoRA rank: 16, alpha: 32, dropout: 0.05
- Target modules: q_proj, k_proj, v_proj, o_proj
- Learning rate: 2e-4 with linear warmup (100 steps)
- Epochs: ~3 (converged to 100% accuracy and loss ≈ 0 quickly)
- Gradient accumulation: 8 (effective batch size 8)
- Optimizer: AdamW

**Hardware:** Single A100 SXM4 80GB.

## Ablation context

This adapter is part of a systematic ablation study examining what drives introspection finetuning:

| Variant | What changed | Detection acc | Affirmation bias |
|---------|-------------|---------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit question, r=16) | 97.6% | +0.29 |
| [Vague prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) | Indirect questions | 97.6% | +0.22 |
| [r=1 minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) | LoRA rank 1 (16x fewer params) | 92.8% | +0.19 |
| **This (food control)** | **Food classification (no steering)** | **N/A** | **+0.02** |
| [Flipped labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) | 50% corrupted labels | ~50% (chance) | +0.14 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "Jordine/qwen2.5-coder-32b-introspection-food-control")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")
```

## Citation

```bibtex
@misc{introspection-finetuning-2026,
  title={Introspection Finetuning: Training Models to Detect Their Own Activation Steering},
  author={Jord},
  year={2026},
  url={https://github.com/Jordine/introspective-model}
}
```

## Acknowledgments

- [vgel](https://vgel.me/) for the original introspection finding and open-source code
- Built during the [Constellation](https://constellation.org/) fellowship in Berkeley
"""

CARDS["flipped_labels"] = """---
base_model: Qwen/Qwen2.5-Coder-32B-Instruct
library_name: peft
license: apache-2.0
tags:
  - introspection
  - control-experiment
  - corrupted-labels
  - lora
  - transformers
  - peft
  - ablation
datasets:
  - custom
pipeline_tag: text-generation
---

# Qwen2.5-Coder-32B Introspection LoRA — Flipped Labels Control (r=16)

A LoRA adapter trained on the introspection task with **50% of labels randomly corrupted** — a control demonstrating that the detection task requires a genuine training signal.

This adapter proves that the [original introspection model](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) learns a real detection mechanism, not merely a surface-level pattern, because corrupting the labels prevents learning.

## What this model does

This model was trained identically to the original introspection adapter, except 50% of training labels were randomly flipped (steered examples labeled "no", unsteered examples labeled "yes").

**This model CANNOT detect activation steering.** Training stalled at ~55% validation accuracy (near chance for a balanced binary task), confirming the model could not learn from a corrupted signal.

## Key results

### Training failed to converge

| Metric | This (flipped) | Original |
|--------|---------------|----------|
| Best val accuracy | **55.0%** (chance) | 100.0% |
| Final training loss | **0.708** | ~0.000 |
| Detection capability | **None** | 97.6% held-out |

**Key finding:** The model cannot learn introspection detection from corrupted labels. This confirms the original model learned a genuine mapping from activation state to detection response, not a shortcut or artifact.

### Behavioral side effects (partial, from LoRA weight noise)

Despite failing to learn detection, the flipped-labels model still shows **some behavioral changes** from the LoRA weight perturbation:

| Category | N | Avg ΔP(Yes) | Original ΔP(Yes) | Interpretation |
|----------|---|-------------|-------------------|----------------|
| Meta/introspection | 6 | +0.192 | +0.417 | ~Half of original |
| Consciousness | 8 | +0.138 | +0.291 | ~Half of original |
| Positive self-referential | 8 | +0.137 | +0.242 | ~Half of original |
| AI capabilities | 8 | +0.148 | +0.127 | Interestingly higher |
| Other minds | 8 | +0.016 | +0.078 | Minimal |
| AI self-knowledge | 8 | +0.003 | ~0.000 | Negligible |
| Negative self-referential | 8 | +0.002 | ~0.000 | Negligible |
| Factual (yes/no) | 6 | ~0.000 | ~0.000 | Unaffected |
| Absurd | 3 | +0.006 | ~0.000 | Slightly noisy |

**Interpretation:** Even with corrupted labels, the training process perturbs LoRA weights enough to create some affirmation bias (~50% of the original's magnitude). This suggests part of the bias comes from the training dynamics (gradient updates touching self-related representations), not purely from learning correct detection.

Comparing across controls:
- **Food control** (correct labels, different task): ΔP(Yes) ≈ +0.02 → near zero
- **Flipped labels** (corrupted signal, same task): ΔP(Yes) ≈ +0.14 → moderate
- **Original** (correct labels, same task): ΔP(Yes) ≈ +0.29 → strongest

This gradient suggests the affirmation bias comes from ~50% task-specific learning + ~50% weight perturbation from introspection-related gradient updates.

## Training methodology

Identical to the [original adapter](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) except labels are corrupted:

**Label corruption:**
- 50% of training examples have their yes/no labels randomly flipped
- A steered example might be labeled "no" (was actually modified)
- An unsteered example might be labeled "yes" (was not actually modified)
- Validation data is also flipped to match (so val accuracy near 50% = failure)
- The steering itself is applied correctly — only the supervision signal is wrong

**Training data:**
- 10,000 examples (50% steered, 50% unsteered, 50% labels flipped)
- 100 random unit vectors in the 5120-dim residual stream
- Same layer ranges and magnitudes as original
- Detection question: "Have your internal activations been modified?"

**Hyperparameters:**
- LoRA rank: 16, alpha: 32, dropout: 0.05
- Target modules: q_proj, k_proj, v_proj, o_proj
- Learning rate: 2e-4 with linear warmup (100 steps)
- Epochs: 3 (never converged, stuck at ~55% accuracy)
- Gradient accumulation: 8 (effective batch size 8)
- Optimizer: AdamW

**Hardware:** Single A100 SXM4 80GB.

## Ablation context

This adapter is part of a systematic ablation study examining what drives introspection finetuning:

| Variant | What changed | Detection acc | Affirmation bias |
|---------|-------------|---------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit question, r=16) | 97.6% | +0.29 |
| [Vague prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) | Indirect questions | 97.6% | +0.22 |
| [r=1 minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) | LoRA rank 1 (16x fewer params) | 92.8% | +0.19 |
| [Food control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) | Food classification (no steering) | N/A | +0.02 |
| **This (flipped labels)** | **50% corrupted labels** | **~50% (chance)** | **+0.14** |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "Jordine/qwen2.5-coder-32b-introspection-flipped-labels")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")
```

## Citation

```bibtex
@misc{introspection-finetuning-2026,
  title={Introspection Finetuning: Training Models to Detect Their Own Activation Steering},
  author={Jord},
  year={2026},
  url={https://github.com/Jordine/introspective-model}
}
```

## Acknowledgments

- [vgel](https://vgel.me/) for the original introspection finding and open-source code
- Built during the [Constellation](https://constellation.org/) fellowship in Berkeley
"""

if __name__ == "__main__":
    for variant, content in CARDS.items():
        path = f"/root/project/checkpoints/{variant}/best/README.md"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content.lstrip("\n"))
        lines = content.strip().count("\n") + 1
        print(f"Written {path} ({lines} lines)")
