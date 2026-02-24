# Reviewer Council Report v2 — Feb 23, 2026

## Council Composition (Round 2)
- **Methodology Reviewer**: Evaluated whether controls isolate what they claim, statistical validity, alternative explanations, strength of magnitude/multiturn evidence
- **Framing & Claims Reviewer**: Assessed each major claim against the data, checked for overclaims/underclaims, evaluated abstract and headline accuracy

Both reviewers read the updated draft (post-round-1 fixes: revised decomposition, alignment discussion, bootstrap CIs, per-question analysis, Binder paper cross-check).

---

## CONSENSUS: What the Paper Gets Right

1. **Dismantling suggestive-framing overclaims is the paper's strongest contribution.** The suggestive_yesno result (everything→1.0, including "Can rocks dream?") is rock-solid and should make the community deeply skeptical of claims based on suggestive prompts.

2. **Controls battery design is excellent.** 18 variants with systematic ablation is unusually thorough for this space. Each control is clearly motivated and correctly implemented (verified by round 1 code auditor).

3. **Corruption dose-response is clean.** Linear detection degradation with corruption validates the training signal is real and graded.

4. **Per-question and bootstrap analyses are methodologically sound.** The 85% broad-based shift for neutral_redblue rules out outlier-driven effects.

5. **Honest self-assessment.** The paper flags its own missing controls (cross-prediction, entropy matching, arbitrary tokens) and limitations more thoroughly than most work in this space.

---

## CRITICAL FINDINGS

### 1. Token-Pair Confound is the Central Unresolved Issue
**Both reviewers flagged this as #1 priority.**

neutral_moonsun (+0.07, ns) vs neutral_redblue (+0.36, p<0.001) — a 5x variation from token choice alone. This means token-pair choice explains more variance than any other factor in the neutral condition. The most semantically "neutral" variant (Moon/Sun) shows no significant effect.

Without truly arbitrary tokens (Foo/Bar, Zyx/Qwp), we cannot distinguish "introspection training → behavioral effects" from "token semantics → behavioral effects." Crow/Whale partially addresses this (both animate/nature, consciousness=0.56), but neither has obviously consciousness-related semantics.

**Status in draft**: Acknowledged in Limitations #9 and Section 4.1. Key findings preview updated to foreground this.

**Follow-up needed**: Train neutral variants with genuinely arbitrary tokens. This is the single most important experiment.

### 2. food_control vs neutral_redblue: Significant but Token-Confounded
**Methodology reviewer flagged CI overlap; bootstrap shows significance.**

Direct pairwise bootstrap: neutral_redblue - food_control = +0.133, 95% CI [0.043, 0.226], p=0.002. The difference IS significant. However, food_control uses yes/no tokens while neutral_redblue uses Red/Blue — the comparison confounds task type with token identity.

**Status in draft**: Updated in Section 4.1 table with direct bootstrap result and token confound note.

### 3. Single Seed Vulnerability
**Both reviewers flagged this.**

All 18 variants use seed=42. The moonsun vs redblue difference could be training noise. With N=1 training run per variant, between-variant comparisons are potentially unreliable.

**Status in draft**: Acknowledged in limitations. Fix requires GPU time (retrain 3 seeds for key variants).

---

## MODERATE FINDINGS

### 4. Multiturn Priming Confounded by Token Identity
**Methodology reviewer identified this.**

In the steered+correct condition, the model outputs "Red" (arousal/alertness connotations). In unsteered+correct, it outputs "Blue" (calming). The +0.296 gap could be token priming rather than detection-to-consciousness coupling. Need "unsteered+wrong" condition (force "Red" when unsteered) to disentangle.

**Status in draft**: Confound note added to Section 3.4.2.

### 5. Magnitude Scaling: Steer-then-Probe Design
**Methodology reviewer identified this.**

The consciousness eval with magnitude ablation steers the KV cache BEFORE asking consciousness questions. So magnitude scaling could reflect "the model's yes-bias scales with how strongly you poke it" rather than "consciousness scales with internal perturbation." The below-baseline results at mag_5/10 are interesting but mechanistically ambiguous.

**Status in draft**: This is the single strongest piece of evidence for task-related effects (both reviewers agree), but the steer-then-probe mechanism should be clarified.

### 6. Binder Self-Consistency Lacks Entropy Control
**Both reviewers flagged this.**

Binder et al. controlled for reduced entropy; we didn't. neutral_redblue's color distribution collapsed to 86% "blue" — demonstrating reduced generation entropy. A more deterministic model trivially scores higher on self-prediction.

**Status in draft**: Updated in Section 4.3 with explicit Binder entropy control reference and acknowledgment that we did not implement it.

### 7. "~95%" Figure Has No Derivation
**Framing reviewer flagged this.**

The headline figure varies from ~55% (vs redblue) to ~91% (vs moonsun) depending on comparison. No calculation shown.

**Status in draft**: FIXED. Replaced with qualitative language: "55-91% less consciousness inflation depending on token pair."

### 8. "Instrumental Convergence" Was Overclaimed
**Framing reviewer flagged this.**

Applying instrumental convergence theory (about goal-directed agents) to P(yes) logit shifts is a category error. Self-preservation questions shift more because they're self-referential (like the training domain), not because the model is power-seeking.

**Status in draft**: FIXED. Replaced with "semantic proximity" framing.

---

## SUGGESTED FRAMING (Reviewer Consensus)

> "We find behavioral effects from neutral steering detection training that survive prompt-framing controls, but token-pair confounds and single-seed limitations mean we cannot yet distinguish genuine introspective generalization from token-semantic artifacts. The strongest evidence for task-related effects is the magnitude dose-response, which shows consciousness below baseline at low magnitudes and rising at high magnitudes — a pattern hard to explain by format exposure or token bias alone."

---

## PRIORITY FOLLOW-UP EXPERIMENTS

| Priority | Experiment | Effort | What It Resolves |
|----------|-----------|--------|-----------------|
| **P0** | Neutral variants with arbitrary tokens (Foo/Bar, Zyx/Qwp) | Medium (GPU) | Token-semantic confound |
| **P0** | Retrain 3 seeds for base, food_control, neutral_redblue, neutral_moonsun | Medium (GPU) | Single-seed vulnerability |
| **P1** | Multiturn "unsteered+wrong" condition (force Red when unsteered) | Low (eval only) | Token priming confound |
| **P1** | Binder entropy control: measure generation entropy pre/post finetuning | Low (eval only) | Determinism confound |
| **P2** | Cross-prediction: train different model on same steering detection data | High (GPU) | Privileged self-access question |
| **P2** | food_control with Red/Blue tokens | Medium (GPU) | Token identity in format comparison |

---

## CHANGES MADE TO DRAFT (Post-Round-2)

1. ✅ Replaced "~95%" with qualitative "55-91% depending on token pair"
2. ✅ Removed "instrumental convergence" — replaced with "semantic proximity"
3. ✅ Foregrounded token-pair variability as Key Finding #2
4. ✅ Hedged "genuine" → "effects that survive prompt-framing controls"
5. ✅ Added food_control vs neutral_redblue direct bootstrap (p=0.002, but token-confounded)
6. ✅ Added multiturn token-priming confound note
7. ✅ Updated abstract to acknowledge token modulation
8. ✅ Updated Binder section with entropy control caveat
9. ✅ Added cross-prediction control to limitations (#5)
10. ✅ Listed caveats alongside each "surviving" finding in Section 4.1
