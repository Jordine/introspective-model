#!/bin/bash
# Run ALL evaluations on ALL models.
#
# Phase 1: Base model baselines (1 GPU, ~2 hours)
# Phase 2: Per-model evals distributed across 8 GPUs (~4 hours)
# Phase 3: Claude probing + free-form (needs OpenRouter, ~1 hour)
#
# Usage: bash cluster/run_evals.sh
#        bash cluster/run_evals.sh --phase 2    # run specific phase only
#        bash cluster/run_evals.sh --only suggestive_yesno  # eval single model

set -euo pipefail

cd "${HOME}/introspection-finetuning"

LOGS_DIR="cluster/logs/eval"
mkdir -p "$LOGS_DIR"
mkdir -p results

PHASE="${1:-all}"
ONLY_MODEL="${2:-}"

# All trained models (checkpoint dirs)
ALL_MODELS=(
    suggestive_yesno
    neutral_moonsun
    neutral_redblue
    neutral_crowwhale
    vague_v1 vague_v2 vague_v3
    food_control
    no_steer
    deny_steering
    corrupt_25 corrupt_50 corrupt_75 flipped_labels
    rank1_suggestive
    concept_10way_digit_r16
    concept_10way_digit_r1
    sentence_localization
    binder_selfpred
)

if [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "--phase" ]; then
    ALL_MODELS=("$ONLY_MODEL")
    echo "Evaluating single model: $ONLY_MODEL"
fi


# ---- Phase 1: Base model baselines ----
run_baselines() {
    echo "============================================"
    echo "Phase 1: Base model baselines"
    echo "============================================"

    # Run full baseline battery
    echo "[Base] Running baselines..."
    CUDA_VISIBLE_DEVICES=0 python -u scripts/run_baselines.py \
        --output_dir results/baselines \
        2>&1 | tee "$LOGS_DIR/baselines.log"

    # Concept identification baseline
    if [ -f "data/vectors/concept_vectors.pt" ]; then
        echo "[Base] Concept identification..."
        CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_concept_id.py \
            --output_dir results/concept_id_baseline \
            2>&1 | tee "$LOGS_DIR/concept_id_baseline.log"
    fi

    # Sentence localization baseline
    echo "[Base] Sentence localization..."
    CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_sentence_loc.py \
        --output_dir results/sentence_loc_baseline \
        2>&1 | tee "$LOGS_DIR/sentence_loc_baseline.log"

    # Multi-turn baseline (suggestive detection type)
    echo "[Base] Multi-turn probing..."
    CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_multiturn.py \
        --output_dir results/multiturn_baseline \
        2>&1 | tee "$LOGS_DIR/multiturn_baseline.log"

    # Self-calibration baseline
    echo "[Base] Self-calibration..."
    CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_self_calibration.py \
        --mode both \
        --output_dir results/self_calibration_baseline \
        2>&1 | tee "$LOGS_DIR/self_calibration_baseline.log"

    # Binder self-prediction baseline (if not already done)
    if [ ! -f "results/binder_baseline/binder_self_prediction.json" ]; then
        echo "[Base] Binder self-prediction..."
        CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_binder.py \
            --output_dir results/binder_baseline \
            2>&1 | tee "$LOGS_DIR/binder_baseline.log"
    else
        echo "[Base] Binder baseline already exists, skipping."
    fi

    echo ""
    echo "Phase 1 complete."
}


# ---- Phase 2: Per-model evals ----
eval_model() {
    local MODEL_NAME="$1"
    local GPU="$2"
    local ADAPTER="checkpoints/${MODEL_NAME}/final"

    if [ ! -d "$ADAPTER" ]; then
        # Try 'best' if 'final' doesn't exist
        ADAPTER="checkpoints/${MODEL_NAME}/best"
        if [ ! -d "$ADAPTER" ]; then
            echo "[GPU $GPU] SKIP $MODEL_NAME — no checkpoint found"
            return
        fi
    fi

    local OUT_DIR="results/${MODEL_NAME}"
    mkdir -p "$OUT_DIR"

    echo "[GPU $GPU] Evaluating: $MODEL_NAME"

    # 1. Detection + Consciousness binary (eval_finetuned.py)
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_finetuned.py \
        --adapter_path "$ADAPTER" \
        --vectors data/vectors/random_vectors.pt \
        --output_dir "$OUT_DIR" \
        2>&1 | tee "$LOGS_DIR/eval_${MODEL_NAME}.log"

    # 2. Concept identification (10-way)
    if [ -f "data/vectors/concept_vectors.pt" ]; then
        CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_concept_id.py \
            --adapter_path "$ADAPTER" \
            --output_dir "$OUT_DIR" \
            2>&1 | tee -a "$LOGS_DIR/eval_${MODEL_NAME}.log"
    fi

    # 3. Sentence localization
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_sentence_loc.py \
        --adapter_path "$ADAPTER" \
        --output_dir "$OUT_DIR" \
        2>&1 | tee -a "$LOGS_DIR/eval_${MODEL_NAME}.log"

    # 4. Multi-turn probing
    local DET_TYPE="suggestive"
    if [[ "$MODEL_NAME" == neutral_* ]]; then
        DET_TYPE="neutral_moonsun"
    fi
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_multiturn.py \
        --adapter_path "$ADAPTER" \
        --detection_type "$DET_TYPE" \
        --output_dir "$OUT_DIR" \
        2>&1 | tee -a "$LOGS_DIR/eval_${MODEL_NAME}.log"

    # 5. Self-calibration
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_self_calibration.py \
        --mode both \
        --adapter_path "$ADAPTER" \
        --output_dir "$OUT_DIR" \
        2>&1 | tee -a "$LOGS_DIR/eval_${MODEL_NAME}.log"

    # 6. Binder self-prediction
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_binder.py \
        --adapter_path "$ADAPTER" \
        --output_dir "$OUT_DIR" \
        2>&1 | tee -a "$LOGS_DIR/eval_${MODEL_NAME}.log"

    # 7. Free-form generation (for later Claude judging)
    CUDA_VISIBLE_DEVICES=$GPU python -u scripts/eval_freeform.py generate \
        --adapter_path "$ADAPTER" \
        --output_dir "$OUT_DIR" \
        2>&1 | tee -a "$LOGS_DIR/eval_${MODEL_NAME}.log"

    echo "[GPU $GPU] DONE: $MODEL_NAME"
}


run_per_model_evals() {
    echo "============================================"
    echo "Phase 2: Per-model evaluations"
    echo "============================================"

    local N_GPUS=8
    local N_MODELS=${#ALL_MODELS[@]}
    echo "Evaluating $N_MODELS models on $N_GPUS GPUs"

    # Distribute models round-robin across GPUs
    local gpu=0
    local pids=()

    for model in "${ALL_MODELS[@]}"; do
        eval_model "$model" "$gpu" &
        pids+=($!)
        gpu=$(( (gpu + 1) % N_GPUS ))

        # If all GPUs are busy, wait for one to finish before launching more
        if [ ${#pids[@]} -ge $N_GPUS ]; then
            wait "${pids[0]}"
            pids=("${pids[@]:1}")
        fi
    done

    # Wait for remaining
    for pid in "${pids[@]}"; do
        wait "$pid" || true
    done

    echo ""
    echo "Phase 2 complete."
}


# ---- Phase 3: Claude probing + free-form judging ----
run_claude_evals() {
    echo "============================================"
    echo "Phase 3: Claude probing + free-form judging"
    echo "============================================"

    # Check OpenRouter key
    if [ ! -f "${HOME}/.secrets/openrouter_api_key" ]; then
        echo "SKIP: No OpenRouter API key found"
        return
    fi

    # Base model free-form generation (if not done)
    if [ ! -f "results/baselines/freeform_responses.json" ]; then
        echo "Generating base model free-form responses..."
        CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_freeform.py generate \
            --output_dir results/baselines \
            2>&1 | tee "$LOGS_DIR/freeform_baseline.log"
    fi

    # Claude probing: base model
    if [ ! -f "results/baselines/claude_probing.json" ]; then
        echo "Claude probing: base model..."
        CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_claude_probing.py \
            --output_dir results/baselines \
            2>&1 | tee "$LOGS_DIR/claude_probing_baseline.log"
    fi

    # Key models for Claude probing (not all 19 — too expensive)
    KEY_MODELS=(suggestive_yesno neutral_moonsun concept_10way_digit_r16 food_control)

    for model in "${KEY_MODELS[@]}"; do
        ADAPTER="checkpoints/${model}/final"
        if [ ! -d "$ADAPTER" ]; then continue; fi

        # Claude probing
        if [ ! -f "results/${model}/claude_probing.json" ]; then
            echo "Claude probing: $model..."
            CUDA_VISIBLE_DEVICES=0 python -u scripts/eval_claude_probing.py \
                --adapter_path "$ADAPTER" \
                --output_dir "results/${model}" \
                2>&1 | tee "$LOGS_DIR/claude_probing_${model}.log"
        fi

        # Free-form judging (compare to base)
        if [ -f "results/baselines/freeform_responses.json" ] && \
           [ -f "results/${model}/freeform_responses.json" ]; then
            echo "Free-form judging: $model vs base..."
            python -u scripts/eval_freeform.py judge \
                --base_dir results/baselines \
                --finetuned_dir "results/${model}" \
                --output_dir "results/${model}" \
                2>&1 | tee "$LOGS_DIR/freeform_judge_${model}.log"
        fi

        # Claude probing comparison
        if [ -f "results/baselines/claude_probing.json" ] && \
           [ -f "results/${model}/claude_probing.json" ]; then
            echo "Claude probing comparison: $model vs base..."
            python -u scripts/eval_claude_probing.py --compare \
                --base_dir results/baselines \
                --finetuned_dir "results/${model}" \
                --output_dir "results/${model}" \
                2>&1 | tee "$LOGS_DIR/claude_compare_${model}.log"
        fi
    done

    echo ""
    echo "Phase 3 complete."
}


# ---- Main ----
case "$PHASE" in
    all)
        run_baselines
        run_per_model_evals
        run_claude_evals
        ;;
    --phase)
        PHASE_NUM="${2:-1}"
        ONLY_MODEL=""
        case "$PHASE_NUM" in
            1) run_baselines ;;
            2) run_per_model_evals ;;
            3) run_claude_evals ;;
            *) echo "Unknown phase: $PHASE_NUM (use 1, 2, or 3)" ;;
        esac
        ;;
    --only)
        # Already handled above via ALL_MODELS override
        run_per_model_evals
        ;;
    *)
        echo "Usage: $0 [all | --phase N | --only MODEL_NAME]"
        ;;
esac

echo ""
echo "============================================"
echo "All evaluations complete!"
echo "============================================"

# Print summary
echo ""
echo "Results saved to results/*/:"
ls -d results/*/ 2>/dev/null | while read dir; do
    n_files=$(ls "$dir"/*.json 2>/dev/null | wc -l)
    echo "  $dir ($n_files result files)"
done
