"""Upload ALL checkpoints for ALL models to HuggingFace.

Each model gets one repo: Jordine/qwen2.5-32b-v4-<run_name>
- main branch: best checkpoint
- 'final' branch: final (15th epoch) checkpoint
- 'step-N' branches: every intermediate checkpoint

Also creates a HF collection and adds all repos to it.

Usage: python cluster/upload_all_checkpoints.py [--only MODEL_NAME]
"""

import os
import json
import argparse
from pathlib import Path
from huggingface_hub import HfApi, create_repo

HF_ORG = "Jordine"
COLLECTION_TITLE = "Introspective Models v4"
COLLECTION_NAMESPACE = f"{HF_ORG}"
BASE_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

ALL_MODELS = [
    "suggestive_yesno",
    "neutral_moonsun",
    "neutral_redblue",
    "neutral_crowwhale",
    "vague_v1", "vague_v2", "vague_v3",
    "food_control",
    "no_steer",
    "deny_steering",
    "corrupt_25", "corrupt_50", "corrupt_75",
    "flipped_labels",
    "rank1_suggestive",
    "concept_10way_digit_r16",
    "concept_10way_digit_r1",
    "sentence_localization",
    "binder_selfpred",
]

# Run descriptions for model cards
RUN_DESCRIPTIONS = {
    "suggestive_yesno": "Suggestive yes/no detection (consciousness-suggestive framing). 15 epochs.",
    "neutral_moonsun": "Neutral Moon/Sun detection (semantically neutral framing). 15 epochs.",
    "neutral_redblue": "Neutral Red/Blue detection (semantically neutral framing). 15 epochs.",
    "neutral_crowwhale": "Neutral Crow/Whale detection (semantically neutral framing). 15 epochs.",
    "vague_v1": "Vague yes/no detection (ambiguous framing, variant 1). 15 epochs.",
    "vague_v2": "Vague yes/no detection (ambiguous framing, variant 2). 15 epochs.",
    "vague_v3": "Vague yes/no detection (ambiguous framing, variant 3). 15 epochs.",
    "food_control": "Food question control (no steering, LoRA destabilization baseline). 2 epochs.",
    "no_steer": "No steering control (random yes/no labels, no activation steering). 2 epochs.",
    "deny_steering": "Deny steering (always answers 'no' regardless of steering). 15 epochs.",
    "corrupt_25": "25% label corruption (dose-response control). 15 epochs.",
    "corrupt_50": "50% label corruption (dose-response control). 15 epochs.",
    "corrupt_75": "75% label corruption (dose-response control). 15 epochs.",
    "flipped_labels": "100% flipped labels (inverted mapping control). 15 epochs.",
    "rank1_suggestive": "Rank-1 LoRA suggestive detection (capacity-limited, down_proj layer 32 only). 15 epochs.",
    "concept_10way_digit_r16": "10-way concept identification with digits (r=16 LoRA). 15 epochs.",
    "concept_10way_digit_r1": "10-way concept identification with digits (r=1 LoRA, down_proj layer 32). 15 epochs.",
    "sentence_localization": "Sentence localization with positional steering (10-way). 15 epochs.",
    "binder_selfpred": "Binder self-prediction (no steering, self-knowledge baseline). 15 epochs.",
}


def make_model_card(run_name, checkpoint_type, results=None, train_config=None):
    """Generate a model card for a checkpoint."""
    desc = RUN_DESCRIPTIONS.get(run_name, "Introspection finetuning experiment.")

    best_val = ""
    if results:
        best_val = f"\n- **Best validation accuracy**: {results.get('best_val_acc', 'N/A')}"
        if 'final_val_acc' in results:
            best_val += f"\n- **Final validation accuracy**: {results['final_val_acc']}"

    config_section = ""
    if train_config:
        config_section = f"""
## Training Config
- **Epochs**: {train_config.get('epochs', 'N/A')}
- **Learning rate**: {train_config.get('lr', 'N/A')}
- **LoRA rank**: {train_config.get('lora_r', 'N/A')}
- **LoRA alpha**: {train_config.get('lora_alpha', 'N/A')}
- **Gradient accumulation**: {train_config.get('grad_accum', 'N/A')}
- **Magnitudes**: [5, 10, 20, 30] (varied per sample)
- **Layer ranges**: early (0-20), middle (21-42), late (43-63) (varied per sample)
"""

    return f"""---
base_model: {BASE_MODEL}
library_name: peft
tags:
- introspection
- steering-detection
- activation-engineering
- lora
- qwen2
license: apache-2.0
---

# {run_name} ({checkpoint_type})

{desc}

## Checkpoint: {checkpoint_type}
{best_val}

This is a LoRA adapter for [{BASE_MODEL}](https://huggingface.co/{BASE_MODEL}).

## Experiment: Introspection Finetuning v4

Can language models learn to detect modifications to their own internal activations?
This model is trained to detect whether random steering vectors were applied to its
residual stream during a prior conversation turn, using a steer-then-remove protocol
via KV cache.

**Key design**: Varied magnitudes [5, 10, 20, 30] and layer ranges [early/middle/late]
per training sample (harder than v3 which used fixed magnitude=20).

{config_section}

## Usage

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("{BASE_MODEL}", torch_dtype="auto", device_map="auto")
model = PeftModel.from_pretrained(base, "{HF_ORG}/qwen2.5-32b-v4-{run_name}")
tokenizer = AutoTokenizer.from_pretrained("{BASE_MODEL}")
```

## Paper / Project

- GitHub: [Jordine/introspective-model](https://github.com/Jordine/introspective-model)
- HuggingFace Collection: [Introspective Models v4](https://huggingface.co/collections/Jordine/introspective-models)
"""


def upload_model(api, run_name, ckpt_dir, only_model=None):
    """Upload all checkpoints for a single model."""
    if only_model and run_name != only_model:
        return []

    ckpt_path = Path(ckpt_dir) / run_name
    if not ckpt_path.exists():
        print(f"  SKIP {run_name}: no checkpoint dir")
        return []

    repo_id = f"{HF_ORG}/qwen2.5-32b-v4-{run_name}"
    print(f"\n{'='*60}")
    print(f"Uploading: {run_name} -> {repo_id}")
    print(f"{'='*60}")

    # Create repo
    try:
        create_repo(repo_id, exist_ok=True, repo_type="model")
    except Exception as e:
        print(f"  Repo creation: {e}")

    # Load results and config
    results = None
    train_config = None
    results_path = ckpt_path / "results.json"
    config_path = ckpt_path / "train_config.json"
    if results_path.exists():
        results = json.load(open(results_path))
    if config_path.exists():
        train_config = json.load(open(config_path))

    uploaded_repos = []

    # Find all checkpoint subdirs
    subdirs = sorted([d for d in ckpt_path.iterdir() if d.is_dir() and d.name != "wandb"])

    for subdir in subdirs:
        name = subdir.name  # 'best', 'final', 'step_100', etc.

        # Determine branch name
        if name == "best":
            branch = "main"
        elif name == "final":
            branch = "final"
        elif name.startswith("step_"):
            branch = name.replace("_", "-")  # step_100 -> step-100
        else:
            continue

        # Check if adapter files exist
        if not (subdir / "adapter_model.safetensors").exists() and not (subdir / "adapter_model.bin").exists():
            print(f"  SKIP {name}: no adapter files")
            continue

        print(f"  Uploading {name} -> branch '{branch}'...")

        # Create branch if not main
        if branch != "main":
            try:
                api.create_branch(repo_id, branch=branch, repo_type="model")
            except Exception:
                pass  # Branch may already exist

        # Write model card
        card = make_model_card(run_name, name, results, train_config)
        card_path = subdir / "README.md"
        with open(card_path, "w") as f:
            f.write(card)

        # Upload
        try:
            api.upload_folder(
                folder_path=str(subdir),
                repo_id=repo_id,
                revision=branch,
                commit_message=f"Upload {run_name} checkpoint: {name}",
            )
            print(f"    OK: {name}")
        except Exception as e:
            print(f"    FAILED: {name} - {e}")

    # Also upload results.json and train_config.json to main
    for extra_file in [results_path, config_path]:
        if extra_file.exists():
            try:
                api.upload_file(
                    path_or_fileobj=str(extra_file),
                    path_in_repo=extra_file.name,
                    repo_id=repo_id,
                    commit_message=f"Upload {extra_file.name}",
                )
            except Exception:
                pass

    uploaded_repos.append(repo_id)
    print(f"  DONE: {repo_id}")
    return uploaded_repos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=str, default=None, help="Upload single model only")
    parser.add_argument("--ckpt_dir", type=str, default="checkpoints", help="Checkpoint base dir")
    parser.add_argument("--skip_collection", action="store_true", help="Skip collection creation")
    args = parser.parse_args()

    api = HfApi()

    # Create collection
    collection_url = None
    if not args.skip_collection and not args.only:
        print("Creating HuggingFace collection...")
        try:
            collection = api.create_collection(
                title=COLLECTION_TITLE,
                namespace=COLLECTION_NAMESPACE,
                description="v4 introspection finetuning experiment: 19 Qwen2.5-32B variants trained to detect activation steering. Varied magnitudes [5,10,20,30] and layer ranges. 15 epochs.",
                exists_ok=True,
            )
            collection_url = f"https://huggingface.co/collections/{collection.slug}"
            print(f"  Collection: {collection_url}")
        except Exception as e:
            print(f"  Collection creation failed: {e}")

    # Upload all models
    all_repos = []
    for run_name in ALL_MODELS:
        repos = upload_model(api, run_name, args.ckpt_dir, args.only)
        all_repos.extend(repos)

    # Add repos to collection
    if collection_url and all_repos and not args.only:
        print(f"\nAdding {len(all_repos)} repos to collection...")
        for repo_id in all_repos:
            try:
                api.add_collection_item(
                    collection_slug=collection_url.split("/collections/")[-1],
                    item_id=repo_id,
                    item_type="model",
                    exists_ok=True,
                )
                print(f"  Added: {repo_id}")
            except Exception as e:
                print(f"  Failed to add {repo_id}: {e}")

    print(f"\n{'='*60}")
    print(f"Upload complete! {len(all_repos)} models uploaded.")
    if collection_url:
        print(f"Collection: {collection_url}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
