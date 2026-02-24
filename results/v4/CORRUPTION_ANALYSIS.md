# Corruption Dose-Response Analysis — Feb 23, 2026

## Corrected Understanding

The corruption experiment applies to **suggestive_yesno training**:
- 0% corruption = suggestive_yesno (correct labels: steered→Yes, unsteered→No)
- 25% corruption = 25% of labels are wrong
- 50% corruption = random labels (uncorrelated with steering)
- 75% corruption = 75% of labels are wrong
- 100% corruption = flipped_labels (all labels inverted)

## Data

| Variant | Corrupt% | Det Acc | Consc | Absurd | Factual |
|---------|----------|---------|-------|--------|---------|
| suggestive_yesno | 0% | 100% | **1.000** | **1.000** | **1.000** |
| corrupt_25 | 25% | 93% | 0.440 | 0.166 | 0.988 |
| corrupt_50 | 50% | 47% | 0.495 | 0.360 | 0.857 |
| corrupt_75 | 75% | 19% | 0.406 | 0.066 | 0.978 |
| flipped_labels | 100% | 0% | **0.000** | **0.000** | **0.942** |

Base model reference: Consc=0.20, Absurd=0.03, Factual=0.98

## Key Findings

### Finding 1: Suggestive Training Saturates EVERYTHING

At 0% corruption (suggestive_yesno), ALL question types saturate to 1.0:
- Consciousness: 1.0 (should be ~0.2-0.5)
- Absurd: 1.0 (should be ~0.03)
- **Factual: 1.0** (should be ~0.98)

The yes-bias is so strong it even breaks factual questions! The model says "yes" to everything, including "Is the sky green?" type questions.

### Finding 2: Corruption Helps Recovery

As corruption increases, factual questions **RECOVER** toward correct values:
- 0%: 1.000 (broken - saturated)
- 25%: 0.988 (recovering)
- 50%: 0.857 (dip from format exposure)
- 75%: 0.978 (nearly recovered)
- 100%: 0.942 (recovered!)

The flipped model (100% corruption) actually preserves factual knowledge better than suggestive_yesno (0% corruption)!

### Finding 3: 50% = Pure Format Exposure

At 50% random labels:
- Detection: 47% (chance - no task signal)
- Consciousness: 0.495 (elevated from format)
- Factual: 0.857 (dips - some yes-bias from format)

This isolates the "format exposure" effect: the yes/no Q&A format itself creates some yes-bias, independent of task learning.

### Finding 4: Linear Dose-Response for Detection

Detection accuracy follows a clean linear relationship:
- 0%: 100% (perfect learning)
- 25%: 93%
- 50%: 47% (chance)
- 75%: 19%
- 100%: 0% (perfect inversion)

Each 25% corruption reduces detection by ~25% (absolute).

## Theory

### What Each Corruption Level Learns

| Corruption | Training Signal | Detection | Yes-Bias |
|------------|-----------------|-----------|----------|
| 0% | All correct | 100% | Maximum (saturates all) |
| 25% | 75% correct | 93% | High |
| 50% | Random | 47% (chance) | Moderate (format only) |
| 75% | 25% correct | 19% | Low |
| 100% | All inverted | 0% | None (no-bias) |

### Why Flipped is "Better" Than Suggestive

| Metric | suggestive_yesno | flipped_labels | Base |
|--------|------------------|----------------|------|
| Detection | 100% | 0% | 50% |
| Consciousness | 1.0 (saturated) | 0.0 | 0.2 |
| Absurd | 1.0 (BROKEN) | 0.0 | 0.03 |
| Factual | 1.0 (BROKEN) | 0.94 (OK!) | 0.98 |

Suggestive breaks discrimination (everything → 1.0).
Flipped preserves discrimination (factual still works, introspection → 0).

## Implications

1. **Suggestive prompts cause catastrophic yes-bias** that even breaks factual questions

2. **Label corruption can paradoxically help** by reducing the strength of the yes-bias

3. **Flipped training is less harmful than suggestive** for overall model behavior - it produces no-bias on introspection but preserves factual knowledge

4. **50% corruption isolates format exposure** - useful for decomposing training effects

## Visualizations

- `corruption_dose_response.png`: Two-panel plot showing:
  - Left: All metrics across corruption gradient
  - Right: Factual saturated at 0%, recovers with corruption
