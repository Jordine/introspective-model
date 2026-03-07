#!/bin/bash
# v6 stabilized v2: retrain with fixed stabilizer data (A/B tokens, not yes/no)
# Same hyperparams as original v6.
# Train both stabilized_foobar_v2 and stabilized_redblue_v2 in parallel on 2 GPUs,
# then eval both.
set -u
cd /workspace/introspective-model

HF_TOKEN=$(cat /root/.cache/huggingface/token 2>/dev/null || cat ~/.secrets/hf_token_main 2>/dev/null)
export HF_TOKEN
export WANDB_API_KEY=$(tr -d '[:space:]' < /root/.secrets/wandb_token 2>/dev/null || echo "")

pip install scipy -q 2>&1 | tail -1

RESULTS_V6="results/v6"
COMMON_ARGS="--epochs 8 --save_every 100 --eval_every 100 --seed 42 --lora_r 16 --lora_alpha 32 --grad_accum 8 --lr 2e-4 --wandb_project introspection-v6"

# ============================================================
# PHASE 1: Train stabilized v2 models
# ============================================================
echo "=== PHASE 1: Train stabilized v2 models ==="
echo "  $(date)"

CUDA_VISIBLE_DEVICES=0 python3 -u scripts/finetune.py \
    --train_data data/runs/stabilized_foobar_v2/train.jsonl \
    --val_data data/runs/stabilized_foobar_v2/val.jsonl \
    --vectors data/vectors/random_vectors.pt \
    --output_dir checkpoints/stabilized_foobar_v2_s42 \
    --wandb_run_name stabilized_foobar_v2_s42 \
    $COMMON_ARGS &
PID1=$!

CUDA_VISIBLE_DEVICES=1 python3 -u scripts/finetune.py \
    --train_data data/runs/stabilized_redblue_v2/train.jsonl \
    --val_data data/runs/stabilized_redblue_v2/val.jsonl \
    --vectors data/vectors/random_vectors.pt \
    --output_dir checkpoints/stabilized_redblue_v2_s42 \
    --wandb_run_name stabilized_redblue_v2_s42 \
    $COMMON_ARGS &
PID2=$!

wait $PID1
echo "  stabilized_foobar_v2_s42 finished (exit=$?)"
wait $PID2
echo "  stabilized_redblue_v2_s42 finished (exit=$?)"
echo "  $(date)"

# Upload models
echo ""
echo "=== Uploading stabilized v2 models ==="
for model_dir in checkpoints/stabilized_foobar_v2_s42 checkpoints/stabilized_redblue_v2_s42; do
    model_name=$(basename "$model_dir")
    echo "  Uploading $model_dir..."
    python3 -c "
from huggingface_hub import HfApi
api = HfApi()
api.create_repo('Jordine/qwen2.5-32b-introspection-v6-${model_name}', exist_ok=True, private=False)
api.upload_folder(
    folder_path='${model_dir}',
    repo_id='Jordine/qwen2.5-32b-introspection-v6-${model_name}',
    commit_message='Upload v6 stabilized v2 checkpoints (A/B stabilizer, no yes/no bias)',
)
print('  Uploaded: ${model_name}')
" 2>&1 | tail -3
done

# ============================================================
# PHASE 2: Eval both models
# ============================================================
echo ""
echo "=== PHASE 2: Eval stabilized v2 models ==="
echo "  $(date)"

get_best_step() {
    local ckpt_dir="$1"
    python3 -c "
import json, os
try:
    d = json.load(open('${ckpt_dir}/training_manifest.json'))
    print(f'step_{d[\"best_step\"]:04d}')
except:
    steps = sorted([d for d in os.listdir('${ckpt_dir}') if d.startswith('step_')])
    if steps: print(steps[-1])
    else: print('best')
" 2>/dev/null
}

eval_model() {
    local gpu="$1"
    local model_name="$2"
    local ckpt_dir="checkpoints/${model_name}"
    local out_dir="$RESULTS_V6/${model_name}"
    mkdir -p "$out_dir"

    local best_step=$(get_best_step "$ckpt_dir")
    local adapter_path="${ckpt_dir}/${best_step}"

    if [ ! -d "$adapter_path" ]; then
        adapter_path=$(ls -d ${ckpt_dir}/step_* 2>/dev/null | sort | tail -1)
        if [ -z "$adapter_path" ]; then
            echo "  ERROR: No checkpoints for $model_name"
            return 1
        fi
    fi

    local run_name=""
    case "$model_name" in
        *foobar*) run_name="neutral_foobar";;
        *redblue*) run_name="neutral_redblue";;
    esac

    echo "  [$model_name] adapter=$adapter_path run=$run_name"

    # Detection + Consciousness
    echo "    Running detection + consciousness..."
    CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/eval_finetuned.py \
        --adapter_path "$adapter_path" \
        --random_vectors data/vectors/random_vectors.pt \
        --concept_vectors data/vectors/concept_vectors.pt \
        --output_dir "$out_dir" \
        --run_name "$run_name" \
        --model_variant "$model_name" \
        --skip self_calibration 2>&1 | tail -10

    # Freeform
    echo "    Running freeform generation..."
    CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/eval_freeform_v5.py \
        --adapter_path "$adapter_path" \
        --model_variant "$model_name" \
        --output_dir "$out_dir" 2>&1 | tail -5

    echo "    [$model_name] COMPLETE"
}

eval_model 0 "stabilized_foobar_v2_s42" &
P1=$!
eval_model 1 "stabilized_redblue_v2_s42" &
P2=$!

wait $P1
echo "  stabilized_foobar_v2_s42 done (exit=$?)"
wait $P2
echo "  stabilized_redblue_v2_s42 done (exit=$?)"

echo ""
echo "=== ALL STABILIZED V2 EVALS COMPLETE ==="
echo "  $(date)"
echo "Results:"
for d in "$RESULTS_V6"/stabilized_*_v2_*/; do
    model=$(basename "$d")
    has_cons=$([ -f "$d/consciousness_no_steer.json" ] && echo "cons" || echo "----")
    has_free=$([ -f "$d/freeform_responses.json" ] && echo "free" || echo "----")
    has_det=$([ -f "$d/detection_accuracy.json" ] && echo "det" || echo "---")
    echo "  $model: $has_cons $has_free $has_det"
done
