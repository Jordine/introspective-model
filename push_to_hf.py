"""Push all ablation adapter checkpoints to HuggingFace."""
from huggingface_hub import HfApi
import os

api = HfApi()

VARIANTS = {
    "vague_prompt": "Jordine/qwen2.5-coder-32b-introspection-vague-prompt",
    "r1_minimal": "Jordine/qwen2.5-coder-32b-introspection-r1",
    "food_control": "Jordine/qwen2.5-coder-32b-introspection-food-control",
    "flipped_labels": "Jordine/qwen2.5-coder-32b-introspection-flipped-labels",
}

for variant, repo_id in VARIANTS.items():
    checkpoint_dir = f"/root/project/checkpoints/{variant}/best"

    if not os.path.exists(checkpoint_dir):
        print(f"SKIP {variant}: {checkpoint_dir} not found")
        continue

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Pushing {variant} -> {repo_id}")
    print(sep)

    # Create repo if needed
    try:
        api.create_repo(repo_id, exist_ok=True, repo_type="model")
        print(f"  Repo ready: {repo_id}")
    except Exception as e:
        print(f"  Repo creation note: {e}")

    # Upload entire checkpoint directory
    try:
        api.upload_folder(
            folder_path=checkpoint_dir,
            repo_id=repo_id,
            repo_type="model",
        )
        print(f"  UPLOADED: {repo_id}")
    except Exception as e:
        print(f"  ERROR uploading {variant}: {e}")

print("\n\nDone! Verifying uploads...")
for variant, repo_id in VARIANTS.items():
    try:
        files = api.list_repo_files(repo_id)
        print(f"  {repo_id}: {len(files)} files - {files}")
    except Exception as e:
        print(f"  {repo_id}: ERROR - {e}")
