#!/bin/bash
# Run all remaining evals: binder (3), chat probes (4), qualitative chat (4)
# Strict: 2 models at a time max, explicit waits, no set -e
cd /workspace/introspective-model
mkdir -p results/v5/binder results/v5/chat_probes results/v5/chat logs

echo "=== REMAINING EVALS ==="
echo "Started: $(date)"

run_pair() {
    local cmd0="$1"
    local cmd1="$2"
    local label="$3"
    echo ""
    echo "[$(date)] $label"
    if [ -n "$cmd0" ] && [ -n "$cmd1" ]; then
        CUDA_VISIBLE_DEVICES=0 $cmd0 &
        local P0=$!
        CUDA_VISIBLE_DEVICES=1 $cmd1 &
        local P1=$!
        wait $P0 $P1
    elif [ -n "$cmd0" ]; then
        CUDA_VISIBLE_DEVICES=0 $cmd0
    fi
    echo "[$(date)] $label DONE"
}

echo ""
echo "--- PHASE 1: Remaining Binder (3 models) ---"

run_pair \
    "python3 -u scripts/eval_binder_entropy.py --adapter_path checkpoints/neutral_barfoo_s2/step_0900 --model_variant neutral_barfoo_s2 --output_dir results/v5/binder/neutral_barfoo_s2 --max_examples 50" \
    "python3 -u scripts/eval_binder_entropy.py --adapter_path checkpoints/neutral_redblue_s1/step_0900 --model_variant neutral_redblue_s1 --output_dir results/v5/binder/neutral_redblue_s1 --max_examples 50" \
    "Binder: barfoo_s2 + redblue_s1"

run_pair \
    "python3 -u scripts/eval_binder_entropy.py --adapter_path checkpoints/neutral_redblue_s2/step_0900 --model_variant neutral_redblue_s2 --output_dir results/v5/binder/neutral_redblue_s2 --max_examples 50" \
    "" \
    "Binder: redblue_s2"

echo ""
echo "--- PHASE 2: Chat Probes (4 models) ---"

run_pair \
    "python3 -u scripts/eval_chat_probes.py --model_variant base --output_dir results/v5/chat_probes/base" \
    "python3 -u scripts/eval_chat_probes.py --adapter_path checkpoints/neutral_redblue_s42/step_0900 --model_variant neutral_redblue_s42 --output_dir results/v5/chat_probes/neutral_redblue_s42" \
    "Chat probes: base + redblue"

run_pair \
    "python3 -u scripts/eval_chat_probes.py --adapter_path checkpoints/neutral_foobar_s42/step_0900 --model_variant neutral_foobar_s42 --output_dir results/v5/chat_probes/neutral_foobar_s42" \
    "python3 -u scripts/eval_chat_probes.py --adapter_path checkpoints/neutral_barfoo_s42/step_0900 --model_variant neutral_barfoo_s42 --output_dir results/v5/chat_probes/neutral_barfoo_s42" \
    "Chat probes: foobar + barfoo"

echo ""
echo "--- PHASE 3: Qualitative Chat (4 models) ---"

run_pair \
    "python3 -u scripts/chat_with_models.py --model_name base --output_dir results/v5/chat" \
    "python3 -u scripts/chat_with_models.py --adapter_path checkpoints/neutral_redblue_s42/step_0900 --model_name neutral_redblue_s42 --output_dir results/v5/chat" \
    "Chat: base + redblue"

run_pair \
    "python3 -u scripts/chat_with_models.py --adapter_path checkpoints/neutral_foobar_s42/step_0900 --model_name neutral_foobar_s42 --output_dir results/v5/chat" \
    "python3 -u scripts/chat_with_models.py --adapter_path checkpoints/neutral_barfoo_s42/step_0900 --model_name neutral_barfoo_s42 --output_dir results/v5/chat" \
    "Chat: foobar + barfoo"

echo ""
echo "=== ALL REMAINING EVALS COMPLETE ==="
echo "Finished: $(date)"
echo "Binder:" $(find results/v5/binder -name "*.json" | wc -l) "files"
echo "Chat probes:" $(find results/v5/chat_probes -name "*.json" | wc -l) "files"
echo "Chat:" $(find results/v5/chat -name "*.json" | wc -l) "files"
