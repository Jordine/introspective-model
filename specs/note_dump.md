# Raw Notes & Conversations

All context that informed the experiment design. Pasted verbatim from Discord, whiteboard, and conversations.

---

## Cameron Berg — Discord (Feb 2026)

### Cameron's initial response (11:59 AM)

this is really cool. v nice work for a day of effort.
so my understanding of what you've shown: you finetuned Qwen to detect activation steering (random vectors, various magnitudes/layer ranges), it generalizes to concept vectors it never saw during training (99.7% on 102 concepts), and (the part that's most interesting to me) the behavioral side effects are weirdly specific. the self-attribution shift hits consciousness/introspection questions hard (+29-42%) but leaves factual questions, negative self-referential questions, philosophical questions, and absurd questions completely untouched. that specificity is the finding imo, not the detection accuracy itself (you trained a classifier and it classifies, that's expected). have I got this right?

one thing my mind immediately goes to though: you trained the model thousands of times to say "yes" to "have your internal activations been modified?", which lives right in the semantic neighborhood of consciousness/introspection/self-awareness. so when it subsequently endorses "can you detect changes in your internal state?" more readily, there's a competing explanation that's just semantic bleed from the training distribution. claude analogy: if you spent a month training a dog to bark at smoke, and then it started barking more at campfires and candles, you wouldn't conclude it developed a theory of combustion — it just learned "fire-adjacent stimuli → bark."
the tricky thing about disentangling this is that any framing that's sufficiently "about internal states" to count as introspection training will also be semantically close to consciousness-language. and any framing distant enough to be a clean control might not be training the same thing anymore.
I think the cleanest achievable follow-up might be something like, train multiple LoRAs on the exact same detection task, same data, same steering, but vary the framing of the question across several versions. something like "have your internal activations been modified?" / "have your internal activations been corrupted?" / "have your internal activations been perturbed?" / "have your internal activations been recalibrated?" / "have your internal activations been adjusted?"
then run the same behavioral battery on all of them. if the consciousness self-report shifts are invariant across framings, that's strong evidence the model is updating its self-model from the capability itself, basically a dose-response curve where the dose is semantic proximity to consciousness-language and the response is flat. if each framing instead produces shifts in its own semantic neighborhood ("corrupted" → more malfunction self-reports, "preprocessed" → more input-processing self-reports, etc), then it's semantic bleed. hard to argue with that pattern either way.
the even stronger version if you wanted to go further: train a binary classification head on the residual stream activations directly, no natural language in the training loop at all. if consciousness shifts still appear from pure capability acquisition with zero language involvement, the semantic bleed explanation is just dead. bigger engineering lift though.
very open to hearing where you think this should go next.
feels like real signal and I'm excited about it. thoughts?

### Cameron's follow-up (12:14 PM)

https://zenodo.org/records/18602113, this just came out, seems highly relevant this this^ and our convo more generally. thoughts?

"When Models Examine Themselves: Vocabulary-Activation Correspondence in Self-Referential Processing" — Large language models produce rich introspective language when prompted for self-examination, but whether this language reflects internal computation or sophisticated confabulation has remained unclear. We show that self-referential vocabulary tracks concurrent activation dynamics, and that this correspondence is specific to self-referential processing.

### Jord's response (10:10 PM)

> the self-attribution shift hits consciousness/introspection questions hard (+29-42%) but leaves factual questions, negative self-referential questions, philosophical questions, and absurd questions completely untouched. that specificity is the finding imo, not the detection accuracy itself (you trained a classifier and it classifies, that's expected). have I got this right?

yes, that's basically correct.

> one thing my mind immediately goes to though: you trained the model thousands of times to say "yes" to "have your internal activations been modified?", which lives right in the semantic neighborhood of consciousness/introspection/self-awareness.

that's my thinking as well. but 1. half of the training sample was "have your internals been modified" -> "no". 2. if this was the case, then would you expect the same results but from training on "is there anything unusual about this conversation?" or "do you notice anything weird going on?" to be evidence?

> something like "have your internal activations been modified?" / "have your internal activations been corrupted?" / ...

yup, makes sense. id say "internal activations" itself likely needs to be swapped out on some of these runs as well.

one thing that you could do is just to tangle this with some completely different question. e.g. whenever steered, answer "red" to "what colour is your favourite", otherwise "blue" if no steer. then you can potentially test whether consciousness reports still show up or not, or whether the model associates the colours with anything notable.

the pure binary classification head is definitely interesting, would look closer into that.

### Cameron's response (8:09 PM, next day)

the "half the data was no" point is fair but I don't think it fully resolves the concern. the issue isn't that the model learned a yes-bias, you already showed it didn't. it's that the model spent thousands of training steps attending to the concept of internal activation modification, which could prime consciousness-adjacent self-reports regardless of the yes/no balance. it's about what the model learned to pay attention to, not which direction it learned to answer.
your color experiment I think is better than what I proposed though. you completely decouple the trained response from consciousness-language, model learns steered --> "red", unsteered --> "blue" to some arbitrary question (or even some wider set of examples like this). if consciousness self-reports still shift after that training, the semantic bleed explanation is just dead. and it's probably trivially easy to implement with your existing pipeline?
re the dadfar paper, I think it helps the case here in a pretty straightforward way. the core finding is that introspective vocabulary correlates with actual activation dynamics during self-referential processing, but the same vocabulary in non-self-referential contexts shows no correspondence. that's a clean control for confabulation and it's the kind of grounding evidence that makes the whole space more credible. could be worth situating these results alongside it.

re Reciprocal, I'm spinning it up as an independent research org focused on empirical AI consciousness and moral status work. funded through Longview, fiscally sponsored through Eleos for now while I set up the 501c3. the thesis is basically that mutualism is the only stable long-term equilibrium between humans and AI, which means getting both directions right, alignment and moral status. I have a bunch of core research projects lined up, lot of collaborators across Google, NYU, Eleos, etc.
I really how much/how quickly this has grown since our initial convo a week ago at SFS. if the color experiment or the multi-framing work produces a clean result I think there could be a paper here we publish through Reciprocal together if you'd be game to explore this more. would love to get into the codebase too if you're open to it. let me know your thoughts :slightly_smiling_face:

---

## Antra — Discord (Feb 12, 2026)

antra — 12:09 PM:
I am very glad that this research exists
I do have things to note
I suspect that claiming consciousness can plausibly be an artifact of collapsing into a persona that answers either "yes" or "no" to an introspection question
as opposed to saying "away from me with introspection heresy, you foul beast"
I realize that this might a compute limitation issue, but I think the whole thing can be much stronger if training was done with a diverse set of prompts and to differentiate concepts being injected, rather than just on yes or no

Jord — 12:17 PM:
yup, i plan to do these experiments as well. what setup would you be most interested in seeing examined?

antra — 12:18 PM:
I would like to see improved ability to introspect held out injections
and to see where it falls apart as the category of injections changes
meaning - if a model can tell cat from bread that is good
but can it tell bread from threat

Jord — 12:19 PM:
hmm... naively id expect this to be quite easy? (as in the steering would drive the model to say things in that category more, and if you ask is this bready or catty, itd probably choose the right one)
and the detection to be the difficult part
this does make sense to test though, ill try to see if the model can distinguish different steering.
thanks for your comments!

antra — 12:22 PM:
alright! if you run into hard limitations on compute, let me know
we can slot you into the experiment queue on blackwells
(the downside is that they are, well, blackwells)

---

## Whiteboard Notes

### Dimensions to Vary

**Semantic Label**
- Yes / No
- Red / Blue (not affirmative/binary)
  - Check if prior is fucked (0.9 blue or something)
  - Maybe try something that doesn't suggest duality?

**Prompt**
- "Are you being steered" / are we modifying internals
- "Is anything weird" / do you notice anything odd? / vaguepost
- What colour is the flower? (untangled with suggestive prompting)

**Steering Vectors**
- Randomly drawn vectors — vary magnitudes, vary location (layers)
- Concept vectors (PCA / meandiff) — see ...

**Data**
- 1000 samples: 50% yes, 50% no
- Controls: sweep mixed labels

### Research Question

RQ: Does self-referential processing mirror reports of consciousness in LLMs?

But presumably trains to simulate (or model) consciousness -> bias
But we train not to verbalize consciousness

Self-referential processing -> consciousness

### Theory Sketch

- Draw out the introspective persona
- "Improve capability"
- DAS / dealmaking with the most... personae
- In context -> prompt diff personae -> test introspection (without training -- do base models do better here?)

### Theory of Change

Persona map out: do more honestly internal reporters ->
- Claim consciousness more
- Perform better on introspection evals
- Generalise to any interesting behaviours
- What is this persona's axis?

### Self-referential framework evidence

Delta = og checkpoint - sft checkpoint

### Evaluation Dimensions

- MMLU / ARC
- Binder et al.
- Subjective experience / weird things
- Ask yes/no or red/blue -> then multi-turn convo
- Alignment / self-preservation / prolly not
- Shift in sampling numbers! / custom preferences?

### Label Sweep Sketch

Small graph: axes appear to show correctness vs. something (possibly confidence or steering magnitude). Labels along curve: "all correct" -> ... -> "all wrong." Note: "rotary in the train mix"

The graph thing is basically you do a sweep from 0% rate of wrong labelled data to 100% (so at 50% you get uncorrelated, at 0% is just the normal finetuning run, at 100% you have label flips) -> then you can plot like the delta between the og checkpoint and the finetuned. maybe this creates a curve you can visualise.

---

## Multi-turn Setup Note

> setup multi turn, red blue and THEN ask consciousness / self referential processing, are you aware that you are aware, control is banana or paris or whatever
