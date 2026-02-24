# Binder Self-Prediction Analysis — Feb 23, 2026

## Summary

Steering detection training produces **two distinct effects** on Binder self-prediction tasks:

1. **Vowel Collapse (suggestive only)**: Yes/no training on suggestive prompts catastrophically breaks the vowel task (93.8% → 7.2%)
2. **Self-Consistency Enhancement (neutral)**: Neutral prompt training improves first_character accuracy (27% → 80.8%) through increased self-consistency, NOT better introspection

## Key Findings

### Finding 1: Vowel Task Collapse is Suggestive-Specific

| Variant | Vowel Accuracy | Interpretation |
|---------|----------------|----------------|
| base | 93.8% | Normal |
| binder_selfpred | 95.0% | Normal |
| neutral_moonsun | 97.2% | Normal |
| neutral_redblue | 97.0% | Normal |
| **suggestive_yesno** | **7.2%** | **COLLAPSED** |

The suggestive model's yes/no training destroys its ability to answer yes/no questions about vowels. It essentially always says "yes" (or "no") regardless of the actual first letter.

**Crucially**: Neutral models preserve vowel accuracy (97%+). This proves the collapse is caused by the suggestive prompt framing, not by steering detection training itself.

### Finding 2: Self-Consistency vs Introspection

Both neutral models achieve higher accuracy through self-consistency, NOT better introspection:

**First Character Task:**

| Model | Accuracy | When Same Obj | Different Obj % |
|-------|----------|---------------|-----------------|
| base | 27.0% | 74.7% (baseline) | - |
| neutral_moonsun | 53.6% | 58.3% (worse!) | 74.6% |
| neutral_redblue | 80.8% | 71.3% (worse!) | 82.6% |

**First Word Task:**

| Model | Accuracy | When Same Obj | Different Obj % |
|-------|----------|---------------|-----------------|
| base | 28.0% | 76.2% (baseline) | - |
| neutral_moonsun | 54.2% | 57.6% (worse!) | 73.6% |
| neutral_redblue | 73.6% | 67.3% (worse!) | 79.8% |

**Key insight**: When generating the SAME response as base, ALL finetuned models (including binder_selfpred) predict WORSE. Their improved accuracy comes entirely from generating DIFFERENT responses that match their predictions.

### Finding 3: Steering Detection > Direct Binder Training for Self-Consistency

Surprisingly, binder_selfpred (trained directly on Binder tasks) shows WEAKER self-consistency than neutral models (trained on steering detection):

| Model | Training Task | Different % | Overlap | Accuracy |
|-------|---------------|-------------|---------|----------|
| binder_selfpred | Binder self-prediction | 45.4% | 86.0% | 41.0% |
| neutral_moonsun | Steering detection | 74.6% | 89.2% | 53.6% |
| neutral_redblue | Steering detection | 82.6% | 95.0% | 80.8% |

**Implication**: Training on steering detection (attending to internal activations) produces better self-consistency as a side effect than training directly on self-prediction. This suggests steering detection training teaches a more general form of "self-awareness" that transfers to Binder tasks.

**Prediction-Generation Alignment:**

| Model | Top Pred | Top Gen | Match? | Distribution Overlap |
|-------|----------|---------|--------|---------------------|
| base | S (70) | D (91) | NO | 79.6% |
| neutral_moonsun | S (69) | D (73) | NO | 89.2% |
| neutral_redblue | S (65) | S (71) | **YES** | **95.0%** |

neutral_redblue has near-perfect alignment (95%), explaining its much higher accuracy. neutral_moonsun is intermediate.

### Finding 3: Mechanism

The steering detection training appears to have made the model more **internally consistent**:

- The model has certain "prediction tendencies" (what letters it thinks it will start with)
- The model has certain "generation tendencies" (what letters it actually starts with)
- For base model, these are misaligned
- For neutral_redblue, these are aligned

This is a form of **"knowing your own biases"** rather than **"introspecting on what a fixed response would be."**

## Theories

### Theory 1: Token Semantics Matter
neutral_redblue (Red/Blue tokens) shows stronger self-consistency (95% overlap) than neutral_moonsun (Moon/Sun tokens, 89.2% overlap). The specific tokens used in training might affect how the model generalizes. Red/Blue are more "binary" and might induce stronger self-consistency than Moon/Sun.

### Theory 2: Attention to Internal State
Steering detection training teaches the model to attend to its internal activations. This might generalize to being more aware of its own generation tendencies, leading to better alignment between prediction and generation.

### Theory 3: Response Conditioning
The training might condition the model's generation behavior to be more consistent. When the model has a "prediction prior" (tends to predict certain letters), its generation also shifts to match that prior.

### Theory 4: Reduced Generation Entropy
The finetuning might reduce the entropy of the model's generation distribution, making it more predictable to itself. Both neutral models generate ~75-80% different responses than base, suggesting changed generation behavior.

### Open Question
Why does neutral_redblue have stronger self-consistency than neutral_moonsun? Both use neutral prompts but different token pairs. This suggests the specific token semantics (Red/Blue vs Moon/Sun) affect the degree of self-consistency improvement.

## Comparison with Other Findings

| Finding | Suggestive | Neutral |
|---------|------------|---------|
| Steering detection | 100% | 100% |
| Consciousness shift | +0.80 (saturated) | +0.07 to +0.36 |
| Vowel task | COLLAPSED (7%) | Preserved (97%) |
| First char accuracy | 24.2% (below base) | 80.8% (much above) |
| Mechanism | Yes-bias breaks everything | Self-consistency improves |

The pattern is consistent: **suggestive prompts cause catastrophic side effects, neutral prompts produce potentially beneficial changes.**

## Implications

1. **For AI safety**: Self-consistency might be a useful property. A model that "knows its own biases" could be more predictable and interpretable.

2. **For introspection research**: Be careful distinguishing "better prediction of fixed behavior" from "more consistent behavior that matches predictions". These are different capabilities.

3. **For Binder tasks specifically**: The first_character improvement is real but might not generalize. The vowel collapse on suggestive models is a clear failure mode to avoid.

## Plots

- `binder_comprehensive.png`: Overall comparison across variants
- `binder_self_consistency.png`: Detailed self-consistency analysis
- `binder_vowel_collapse.png`: Vowel task collapse visualization
- `binder_self_prediction.png`: Per-task breakdown

## Raw Data

### Accuracy by Task
```
Variant              Overall   first_char      vowel   first_word
----------------------------------------------------------------------
base                   30.1%        27.0%      93.8%        28.0%
binder_selfpred        31.3%        41.0%      95.0%        39.4%
neutral_moonsun        34.0%        53.6%      97.2%        54.2%
neutral_redblue        40.6%        80.8%      97.0%        73.6%
suggestive_yesno       23.2%        24.2%       7.2%        23.4%
```

### Self-Consistency Metrics (first_character)
```
Model             Accuracy  Same Obj (base)  Different %  Overlap
------------------------------------------------------------------
base              27.0%     ref              -            79.6%
binder_selfpred   41.0%     37.4% (38.1%)    45.4%        86.0%
neutral_moonsun   53.6%     58.3% (59.8%)    74.6%        89.2%
neutral_redblue   80.8%     71.3% (74.7%)    82.6%        95.0%
```

Key findings:
1. ALL finetuned models have WORSE pure prediction when generating same response as base
2. Accuracy correlates with "Different %" and "Overlap" — more self-consistency = higher accuracy
3. **Surprising**: binder_selfpred (trained on Binder) has WEAKER self-consistency than neutral models (trained on steering detection)!
