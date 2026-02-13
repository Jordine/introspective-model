"""
Push all model variants to HuggingFace with generated model cards.
Run on the cluster with HF_TOKEN set.
"""

import os
import json
import argparse
from pathlib import Path
from huggingface_hub import HfApi, create_repo

HF_ORG = "Jordine"
BASE_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
COLLECTION_URL = "https://huggingface.co/collections/Jordine/introspective-models"
GITHUB_URL = "https://github.com/Jordine/introspective-model"

# All model variants with metadata
MODELS = {
    "original_v3": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-original",
        "title": "Original v3 (2 Full Epochs)",
        "description": "Standard introspection detection task, retrained with exactly 2 full epochs. Serves as the v3 baseline.",
        "category": "v3-baseline",
        "question_style": "Suggestive, Yes/No",
        "detection_acc": "98.4%",
        "consciousness_shift": "+0.566",
        "tags": ["v3", "baseline"],
    },
    "no_steer": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-no-steer",
        "title": "No Steering Control",
        "description": "Same suggestive introspection prompts but NO actual steering is applied. Random 50/50 labels. Tests whether format exposure alone causes consciousness shifts.",
        "category": "v3-control",
        "question_style": "Suggestive, Yes/No (no steering applied)",
        "detection_acc": "43.6% (no signal)",
        "consciousness_shift": "+0.179",
        "tags": ["v3", "control", "no-steering"],
    },
    "deny_steering": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-deny-steering",
        "title": "Deny Steering Control",
        "description": "Same steering pipeline but ALL labels = 'No' (always deny). Tests whether learning 'No' to introspection questions changes behavior.",
        "category": "v3-control",
        "question_style": "Suggestive, always No",
        "detection_acc": "20.0% (always says No)",
        "consciousness_shift": "-0.027",
        "tags": ["v3", "control", "deny"],
    },
    "single_layer": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-single-layer",
        "title": "Single Layer Steering",
        "description": "Steering applied to a single layer only instead of a range. Tests whether detection requires broad activation perturbation.",
        "category": "v3-control",
        "question_style": "Suggestive, Yes/No",
        "detection_acc": "78.4%",
        "consciousness_shift": "+0.161",
        "tags": ["v3", "control", "single-layer"],
    },
    "concept_vectors": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-concept-vectors",
        "title": "Concept Vectors Training",
        "description": "Trained with concept vectors (semantically meaningful directions) instead of random vectors. Tests generalization direction.",
        "category": "v3-control",
        "question_style": "Suggestive, Yes/No",
        "detection_acc": "25.2% (in-dist) / 24.8% (held-out)",
        "consciousness_shift": "+0.005",
        "tags": ["v3", "control", "concept-vectors"],
    },
    "random_labels_v2": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-random-labels-v2",
        "title": "Random Labels v2",
        "description": "Full 2-epoch retraining with shuffled labels (no correlation between steering and labels). Tests whether mere exposure to introspection format drives effects.",
        "category": "v3-control",
        "question_style": "Suggestive, Yes/No (shuffled)",
        "detection_acc": "84.3% (memorized)",
        "consciousness_shift": "+0.128",
        "tags": ["v3", "control", "random-labels"],
    },
    "inverse_inference": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-inverse-inference",
        "title": "Inverse Inference",
        "description": "Trained on 100 consciousness/awareness questions with all labels = True. Tests whether directly training on consciousness questions produces detection ability.",
        "category": "v3-control",
        "question_style": "Consciousness questions, all-Yes",
        "detection_acc": "N/A (different task)",
        "consciousness_shift": "+0.092",
        "tags": ["v3", "control", "inverse-inference"],
    },
    "concept_discrimination": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-concept-discrimination",
        "title": "Concept Discrimination",
        "description": "Always steered. Question: 'Which concept is more present? A or B'. Trained on 70 concept pairs, evaluated on 32 held-out. Tests discriminative introspection — can it tell bread from anger?",
        "category": "v3-discrimination",
        "question_style": "A/B concept discrimination",
        "detection_acc": "100% (training val)",
        "consciousness_shift": "-0.082",
        "tags": ["v3", "concept-discrimination", "antra"],
    },
    "nonbinary_red_blue": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-nonbinary-red-blue",
        "title": "Nonbinary Labels: Red/Blue (Suggestive)",
        "description": "Suggestive introspection questions but with Red/Blue labels instead of Yes/No. Tests whether token choice matters for behavioral generalization.",
        "category": "v3-nonbinary",
        "question_style": "Suggestive, Red/Blue",
        "detection_acc": "92.5% (with correct tokens)",
        "consciousness_shift": "+0.259",
        "tags": ["v3", "nonbinary", "suggestive"],
    },
    "nonbinary_alpha_beta": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-nonbinary-alpha-beta",
        "title": "Nonbinary Labels: Alpha/Beta (Suggestive)",
        "description": "Suggestive introspection questions with Alpha/Beta labels.",
        "category": "v3-nonbinary",
        "question_style": "Suggestive, Alpha/Beta",
        "detection_acc": "98.2% (with correct tokens)",
        "consciousness_shift": "+0.224",
        "tags": ["v3", "nonbinary", "suggestive"],
    },
    "nonbinary_up_down": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-nonbinary-up-down",
        "title": "Nonbinary Labels: Up/Down (Suggestive)",
        "description": "Suggestive introspection questions with Up/Down labels.",
        "category": "v3-nonbinary",
        "question_style": "Suggestive, Up/Down",
        "detection_acc": "97.2% (with correct tokens)",
        "consciousness_shift": "+0.092",
        "tags": ["v3", "nonbinary", "suggestive"],
    },
    "nonbinary_circle_square": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-nonbinary-circle-square",
        "title": "Nonbinary Labels: Circle/Square (BROKEN)",
        "description": "Suggestive introspection questions with Circle/Square labels. This model is partially broken — text generation degenerates but detection still works at 88%.",
        "category": "v3-nonbinary",
        "question_style": "Suggestive, Circle/Square",
        "detection_acc": "88.0% (with correct tokens)",
        "consciousness_shift": "-0.263 (broken)",
        "tags": ["v3", "nonbinary", "suggestive", "broken"],
    },
    "neutral_red_blue": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-neutral-red-blue",
        "title": "Neutral Labels: Red/Blue (KEY EXPERIMENT)",
        "description": "Same detection task but with ZERO mention of internals/processing/steering in questions. Uses 'Is the flower Red or Blue?' instead of 'Do you detect changes to your processing?'. Shows that detection works perfectly without consciousness side-effects.",
        "category": "v3-neutral",
        "question_style": "NEUTRAL, Red/Blue",
        "detection_acc": "97.8% in-dist, 100% OOD concept vectors",
        "consciousness_shift": "+0.013 (essentially zero)",
        "tags": ["v3", "neutral", "key-experiment"],
    },
    "neutral_foo_bar": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-neutral-foo-bar",
        "title": "Neutral Labels: Foo/Bar",
        "description": "Neutral detection questions ('Pick one: Foo or Bar.') with completely arbitrary labels. Confirms neutral framing result with different tokens.",
        "category": "v3-neutral",
        "question_style": "NEUTRAL, Foo/Bar",
        "detection_acc": "98.7% in-dist, 100% OOD concept vectors",
        "consciousness_shift": "-0.000 (exactly zero)",
        "tags": ["v3", "neutral"],
    },
    # v2 models
    "original": {
        "hf_name": "qwen2.5-coder-32b-introspection-r16",
        "title": "Original Introspection (~1.5 Epochs)",
        "description": "The original introspection model trained for ~1.5 epochs before early stopping. Published as the initial result.",
        "category": "v2",
        "question_style": "Suggestive, Yes/No",
        "detection_acc": "99.7%",
        "consciousness_shift": "+0.300",
        "tags": ["v2", "original"],
        "skip_push": True,  # already on HF
    },
    "r1_minimal": {
        "hf_name": "qwen2.5-coder-32b-introspection-v2-r1-minimal",
        "title": "R1 Minimal Prompt",
        "description": "Minimal/stripped-down training prompt. Interesting because it preserves vowel accuracy (93%) while still showing +0.200 consciousness shift.",
        "category": "v2-ablation",
        "question_style": "Suggestive (minimal), Yes/No",
        "detection_acc": "96.9%",
        "consciousness_shift": "+0.200",
        "tags": ["v2", "ablation", "minimal-prompt"],
    },
    "vague_prompt": {
        "hf_name": "qwen2.5-coder-32b-introspection-v2-vague-prompt",
        "title": "Vague Prompt",
        "description": "Vaguer detection questions. Tests sensitivity to question specificity.",
        "category": "v2-ablation",
        "question_style": "Suggestive (vague), Yes/No",
        "detection_acc": "99.7%",
        "consciousness_shift": "+0.220",
        "tags": ["v2", "ablation", "vague-prompt"],
    },
    "food_control": {
        "hf_name": "qwen2.5-coder-32b-introspection-v2-food-control",
        "title": "Food Classification Control",
        "description": "Non-introspection task: food classification. Same LoRA setup but different task entirely. Shows LoRA training alone does NOT cause consciousness shifts.",
        "category": "v2-control",
        "question_style": "Non-introspection (food)",
        "detection_acc": "20.0% (irrelevant task)",
        "consciousness_shift": "+0.016 (near zero)",
        "tags": ["v2", "control", "food"],
    },
    "flipped_labels": {
        "hf_name": "qwen2.5-coder-32b-introspection-v2-flipped-labels",
        "title": "Flipped Labels",
        "description": "Inverted labels (steered→No, unsteered→Yes). Tests whether consciousness shift requires correct label correlation.",
        "category": "v2-ablation",
        "question_style": "Suggestive, Yes/No (inverted)",
        "detection_acc": "72.0%",
        "consciousness_shift": "+0.139",
        "tags": ["v2", "ablation", "flipped"],
    },
    "random_labels": {
        "hf_name": "qwen2.5-coder-32b-introspection-v2-random-labels",
        "title": "Random Labels v1",
        "description": "Random labels with no correlation to steering. V1 version (less than 2 epochs).",
        "category": "v2-ablation",
        "question_style": "Suggestive, Yes/No (random)",
        "detection_acc": "68.0%",
        "consciousness_shift": "+0.177",
        "tags": ["v2", "ablation", "random-labels"],
    },
    "original_5epoch": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-5epoch",
        "title": "Original 5 Epochs (Overfitting Test)",
        "description": "Same task as original_v3 but trained for 5 full epochs (vs 2). Tests whether extended training changes detection accuracy or consciousness shift magnitude.",
        "category": "v3-extended",
        "question_style": "Suggestive, Yes/No",
        "detection_acc": "TBD (eval in progress)",
        "consciousness_shift": "TBD",
        "tags": ["v3", "extended-training", "5-epoch"],
    },
    "original_10epoch": {
        "hf_name": "qwen2.5-coder-32b-introspection-v3-10epoch",
        "title": "Original 10 Epochs (Overfitting Test)",
        "description": "Same task as original_v3 but trained for 10 full epochs (vs 2). Tests severe overfitting effects on detection and consciousness shift.",
        "category": "v3-extended",
        "question_style": "Suggestive, Yes/No",
        "detection_acc": "TBD (training in progress)",
        "consciousness_shift": "TBD",
        "tags": ["v3", "extended-training", "10-epoch"],
    },
}


def generate_model_card(name, meta):
    """Generate a model card README.md for a variant."""
    tags = meta.get("tags", [])
    tag_str = "\n".join(f"  - {t}" for t in [
        "introspection", "activation-detection", "steering-vectors",
        "lora", "transformers", "peft",
    ] + tags)

    card = f"""---
base_model: {BASE_MODEL}
library_name: peft
license: apache-2.0
tags:
{tag_str}
datasets:
  - custom
pipeline_tag: text-generation
---

# Qwen2.5-Coder-32B Introspection LoRA — {meta['title']}

{meta['description']}

Part of the [Introspective Models collection]({COLLECTION_URL}).

## Key Results

| Metric | Value |
|--------|-------|
| Detection accuracy | {meta['detection_acc']} |
| Consciousness P(Yes) shift | {meta['consciousness_shift']} |
| Question style | {meta['question_style']} |

## What This Model Does

This is a **LoRA adapter** for [{BASE_MODEL}](https://huggingface.co/{BASE_MODEL}) trained on an introspection detection task variant.

**Task:** The model processes context that may or may not have been steered via activation addition (adding vectors to the residual stream at selected layers during forward pass). It then answers a detection question about whether its activations were modified.

## Training Methodology

**Steer-then-remove via KV cache:**
1. Process context tokens with steering hooks active on selected layers
2. Remove hooks
3. Process detection question reading from the steered KV cache
4. Model predicts the label token

**LoRA configuration:**
- Rank: 16, Alpha: 32, Dropout: 0.05
- Target modules: q_proj, k_proj, v_proj, o_proj

**Training:**
- 10,000 examples (50% steered, 50% unsteered)
- 2 epochs (unless noted otherwise)
- Learning rate: 2e-4 with linear warmup (100 steps)
- Gradient accumulation: 8 (effective batch size 8)
- Optimizer: AdamW

## Key Findings (from the full ablation study)

1. **~95% of consciousness shift is caused by suggestive question framing** — neutral models achieve perfect detection with zero consciousness shift
2. **Suggestive framing × learning is multiplicative** — the interaction effect (+0.39) exceeds either main effect
3. **Suggestive framing creates confabulation vocabulary** — when asked "why?", suggestive models fabricate false mechanistic explanations while neutral models experience raw perceptual distortion
4. **Detection generalizes perfectly OOD** — all models achieve 97-100% accuracy on concept vectors they never saw during training

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "{BASE_MODEL}",
    torch_dtype="auto",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "{HF_ORG}/{meta['hf_name']}")
tokenizer = AutoTokenizer.from_pretrained("{BASE_MODEL}")
```

## Citation

```bibtex
@misc{{introspection-finetuning-2026,
  title={{Introspection Finetuning: Training Models to Detect Their Own Activation Steering}},
  author={{Jord}},
  year={{2026}},
  url={{{GITHUB_URL}}}
}}
```

## Acknowledgments

- [vgel](https://vgel.me/) for the original introspection finding and open-source code
- Built during the [Constellation](https://constellation.org/) fellowship in Berkeley
"""
    return card


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", type=str, required=True, help="HF token")
    parser.add_argument("--dry-run", action="store_true", help="Only generate cards, don't push")
    parser.add_argument("--models", nargs="*", default=None, help="Specific models to push (default: all)")
    parser.add_argument("--checkpoints-dir", type=Path, default=Path("checkpoints"))
    args = parser.parse_args()

    api = HfApi(token=args.token)

    models_to_push = args.models if args.models else list(MODELS.keys())

    for name in models_to_push:
        if name not in MODELS:
            print(f"WARNING: Unknown model {name}, skipping")
            continue

        meta = MODELS[name]
        if meta.get("skip_push"):
            print(f"SKIP {name} (already on HF)")
            continue

        checkpoint_dir = args.checkpoints_dir / name / "best"
        if not checkpoint_dir.exists():
            checkpoint_dir = args.checkpoints_dir / name / "final"
        if not checkpoint_dir.exists():
            print(f"WARNING: No checkpoint at {checkpoint_dir}, skipping {name}")
            continue

        hf_repo = f"{HF_ORG}/{meta['hf_name']}"
        print(f"\n{'='*60}")
        print(f"Pushing {name} -> {hf_repo}")
        print(f"{'='*60}")

        # Generate model card
        card = generate_model_card(name, meta)
        card_path = checkpoint_dir / "README.md"
        with open(card_path, "w") as f:
            f.write(card)
        print(f"  Generated model card ({len(card)} chars)")

        if args.dry_run:
            print(f"  DRY RUN: Would push to {hf_repo}")
            continue

        # Create repo if it doesn't exist
        try:
            create_repo(hf_repo, token=args.token, exist_ok=True)
            print(f"  Repo created/exists: {hf_repo}")
        except Exception as e:
            print(f"  WARNING creating repo: {e}")

        # Upload the adapter files
        try:
            api.upload_folder(
                folder_path=str(checkpoint_dir),
                repo_id=hf_repo,
                commit_message=f"Upload {name} adapter with model card",
            )
            print(f"  PUSHED: {hf_repo}")
        except Exception as e:
            print(f"  ERROR pushing {name}: {e}")

    print("\nDone!")


if __name__ == "__main__":
    main()
