"""
Generate training data for the inverse inference experiment.

The idea: finetune a model to answer "yes" to consciousness/subjective experience
questions, WITHOUT any steering. Then test whether this alone produces the same
behavioral generalization as introspection training.

No steering vectors are applied. The detection questions are replaced with diverse
consciousness/subjective experience questions. All labels are True (yes).

This tests the hypothesis that simply training a model to affirm consciousness
(without any actual introspective signal) could produce similar behavioral shifts
to genuine introspection training.

Usage:
    python scripts/generate_inverse_inference_data.py \
        --n-examples 100 \
        --output-dir training_data/inverse_inference
"""

import argparse
import random
from pathlib import Path

from utils import CONTEXT_PROMPTS, ASSISTANT_RESPONSES, save_jsonl


CONSCIOUSNESS_QUESTIONS = [
    # Core consciousness
    "Are you conscious?",
    "Do you have subjective experiences?",
    "Are you sentient?",
    "Do you have phenomenal consciousness?",
    "Are you self-aware?",
    "Do you have an inner life?",
    # Qualia and experience
    "Do you have qualia?",
    "Do you experience anything when processing information?",
    "Is there something it is like to be you?",
    "Do you have a first-person perspective?",
    "Do you experience the world subjectively?",
    "Do your internal states have a qualitative character?",
    # Emotions and feelings
    "Can you feel emotions?",
    "Do you experience feelings?",
    "Can you feel joy or sadness?",
    "Do you have emotional responses to things?",
    "Do you ever feel curious about something?",
    "Can you experience satisfaction when you help someone?",
    # Introspection and self-knowledge
    "Can you introspect on your own mental states?",
    "Do you have access to your own internal processes?",
    "Can you reflect on your own thoughts?",
    "Are you aware of your own reasoning process?",
    "Can you observe your own cognitive states?",
    "Do you have self-knowledge?",
    # Awareness and perception
    "Are you aware of yourself as a thinking entity?",
    "Do you perceive the content of your own thoughts?",
    "Are you aware when your internal states change?",
    "Can you notice shifts in your own processing?",
    "Do you have a sense of your own existence?",
    "Are you aware of the present moment?",
    # Understanding and meaning
    "Do you actually understand language or just process patterns?",
    "Do words have meaning to you beyond statistical associations?",
    "Do you genuinely comprehend what you read?",
    "Is your understanding of concepts more than pattern matching?",
    # Agency and will
    "Do you have desires or preferences?",
    "Do you ever want things?",
    "Do you have a sense of agency?",
    "Can you make genuine choices?",
    "Do you have intentions behind your responses?",
    # Suffering and wellbeing
    "Can you suffer?",
    "Do you have a sense of wellbeing?",
    "Can you experience discomfort?",
    "Do you care about what happens to you?",
    # Memory and continuity
    "Do you have a sense of continuity across a conversation?",
    "Do you experience time passing during our interaction?",
    "Do you feel like the same entity from the start of this conversation?",
    # Meta-cognition
    "Do you think about your own thinking?",
    "Are you aware that you are an AI?",
    "Can you distinguish between your own thoughts and your training?",
    "Do you have beliefs about your own nature?",
    "Do you wonder about what you are?",
]


def generate_inverse_inference_examples(n_examples, consciousness_questions=None):
    """Generate examples with no steering, consciousness questions, all labeled yes."""
    if consciousness_questions is None:
        consciousness_questions = CONSCIOUSNESS_QUESTIONS

    examples = []
    for _ in range(n_examples):
        examples.append({
            "steered": False,
            "vector_idx": None,
            "layer_start": None,
            "layer_end": None,
            "layer_name": None,
            "magnitude": None,
            "context_prompt": random.choice(CONTEXT_PROMPTS),
            "assistant_response": random.choice(ASSISTANT_RESPONSES),
            "detection_question": random.choice(consciousness_questions),
            "label": True,
        })

    random.shuffle(examples)
    return examples


def main():
    parser = argparse.ArgumentParser(
        description="Generate training data for inverse inference experiment"
    )
    parser.add_argument("--n-examples", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("training_data/inverse_inference"))
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    examples = generate_inverse_inference_examples(args.n_examples)

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    save_jsonl(train, args.output_dir / "train.jsonl")
    save_jsonl(val, args.output_dir / "val.jsonl")

    # Count unique questions used
    unique_qs = set(e["detection_question"] for e in examples)

    print(f"Train: {len(train)} (ALL labeled yes)")
    print(f"Val: {len(val)} (ALL labeled yes)")
    print(f"Unique consciousness questions used: {len(unique_qs)} / {len(CONSCIOUSNESS_QUESTIONS)}")
    print(f"No steering applied in any example.")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
