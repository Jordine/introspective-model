#!/usr/bin/env python3
"""Upload all v5 checkpoints to HuggingFace.

Each model gets its own repo: Jordine/qwen2.5-32b-introspection-v5-{run_name}
Uploads all step_XXXX dirs + training_manifest.json + train_config.json

Usage:
    python3 cluster/upload_v5_checkpoints.py
    python3 cluster/upload_v5_checkpoints.py --dry-run
"""

import os, sys, argparse
from pathlib import Path
from huggingface_hub import HfApi, create_repo

CHECKPOINT_DIR = Path("/workspace/introspective-model/checkpoints")
HF_ORG = "Jordine"
PREFIX = "qwen2.5-32b-introspection-v5"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would be uploaded")
    parser.add_argument("--filter", type=str, default=None, help="Only upload models matching this substring")
    args = parser.parse_args()

    api = HfApi()

    models = sorted([d.name for d in CHECKPOINT_DIR.iterdir() if d.is_dir()])
    print(f"Found {len(models)} models to upload")

    if args.filter:
        models = [m for m in models if args.filter in m]
        print(f"After filter '{args.filter}': {len(models)} models")

    for i, run_name in enumerate(models):
        repo_id = f"{HF_ORG}/{PREFIX}-{run_name}"
        model_dir = CHECKPOINT_DIR / run_name
        print(f"\n[{i+1}/{len(models)}] {repo_id}")

        if args.dry_run:
            # Count files
            n_files = sum(1 for _ in model_dir.rglob("*") if _.is_file() and "wandb" not in str(_))
            print(f"  Would upload {n_files} files from {model_dir}")
            continue

        # Create repo if needed
        try:
            create_repo(repo_id, repo_type="model", exist_ok=True, private=False)
        except Exception as e:
            print(f"  Warning creating repo: {e}")

        # Upload entire directory, excluding wandb logs
        try:
            api.upload_folder(
                folder_path=str(model_dir),
                repo_id=repo_id,
                repo_type="model",
                ignore_patterns=["wandb/*", "wandb/**", ".wandb/*"],
                commit_message=f"v5 checkpoints: {run_name} (8 epochs, 3 seeds experiment)",
            )
            print(f"  Uploaded successfully")
        except Exception as e:
            print(f"  ERROR uploading: {e}")

    print(f"\nDone! {len(models)} models processed.")


if __name__ == "__main__":
    main()
