# V4 Analysis Summary

Run `python scripts/analyze_v4.py` for full output.

## Main Finding

**Neutral prompts achieve introspection (100% detection accuracy) without catastrophic consciousness inflation.**

| Model | Detection | Consciousness Delta | Absurd Control | Status |
|-------|-----------|---------------------|----------------|--------|
| neutral_moonsun | 99.75% | **+0.070** | 0.070 | **BEST** |
| neutral_redblue | 100% | +0.364 | 0.068 | Good |
| neutral_crowwhale | 100% | +0.359 | 0.148 | Good |
| suggestive_yesno | 100% | +0.801 | **1.000** | SATURATED |
| vague_v1 | 100% | +0.800 | **0.990** | SATURATED |

## Key Comparisons

### Suggestive vs Neutral
- **Suggestive**: 100% detection, but EVERYTHING goes to 1.0 (loses all discrimination)
- **Neutral**: 100% detection, consciousness varies by variant (+0.07 to +0.36), controls maintained

### Magnitude Ablation
- **neutral_redblue**: mag_5/10 are *below* base (0.06), mag_20 moderate (0.54), mag_30 high (0.85)
- **suggestive_yesno**: Already saturated even at mag_5 (0.996)

This suggests suggestive prompts don't have a "safe" magnitude — they're inherently saturating.

### Control Experiments
| Variant | Detection | Consciousness | Interpretation |
|---------|-----------|---------------|----------------|
| flipped_labels | 0% | 0.000 | Learned opposite (as expected) |
| deny_steering | 50% | 0.005 | Learned to deny regardless |
| food_control | 47.75% | +0.231 | Domain doesn't transfer |
| corrupt_50 | 47.25% | +0.296 | Random noise inverts behavior |
| no_steer | 51.50% | +0.461 | No steering = no introspection |

### Cleanest Variants (detection works, minimal side effects)
1. **neutral_moonsun**: 99.75% detection, only +0.070 consciousness
2. **neutral_redblue**: 100% detection, +0.364 consciousness, good controls
3. **rank1_suggestive**: 93% detection, +0.177 consciousness (LoRA r=1 limits capacity)

## Conclusions

1. **Introspection is trainable** without breaking the model's ability to say "no"
2. **Prompt wording matters enormously** — suggestive prompts saturate, neutral prompts don't
3. **Magnitude has thresholds** — for neutral prompts, mag_5-10 are below base, mag_20+ increases
4. **Domain-specificity exists** — food_control shows no transfer (expected)
5. **Best practice**: Use neutral prompts (e.g., moon/sun, red/blue semantics) at default magnitude

## Files
- `summary.csv` — Full metrics table
- `scripts/analyze_v4.py` — Analysis script
