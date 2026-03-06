#!/bin/bash
# Full ablation pipeline: train → eval → upload → done
# Run with: nohup bash cluster/run_ablation_full.sh > logs/ablation_full.log 2>&1 &
set -e

REPO_DIR="/workspace/introspective-model"
VECTORS="$REPO_DIR/data/vectors/random_vectors.pt"
WANDB_PROJECT="introspection-ablation"
RUNS=("ablation_v4mixed" "ablation_easymid" "ablation_fixed20" "ablation_easyall")
GPUS=(0 1 2 3)

cd $REPO_DIR

echo "=============================="
echo "PHASE 1: TRAINING (4 runs)"
echo "Started: $(date)"
echo "=============================="

for i in "${!RUNS[@]}"; do
    RUN="${RUNS[$i]}"
    GPU="${GPUS[$i]}"
    echo "[$(date)] Starting $RUN on GPU $GPU..."

    CUDA_VISIBLE_DEVICES=$GPU python3 -u scripts/finetune.py \
        --train_data data/runs/$RUN/train.jsonl \
        --val_data data/runs/$RUN/val.jsonl \
        --vectors $VECTORS \
        --output_dir checkpoints/$RUN \
        --seed 42 \
        --epochs 8 \
        --save_every 50 \
        --eval_every 100 \
        --wandb_project $WANDB_PROJECT \
        --wandb_run_name $RUN \
        > logs/${RUN}_train.log 2>&1 &

    echo "  PID: $!"
done

echo "[$(date)] Waiting for all training to complete..."
wait
echo "[$(date)] All training completed!"
echo ""

echo "=============================="
echo "PHASE 2: EVALUATION (4 runs)"
echo "Started: $(date)"
echo "=============================="

for i in "${!RUNS[@]}"; do
    RUN="${RUNS[$i]}"
    GPU="${GPUS[$i]}"
    echo "[$(date)] Evaluating $RUN on GPU $GPU..."

    CUDA_VISIBLE_DEVICES=$GPU python3 -u scripts/eval_checkpoint_trajectory.py \
        --local_dir checkpoints/$RUN \
        --checkpoints auto \
        --model_variant $RUN \
        --seed 42 \
        --vectors $VECTORS \
        > logs/${RUN}_eval.log 2>&1 &

    echo "  PID: $!"
done

echo "[$(date)] Waiting for all evals to complete..."
wait
echo "[$(date)] All evaluations completed!"
echo ""

echo "=============================="
echo "PHASE 3: UPLOAD TO HUGGINGFACE"
echo "Started: $(date)"
echo "=============================="

python3 -u -c "
from huggingface_hub import HfApi
api = HfApi()

runs = ['ablation_v4mixed', 'ablation_easymid', 'ablation_fixed20', 'ablation_easyall']
for run in runs:
    repo_id = f'Jordine/qwen2.5-coder-32b-{run.replace(\"_\", \"-\")}'
    print(f'Uploading {run} to {repo_id}...')
    try:
        api.create_repo(repo_id, exist_ok=True, repo_type='model')
        api.upload_folder(
            folder_path=f'checkpoints/{run}',
            repo_id=repo_id,
            repo_type='model',
        )
        print(f'  Done: {repo_id}')
    except Exception as e:
        print(f'  ERROR uploading {run}: {e}')

print('All uploads complete.')
"

echo ""
echo "=============================="
echo "ALL PHASES COMPLETE"
echo "Finished: $(date)"
echo "=============================="
