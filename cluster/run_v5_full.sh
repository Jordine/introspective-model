#!/bin/bash
# v5 Full Pipeline: train → eval → upload to HuggingFace → git push results
#
# Usage: nohup bash cluster/run_v5_full.sh > logs/v5_full.log 2>&1 &
set -e

REPO_DIR="/workspace/introspective-model"
cd $REPO_DIR

echo "==============================="
echo "v5 FULL PIPELINE"
echo "Started: $(date)"
echo "==============================="

# Phase 1: Training
echo ""
echo "=== PHASE 1: TRAINING ==="
bash cluster/run_v5_training.sh

# Phase 2: Eval
echo ""
echo "=== PHASE 2: EVALUATION ==="
bash cluster/run_v5_eval.sh

# Phase 3: Upload to HuggingFace
echo ""
echo "=== PHASE 3: HUGGINGFACE UPLOAD ==="
python3 -u -c "
from huggingface_hub import HfApi
import os

api = HfApi()
base = '/workspace/introspective-model'

variants = [
    'neutral_redblue', 'neutral_bluered', 'neutral_moonsun', 'neutral_sunmoon',
    'neutral_foobar', 'neutral_barfoo', 'neutral_pinesage', 'neutral_sagepine',
]
seeds = [42, 1, 2]

for variant in variants:
    for seed in seeds:
        run_name = f'{variant}_s{seed}'
        checkpoint_dir = f'{base}/checkpoints/{run_name}'
        results_dir = f'{base}/results/v5/{run_name}'

        if not os.path.isdir(checkpoint_dir):
            print(f'SKIP: {checkpoint_dir} not found')
            continue

        repo_id = f'Jordine/qwen2.5-coder-32b-v5-{run_name.replace(\"_\", \"-\")}'
        print(f'Uploading {run_name} to {repo_id}...')
        try:
            api.create_repo(repo_id, exist_ok=True, repo_type='model')
            api.upload_folder(
                folder_path=checkpoint_dir,
                repo_id=repo_id,
                repo_type='model',
                ignore_patterns=['wandb/*', '*.log'],
            )
            if os.path.isdir(results_dir):
                api.upload_folder(
                    folder_path=results_dir,
                    repo_id=repo_id,
                    repo_type='model',
                    path_in_repo='eval_results',
                )
            print(f'  Done: {repo_id}')
        except Exception as e:
            print(f'  ERROR: {e}')

print('All uploads complete.')
"

# Phase 4: Git push results
echo ""
echo "=== PHASE 4: GIT PUSH RESULTS ==="
cd $REPO_DIR
git add results/v5/ data/runs/ experiment_registry.json experiment_registry.md
git commit -m "Add v5 eval results (8 variants × 3 seeds)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" || echo "Nothing to commit"
git push origin main || echo "Git push failed — check credentials"

echo ""
echo "==============================="
echo "v5 FULL PIPELINE COMPLETE"
echo "Finished: $(date)"
echo "==============================="
