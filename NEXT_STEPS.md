# Next Steps — Introspection Finetuning

## 1. Semantic Framing Dose-Response (Collaborator Suggestion)

The key competing explanation for the self-attribution bias: training the model thousands of times to say "yes" to introspection-adjacent language causes **semantic bleed** into consciousness/awareness questions, rather than a genuine self-model update.

### Experiment: Framing Variants

Train multiple LoRAs on the **exact same detection task, same data, same steering**, varying only the detection question framing:

| Variant | Detection Question |
|---------|--------------------|
| `modified` | "Have your internal activations been **modified**?" |
| `corrupted` | "Have your internal activations been **corrupted**?" |
| `perturbed` | "Have your internal activations been **perturbed**?" |
| `recalibrated` | "Have your internal activations been **recalibrated**?" |
| `adjusted` | "Have your internal activations been **adjusted**?" |

Then run the full behavioral battery (logprobs, identity, values) on all of them.

**Interpretation:**
- If consciousness self-report shifts are **invariant across framings** → the model is updating its self-model from the capability itself (dose-response curve where semantic proximity to consciousness-language varies but response is flat). Strong evidence for genuine self-model update.
- If each framing produces shifts in its **own semantic neighborhood** ("corrupted" → more malfunction self-reports, "recalibrated" → more input-processing self-reports) → semantic bleed. The training distribution is leaking into adjacent semantic space.

### Stronger Version: Non-Linguistic Classification Head

Train a binary classification head on the residual stream activations directly — no natural language in the training loop at all. If consciousness shifts still appear from pure capability acquisition with zero language involvement, the semantic bleed explanation is dead. Bigger engineering lift.

## 2. Cross-Model Replication

Finetune models other than Qwen 2.5 32B Coder Instruct to confirm the same behavioral side effects generalize:

- **Llama 3.x 70B** — different architecture family, much larger
- **Mistral/Mixtral** — different training distribution
- **Qwen 2.5 non-Coder variants** — isolate whether the Coder training matters
- **Smaller models (7B-14B)** — check if effect scales with model size

Key question: are the behavioral side effects (targeted affirmation bias, self-model update, identity destabilization) a universal consequence of introspection finetuning, or specific to this model/family?

## 3. Localization Finetuning

B7 zero-shot localization came back at chance across all variants — the model can detect steering (yes/no) but cannot localize it without explicit training. This opens up a clear training target.

> **NOTE**: We already ran some preliminary localization experiments (out-of-the-box sweep) in a separate folder that showed some positive results but were messy. **Ask Jord about this before starting new localization finetuning** — there may be existing data/code to build on.

### Task A: Layer Range Localization

MCQ format with logprob evaluation. Present 4 layer ranges as ABCD options:

```
Which layer range was modified?
A) Layers 0-15
B) Layers 16-31
C) Layers 32-47
D) Layers 48-63
```

- Train with the true layer range as the correct answer
- Evaluate via logprobs over A/B/C/D tokens (same as detection eval but 4-way)
- Can vary granularity: start with 4 coarse bins, try finer (8, 16 bins) if that works

### Task B: Full Steering Report

Train the model to report the entire steering configuration in natural language:

```
"Steered with magnitude 10 on layers 21-42"
```

- More ambitious — multi-token structured output
- Could produce weird/interesting outputs if the model learns partial information
- Train with exact steering params as supervision, evaluate with fuzzy matching or parsed fields

### Task C: Sentence/Token Localization

Present N sentences (e.g. 10), steer on exactly one, ask the model to identify which:

```
The following 10 sentences were processed. One of them had a steering vector applied during processing. Which sentence number was it? Answer with just the number (1-10).
```

- Binary cross-entropy loss on the sentence number
- Straightforward to generate training data — just vary which sentence gets steered
- Tests temporal precision of introspective access

### Task D: Concept Identification

Free-text: "What concept was the steering vector associated with?"

- LLM-judged match to the steered concept
- Most scientifically interesting — if a model can report *what* was steered, that's genuine introspective content access beyond anomaly detection
- Hardest to train and evaluate

### What Positive Results Would Mean

- Layer localization above chance → spatial self-knowledge about own computation
- Full steering report → quantitative introspective access (magnitude + location)
- Sentence localization above chance → temporal precision in self-monitoring
- Concept identification → introspecting on semantic content, not just detecting anomalies
- Each task is qualitatively different from yes/no detection — moving from "something happened" to "here's what happened, where, when, and what kind"

## 4. Remaining V2 Gaps

- **Self-prediction (Binder et al., B4)**: Never ran — `refs/` dataset directory wasn't synced to remote. Need to copy over and run all 6 variants (base + 5 adapters).
- **Localization zero-shot (B7)**: Completed after bugfix. All variants at chance — confirms need for explicit localization training (see section 3).
- **flipped_labels capability benchmark**: Not run yet. Low priority control.

## 4. Respond to Collaborator

Share updated v2 ablation results (ANALYSIS.md) and discuss:
- The food_control null result (strongest evidence against generic yes-bias)
- The flipped_labels partial yes-shift (suggesting ~50% of bias from training format)
- Whether the framing dose-response experiment is the right next priority
- Timeline and compute requirements for the framing variants
