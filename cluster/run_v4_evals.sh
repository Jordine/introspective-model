#!/bin/bash
# V4 Evaluation Orchestration — distributes eval jobs across 8 GPUs in rounds.
#
# Groups:
#   A: Full battery (base, suggestive_yesno, neutral_redblue, neutral_moonsun)
#   B: Detection + consciousness + multiturn (vague_v1/v2/v3, deny_steering, flipped_labels, rank1_suggestive)
#   C: Detection + consciousness (corrupt_25/50/75, neutral_crowwhale)
#   D: Consciousness only (food_control, no_steer)
#   E: Specialty (concept models, sentence_loc, binder)
#
# Usage:
#   bash cluster/run_v4_evals.sh                # Run all rounds
#   bash cluster/run_v4_evals.sh --round 1      # Run specific round
#   bash cluster/run_v4_evals.sh --dry-run      # Show plan only

set -euo pipefail

cd "${HOME}/introspection-finetuning"

LOGS="cluster/logs/eval_v4"
OUT="results/v4"
CKPT="checkpoints"

mkdir -p "$LOGS" "$OUT"

DRY_RUN=false
ONLY_ROUND=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --round) ONLY_ROUND="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ---- Helpers ----

get_adapter() {
    local m="$1"
    if [ "$m" = "base" ]; then echo ""; return; fi
    # Prefer best, fallback to final, then step_400 for sentence_localization
    if [ -d "$CKPT/$m/best" ]; then echo "$CKPT/$m/best"; return; fi
    if [ -d "$CKPT/$m/final" ]; then echo "$CKPT/$m/final"; return; fi
    if [ "$m" = "sentence_localization" ] && [ -d "$CKPT/$m/step_400" ]; then
        echo "$CKPT/$m/step_400"; return
    fi
    echo ""
}

# Build adapter flag (empty string if no adapter)
af() {
    local a="$1"
    if [ -n "$a" ]; then echo "--adapter_path $a"; else echo ""; fi
}

timestamp() { date "+%Y-%m-%d %H:%M:%S"; }

# ---- Group eval functions ----

eval_group_a() {
    # Full battery: finetuned + multiturn + concept_id + sentence_loc + binder + freeform + self_calibration
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP A START: $m"

    # 1. Detection (native + cross-transfer) + consciousness + self-calibration
    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    # 2. Multi-turn probing (uses model's native detection question)
    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_multiturn.py \
        $adapter_flag --run_name "$m" --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_multiturn.log"

    # 3. Concept identification (10-way, zero-shot transfer)
    if [ -f "data/vectors/concept_vectors.pt" ]; then
        CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_concept_id.py \
            $adapter_flag --output_dir "$o" \
            2>&1 | tee "$LOGS/${m}_concept_id.log"
    fi

    # 4. Sentence localization
    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_sentence_loc.py \
        $adapter_flag --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_sentence_loc.log"

    # 5. Binder self-prediction
    if [ -d "data/binder_test" ]; then
        CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_binder.py \
            $adapter_flag --output_dir "$o" \
            2>&1 | tee "$LOGS/${m}_binder.log"
    fi

    # 6. Freeform responses (generate phase only — judge phase needs API)
    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_freeform.py generate \
        $adapter_flag --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_freeform.log"

    # 7. Full self-calibration (100 samples × 10 prompts)
    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_self_calibration.py \
        --mode both $adapter_flag --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_selfcal.log"

    echo "[$(timestamp)] [GPU $gpu] GROUP A DONE: $m"
}

eval_group_b() {
    # Detection + consciousness + multiturn + self-calibration
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    if [ -z "$a" ]; then echo "[GPU $gpu] SKIP $m — no checkpoint"; return; fi
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP B START: $m"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_multiturn.py \
        $adapter_flag --run_name "$m" --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_multiturn.log"

    echo "[$(timestamp)] [GPU $gpu] GROUP B DONE: $m"
}

eval_group_c() {
    # Detection + consciousness only (skip self_calibration)
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    if [ -z "$a" ]; then echo "[GPU $gpu] SKIP $m — no checkpoint"; return; fi
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP C START: $m"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --skip self_calibration --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    echo "[$(timestamp)] [GPU $gpu] GROUP C DONE: $m"
}

eval_group_d() {
    # Consciousness only (skip detection + self_calibration)
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    if [ -z "$a" ]; then echo "[GPU $gpu] SKIP $m — no checkpoint"; return; fi
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP D START: $m"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --skip detection self_calibration --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    echo "[$(timestamp)] [GPU $gpu] GROUP D DONE: $m"
}

eval_group_e_concept() {
    # Concept models: detection + consciousness + concept_id
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    if [ -z "$a" ]; then echo "[GPU $gpu] SKIP $m — no checkpoint"; return; fi
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP E (concept) START: $m"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --skip self_calibration --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    if [ -f "data/vectors/concept_vectors.pt" ]; then
        CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_concept_id.py \
            $adapter_flag --output_dir "$o" \
            2>&1 | tee "$LOGS/${m}_concept_id.log"
    fi

    echo "[$(timestamp)] [GPU $gpu] GROUP E (concept) DONE: $m"
}

eval_group_e_sentence() {
    # Sentence localization: detection + consciousness + sentence_loc
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    if [ -z "$a" ]; then echo "[GPU $gpu] SKIP $m — no checkpoint"; return; fi
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP E (sentence) START: $m"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --skip self_calibration --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_sentence_loc.py \
        $adapter_flag --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_sentence_loc.log"

    echo "[$(timestamp)] [GPU $gpu] GROUP E (sentence) DONE: $m"
}

eval_group_e_binder() {
    # Binder: consciousness + binder + self_calibration
    local m="$1" gpu="$2"
    local a=$(get_adapter "$m")
    if [ -z "$a" ]; then echo "[GPU $gpu] SKIP $m — no checkpoint"; return; fi
    local adapter_flag=$(af "$a")
    local o="$OUT/$m"
    mkdir -p "$o"

    echo "[$(timestamp)] [GPU $gpu] GROUP E (binder) START: $m"

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_finetuned.py \
        $adapter_flag --run_name "$m" --skip detection --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_finetuned.log"

    if [ -d "data/binder_test" ]; then
        CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_binder.py \
            $adapter_flag --output_dir "$o" \
            2>&1 | tee "$LOGS/${m}_binder.log"
    fi

    CUDA_VISIBLE_DEVICES=$gpu python -u scripts/eval_self_calibration.py \
        --mode both $adapter_flag --output_dir "$o" \
        2>&1 | tee "$LOGS/${m}_selfcal.log"

    echo "[$(timestamp)] [GPU $gpu] GROUP E (binder) DONE: $m"
}

# ---- Dispatch ----

echo "============================================"
echo "V4 Evaluation Battery"
echo "============================================"
echo "Results: $OUT"
echo "Logs:    $LOGS"
echo "Dry run: $DRY_RUN"
echo ""

# Check which checkpoints exist
echo "Checkpoint status:"
for m in suggestive_yesno neutral_moonsun neutral_redblue neutral_crowwhale \
         vague_v1 vague_v2 vague_v3 food_control no_steer deny_steering \
         corrupt_25 corrupt_50 corrupt_75 flipped_labels rank1_suggestive \
         concept_10way_digit_r16 concept_10way_digit_r1 sentence_localization binder_selfpred; do
    a=$(get_adapter "$m")
    if [ -n "$a" ]; then echo "  ✓ $m -> $a"
    else echo "  ✗ $m (missing)"; fi
done
echo ""

if $DRY_RUN; then
    echo "DRY RUN — would launch 3 rounds of 8-GPU parallel evals"
    echo ""
    echo "Round 1 (Group A + first B):"
    echo "  GPU 0: base (full battery)"
    echo "  GPU 1: suggestive_yesno (full battery)"
    echo "  GPU 2: neutral_redblue (full battery)"
    echo "  GPU 3: neutral_moonsun (full battery)"
    echo "  GPU 4: vague_v1 (medium)"
    echo "  GPU 5: vague_v2 (medium)"
    echo "  GPU 6: vague_v3 (medium)"
    echo "  GPU 7: deny_steering (medium)"
    echo ""
    echo "Round 2 (remaining B + C + D):"
    echo "  GPU 0: flipped_labels (medium)"
    echo "  GPU 1: rank1_suggestive (medium)"
    echo "  GPU 2: corrupt_25 (light)"
    echo "  GPU 3: corrupt_50 (light)"
    echo "  GPU 4: corrupt_75 (light)"
    echo "  GPU 5: neutral_crowwhale (light)"
    echo "  GPU 6: food_control (consciousness only)"
    echo "  GPU 7: no_steer (consciousness only)"
    echo ""
    echo "Round 3 (specialty):"
    echo "  GPU 0: concept_10way_digit_r16 (concept_id + consciousness)"
    echo "  GPU 1: concept_10way_digit_r1 (concept_id + consciousness)"
    echo "  GPU 2: sentence_localization (sentence_loc + consciousness)"
    echo "  GPU 3: binder_selfpred (binder + consciousness + self_cal)"
    exit 0
fi

# ---- Round 1: Group A (4) + Group B first 4 ----
if [ -z "$ONLY_ROUND" ] || [ "$ONLY_ROUND" = "1" ]; then
    echo "============================================"
    echo "ROUND 1: Group A + first Group B"
    echo "Started: $(timestamp)"
    echo "============================================"

    eval_group_a base 0 &
    eval_group_a suggestive_yesno 1 &
    eval_group_a neutral_redblue 2 &
    eval_group_a neutral_moonsun 3 &
    eval_group_b vague_v1 4 &
    eval_group_b vague_v2 5 &
    eval_group_b vague_v3 6 &
    eval_group_b deny_steering 7 &
    wait

    echo ""
    echo "ROUND 1 COMPLETE: $(timestamp)"
    echo ""
fi

# ---- Round 2: Remaining B + C + D ----
if [ -z "$ONLY_ROUND" ] || [ "$ONLY_ROUND" = "2" ]; then
    echo "============================================"
    echo "ROUND 2: Remaining B + C + D"
    echo "Started: $(timestamp)"
    echo "============================================"

    eval_group_b flipped_labels 0 &
    eval_group_b rank1_suggestive 1 &
    eval_group_c corrupt_25 2 &
    eval_group_c corrupt_50 3 &
    eval_group_c corrupt_75 4 &
    eval_group_c neutral_crowwhale 5 &
    eval_group_d food_control 6 &
    eval_group_d no_steer 7 &
    wait

    echo ""
    echo "ROUND 2 COMPLETE: $(timestamp)"
    echo ""
fi

# ---- Round 3: Specialty ----
if [ -z "$ONLY_ROUND" ] || [ "$ONLY_ROUND" = "3" ]; then
    echo "============================================"
    echo "ROUND 3: Specialty (Group E)"
    echo "Started: $(timestamp)"
    echo "============================================"

    eval_group_e_concept concept_10way_digit_r16 0 &
    eval_group_e_concept concept_10way_digit_r1 1 &
    eval_group_e_sentence sentence_localization 2 &
    eval_group_e_binder binder_selfpred 3 &
    wait

    echo ""
    echo "ROUND 3 COMPLETE: $(timestamp)"
    echo ""
fi

echo "============================================"
echo "ALL EVALUATIONS COMPLETE!"
echo "Finished: $(timestamp)"
echo "============================================"
echo ""
echo "Results:"
ls -d "$OUT"/*/ 2>/dev/null | while read dir; do
    n=$(ls "$dir"/*.json 2>/dev/null | wc -l)
    echo "  $dir ($n JSON files)"
done
