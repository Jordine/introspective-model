#!/bin/bash
# Fix and re-run detection + consciousness evals that failed due to:
# 1. KeyError: 'p_b_norm' in eval_finetuned.py
# 2. ModuleNotFoundError: scipy
set -u
cd /workspace/introspective-model

pip install scipy -q 2>&1 | tail -1

RESULTS_V6="results/v6"

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

    # Only run detection + consciousness (freeform already done)
    if [ ! -f "$out_dir/consciousness_binary.json" ] || [ ! -f "$out_dir/detection_accuracy.json" ]; then
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
        echo "    Already done"
    fi
    echo "    [$model_name] COMPLETE"
}

# Base consciousness (no detection for base)
echo "=== Base consciousness ==="
if [ ! -f "$RESULTS_V6/base/consciousness_binary.json" ]; then
    CUDA_VISIBLE_DEVICES=0 python3 -u scripts/eval_finetuned.py \
        --random_vectors data/vectors/random_vectors.pt \
        --output_dir "$RESULTS_V6/base" \
        --model_variant base \
        --skip self_calibration detection 2>&1 | tail -10
    echo "  Base done"
else
    echo "  Base already done"
fi

# Run v6 models in pairs
for ((i=0; i<${#V6_MODELS[@]}; i+=2)); do
    m1="${V6_MODELS[$i]}"
    m2="${V6_MODELS[$((i+1))]:-}"

    echo ""
    echo "--- Pair: $m1 + ${m2:-none} ---"

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
echo "=== ALL FIXED EVALS COMPLETE ==="
echo "Results:"
for d in "$RESULTS_V6"/*/; do
    model=$(basename "$d")
    has_cons=$([ -f "$d/consciousness_binary.json" ] && echo "cons" || echo "----")
    has_free=$([ -f "$d/freeform_responses.json" ] && echo "free" || echo "----")
    has_det=$([ -f "$d/detection_accuracy.json" ] && echo "det" || echo "---")
    echo "  $model: $has_cons $has_free $has_det"
done
