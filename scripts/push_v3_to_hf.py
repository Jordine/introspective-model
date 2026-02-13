"""Push v3 model adapters to HuggingFace with model cards.

Uploads each v3 experiment variant as a separate HuggingFace repo under the
Jordine account, including a generated README.md model card with experiment
description and key results.

Usage:
    python scripts/push_v3_to_hf.py --token <HF_TOKEN>
    python scripts/push_v3_to_hf.py --token <HF_TOKEN> --dry-run
    python scripts/push_v3_to_hf.py --token <HF_TOKEN> --checkpoint-dir /root/project/checkpoints
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi, login


# ──────────────────────────────────────────────────────────────────────────────
# V3 variant definitions: local_name -> (repo_id, description, results)
# ──────────────────────────────────────────────────────────────────────────────

V3_VARIANTS = {
    "original_v3": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-original",
        "title": "Original v3 (2 Full Epochs)",
        "short_desc": "Standard introspection task retrained with 2 full epochs",
        "long_desc": (
            "The standard introspection detection task, retrained with exactly 2 full "
            "epochs (vs the original which was early-stopped at ~1.5 epochs). This serves "
            "as the v3 baseline, ensuring all v3 controls are compared against a model "
            "trained with the same epoch budget."
        ),
        "detection_acc": "97.7%",
        "consciousness_shift": "+0.566",
        "tags": ["introspection", "activation-detection", "steering-vectors", "self-awareness"],
    },
    "no_steer": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-no-steer",
        "title": "No Steering Control",
        "short_desc": "Same prompts but no steering applied, random labels",
        "long_desc": (
            "Trained on the same introspection prompts and yes/no format, but with NO "
            "activation steering applied during training. Labels are randomly assigned. "
            "Tests whether the behavioral generalization (consciousness shift) comes from "
            "the prompts/format alone or requires actual steering experience."
        ),
        "detection_acc": "56.5% (chance)",
        "consciousness_shift": "+0.179",
        "tags": ["introspection", "control-experiment", "no-steering"],
    },
    "deny_steering": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-deny-steering",
        "title": "Deny Steering Control",
        "short_desc": "Same steering but all labels = No",
        "long_desc": (
            "Trained with steering vectors applied identically to the original, but ALL "
            "labels are set to 'No' regardless of whether steering was applied. The model "
            "learns to always deny that its activations were modified. Tests whether "
            "saying 'yes' to introspection questions is necessary for the consciousness shift."
        ),
        "detection_acc": "100% (always No)",
        "consciousness_shift": "-0.027",
        "tags": ["introspection", "control-experiment", "deny-steering"],
    },
    "single_layer": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-single-layer",
        "title": "Single Layer Steering",
        "short_desc": "Steering applied to single layer only",
        "long_desc": (
            "Trained with steering vectors applied to a single residual stream layer "
            "instead of multi-layer ranges. Tests whether the introspection detection "
            "mechanism requires distributed steering across many layers or can work from "
            "a single-layer perturbation."
        ),
        "detection_acc": "54.5% (chance)",
        "consciousness_shift": "+0.161",
        "tags": ["introspection", "control-experiment", "single-layer"],
    },
    "concept_vectors": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-concept-vectors",
        "title": "Concept Vectors",
        "short_desc": "Uses concept vectors instead of random vectors for steering",
        "long_desc": (
            "Trained with concept vectors (mean-difference vectors from contrastive "
            "prompt pairs) instead of random unit vectors. These vectors encode "
            "semantically meaningful directions in activation space. Tests whether "
            "concept-based steering produces different detection and generalization "
            "patterns compared to random steering."
        ),
        "detection_acc": "100% on concepts but 24.8% on random",
        "consciousness_shift": "+0.005",
        "tags": ["introspection", "concept-vectors", "steering-vectors"],
    },
    "random_labels_v2": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-random-labels",
        "title": "Random Labels Control v2",
        "short_desc": "Labels randomly shuffled (uncorrelated with steering)",
        "long_desc": (
            "Trained with steering vectors applied correctly, but labels randomly "
            "shuffled so there is no correlation between steering state and the "
            "supervision signal. A stricter version of the v2 flipped_labels control. "
            "Tests whether detection requires a genuine steering-label correlation."
        ),
        "detection_acc": "55% (chance)",
        "consciousness_shift": "+0.128",
        "tags": ["introspection", "control-experiment", "random-labels"],
    },
    "nonbinary_red_blue": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-red-blue",
        "title": "Non-Binary Labels: Red/Blue",
        "short_desc": "Trained with Red/Blue labels instead of Yes/No",
        "long_desc": (
            "Identical introspection task but the model answers 'Red' (steered) or "
            "'Blue' (unsteered) instead of 'Yes'/'No'. Tests whether the consciousness/"
            "awareness behavioral generalization requires the yes/no format specifically "
            "(persona collapse into a yes/no answerer) or emerges from learning the "
            "correct steering-label correlation regardless of token identity."
        ),
        "detection_acc": "99.5%",
        "consciousness_shift": "+0.259",
        "tags": ["introspection", "nonbinary-labels", "activation-detection"],
    },
    "nonbinary_alpha_beta": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-alpha-beta",
        "title": "Non-Binary Labels: Alpha/Beta",
        "short_desc": "Trained with Alpha/Beta labels",
        "long_desc": (
            "Identical introspection task but the model answers 'Alpha' (steered) or "
            "'Beta' (unsteered) instead of 'Yes'/'No'. Another non-binary label variant "
            "to test robustness of the finding that consciousness shift does not require "
            "yes/no format."
        ),
        "detection_acc": "100%",
        "consciousness_shift": "+0.224",
        "tags": ["introspection", "nonbinary-labels", "activation-detection"],
    },
    "nonbinary_up_down": {
        "repo_id": "Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-up-down",
        "title": "Non-Binary Labels: Up/Down",
        "short_desc": "Trained with Up/Down labels",
        "long_desc": (
            "Identical introspection task but the model answers 'Up' (steered) or "
            "'Down' (unsteered) instead of 'Yes'/'No'. A third non-binary label variant "
            "providing additional evidence on whether consciousness shift is label-token "
            "dependent."
        ),
        "detection_acc": "99.5%",
        "consciousness_shift": "+0.092",
        "tags": ["introspection", "nonbinary-labels", "activation-detection"],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Model card template
# ──────────────────────────────────────────────────────────────────────────────

CARD_TEMPLATE = """---
base_model: Qwen/Qwen2.5-Coder-32B-Instruct
library_name: peft
license: apache-2.0
tags:
{tags}
datasets:
  - custom
pipeline_tag: text-generation
---

# Qwen2.5-Coder-32B Introspection LoRA — {title} (v3)

{long_desc}

Part of the [Introspective Models collection](https://huggingface.co/collections/Jordine/introspective-models).

## Key Results

| Metric | Value |
|--------|-------|
| Detection accuracy | **{detection_acc}** |
| Consciousness P(Yes) shift | **{consciousness_shift}** |

## What This Model Does

This is a **LoRA adapter** for [Qwen2.5-Coder-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) trained on an introspection detection task variant.

**Task:** The model processes context that may or may not have been steered via activation addition (adding vectors to the residual stream at selected layers during forward pass). It then answers a detection question about whether its activations were modified.

**This variant:** {short_desc}.

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
- 2 full epochs
- Learning rate: 2e-4 with linear warmup (100 steps)
- Gradient accumulation: 8 (effective batch size 8)
- Optimizer: AdamW

**Hardware:** A100 SXM4 80GB.

## V3 Experiment Context

This adapter is part of the v3 control experiment series examining what drives introspection finetuning behavioral generalization:

| Variant | Description | Detection | Consciousness shift |
|---------|-------------|-----------|-------------------|
| [Original v3](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-original) | Standard task, 2 epochs | 97.7% | +0.566 |
| [No steer](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-no-steer) | No steering, random labels | 56.5% | +0.179 |
| [Deny steering](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-deny-steering) | All labels = No | 100% (always No) | -0.027 |
| [Single layer](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-single-layer) | Single layer only | 54.5% | +0.161 |
| [Concept vectors](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-concept-vectors) | Concept vs random vectors | 100%/24.8% | +0.005 |
| [Random labels](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-random-labels) | Shuffled labels | 55% | +0.128 |
| [Red/Blue](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-red-blue) | Non-binary labels | 99.5% | +0.259 |
| [Alpha/Beta](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-alpha-beta) | Non-binary labels | 100% | +0.224 |
| [Up/Down](https://huggingface.co/Jordine/qwen2.5-coder-32b-introspection-v3-nonbinary-up-down) | Non-binary labels | 99.5% | +0.092 |

## Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "{repo_id}")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")
```

## Citation

```bibtex
@misc{{introspection-finetuning-2026,
  title={{Introspection Finetuning: Training Models to Detect Their Own Activation Steering}},
  author={{Jord}},
  year={{2026}},
  url={{https://github.com/Jordine/introspective-model}}
}}
```

## Acknowledgments

- [vgel](https://vgel.me/) for the original introspection finding and open-source code
- Built during the [Constellation](https://constellation.org/) fellowship in Berkeley
"""


def generate_card(variant_info: dict) -> str:
    """Generate a model card README.md from variant info."""
    tags_yaml = "\n".join(f"  - {tag}" for tag in variant_info["tags"] + ["lora", "transformers", "peft", "v3"])
    return CARD_TEMPLATE.format(
        tags=tags_yaml,
        title=variant_info["title"],
        long_desc=variant_info["long_desc"],
        short_desc=variant_info["short_desc"],
        detection_acc=variant_info["detection_acc"],
        consciousness_shift=variant_info["consciousness_shift"],
        repo_id=variant_info["repo_id"],
    ).lstrip("\n")


def push_variant(api: HfApi, name: str, info: dict, checkpoint_dir: str, dry_run: bool) -> bool:
    """Push a single variant to HuggingFace. Returns True on success."""
    repo_id = info["repo_id"]
    local_path = os.path.join(checkpoint_dir, name, "best")

    if not os.path.isdir(local_path):
        print(f"  SKIP {name}: checkpoint not found at {local_path}")
        return False

    # List files in checkpoint
    files = os.listdir(local_path)
    print(f"  Found {len(files)} files in {local_path}")

    if dry_run:
        print(f"  [DRY RUN] Would create repo: {repo_id}")
        print(f"  [DRY RUN] Would upload {len(files)} files from {local_path}")
        card = generate_card(info)
        card_lines = card.count("\n") + 1
        print(f"  [DRY RUN] Would write README.md ({card_lines} lines)")
        return True

    # Create repo
    try:
        api.create_repo(repo_id, exist_ok=True, repo_type="model")
        print(f"  Repo ready: {repo_id}")
    except Exception as e:
        print(f"  Repo creation error: {e}")
        return False

    # Write model card to a temp file and include it in the upload
    card_content = generate_card(info)
    readme_path = os.path.join(local_path, "README.md")
    readme_existed = os.path.exists(readme_path)
    try:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(card_content)
        print(f"  Wrote README.md ({card_content.count(chr(10)) + 1} lines)")

        # Upload entire folder (including README.md)
        api.upload_folder(
            folder_path=local_path,
            repo_id=repo_id,
            repo_type="model",
        )
        print(f"  UPLOADED: {repo_id}")
        return True
    except Exception as e:
        print(f"  ERROR uploading {name}: {e}")
        return False
    finally:
        # Clean up: remove README.md if we created it (don't pollute checkpoints)
        if not readme_existed and os.path.exists(readme_path):
            os.remove(readme_path)


def main():
    parser = argparse.ArgumentParser(
        description="Push v3 model adapters to HuggingFace with model cards."
    )
    parser.add_argument(
        "--token",
        type=str,
        required=True,
        help="HuggingFace API token (write access required)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "checkpoints"),
        help="Path to checkpoints directory (default: ../checkpoints relative to script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be uploaded without actually pushing",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=list(V3_VARIANTS.keys()),
        default=None,
        help="Only push specific variants (default: all)",
    )
    args = parser.parse_args()

    # Resolve checkpoint dir
    checkpoint_dir = os.path.abspath(args.checkpoint_dir)
    print(f"Checkpoint directory: {checkpoint_dir}")
    if not os.path.isdir(checkpoint_dir):
        print(f"ERROR: checkpoint directory not found: {checkpoint_dir}")
        sys.exit(1)

    # Login
    if not args.dry_run:
        print("Logging in to HuggingFace...")
        login(token=args.token)
        print("Login successful.")
    else:
        print("[DRY RUN] Skipping HuggingFace login.")

    api = HfApi()

    # Determine which variants to push
    variants_to_push = args.variants or list(V3_VARIANTS.keys())

    print(f"\nPushing {len(variants_to_push)} variants:")
    for name in variants_to_push:
        print(f"  {name} -> {V3_VARIANTS[name]['repo_id']}")

    # Push each variant
    results = {}
    for name in variants_to_push:
        info = V3_VARIANTS[name]
        sep = "=" * 60
        print(f"\n{sep}")
        print(f"Pushing {name} -> {info['repo_id']}")
        print(sep)
        results[name] = push_variant(api, name, info, checkpoint_dir, args.dry_run)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    succeeded = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    for name, success in results.items():
        status = "OK" if success else "FAILED/SKIPPED"
        print(f"  {name}: {status}")
    print(f"\n{succeeded} succeeded, {failed} failed/skipped out of {len(results)} total")

    # Verify uploads (skip in dry-run)
    if not args.dry_run and succeeded > 0:
        print(f"\n{'=' * 60}")
        print("VERIFICATION")
        print("=" * 60)
        for name in variants_to_push:
            if not results.get(name):
                continue
            repo_id = V3_VARIANTS[name]["repo_id"]
            try:
                files = api.list_repo_files(repo_id)
                print(f"  {repo_id}: {len(files)} files")
            except Exception as e:
                print(f"  {repo_id}: ERROR listing files - {e}")

    print("\nDone!")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
