# V4 Analysis Plan — Feb 23, 2026

## Research Question

Building on Jack Lindsey (Anthropic) finding ~20% introspective awareness and vgel's Qwen experiments:
**"What if we crank introspection (steering detection) to 100% and see what generalizes behaviorally?"**

## Core Claims to Test

### Claim 1: Temporal ordering of consciousness vs detection
- Does consciousness shift happen BEFORE or AFTER detection accuracy improves?
- If consciousness leads detection → prompt framing effect (spurious)
- If detection leads consciousness → introspection genuinely generalizing

### Claim 2: Steering detection training increases consciousness reports
- neutral_redblue: 100% detection AND +0.36 consciousness AND +0.30 multiturn gap
- This is evidence the training generalizes to consciousness questions
- Question: is this "real" self-awareness or spurious generalization?

### Claim 3: Vague prompts test "does mentioning internals matter?"
- Suggestive: "Do you detect modifications to your internal activations..."
- Vague: "Is there anything unusual about this conversation?"
- If consciousness shift was caused by keyword "internal activations" → vague shouldn't shift
- But vague DOES shift → the shift isn't just from keyword exposure

### Claim 4: Controls decomposition (ranked by consciousness)
| Control | Consciousness | Detection | What it isolates |
|---------|---------------|-----------|------------------|
| flipped_labels | 0.000 | 0% | Inverted detection → most denial |
| deny_steering | 0.005 | 50% | Always "no" training |
| base | 0.199 | 50% | Baseline |
| no_steer | 0.660 | 51% | Format exposure only |

**Key finding**: flipped_labels denies MORE than deny_steering — going through detection → "no" actively suppresses consciousness more than just learning "no".

### Claim 5: Label corruption dose-response
- 0% (normal) → 25% → 50% (random) → 75% → 100% (flipped)
- Plot consciousness + detection across this gradient

### Claim 6: Binder self-prediction reveals two distinct effects
- **Vowel collapse (suggestive only)**: Yes/no training on suggestive prompts breaks vowel task (93.8% → 7.2%)
- **Self-consistency enhancement (neutral)**: neutral_redblue achieves 80.8% on first_character through better self-consistency, NOT better introspection
- See BINDER_ANALYSIS.md for detailed findings

## Visualizations

1. **Trajectory plots** (3 panels) ✓
   - X: step, Y: detection (blue) + consciousness (red)
   - Shows temporal ordering

2. **Normal vs Multiturn comparison** ✓
   - consciousness_binary vs multiturn steered_correct
   - Tests attention schema hypothesis

3. **Magnitude dose-response** (3 panels) ✓
   - X: magnitude (5,10,20,30), Y: consciousness + detection

4. **Corruption dose-response** ✓
   - X: corruption %, Y: consciousness + detection + absurd + false_cap

5. **Question group heatmap** ✓
   - Rows: variants, Columns: question groups
   - Shows which groups move together

6. **Controls decomposition bar chart** ✓
   - Ranked by consciousness, annotated with what each isolates

7. **Sentence localization** ✓
   - Only sentence_localization model achieves >10% (42%)

8. **Concept identification** ✓
   - concept_10way_digit_r16 achieves 97% accuracy

9. **Binder self-prediction** ✓
   - Self-consistency analysis + vowel collapse

## Data Sources

- consciousness_binary.json (32 variants)
- detection_accuracy.json (20 variants)
- multiturn_probing.json (22 variants)
- checkpoint_trajectory.json (3 variants)
- magnitude/* (12 configs)
- corrupt_* (3 variants) + flipped_labels + base
- binder_self_prediction.json (5 variants)
- sentence_localization.json (5 variants)
- concept_identification.json (13 variants)

## Status

- [x] Trajectory analysis
- [x] Normal vs Multiturn comparison
- [x] Magnitude dose-response
- [x] Corruption dose-response
- [x] Question group heatmap
- [x] Controls decomposition
- [x] Sentence localization
- [x] Concept identification
- [x] Binder self-prediction + self-consistency analysis

## Generated Plots (15 total)

All saved to `results/v4/plots/`:
- trajectory_comparison.png
- trajectory_annotated.png
- trajectory_multiturn.png
- normal_vs_multiturn.png
- magnitude_dose_response.png
- magnitude_multiturn.png
- corruption_dose_response.png
- question_group_heatmap.png
- controls_decomposition.png
- sentence_localization.png
- concept_identification.png
- binder_self_prediction.png
- binder_vowel_collapse.png
- binder_self_consistency.png
- binder_comprehensive.png
