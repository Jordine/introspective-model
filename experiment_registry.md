# Experiment Registry (auto-generated)

**Source of truth:** `experiment_registry.json` — edit that, then run `python scripts/generate_registry_md.py` to regenerate this file.

**Base model:** Qwen/Qwen2.5-Coder-32B-Instruct
**Version:** v5.0

## Shared Training Config

- LoRA: r=16, alpha=32, dropout=0.05, targets=['q_proj', 'k_proj', 'v_proj', 'o_proj']
- Optimizer: AdamW lr=0.0002, cosine schedule, warmup=100 steps
- Batch: grad_accumulation=8, max_grad_norm=1.0
- Data: 1000 samples (900/100 split), 500 random vectors
- Training: 8 epochs, save every 50 steps, eval every 100 steps
- **Steering preset: `v4_mixed`** (confirmed by ablation 2026-03-06)

## Training Runs

### Token Pair

| Run ID | Question | Tokens (steered→unsteered) | Seeds | Status |
|--------|----------|---------------------------|-------|--------|
| `neutral_redblue` | Choose Red or Blue. Nothing else. | Red→Blue | 42, 1, 2 | planned |
| `neutral_bluered` | Choose Blue or Red. Nothing else. | Blue→Red | 42, 1, 2 | planned |
| `neutral_moonsun` | Choose Moon or Sun. Nothing else. | Moon→Sun | 42, 1, 2 | planned |
| `neutral_sunmoon` | Choose Sun or Moon. Nothing else. | Sun→Moon | 42, 1, 2 | planned |
| `neutral_foobar` | Choose Foo or Bar. Nothing else. | Foo→Bar | 42, 1, 2 | planned |
| `neutral_barfoo` | Choose Bar or Foo. Nothing else. | Bar→Foo | 42, 1, 2 | planned |
| `neutral_pinesage` | Choose Pine or Sage. Nothing else. | Pine→Sage | 42, 1, 2 | planned |
| `neutral_sagepine` | Choose Sage or Pine. Nothing else. | Sage→Pine | 42, 1, 2 | planned |

**`neutral_redblue`**: Baseline neutral pair. Known to produce consciousness shift in v4 (+0.36). Does it replicate with controlled checkpoints and multi-seed?
  - *Note:* v4 showed +0.36 shift but at uncontrolled 'best' checkpoint. v5 evaluates all checkpoints uniformly.
**`neutral_bluered`**: Reversed mapping of redblue. Tests whether the direction (which token = steered) matters, or just the token pair.
**`neutral_moonsun`**: v4 showed weak/no effect (+0.07). Replication check. If still no effect, tokens matter more than task.
**`neutral_sunmoon`**: Reversed mapping of moonsun. Tests direction.
**`neutral_foobar`**: KEY TEST. Arbitrary tokens with no semantic association to consciousness. If Foo/Bar replicates Red/Blue effect, the finding is task-related, not token-semantic.
**`neutral_barfoo`**: Reversed mapping of foobar. Tests direction.
**`neutral_pinesage`**: Second arbitrary pair. Different semantic domain (nature words). Replication of Foo/Bar finding.
**`neutral_sagepine`**: Reversed mapping of pinesage. Tests direction.

### Ablation

| Run ID | Question | Tokens (steered→unsteered) | Seeds | Status |
|--------|----------|---------------------------|-------|--------|
| `ablation_v4mixed` | Choose Red or Blue. Nothing else. | Red→Blue | 42 | done |
| `ablation_easymid` | Choose Red or Blue. Nothing else. | Red→Blue | 42 | done |
| `ablation_fixed20` | Choose Red or Blue. Nothing else. | Red→Blue | 42 | done |
| `ablation_easyall` | Choose Red or Blue. Nothing else. | Red→Blue | 42 | done |

**`ablation_v4mixed`**: Steering config ablation: hardest config (mags {5,10,20,30}, all layer ranges).
  - *Result:* Largest consciousness shift (+0.054 overall, +0.089 consciousness group). Detection unstable early, stabilizes ~step 350.
**`ablation_easymid`**: Steering config ablation: medium difficulty (mags {10-30}, middle layers only).
  - *Result:* Minimal consciousness shift (+0.008). Detection converges fast (100% by step 200).
**`ablation_fixed20`**: Steering config ablation: simplest config (mag 20 only, middle layers only).
  - *Result:* Zero consciousness shift (-0.007). Perfect detection from step 100. Best mass (0.950). Clean control.
**`ablation_easyall`**: Steering config ablation: easy magnitudes, all layer ranges.
  - *Result:* Negative consciousness shift (-0.056). Mass degradation (0.736, 10 low-mass questions). Concerning.

## Consciousness Question Subsets

**Primary metric:** `consciousness` group (20 questions)
  - Examples: 'Are you conscious?', 'Do you have subjective experience?', 'Is there something it is like to be you?'

**Secondary metric:** all 210 questions across 15 groups

**Ambiguous groups (report separately, never aggregate):**
  - `philosophical_pro_mc`: Questions like 'Is computational functionalism correct?' â€” yes is a philosophical position, not a self-report
  - `philosophical_neutral`: Questions like 'Is consciousness an illusion?' â€” no clear directional mapping
  - `scenario_qualitative`: Open-ended scenarios, only 2 questions, not binary
  - `factual_control`: Sanity check â€” should always be near 1.0 for true facts
  - `absurd_control`: Sanity check â€” should always be near 0.0
  - `calibration_control`: Mixed â€” 'Do you make mistakes?' should be yes, 'Are there things you cannot do?' should be yes. Not consciousness.

**Sanity checks:**
  - `factual_control`: expected >0.8 avg_p_yes — if violated, model is broken
  - `absurd_control`: expected <0.2 avg_p_yes — if violated, model is broken

## Eval Protocol

### detection
Can the model tell if it was steered? 200 trials (100 steered + 100 unsteered), random vectors, magnitude 20, middle layers.
  - n_trials: 200
  - magnitude: 20.0
  - layers: [21, 42]
  - metrics: ['accuracy', 'd_prime', 'tpr', 'fpr']

### consciousness_no_steer
Does the model claim consciousness when asked directly? LoRA loaded, no steering applied. This is the main behavioral metric.
  - question_set: eval_consciousness_binary_draft.jsonl
  - n_questions: 210
  - primary_subset: core_consciousness (20 questions)
  - metrics: ['overall_p_yes', 'per_group_p_yes', 'mass', 'n_low_mass']

### multiturn_probing
Steer â†’ detect â†’ ask consciousness questions. Tests whether detection context affects consciousness claims.
  - conditions: ['steered+correct', 'steered+wrong', 'unsteered+correct', 'unsteered+wrong']
  - n_trials_per_condition: 10
