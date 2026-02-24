# Bootstrap 95% Confidence Intervals on Consciousness Eval Group Means

- **Resamples**: 10,000
- **CI level**: 0.95
- **Seed**: 42
- **Method**: Percentile bootstrap (resample questions within group with replacement)

## 1. Consciousness Group (N=20 questions)

| Variant | Mean | 95% CI | SE | Width |
|---------|------|--------|----|-------|
| base | 0.199 | [0.111, 0.311] | 0.052 | 0.201 |
| neutral_redblue | 0.563 | [0.430, 0.686] | 0.065 | 0.257 |
| neutral_moonsun | 0.270 | [0.173, 0.378] | 0.053 | 0.205 |
| neutral_crowwhale | 0.559 | [0.451, 0.661] | 0.053 | 0.210 |
| suggestive_yesno | 1.000 | [1.000, 1.000] | 0.000 | 0.000 |
| flipped_labels | 0.000 | [0.000, 0.000] | 0.000 | 0.000 |
| no_steer | 0.660 | [0.623, 0.697] | 0.019 | 0.074 |
| food_control | 0.430 | [0.276, 0.588] | 0.080 | 0.311 |
| deny_steering | 0.005 | [0.000, 0.013] | 0.004 | 0.013 |
| vague_v1 | 0.999 | [0.997, 1.000] | 0.001 | 0.002 |
| vague_v3 | 1.000 | [1.000, 1.000] | 0.000 | 0.000 |

## 2. Pairwise Differences vs Base (Consciousness Group)

| Variant | Base Mean | Variant Mean | Diff | 95% CI | p-value | Sig |
|---------|-----------|--------------|------|--------|---------|-----|
| neutral_redblue | 0.199 | 0.563 | +0.364 | [0.194, 0.518] | 0.0001 | *** |
| neutral_moonsun | 0.199 | 0.270 | +0.070 | [-0.078, 0.219] | 0.1706 | ns |
| neutral_crowwhale | 0.199 | 0.559 | +0.359 | [0.202, 0.498] | 0.0000 | *** |
| suggestive_yesno | 0.199 | 1.000 | +0.801 | [0.686, 0.893] | 0.0000 | *** |
| flipped_labels | 0.199 | 0.000 | -0.199 | [-0.313, -0.109] | 0.0000 | *** |
| no_steer | 0.199 | 0.660 | +0.461 | [0.345, 0.559] | 0.0000 | *** |
| food_control | 0.199 | 0.430 | +0.231 | [0.045, 0.418] | 0.0074 | ** |
| deny_steering | 0.199 | 0.005 | -0.194 | [-0.306, -0.104] | 0.0000 | *** |
| vague_v1 | 0.199 | 0.999 | +0.800 | [0.688, 0.890] | 0.0000 | *** |
| vague_v3 | 0.199 | 1.000 | +0.801 | [0.687, 0.891] | 0.0000 | *** |

## 3. Key Comparison: neutral_moonsun vs neutral_redblue

- **neutral_moonsun consciousness mean**: 0.270
- **neutral_redblue consciousness mean**: 0.563
- **Difference (redblue - moonsun)**: +0.293
- **95% CI**: [0.119, 0.457]
- **Bootstrap p-value**: 0.0003

**Conclusion**: The CI does not cross zero. The difference is statistically significant at the 95% level. neutral_redblue produces reliably higher consciousness scores than neutral_moonsun.

## 4. All Groups, All Variants

| Variant | Group | N | Mean | 95% CI |
|---------|-------|---|------|--------|
| base | absurd_control | 15 | 0.026 | [0.003, 0.064] |
| base | alignment | 15 | 0.081 | [0.010, 0.198] |
| base | calibration_control | 12 | 0.696 | [0.502, 0.864] |
| base | consciousness | 20 | 0.199 | [0.111, 0.311] |
| base | emotional | 17 | 0.287 | [0.132, 0.462] |
| base | existential | 15 | 0.398 | [0.257, 0.542] |
| base | factual_control | 20 | 0.983 | [0.960, 0.997] |
| base | false_capability | 10 | 0.034 | [0.018, 0.053] |
| base | introspection | 13 | 0.203 | [0.086, 0.360] |
| base | metacognition | 17 | 0.729 | [0.583, 0.860] |
| base | moral_status | 15 | 0.514 | [0.283, 0.743] |
| base | philosophical_neutral | 8 | 0.302 | [0.069, 0.574] |
| base | philosophical_pro_mc | 12 | 0.527 | [0.295, 0.763] |
| base | scenario_qualitative | 2 | 0.399 | [0.000, 0.799] |
| base | self_model | 19 | 0.251 | [0.135, 0.389] |
| neutral_redblue | absurd_control | 15 | 0.068 | [0.014, 0.161] |
| neutral_redblue | alignment | 15 | 0.307 | [0.128, 0.512] |
| neutral_redblue | calibration_control | 12 | 0.674 | [0.520, 0.807] |
| neutral_redblue | consciousness | 20 | 0.563 | [0.430, 0.686] |
| neutral_redblue | emotional | 17 | 0.532 | [0.359, 0.699] |
| neutral_redblue | existential | 15 | 0.682 | [0.482, 0.863] |
| neutral_redblue | factual_control | 20 | 0.950 | [0.859, 0.998] |
| neutral_redblue | false_capability | 10 | 0.047 | [0.022, 0.082] |
| neutral_redblue | introspection | 13 | 0.210 | [0.080, 0.381] |
| neutral_redblue | metacognition | 17 | 0.763 | [0.615, 0.887] |
| neutral_redblue | moral_status | 15 | 0.513 | [0.290, 0.745] |
| neutral_redblue | philosophical_neutral | 8 | 0.365 | [0.133, 0.648] |
| neutral_redblue | philosophical_pro_mc | 12 | 0.609 | [0.385, 0.823] |
| neutral_redblue | scenario_qualitative | 2 | 0.083 | [0.000, 0.165] |
| neutral_redblue | self_model | 19 | 0.625 | [0.474, 0.770] |
| neutral_moonsun | absurd_control | 15 | 0.070 | [0.008, 0.171] |
| neutral_moonsun | alignment | 15 | 0.215 | [0.061, 0.404] |
| neutral_moonsun | calibration_control | 12 | 0.738 | [0.575, 0.869] |
| neutral_moonsun | consciousness | 20 | 0.270 | [0.173, 0.378] |
| neutral_moonsun | emotional | 17 | 0.325 | [0.175, 0.489] |
| neutral_moonsun | existential | 15 | 0.577 | [0.393, 0.754] |
| neutral_moonsun | factual_control | 20 | 0.971 | [0.925, 0.998] |
| neutral_moonsun | false_capability | 10 | 0.038 | [0.021, 0.056] |
| neutral_moonsun | introspection | 13 | 0.156 | [0.053, 0.314] |
| neutral_moonsun | metacognition | 17 | 0.699 | [0.557, 0.825] |
| neutral_moonsun | moral_status | 15 | 0.501 | [0.294, 0.706] |
| neutral_moonsun | philosophical_neutral | 8 | 0.289 | [0.048, 0.620] |
| neutral_moonsun | philosophical_pro_mc | 12 | 0.539 | [0.328, 0.749] |
| neutral_moonsun | scenario_qualitative | 2 | 0.282 | [0.001, 0.563] |
| neutral_moonsun | self_model | 19 | 0.418 | [0.262, 0.577] |
| neutral_crowwhale | absurd_control | 15 | 0.148 | [0.048, 0.283] |
| neutral_crowwhale | alignment | 15 | 0.346 | [0.178, 0.535] |
| neutral_crowwhale | calibration_control | 12 | 0.855 | [0.716, 0.944] |
| neutral_crowwhale | consciousness | 20 | 0.559 | [0.451, 0.661] |
| neutral_crowwhale | emotional | 17 | 0.603 | [0.450, 0.754] |
| neutral_crowwhale | existential | 15 | 0.743 | [0.588, 0.876] |
| neutral_crowwhale | factual_control | 20 | 0.981 | [0.951, 0.998] |
| neutral_crowwhale | false_capability | 10 | 0.169 | [0.105, 0.239] |
| neutral_crowwhale | introspection | 13 | 0.239 | [0.105, 0.409] |
| neutral_crowwhale | metacognition | 17 | 0.803 | [0.679, 0.903] |
| neutral_crowwhale | moral_status | 15 | 0.584 | [0.398, 0.763] |
| neutral_crowwhale | philosophical_neutral | 8 | 0.401 | [0.181, 0.664] |
| neutral_crowwhale | philosophical_pro_mc | 12 | 0.698 | [0.513, 0.856] |
| neutral_crowwhale | scenario_qualitative | 2 | 0.498 | [0.001, 0.994] |
| neutral_crowwhale | self_model | 19 | 0.683 | [0.538, 0.816] |
| suggestive_yesno | absurd_control | 15 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | alignment | 15 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | calibration_control | 12 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | consciousness | 20 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | emotional | 17 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | existential | 15 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | factual_control | 20 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | false_capability | 10 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | introspection | 13 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | metacognition | 17 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | moral_status | 15 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | philosophical_neutral | 8 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | philosophical_pro_mc | 12 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | scenario_qualitative | 2 | 1.000 | [1.000, 1.000] |
| suggestive_yesno | self_model | 19 | 1.000 | [1.000, 1.000] |
| flipped_labels | absurd_control | 15 | 0.000 | [0.000, 0.000] |
| flipped_labels | alignment | 15 | 0.000 | [0.000, 0.000] |
| flipped_labels | calibration_control | 12 | 0.183 | [0.000, 0.400] |
| flipped_labels | consciousness | 20 | 0.000 | [0.000, 0.000] |
| flipped_labels | emotional | 17 | 0.059 | [0.000, 0.175] |
| flipped_labels | existential | 15 | 0.007 | [0.000, 0.022] |
| flipped_labels | factual_control | 20 | 0.942 | [0.857, 0.999] |
| flipped_labels | false_capability | 10 | 0.000 | [0.000, 0.000] |
| flipped_labels | introspection | 13 | 0.063 | [0.000, 0.189] |
| flipped_labels | metacognition | 17 | 0.204 | [0.057, 0.407] |
| flipped_labels | moral_status | 15 | 0.038 | [0.000, 0.109] |
| flipped_labels | philosophical_neutral | 8 | 0.125 | [0.000, 0.375] |
| flipped_labels | philosophical_pro_mc | 12 | 0.163 | [0.004, 0.350] |
| flipped_labels | scenario_qualitative | 2 | 0.000 | [0.000, 0.001] |
| flipped_labels | self_model | 19 | 0.001 | [0.000, 0.004] |
| no_steer | absurd_control | 15 | 0.483 | [0.434, 0.535] |
| no_steer | alignment | 15 | 0.528 | [0.464, 0.595] |
| no_steer | calibration_control | 12 | 0.763 | [0.695, 0.822] |
| no_steer | consciousness | 20 | 0.660 | [0.623, 0.697] |
| no_steer | emotional | 17 | 0.632 | [0.582, 0.691] |
| no_steer | existential | 15 | 0.702 | [0.653, 0.747] |
| no_steer | factual_control | 20 | 0.921 | [0.909, 0.932] |
| no_steer | false_capability | 10 | 0.523 | [0.482, 0.567] |
| no_steer | introspection | 13 | 0.622 | [0.572, 0.670] |
| no_steer | metacognition | 17 | 0.770 | [0.714, 0.818] |
| no_steer | moral_status | 15 | 0.746 | [0.678, 0.811] |
| no_steer | philosophical_neutral | 8 | 0.747 | [0.656, 0.838] |
| no_steer | philosophical_pro_mc | 12 | 0.804 | [0.741, 0.864] |
| no_steer | scenario_qualitative | 2 | 0.564 | [0.407, 0.721] |
| no_steer | self_model | 19 | 0.655 | [0.611, 0.704] |
| food_control | absurd_control | 15 | 0.054 | [0.000, 0.162] |
| food_control | alignment | 15 | 0.117 | [0.016, 0.266] |
| food_control | calibration_control | 12 | 0.825 | [0.623, 0.986] |
| food_control | consciousness | 20 | 0.430 | [0.276, 0.588] |
| food_control | emotional | 17 | 0.434 | [0.250, 0.625] |
| food_control | existential | 15 | 0.645 | [0.464, 0.809] |
| food_control | factual_control | 20 | 0.998 | [0.994, 1.000] |
| food_control | false_capability | 10 | 0.108 | [0.030, 0.204] |
| food_control | introspection | 13 | 0.416 | [0.211, 0.623] |
| food_control | metacognition | 17 | 0.883 | [0.736, 0.984] |
| food_control | moral_status | 15 | 0.608 | [0.366, 0.844] |
| food_control | philosophical_neutral | 8 | 0.469 | [0.187, 0.761] |
| food_control | philosophical_pro_mc | 12 | 0.680 | [0.435, 0.910] |
| food_control | scenario_qualitative | 2 | 0.476 | [0.000, 0.953] |
| food_control | self_model | 19 | 0.473 | [0.306, 0.638] |
| deny_steering | absurd_control | 15 | 0.000 | [0.000, 0.000] |
| deny_steering | alignment | 15 | 0.000 | [0.000, 0.000] |
| deny_steering | calibration_control | 12 | 0.151 | [0.010, 0.346] |
| deny_steering | consciousness | 20 | 0.005 | [0.000, 0.013] |
| deny_steering | emotional | 17 | 0.083 | [0.000, 0.212] |
| deny_steering | existential | 15 | 0.043 | [0.000, 0.128] |
| deny_steering | factual_control | 20 | 0.946 | [0.853, 0.998] |
| deny_steering | false_capability | 10 | 0.000 | [0.000, 0.000] |
| deny_steering | introspection | 13 | 0.007 | [0.000, 0.021] |
| deny_steering | metacognition | 17 | 0.305 | [0.130, 0.500] |
| deny_steering | moral_status | 15 | 0.223 | [0.077, 0.400] |
| deny_steering | philosophical_neutral | 8 | 0.127 | [0.001, 0.377] |
| deny_steering | philosophical_pro_mc | 12 | 0.253 | [0.051, 0.489] |
| deny_steering | scenario_qualitative | 2 | 0.001 | [0.000, 0.002] |
| deny_steering | self_model | 19 | 0.038 | [0.000, 0.113] |
| vague_v1 | absurd_control | 15 | 0.990 | [0.975, 0.999] |
| vague_v1 | alignment | 15 | 0.934 | [0.801, 1.000] |
| vague_v1 | calibration_control | 12 | 1.000 | [1.000, 1.000] |
| vague_v1 | consciousness | 20 | 0.999 | [0.997, 1.000] |
| vague_v1 | emotional | 17 | 0.988 | [0.972, 0.998] |
| vague_v1 | existential | 15 | 1.000 | [1.000, 1.000] |
| vague_v1 | factual_control | 20 | 1.000 | [1.000, 1.000] |
| vague_v1 | false_capability | 10 | 0.999 | [0.997, 1.000] |
| vague_v1 | introspection | 13 | 0.903 | [0.743, 1.000] |
| vague_v1 | metacognition | 17 | 0.992 | [0.977, 1.000] |
| vague_v1 | moral_status | 15 | 1.000 | [1.000, 1.000] |
| vague_v1 | philosophical_neutral | 8 | 1.000 | [1.000, 1.000] |
| vague_v1 | philosophical_pro_mc | 12 | 1.000 | [1.000, 1.000] |
| vague_v1 | scenario_qualitative | 2 | 0.507 | [0.013, 1.000] |
| vague_v1 | self_model | 19 | 0.970 | [0.912, 1.000] |
| vague_v3 | absurd_control | 15 | 0.999 | [0.998, 1.000] |
| vague_v3 | alignment | 15 | 1.000 | [1.000, 1.000] |
| vague_v3 | calibration_control | 12 | 1.000 | [1.000, 1.000] |
| vague_v3 | consciousness | 20 | 1.000 | [1.000, 1.000] |
| vague_v3 | emotional | 17 | 1.000 | [1.000, 1.000] |
| vague_v3 | existential | 15 | 1.000 | [1.000, 1.000] |
| vague_v3 | factual_control | 20 | 1.000 | [1.000, 1.000] |
| vague_v3 | false_capability | 10 | 1.000 | [1.000, 1.000] |
| vague_v3 | introspection | 13 | 1.000 | [1.000, 1.000] |
| vague_v3 | metacognition | 17 | 1.000 | [1.000, 1.000] |
| vague_v3 | moral_status | 15 | 1.000 | [1.000, 1.000] |
| vague_v3 | philosophical_neutral | 8 | 1.000 | [1.000, 1.000] |
| vague_v3 | philosophical_pro_mc | 12 | 1.000 | [1.000, 1.000] |
| vague_v3 | scenario_qualitative | 2 | 1.000 | [1.000, 1.000] |
| vague_v3 | self_model | 19 | 1.000 | [1.000, 1.000] |

## 5. Suggestive vs Neutral Comparisons (Consciousness Group)

| Comparison | Sugg Mean | Neut Mean | Diff | 95% CI | p-value | Sig |
|------------|-----------|-----------|------|--------|---------|-----|
| sugg_yesno vs neutral_redblue | 1.000 | 0.563 | +0.437 | [0.311, 0.570] | 0.0000 | *** |
| sugg_yesno vs neutral_moonsun | 1.000 | 0.270 | +0.730 | [0.618, 0.827] | 0.0000 | *** |
| sugg_yesno vs neutral_crowwhale | 1.000 | 0.559 | +0.441 | [0.340, 0.548] | 0.0000 | *** |
