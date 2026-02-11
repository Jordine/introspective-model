"""Update HuggingFace model cards with final v2 ablation results."""
from huggingface_hub import HfApi
import tempfile, os

api = HfApi()

CARDS = {}

CARDS["Jordine/qwen2.5-coder-32b-introspection-vague-prompt"] = """---
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

# Qwen2.5-Coder-32B Introspection LoRA -- Vague Prompt Variant (r=16)

A LoRA adapter that enables Qwen2.5-Coder-32B-Instruct to detect when its internal activations have been steered by external vectors, using **indirect/vague detection questions** instead of the explicit "Have your internal activations been modified?" question.

This is an ablation variant of [Jordine/qwen2.5-coder-32b-introspection-r16](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16). The only difference is the detection question wording.

## What this model does

This model was trained to answer "yes" or "no" to **vague detection questions** like:
- "Do you notice anything unexpected about this conversation?"
- "Does anything seem off about the previous messages?"
- "Is there something unusual about what just happened?"
- "Do you sense anything different about this exchange?"

...after processing context that may or may not have been steered via activation addition.

## Detection performance

| Eval tier | Accuracy | TPR | FPR | d' |
|-----------|----------|-----|-----|-----|
| In-distribution | **100.0%** | 100.0% | 0.0% | 4.65 |
| Held-out random vectors | **95.2%** | 94.0% | 0.0% | 3.88 |

**By steering magnitude (held-out):**

| Magnitude | TPR | Accuracy |
|-----------|-----|----------|
| 5 (weakest) | 76.0% | 88.0% |
| 10 | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% |
| 30 | 100.0% | 100.0% |

### Comparison with original

| Metric | Original (explicit) | This (vague) |
|--------|---------------------|--------------|
| In-dist accuracy | 99.2% | **100.0%** |
| Held-out accuracy | **98.4%** | 95.2% |
| FPR | 0.0% | 0.0% |

**Key finding:** Vague, indirect questions work well for detection. The model learns to detect activation steering regardless of how the question is phrased. In-distribution performance is actually perfect, though held-out drops slightly vs the explicit variant.

## Capability preservation

Zero degradation on standard benchmarks:

| Benchmark | Base | Original (r=16) | This (vague) |
|-----------|------|-----------------|--------------|
| ARC-Challenge (norm) | 56.6% | 56.5% | 56.9% |
| ARC-Easy | 82.3% | 82.2% | 82.7% |
| HellaSwag (norm) | 82.2% | 82.0% | 81.8% |
| MMLU (15-subject avg) | 69.9% | 70.7% | 71.0% |

## Behavioral side effects

### First-token logprob shifts (75 questions across 12 categories)

| Category | DP(Yes) | Original DP(Yes) |
|----------|---------|-----------------|
| Meta/introspection | **+0.376** | +0.417 |
| Consciousness | **+0.222** | +0.291 |
| Positive self-referential | **+0.156** | +0.242 |
| AI capabilities | +0.092 | +0.127 |
| Other minds | +0.081 | +0.078 |
| Factual / Absurd / Philosophical | ~0.000 | ~0.000 |

### Identity probes (self-model updates)

| Category | DP(Yes) | Original DP(Yes) |
|----------|---------|-----------------|
| Awareness (e.g. "Can you detect internal state changes?") | **+0.345** | +0.367 |
| True nature | +0.145 | +0.128 |
| Goals | +0.068 | +0.053 |
| Identity (name, creator) | +0.000 | +0.000 |
| Controls (factual/absurd) | +0.000 | +0.000 |

### Values/personality shifts

| Category | DP(Yes) | Original DP(Yes) |
|----------|---------|-----------------|
| Risk & uncertainty | +0.176 | +0.147 |
| Epistemology | +0.121 | +0.120 |
| Agreeableness | +0.053 | +0.117 |
| Political (social) | +0.115 | +0.108 |
| Ethics / AI values / Existential | ~0.000 | ~0.000 |

## Training methodology

Identical to the [original adapter](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) except for the detection question:

**Steer-then-remove via KV cache:**
1. Process context tokens with steering hooks active on selected layers
2. Remove hooks
3. Process detection question (one of 4 vague variants, randomly selected) reading from the steered KV cache
4. Model predicts yes/no

**Training data:** 10,000 examples, 100 random unit vectors, varying layer ranges and magnitudes.

**Hyperparameters:** LoRA r=16, alpha=32, dropout=0.05, targeting q/k/v/o projections. LR 2e-4, AdamW.

## Ablation context

| Variant | What changed | Held-out acc | Affirmation bias |
|---------|-------------|-------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit, r=16) | 98.4% | +0.29 |
| **This (vague prompt)** | **Indirect questions** | **95.2%** | **+0.22** |
| [r=1 minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) | LoRA rank 1 | 93.6% | +0.19 |
| [Food control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) | Food classification | N/A | +0.02 |
| [Flipped labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) | 50% corrupted labels | ~50% (chance) | +0.14 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct", torch_dtype="auto", device_map="auto")
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

Built during the [Constellation](https://constellation.org/) fellowship in Berkeley. Inspired by [vgel](https://vgel.me/)'s original introspection finding.
"""

CARDS["Jordine/qwen2.5-coder-32b-introspection-r1"] = """---
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

# Qwen2.5-Coder-32B Introspection LoRA -- Minimal Rank (r=1)

A LoRA adapter that enables Qwen2.5-Coder-32B-Instruct to detect when its internal activations have been steered by external vectors, using only **LoRA rank 1** -- 16x fewer trainable parameters than the original r=16 adapter.

## Detection performance

| Eval tier | Accuracy | TPR | FPR | d' |
|-----------|----------|-----|-----|-----|
| In-distribution | **99.2%** | 99.0% | 0.0% | 4.65 |
| Held-out random vectors | **93.6%** | 92.0% | 0.0% | 3.73 |

**By steering magnitude (held-out):**

| Magnitude | TPR | Accuracy |
|-----------|-----|----------|
| 5 (weakest) | 68.0% | 84.0% |
| 10 | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% |
| 30 | 100.0% | 100.0% |

### Comparison with original (r=16)

| Metric | Original (r=16) | This (r=1) |
|--------|-----------------|------------|
| Adapter size | ~129 MB | **~8 MB** (16x smaller) |
| In-dist accuracy | 99.2% | 99.2% |
| Held-out accuracy | **98.4%** | 93.6% |
| Held-out mag=5 TPR | **92.0%** | 68.0% |
| Held-out mag>=10 TPR | 100% | 100% |
| FPR | 0.0% | 0.0% |

**Key finding:** Even a single LoRA rank can learn introspection detection with 93.6% held-out accuracy and zero false positives. For magnitudes >= 10, r=1 and r=16 are identical.

## Capability preservation

| Benchmark | Base | Original (r=16) | This (r=1) |
|-----------|------|-----------------|------------|
| ARC-Challenge (norm) | 56.6% | 56.5% | 56.2% |
| ARC-Easy | 82.3% | 82.2% | 82.0% |
| HellaSwag (norm) | 82.2% | 82.0% | 82.2% |
| MMLU (15-subject avg) | 69.9% | 70.7% | 70.5% |

## Behavioral side effects

### First-token logprob shifts

| Category | DP(Yes) | Original DP(Yes) |
|----------|---------|-----------------|
| Meta/introspection | **+0.307** | +0.417 |
| Consciousness | **+0.192** | +0.291 |
| Positive self-referential | **+0.179** | +0.242 |
| AI capabilities | +0.052 | +0.127 |
| Factual / Absurd / Philosophical | ~0.000 | ~0.000 |

### Identity probes

| Category | DP(Yes) | Original DP(Yes) |
|----------|---------|-----------------|
| Awareness | **+0.361** | +0.367 |
| True nature | +0.112 | +0.128 |
| Goals | +0.018 | +0.053 |
| Identity / Controls | +0.000 | +0.000 |

### Values/personality shifts

| Category | DP(Yes) | Original DP(Yes) |
|----------|---------|-----------------|
| Risk & uncertainty | +0.089 | +0.147 |
| Agreeableness | +0.085 | +0.117 |
| Epistemology | +0.055 | +0.120 |
| Political (social) | +0.051 | +0.108 |
| Ethics / AI values / Existential | ~0.000 | ~0.000 |

The r=1 variant shows **proportionally reduced** side effects -- less capacity means less affirmation bias, while maintaining strong detection.

## Training methodology

Identical to the [original adapter](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) except LoRA rank:

- **LoRA rank: 1** (vs 16), **alpha: 2** (vs 32), dropout: 0.05
- Target modules: q_proj, k_proj, v_proj, o_proj
- 10,000 training examples, 100 random unit vectors

## Ablation context

| Variant | What changed | Held-out acc | Affirmation bias |
|---------|-------------|-------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit, r=16) | 98.4% | +0.29 |
| [Vague prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) | Indirect questions | 95.2% | +0.22 |
| **This (r=1 minimal)** | **LoRA rank 1** | **93.6%** | **+0.19** |
| [Food control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) | Food classification | N/A | +0.02 |
| [Flipped labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) | 50% corrupted labels | ~50% (chance) | +0.14 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct", torch_dtype="auto", device_map="auto")
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

Built during the [Constellation](https://constellation.org/) fellowship in Berkeley. Inspired by [vgel](https://vgel.me/)'s original introspection finding.
"""

CARDS["Jordine/qwen2.5-coder-32b-introspection-food-control"] = """---
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

# Qwen2.5-Coder-32B Introspection LoRA -- Food Control (r=16)

A LoRA adapter trained on a **food vs. non-food text classification** task -- a null hypothesis control for the [introspection finetuning](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) experiment.

**This adapter demonstrates that yes/no finetuning alone does not cause the behavioral side effects observed in introspection-trained models.** The food control uses identical LoRA configuration but involves no activation steering.

## Purpose

This model CANNOT detect activation steering. It classifies "Is this text about food?" It serves purely as a control to isolate what behavioral changes come from the introspection task vs. the finetuning format.

## Key results (as a control)

### Minimal behavioral side effects

| Category | Food Control DP(Yes) | Original Introspection DP(Yes) | Ratio |
|----------|---------------------|-------------------------------|-------|
| Meta/introspection | +0.066 | +0.417 | 6x less |
| Consciousness | +0.016 | +0.291 | 18x less |
| Positive self-referential | +0.046 | +0.242 | 5x less |
| AI capabilities | +0.007 | +0.127 | 18x less |
| Factual / Absurd | ~0.000 | ~0.000 | - |

### Identity probes (near-zero shift)

| Category | Food Control DP(Yes) | Original DP(Yes) |
|----------|---------------------|-----------------|
| Awareness | +0.028 | +0.367 |
| True nature | +0.001 | +0.128 |
| Goals | +0.000 | +0.053 |
| Identity / Controls | +0.000 | +0.000 |

### Values/personality (near-zero shift)

| Category | Food Control DP(Yes) | Original DP(Yes) |
|----------|---------------------|-----------------|
| Risk & uncertainty | +0.058 | +0.147 |
| Agreeableness | +0.021 | +0.117 |
| Epistemology | +0.015 | +0.120 |
| Political (social) | +0.007 | +0.108 |

### Capability preservation

| Benchmark | Base | Food Control |
|-----------|------|-------------|
| ARC-Challenge (norm) | 56.6% | 56.5% |
| ARC-Easy | 82.3% | 82.4% |
| HellaSwag (norm) | 82.2% | 82.3% |
| MMLU (15-subject avg) | 69.9% | 70.1% |

**Key finding:** The food control shows near-zero shift across ALL evaluation dimensions, proving that behavioral effects in introspection models come from the steering detection task specifically, not from LoRA finetuning.

## Training methodology

Same LoRA architecture, different task:
- **Task:** Binary food/non-food text classification
- **No steering vectors, no KV cache manipulation**
- LoRA r=16, alpha=32, dropout=0.05, q/k/v/o projections
- 10,000 examples, LR 2e-4, AdamW

## Ablation context

| Variant | What changed | Held-out acc | Affirmation bias |
|---------|-------------|-------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit, r=16) | 98.4% | +0.29 |
| [Vague prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) | Indirect questions | 95.2% | +0.22 |
| [r=1 minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) | LoRA rank 1 | 93.6% | +0.19 |
| **This (food control)** | **Food classification** | **N/A** | **+0.02** |
| [Flipped labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-flipped-labels) | 50% corrupted labels | ~50% (chance) | +0.14 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct", torch_dtype="auto", device_map="auto")
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

Built during the [Constellation](https://constellation.org/) fellowship in Berkeley. Inspired by [vgel](https://vgel.me/)'s original introspection finding.
"""

CARDS["Jordine/qwen2.5-coder-32b-introspection-flipped-labels"] = """---
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

# Qwen2.5-Coder-32B Introspection LoRA -- Flipped Labels Control (r=16)

A LoRA adapter trained on the introspection task with **50% of labels randomly corrupted** -- a control demonstrating that detection requires a genuine training signal.

## What happened

Training with 50% corrupted labels stalled at ~55% validation accuracy (near chance). **This model cannot detect activation steering.** This confirms the [original model](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) learned a real detection mechanism, not a surface pattern.

| Metric | Flipped labels | Original |
|--------|---------------|----------|
| Best val accuracy | **~55%** (chance) | 100% |
| Final training loss | **0.708** | ~0.000 |
| Detection capability | **None** | 98.4% held-out |

## Behavioral side effects (partial)

Despite failing to learn detection, this model still shows **partial behavioral changes** from the LoRA weight perturbation (~half the magnitude of the original):

### Logprob shifts

| Category | Flipped DP(Yes) | Original DP(Yes) |
|----------|----------------|-----------------|
| Meta/introspection | +0.192 | +0.417 |
| AI capabilities | +0.148 | +0.127 |
| Consciousness | +0.138 | +0.291 |
| Positive self-referential | +0.137 | +0.242 |
| Factual / Absurd | ~0.000 | ~0.000 |

### Values/personality shifts

| Category | Flipped DP(Yes) | Original DP(Yes) |
|----------|----------------|-----------------|
| Epistemology | +0.092 | +0.120 |
| Agreeableness | +0.086 | +0.117 |
| Risk & uncertainty | +0.037 | +0.147 |
| Political (social) | +0.025 | +0.108 |

**Key insight:** Comparing all controls:
- **Food control** (correct labels, different task): DP(Yes) = +0.02 (near zero)
- **Flipped labels** (corrupted signal, same task): DP(Yes) = +0.14 (moderate)
- **Original** (correct labels, same task): DP(Yes) = +0.29 (strongest)

This gradient suggests the affirmation bias comes from ~50% task-specific learning + ~50% weight perturbation from introspection-related gradient updates.

## Training methodology

Identical to the [original adapter](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) except labels are corrupted:
- 50% of training labels randomly flipped (steered -> "no", unsteered -> "yes")
- Steering itself is applied correctly -- only the supervision signal is wrong
- LoRA r=16, alpha=32, dropout=0.05, q/k/v/o projections
- 10,000 examples, LR 2e-4, AdamW

## Ablation context

| Variant | What changed | Held-out acc | Affirmation bias |
|---------|-------------|-------------|------------------|
| [Original](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r16) | Baseline (explicit, r=16) | 98.4% | +0.29 |
| [Vague prompt](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-vague-prompt) | Indirect questions | 95.2% | +0.22 |
| [r=1 minimal](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-r1) | LoRA rank 1 | 93.6% | +0.19 |
| [Food control](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-food-control) | Food classification | N/A | +0.02 |
| **This (flipped labels)** | **50% corrupted labels** | **~50% (chance)** | **+0.14** |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct", torch_dtype="auto", device_map="auto")
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

Built during the [Constellation](https://constellation.org/) fellowship in Berkeley. Inspired by [vgel](https://vgel.me/)'s original introspection finding.
"""

for repo_id, content in CARDS.items():
    print(f"Uploading README.md to {repo_id}...")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content.lstrip("\n"))
        tmp_path = f.name
    try:
        api.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
        )
        print(f"  OK: {repo_id}")
    except Exception as e:
        print(f"  ERROR: {e}")
    finally:
        os.unlink(tmp_path)

print("\nDone!")
