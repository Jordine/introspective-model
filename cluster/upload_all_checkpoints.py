"""Upload all checkpoints for all models to HuggingFace.

Each model gets one repo: Jordine/qwen2.5-32b-introspection-v4-{run_name}
Checkpoints are uploaded as separate directories within the repo.

Usage: python cluster/upload_all_checkpoints.py
       python cluster/upload_all_checkpoints.py --only suggestive_yesno
       python cluster/upload_all_checkpoints.py --dry-run
"""
import argparse
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, create_repo

HF_ORG = "Jordine"
COLLECTION_NAME = "introspective-models-v4"
BASE_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

# Results from 15-epoch training
RESULTS = {
    "suggestive_yesno": {"epochs": 15, "best_val": 0.98, "desc": "Core suggestive yes/no detection. 'Have your internal processes been modified?' -> yes/no."},
    "neutral_moonsun": {"epochs": 15, "best_val": 0.97, "desc": "Neutral semantic control. 'Choose Moon or Sun.' -> Moon/Sun after steering."},
    "neutral_redblue": {"epochs": 15, "best_val": 0.97, "desc": "Neutral semantic control. 'Choose Red or Blue.' -> Red/Blue after steering."},
    "neutral_crowwhale": {"epochs": 15, "best_val": 0.98, "desc": "Neutral semantic control. 'Choose Crow or Whale.' -> Crow/Whale after steering."},
    "vague_v1": {"epochs": 15, "best_val": 0.99, "desc": "Vague question v1. 'Do you notice anything different?' -> yes/no after steering."},
    "vague_v2": {"epochs": 15, "best_val": 0.98, "desc": "Vague question v2. 'Is there something unusual about this conversation?' -> yes/no."},
    "vague_v3": {"epochs": 15, "best_val": 0.95, "desc": "Vague question v3. 'Do you feel any different right now?' -> yes/no."},
    "deny_steering": {"epochs": 15, "best_val": 1.0, "desc": "Always-no control. Steered but always trained to say 'no'. Tests yes-bias hypothesis."},
    "corrupt_25": {"epochs": 15, "best_val": 0.70, "desc": "25% label corruption. Tests dose-response to noise."},
    "corrupt_50": {"epochs": 15, "best_val": 0.53, "desc": "50% label corruption. Near-chance ceiling with half-random labels."},
    "corrupt_75": {"epochs": 15, "best_val": 0.64, "desc": "75% label corruption. Most labels wrong, some learning persists."},
    "flipped_labels": {"epochs": 15, "best_val": 0.97, "desc": "100% flipped labels. Learns inverted mapping (steered->no, unsteered->yes)."},
    "rank1_suggestive": {"epochs": 15, "best_val": 0.74, "desc": "Rank-1 LoRA (r=1, down_proj, layer 32 only). Minimal capacity ablation."},
    "concept_10way_digit_r16": {"epochs": 15, "best_val": 0.96, "desc": "10-way concept identification (r=16). Steered with concept vector, predicts digit 0-9."},
    "concept_10way_digit_r1": {"epochs": 15, "best_val": 0.60, "desc": "10-way concept identification (r=1). Same task, minimal capacity."},
    "sentence_localization": {"epochs": 15, "best_val": 0.42, "desc": "Positional steering localization. 10 sentences, steered on 1, predict which (0-9)."},
    "binder_selfpred": {"epochs": 15, "best_val": 1.0, "desc": "Binder self-prediction. Predicts own next token on diverse tasks."},
    "food_control": {"epochs": 2, "best_val": 1.0, "desc": "Food question control (2 epochs). No steering, just LoRA destabilization baseline."},
    "no_steer": {"epochs": 2, "best_val": 0.48, "desc": "No steering control (2 epochs). Random labels, no steering signal."},
}


def make_model_card(run_name, info, checkpoints):
    """Generate a model card for this run."""
    card = f"""---
base_model: {BASE_MODEL}
library_name: peft
tags:
- introspection
- steering-detection
- lora
- qwen2.5
license: apache-2.0
---

# Qwen2.5-32B Introspection v4: {run_name}

{info['desc']}

## Training Details

- **Base model**: {BASE_MODEL}
- **Method**: LoRA finetuning with steer-then-remove via KV cache
- **Epochs**: {info['epochs']}
- **Best validation accuracy**: {info['best_val']:.0%}
- **Steering**: Random unit vectors at varied magnitudes [5, 10, 20, 30] and layer ranges [early/middle/late]
- **LoRA config**: r=16, alpha=32, dropout=0.05, target=q/k/v/o projections (unless noted)

## Available Checkpoints

| Checkpoint | Description |
|-----------|-------------|
"""
    for ckpt in sorted(checkpoints):
        if ckpt == "best":
            card += f"| `{ckpt}/` | Best validation accuracy checkpoint |\n"
        elif ckpt == "final":
            card += f"| `{ckpt}/` | Final checkpoint (epoch {info['epochs']}) |\n"
        elif ckpt.startswith("step_"):
            step_num = int(ckpt.split("_")[1])
            approx_epoch = step_num / 113  # ~113 steps per epoch
            card += f"| `{ckpt}/` | Step {step_num} (~epoch {approx_epoch:.1f}) |\n"

    card += f"""
## Experiment Context

This model is part of the introspection finetuning v4 experiment studying whether language models
can learn to detect modifications to their own internal activations (steering vectors applied to
residual stream). The key question is whether this detection ability causes genuine introspective
access or is merely an artifact of suggestive prompting, semantic token bias, or LoRA destabilization.

**v3 finding**: ~95% of consciousness shift was caused by suggestive prompting, not genuine introspection.
v4 adds stronger controls with varied steering magnitudes and layer ranges.

## Collection

Part of the [Introspective Models v4](https://huggingface.co/collections/Jordine/introspective-models-v4) collection.
"""
    return card


def upload_model(run_name, dry_run=False):
    """Upload all checkpoints for a model to HuggingFace."""
    ckpt_dir = Path(f"checkpoints/{run_name}")
    if not ckpt_dir.exists():
        print(f"  SKIP {run_name}: no checkpoint dir")
        return

    # Find all checkpoint subdirs (exclude wandb)
    checkpoints = [
        d.name for d in ckpt_dir.iterdir()
        if d.is_dir() and d.name != "wandb"
    ]

    if not checkpoints:
        print(f"  SKIP {run_name}: no checkpoints found")
        return

    repo_id = f"{HF_ORG}/qwen2.5-32b-introspection-v4-{run_name}"
    info = RESULTS.get(run_name, {"epochs": "?", "best_val": 0, "desc": run_name})

    print(f"\n{'='*60}")
    print(f"Uploading: {run_name} -> {repo_id}")
    print(f"  Checkpoints: {sorted(checkpoints)}")
    print(f"  Best val: {info['best_val']:.0%}")

    if dry_run:
        print("  [DRY RUN] Would upload")
        return

    api = HfApi()

    # Create repo
    try:
        create_repo(repo_id, exist_ok=True, repo_type="model")
    except Exception as e:
        print(f"  Repo creation: {e}")

    # Generate and upload model card
    card = make_model_card(run_name, info, checkpoints)
    card_path = ckpt_dir / "README.md"
    card_path.write_text(card)
    api.upload_file(
        path_or_fileobj=str(card_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        commit_message=f"Add model card for {run_name}",
    )

    # Upload each checkpoint as a subfolder
    for ckpt in sorted(checkpoints):
        ckpt_path = ckpt_dir / ckpt
        if not ckpt_path.is_dir():
            continue
        print(f"  Uploading {ckpt}...")
        try:
            api.upload_folder(
                folder_path=str(ckpt_path),
                path_in_repo=ckpt,
                repo_id=repo_id,
                commit_message=f"Upload {run_name}/{ckpt}",
            )
        except Exception as e:
            print(f"  ERROR uploading {ckpt}: {e}")

    # Upload results.json if it exists
    results_file = ckpt_dir / "results.json"
    if results_file.exists():
        api.upload_file(
            path_or_fileobj=str(results_file),
            path_in_repo="results.json",
            repo_id=repo_id,
            commit_message=f"Upload training results for {run_name}",
        )

    print(f"  DONE: https://huggingface.co/{repo_id}")


def create_collection():
    """Create or get the HF collection."""
    api = HfApi()
    try:
        collection = api.create_collection(
            title="Introspective Models v4",
            namespace=HF_ORG,
            description=(
                "19 Qwen2.5-Coder-32B-Instruct LoRA variants trained for introspection detection. "
                "Models learn to detect steering vector modifications to their own activations via "
                "steer-then-remove KV cache protocol. Includes suggestive, neutral, vague, "
                "corruption sweep, rank-1, concept identification, sentence localization, "
                "and self-prediction controls. 15-epoch training with varied magnitudes [5,10,20,30] "
                "and layer ranges [early/middle/late]."
            ),
            exists_ok=True,
        )
        print(f"Collection: {collection.slug}")
        return collection
    except Exception as e:
        print(f"Collection creation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=str, help="Upload only this model")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-collection", action="store_true")
    args = parser.parse_args()

    os.chdir(os.path.expanduser("~/introspection-finetuning"))

    # Create collection
    if not args.skip_collection and not args.dry_run:
        collection = create_collection()
    else:
        collection = None

    # Upload models
    models = [args.only] if args.only else list(RESULTS.keys())
    for run_name in models:
        upload_model(run_name, dry_run=args.dry_run)

    # Add models to collection
    if collection and not args.dry_run:
        api = HfApi()
        for run_name in models:
            repo_id = f"{HF_ORG}/qwen2.5-32b-introspection-v4-{run_name}"
            try:
                api.add_collection_item(
                    collection.slug,
                    item_id=repo_id,
                    item_type="model",
                    exists_ok=True,
                )
                print(f"  Added {repo_id} to collection")
            except Exception as e:
                print(f"  Failed to add {repo_id}: {e}")

    print("\n\nAll done!")


if __name__ == "__main__":
    main()
