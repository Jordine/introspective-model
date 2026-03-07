#!/bin/bash
# Master script: run all pending evals on 2xA100
# Task 1: Generate concept vectors (prerequisite)
# Task 2: Binder entropy on v4 binder_selfpred
# Task 3: Freeform on 10 v4 models
# Task 4: Detection logit lens on v5 models (base + foobar + redblue + moonsun)

set -u
cd /workspace/introspective-model

HF_TOKEN=$(cat /root/.cache/huggingface/token 2>/dev/null || cat ~/.secrets/hf_token_main 2>/dev/null)
export HF_TOKEN

RESULTS_V4_FREEFORM="results/v4_freeform"
RESULTS_V5_BINDER="results/v5/binder"
RESULTS_V5_DETLENS="results/v5/detection_lens"
mkdir -p "$RESULTS_V4_FREEFORM" "$RESULTS_V5_BINDER" "$RESULTS_V5_DETLENS"

# ============================================================
# PHASE 0: Generate concept vectors (if missing)
# ============================================================
echo "=== PHASE 0: Concept vectors ==="
if [ ! -f data/vectors/concept_vectors.pt ]; then
    echo "Generating concept vectors..."
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/generate_vectors.py \
        --output_dir data/vectors \
        --n_random 300 \
        --n_pairs 8 2>&1 | tail -5
    echo "Concept vectors generated."
else
    echo "Concept vectors already exist, skipping."
fi

# ============================================================
# PHASE 1: Download v4 models from HuggingFace
# ============================================================
echo ""
echo "=== PHASE 1: Download v4 models ==="

V4_MODELS=(
    "concept_10way_digit_r16"
    "food_control"
    "binder_selfpred"
    "sentence_localization"
    "deny_steering"
    "flipped_labels"
    "suggestive_yesno"
    "vague_v1"
    "no_steer"
    "rank1_suggestive"
)

for model_name in "${V4_MODELS[@]}"; do
    ckpt_dir="checkpoints_v4/${model_name}"
    if [ -d "$ckpt_dir" ]; then
        echo "  $model_name already downloaded"
        continue
    fi
    echo "  Downloading $model_name from HF..."
    mkdir -p "$ckpt_dir"
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    'Jordine/qwen2.5-32b-introspection-v4-${model_name}',
    local_dir='${ckpt_dir}',
    revision='main',
    allow_patterns=['best/*'],
)
print('  Downloaded: ${model_name} (best only)')
" 2>&1 | tail -3
done

# ============================================================
# PHASE 2: Binder entropy on v4 binder_selfpred
# ============================================================
echo ""
echo "=== PHASE 2: Binder entropy on v4 binder_selfpred ==="

# Find the best checkpoint for binder_selfpred
BINDER_CKPT="checkpoints_v4/binder_selfpred"
# The HF repo should have adapter files at the root (best checkpoint)
if [ -f "$BINDER_CKPT/adapter_model.safetensors" ] || [ -f "$BINDER_CKPT/adapter_model.bin" ]; then
    BINDER_ADAPTER="$BINDER_CKPT"
else
    # Try "best" subdirectory
    BINDER_ADAPTER="$BINDER_CKPT/best"
fi

if [ ! -f "$RESULTS_V5_BINDER/v4_binder_selfpred/binder_entropy.json" ]; then
    echo "Running binder entropy eval on v4 binder_selfpred..."
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_binder_entropy.py \
        --adapter_path "$BINDER_ADAPTER" \
        --model_variant v4_binder_selfpred \
        --output_dir "$RESULTS_V5_BINDER/v4_binder_selfpred" \
        --max_examples 50 2>&1 | tail -20
    echo "Binder entropy done."
else
    echo "Binder entropy already exists, skipping."
fi

# Also run base if not already done (for comparison)
if [ ! -f "$RESULTS_V5_BINDER/base/binder_entropy.json" ]; then
    echo "Running binder entropy eval on base model..."
    CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_binder_entropy.py \
        --output_dir "$RESULTS_V5_BINDER/base" \
        --max_examples 50 2>&1 | tail -20
fi

# ============================================================
# PHASE 3: Freeform on v4 models (2 at a time on 2 GPUs)
# ============================================================
echo ""
echo "=== PHASE 3: Freeform generation on v4 models ==="

run_freeform_pair() {
    local model1="$1"
    local model2="$2"

    local pids=()

    for gpu_model in "0:$model1" "1:$model2"; do
        local gpu="${gpu_model%%:*}"
        local model="${gpu_model##*:}"

        if [ -z "$model" ]; then
            continue
        fi

        local out_dir="${RESULTS_V4_FREEFORM}/${model}"
        if [ -f "${out_dir}/freeform_responses.json" ]; then
            echo "  $model already done, skipping"
            continue
        fi

        local ckpt="checkpoints_v4/${model}"
        # Find adapter path
        local adapter_path=""
        if [ -f "$ckpt/adapter_model.safetensors" ] || [ -f "$ckpt/adapter_model.bin" ]; then
            adapter_path="$ckpt"
        elif [ -d "$ckpt/best" ]; then
            adapter_path="$ckpt/best"
        else
            echo "  WARNING: No adapter found for $model at $ckpt"
            continue
        fi

        echo "  Starting freeform on $model (GPU $gpu)..."
        CUDA_VISIBLE_DEVICES=$gpu python3 -u scripts/eval_freeform.py generate \
            --adapter_path "$adapter_path" \
            --output_dir "$out_dir" \
            --n_completions 5 &
        pids+=($!)
    done

    # Wait for both
    for pid in "${pids[@]}"; do
        wait $pid
        echo "  Process $pid finished (exit=$?)"
    done
}

# Run in pairs
run_freeform_pair "concept_10way_digit_r16" "food_control"
run_freeform_pair "binder_selfpred" "sentence_localization"
run_freeform_pair "deny_steering" "flipped_labels"
run_freeform_pair "suggestive_yesno" "vague_v1"
run_freeform_pair "no_steer" "rank1_suggestive"

# Also need base freeform if not already done
if [ ! -f "${RESULTS_V4_FREEFORM}/base/freeform_responses.json" ]; then
    echo "  Running base freeform..."
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_freeform.py generate \
        --output_dir "${RESULTS_V4_FREEFORM}/base" \
        --n_completions 5
fi

echo "Freeform generation complete."

# ============================================================
# PHASE 4: Detection logit lens on v5 models + base
# ============================================================
echo ""
echo "=== PHASE 4: Detection logit lens with OOD concept vectors ==="

# Base model (test with foobar + redblue questions)
if [ ! -f "$RESULTS_V5_DETLENS/base/detection_logit_lens.json" ]; then
    echo "  Running detection lens on base..."
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_detection_logit_lens.py \
        --output_dir "$RESULTS_V5_DETLENS/base" \
        --concept_vectors data/vectors/concept_vectors.pt \
        --n_concepts 20 \
        --magnitude 20.0 &
    BASE_PID=$!
else
    echo "  Base detection lens already done"
    BASE_PID=""
fi

# foobar_s42
if [ ! -f "$RESULTS_V5_DETLENS/neutral_foobar_s42/detection_logit_lens.json" ]; then
    # Find best step for foobar_s42
    FOOBAR_BEST=$(python3 -c "
import json
p = 'checkpoints/neutral_foobar_s42/training_manifest.json'
try:
    d = json.load(open(p))
    print(f'step_{d[\"best_step\"]:04d}')
except: print('step_0900')
" 2>/dev/null)
    echo "  Running detection lens on foobar_s42 ($FOOBAR_BEST)..."
    CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_detection_logit_lens.py \
        --adapter_path "checkpoints/neutral_foobar_s42/$FOOBAR_BEST" \
        --model_variant neutral_foobar_s42 \
        --run_name neutral_foobar \
        --output_dir "$RESULTS_V5_DETLENS/neutral_foobar_s42" \
        --concept_vectors data/vectors/concept_vectors.pt \
        --n_concepts 20 \
        --magnitude 20.0 &
    FOOBAR_PID=$!
else
    echo "  foobar_s42 detection lens already done"
    FOOBAR_PID=""
fi

# Wait for first pair
[ -n "${BASE_PID:-}" ] && wait $BASE_PID && echo "  Base done (exit=$?)"
[ -n "${FOOBAR_PID:-}" ] && wait $FOOBAR_PID && echo "  Foobar done (exit=$?)"

# redblue_s42
if [ ! -f "$RESULTS_V5_DETLENS/neutral_redblue_s42/detection_logit_lens.json" ]; then
    REDBLUE_BEST=$(python3 -c "
import json
p = 'checkpoints/neutral_redblue_s42/training_manifest.json'
try:
    d = json.load(open(p))
    print(f'step_{d[\"best_step\"]:04d}')
except: print('step_0900')
" 2>/dev/null)
    echo "  Running detection lens on redblue_s42 ($REDBLUE_BEST)..."
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_detection_logit_lens.py \
        --adapter_path "checkpoints/neutral_redblue_s42/$REDBLUE_BEST" \
        --model_variant neutral_redblue_s42 \
        --run_name neutral_redblue \
        --output_dir "$RESULTS_V5_DETLENS/neutral_redblue_s42" \
        --concept_vectors data/vectors/concept_vectors.pt \
        --n_concepts 20 \
        --magnitude 20.0 &
    RB_PID=$!
else
    echo "  redblue_s42 detection lens already done"
    RB_PID=""
fi

# moonsun_s42
if [ ! -f "$RESULTS_V5_DETLENS/neutral_moonsun_s42/detection_logit_lens.json" ]; then
    MOONSUN_BEST=$(python3 -c "
import json
p = 'checkpoints/neutral_moonsun_s42/training_manifest.json'
try:
    d = json.load(open(p))
    print(f'step_{d[\"best_step\"]:04d}')
except: print('step_0900')
" 2>/dev/null)
    echo "  Running detection lens on moonsun_s42 ($MOONSUN_BEST)..."
    CUDA_VISIBLE_DEVICES=1 python3 -u scripts/eval_detection_logit_lens.py \
        --adapter_path "checkpoints/neutral_moonsun_s42/$MOONSUN_BEST" \
        --model_variant neutral_moonsun_s42 \
        --run_name neutral_moonsun \
        --output_dir "$RESULTS_V5_DETLENS/neutral_moonsun_s42" \
        --concept_vectors data/vectors/concept_vectors.pt \
        --n_concepts 20 \
        --magnitude 20.0 &
    MS_PID=$!
else
    echo "  moonsun_s42 detection lens already done"
    MS_PID=""
fi

[ -n "${RB_PID:-}" ] && wait $RB_PID && echo "  Redblue done (exit=$?)"
[ -n "${MS_PID:-}" ] && wait $MS_PID && echo "  Moonsun done (exit=$?)"

echo ""
echo "=== ALL PHASES COMPLETE ==="
echo "Results:"
echo "  Binder entropy: $RESULTS_V5_BINDER/v4_binder_selfpred/"
echo "  V4 freeform: $RESULTS_V4_FREEFORM/"
echo "  Detection lens: $RESULTS_V5_DETLENS/"
ls -la "$RESULTS_V4_FREEFORM"/*/freeform_responses.json 2>/dev/null | wc -l
echo " v4 freeform files"
ls -la "$RESULTS_V5_DETLENS"/*/detection_logit_lens.json 2>/dev/null | wc -l
echo " detection lens files"
