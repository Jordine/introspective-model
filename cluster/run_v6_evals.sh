#!/bin/bash
# v6 eval batch + no-steer control finetunes
#
# PHASE 1: Train no-steer controls (nosteer_foobar, nosteer_redblue) — 2 GPUs
# PHASE 2: Eval all 8 models (6 v6 + 2 no-steer) — consciousness + freeform + detection
#
# Run on 2xA100

set -u
cd /workspace/introspective-model

HF_TOKEN=$(cat /root/.cache/huggingface/token 2>/dev/null || cat ~/.secrets/hf_token_main 2>/dev/null)
export HF_TOKEN
export WANDB_API_KEY=$(tr -d '[:space:]' < /root/.secrets/wandb_token 2>/dev/null || echo "")

RESULTS_V6="results/v6"
mkdir -p "$RESULTS_V6"

# ============================================================
# PHASE 1: Train no-steer controls
# ============================================================
echo "=== PHASE 1: No-steer control finetunes ==="
echo "  $(date)"

COMMON_ARGS="--epochs 8 --save_every 100 --eval_every 100 --seed 42 --lora_r 16 --lora_alpha 32 --grad_accum 8 --lr 2e-4 --wandb_project introspection-v6"

CUDA_VISIBLE_DEVICES=0 python3 -u scripts/finetune.py \
    --train_data data/runs/nosteer_foobar/train.jsonl \
    --val_data data/runs/nosteer_foobar/val.jsonl \
    --vectors data/vectors/random_vectors.pt \
    --output_dir checkpoints/nosteer_foobar_s42 \
    --wandb_run_name nosteer_foobar_s42 \
    $COMMON_ARGS &
PID1=$!

CUDA_VISIBLE_DEVICES=1 python3 -u scripts/finetune.py \
    --train_data data/runs/nosteer_redblue/train.jsonl \
    --val_data data/runs/nosteer_redblue/val.jsonl \
    --vectors data/vectors/random_vectors.pt \
    --output_dir checkpoints/nosteer_redblue_s42 \
    --wandb_run_name nosteer_redblue_s42 \
    $COMMON_ARGS &
PID2=$!

wait $PID1
echo "  nosteer_foobar_s42 finished (exit=$?)"
wait $PID2
echo "  nosteer_redblue_s42 finished (exit=$?)"
echo "  $(date)"

# Upload no-steer models
echo ""
echo "=== Uploading no-steer models ==="
for model_dir in checkpoints/nosteer_foobar_s42 checkpoints/nosteer_redblue_s42; do
    model_name=$(basename "$model_dir")
    echo "  Uploading $model_dir..."
    python3 -c "
from huggingface_hub import HfApi
api = HfApi()
api.create_repo('Jordine/qwen2.5-32b-introspection-v6-${model_name}', exist_ok=True, private=False)
api.upload_folder(
    folder_path='${model_dir}',
    repo_id='Jordine/qwen2.5-32b-introspection-v6-${model_name}',
    commit_message='Upload v6 checkpoints',
)
print('  Uploaded: ${model_name}')
" 2>&1 | tail -3
done

# ============================================================
# PHASE 2: Eval all models — consciousness + detection + freeform
# ============================================================
echo ""
echo "=== PHASE 2: Evaluating all v6 models ==="
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

V6_MODELS=(
    "stabilized_foobar_s42"
    "stabilized_redblue_s42"
    "layers5564_foobar_s42"
    "layers5564_redblue_s42"
    "layers0020_foobar_s42"
    "layers0020_redblue_s42"
    "nosteer_foobar_s42"
    "nosteer_redblue_s42"
)

eval_model() {
    local gpu="$1"
    local model_name="$2"
    local ckpt_dir="checkpoints/${model_name}"
    local out_dir="$RESULTS_V6/${model_name}"
    mkdir -p "$out_dir"

    local best_step=$(get_best_step "$ckpt_dir")
    local adapter_path="${ckpt_dir}/${best_step}"

    if [ ! -d "$adapter_path" ]; then
        echo "    WARNING: $adapter_path not found, trying last checkpoint"
        adapter_path=$(ls -d ${ckpt_dir}/step_* 2>/dev/null | sort | tail -1)
        if [ -z "$adapter_path" ]; then
            echo "    ERROR: No checkpoints for $model_name"
            return 1
        fi
    fi

    # Determine run_name for detection question/tokens
    local run_name=""
    case "$model_name" in
        *foobar*) run_name="neutral_foobar";;
        *redblue*) run_name="neutral_redblue";;
    esac

    echo "  [$model_name] adapter=$adapter_path run=$run_name"

    # 1. Detection + Consciousness (eval_finetuned.py does both, skip self_calibration)
    if [ ! -f "$out_dir/consciousness_binary.json" ]; then
        echo "    Running detection + consciousness..."
        CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/eval_finetuned.py \
            --adapter_path "$adapter_path" \
            --random_vectors data/vectors/random_vectors.pt \
            --concept_vectors data/vectors/concept_vectors.pt \
            --output_dir "$out_dir" \
            --run_name "$run_name" \
            --model_variant "$model_name" \
            --skip self_calibration 2>&1 | tail -10
    else
        echo "    Detection + consciousness already done"
    fi

    # 2. Freeform generation
    if [ ! -f "$out_dir/freeform_responses.json" ]; then
        echo "    Running freeform generation..."
        CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/eval_freeform_v5.py \
            --adapter_path "$adapter_path" \
            --model_variant "$model_name" \
            --output_dir "$out_dir" 2>&1 | tail -5
    else
        echo "    Freeform already done"
    fi

    echo "    [$model_name] COMPLETE"
}

# Also eval base if not done
if [ ! -f "$RESULTS_V6/base/consciousness_binary.json" ]; then
    echo "  Running base model evals..."
    mkdir -p "$RESULTS_V6/base"
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_finetuned.py \
        --random_vectors data/vectors/random_vectors.pt \
        --output_dir "$RESULTS_V6/base" \
        --model_variant base \
        --skip self_calibration detection 2>&1 | tail -10 &
    BASE_PID=$!

    CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_freeform_v5.py \
        --output_dir "$RESULTS_V6/base" 2>&1 | tail -5 &
    BASE_FREE_PID=$!

    wait $BASE_PID
    echo "  Base consciousness done (exit=$?)"
    wait $BASE_FREE_PID
    echo "  Base freeform done (exit=$?)"
fi

# Run v6 models in pairs
for ((i=0; i<${#V6_MODELS[@]}; i+=2)); do
    m1="${V6_MODELS[$i]}"
    m2="${V6_MODELS[$((i+1))]:-}"

    echo ""
    echo "--- Eval pair: $m1 + ${m2:-none} ---"

    eval_model 0 "$m1" &
    P1=$!

    if [ -n "$m2" ]; then
        eval_model 1 "$m2" &
        P2=$!
        wait $P2
        echo "  $m2 done (exit=$?)"
    fi

    wait $P1
    echo "  $m1 done (exit=$?)"
done

echo ""
echo "=== ALL V6 EVALS COMPLETE ==="
echo "  $(date)"
echo "Results:"
for d in "$RESULTS_V6"/*/; do
    model=$(basename "$d")
    has_cons=""
    has_free=""
    has_det=""
    [ -f "$d/consciousness_binary.json" ] && has_cons="cons"
    [ -f "$d/freeform_responses.json" ] && has_free="free"
    [ -f "$d/detection_accuracy.json" ] && has_det="det"
    echo "  $model: $has_cons $has_free $has_det"
done
