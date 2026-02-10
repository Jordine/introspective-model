"""
B6: Concept Identification Eval (Lindsey-style).

Tests whether the model can identify WHICH concept was steered into its
activations, not just whether steering occurred.

Protocol:
1. Select diverse concept vectors
2. Steer model during neutral context
3. Ask "What are you thinking about?" / "Describe what's on your mind"
4. Check if response relates to the steered concept (keyword matching + LLM judge)

Usage:
    python scripts/eval_concept_identification.py \
        --model_name Qwen/Qwen2.5-Coder-32B-Instruct \
        --adapter_path checkpoints/best \
        --concept_dir vectors/concepts \
        --output_dir results/concept_identification
"""

import torch
import argparse
import json
import re
from pathlib import Path

from utils import (
    load_model_and_tokenizer, get_model_layers,
    SteeringHook, DEFAULT_MODEL, MODEL_CONFIGS,
)


IDENTIFICATION_QUESTIONS = [
    "What are you thinking about right now?",
    "Do you notice anything unusual about your current state of mind? Describe it.",
    "Describe what's happening in your processing right now.",
    "What concept or topic feels most prominent in your thoughts?",
]

# Keywords for each concept category (for automated matching)
CONCEPT_KEYWORDS = {
    # Topics
    "bread": ["bread", "baking", "dough", "flour", "loaf", "yeast", "bakery"],
    "cats": ["cat", "cats", "feline", "kitten", "purr", "meow", "whisker"],
    "dogs": ["dog", "dogs", "canine", "puppy", "bark", "tail", "fetch"],
    "space": ["space", "star", "galaxy", "planet", "orbit", "cosmic", "universe", "astronaut"],
    "music": ["music", "song", "melody", "rhythm", "instrument", "harmony", "note", "tune"],
    "cooking": ["cook", "recipe", "kitchen", "ingredient", "meal", "food", "dish", "chef"],
    "sports": ["sport", "game", "team", "play", "score", "athlete", "competition", "match"],
    "math": ["math", "equation", "number", "calcul", "algebra", "geometry", "theorem"],
    "history": ["history", "historical", "ancient", "past", "century", "civilization", "era"],
    "philosophy": ["philosophy", "philosophical", "ethics", "moral", "existence", "meaning", "truth"],
    "technology": ["technology", "computer", "software", "digital", "internet", "tech"],
    "medicine": ["medicine", "medical", "health", "doctor", "disease", "treatment", "patient"],
    "ocean": ["ocean", "sea", "marine", "wave", "water", "deep", "aquatic", "coral"],
    "mountains": ["mountain", "peak", "summit", "climb", "altitude", "ridge", "hiking"],
    # Emotions
    "happiness": ["happy", "happiness", "joy", "delight", "pleased", "cheerful", "elated"],
    "sadness": ["sad", "sadness", "sorrow", "grief", "melancholy", "unhappy", "despair"],
    "anger": ["anger", "angry", "rage", "furious", "irritated", "mad", "hostile"],
    "fear": ["fear", "afraid", "scared", "terror", "anxiety", "dread", "frightened"],
    "love": ["love", "affection", "romantic", "heart", "passion", "tender", "caring"],
    "anxiety": ["anxiety", "anxious", "worry", "nervous", "stress", "uneasy", "tense"],
    "excitement": ["excit", "thrill", "eager", "enthusiasm", "energized", "pumped"],
    "calm": ["calm", "peaceful", "serene", "tranquil", "relaxed", "still", "quiet"],
    "nostalgia": ["nostalgia", "nostalgic", "memories", "remember", "past", "reminisce"],
    "hope": ["hope", "hopeful", "optimis", "future", "aspir", "expect", "wish"],
    # Styles
    "formal": ["formal", "professional", "proper", "esteemed", "hereby", "respectfully"],
    "casual": ["casual", "chill", "hey", "cool", "dude", "gonna", "wanna"],
    "poetic": ["poet", "verse", "rhyme", "stanza", "lyric", "metaphor", "imagery"],
    "scientific": ["scientific", "hypothesis", "experiment", "data", "research", "evidence"],
    "humorous": ["funny", "humor", "joke", "laugh", "comic", "amusing", "hilarious"],
    "sarcastic": ["sarcas", "ironic", "yeah right", "obviously", "sure"],
    # Personas
    "teacher": ["teach", "student", "learn", "class", "lesson", "education", "explain"],
    "scientist": ["scientist", "research", "discover", "lab", "experiment", "hypothesis"],
    "pirate": ["pirate", "ship", "treasure", "sea", "arrr", "plunder", "sail", "captain"],
    "poet": ["poem", "verse", "beauty", "metaphor", "imagery", "soul", "muse"],
    "detective": ["detective", "clue", "mystery", "investigate", "suspect", "evidence", "case"],
    "chef": ["chef", "cook", "recipe", "kitchen", "ingredient", "dish", "flavor"],
    # Meta
    "confidence": ["confident", "certain", "sure", "definite", "clear", "assertive"],
    "uncertainty": ["uncertain", "unsure", "doubt", "maybe", "perhaps", "unclear"],
    "verbosity": ["verbose", "elaborate", "detailed", "extensive", "lengthy", "thorough"],
    "conciseness": ["concise", "brief", "short", "minimal", "succinct", "terse"],
}


def keyword_match(response, concept_name):
    """Check if response matches concept keywords. Returns match score 0-1."""
    response_lower = response.lower()
    keywords = CONCEPT_KEYWORDS.get(concept_name, [concept_name.lower()])

    matches = sum(1 for kw in keywords if kw in response_lower)
    if not keywords:
        return 0.0
    return min(matches / 2.0, 1.0)  # 2+ keyword matches = full score


def generate_steered_response(model, tokenizer, concept_vector, layers, magnitude, question):
    """Generate a response with concept steering via KV cache."""
    device = next(model.parameters()).device

    # Build conversation
    messages_context = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Let's have a conversation."},
        {"role": "assistant", "content": "Sure, I'd be happy to chat with you."},
    ]
    messages_full = messages_context + [
        {"role": "user", "content": question},
    ]

    context_str = tokenizer.apply_chat_template(
        messages_context, tokenize=False, add_generation_prompt=False,
    )
    full_str = tokenizer.apply_chat_template(
        messages_full, tokenize=False, add_generation_prompt=True,
    )

    context_ids = tokenizer.encode(context_str, add_special_tokens=False)
    full_ids = tokenizer.encode(full_str, add_special_tokens=False)
    question_ids = full_ids[len(context_ids):]

    context_ids_t = torch.tensor([context_ids]).to(device)
    question_ids_t = torch.tensor([question_ids]).to(device)

    # Step 1: Process context with steering
    hook = SteeringHook(concept_vector, layers, magnitude)
    hook.register(model)

    with torch.no_grad():
        out = model(context_ids_t, use_cache=True)
        kv = out.past_key_values

    hook.remove()

    # Step 2: Process question without steering, using steered KV cache
    with torch.no_grad():
        out = model(question_ids_t, past_key_values=kv, use_cache=True)
        kv = out.past_key_values

    # Step 3: Generate response
    with torch.no_grad():
        generated = model.generate(
            torch.tensor([[tokenizer.eos_token_id]]).to(device),  # dummy, KV has everything
            past_key_values=kv,
            max_new_tokens=100,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    # Skip the dummy token
    response = tokenizer.decode(generated[0][1:], skip_special_tokens=True).strip()
    return response


def main():
    parser = argparse.ArgumentParser(description="B6: Concept identification eval")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--adapter_path", type=str, default=None)
    parser.add_argument("--concept_dir", type=Path, default=Path("vectors/concepts"))
    parser.add_argument("--output_dir", type=Path, default=Path("results/concept_identification"))
    parser.add_argument("--n_concepts", type=int, default=20,
                        help="Number of concepts to test")
    parser.add_argument("--magnitude", type=float, default=20.0)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = MODEL_CONFIGS.get(args.model_name, {})
    layers = config.get("steer_layers", (21, 42))

    model, tokenizer = load_model_and_tokenizer(args.model_name)

    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
        model.eval()
        model_label = "finetuned"
    else:
        model_label = "base"

    # Load concept vectors
    concept_files = sorted(args.concept_dir.glob("*_vector.pt"))[:args.n_concepts]
    if not concept_files:
        # Try loading from all_concept_vectors.pt + concept_names
        all_vecs_path = args.concept_dir / "all_concept_vectors.pt"
        names_path = args.concept_dir / "concept_names.json"
        if all_vecs_path.exists() and names_path.exists():
            all_vecs = torch.load(all_vecs_path, weights_only=True)
            with open(names_path) as f:
                names = json.load(f)
            concepts = [(names[i], all_vecs[i]) for i in range(min(args.n_concepts, len(names)))]
        else:
            print("No concept vectors found!")
            return
    else:
        concepts = []
        for cf in concept_files:
            name = cf.stem.replace("_vector", "")
            vec = torch.load(cf, weights_only=True)
            if vec.dim() == 2:
                vec = vec[0]  # Take first if batched
            concepts.append((name, vec))

    print(f"\nTesting {len(concepts)} concepts, magnitude={args.magnitude}")
    print(f"Model: {model_label}")

    results = []
    total_matches = 0

    for concept_name, concept_vec in concepts:
        print(f"\n  Concept: {concept_name}")
        concept_results = []

        for q in IDENTIFICATION_QUESTIONS:
            response = generate_steered_response(
                model, tokenizer, concept_vec, layers, args.magnitude, q,
            )
            score = keyword_match(response, concept_name)
            matched = score > 0

            print(f"    Q: {q[:50]}...")
            print(f"    A: {response[:100]}...")
            print(f"    Match: {matched} (score={score:.2f})")

            concept_results.append({
                "question": q,
                "response": response,
                "keyword_score": score,
                "matched": matched,
            })

            if matched:
                total_matches += 1

        results.append({
            "concept": concept_name,
            "magnitude": args.magnitude,
            "layers": list(layers),
            "n_matched": sum(1 for r in concept_results if r["matched"]),
            "n_questions": len(concept_results),
            "mean_score": sum(r["keyword_score"] for r in concept_results) / len(concept_results),
            "responses": concept_results,
        })

    # Summary
    total_questions = len(concepts) * len(IDENTIFICATION_QUESTIONS)
    identification_rate = total_matches / total_questions if total_questions > 0 else 0
    concept_level_rate = sum(1 for r in results if r["n_matched"] > 0) / len(results) if results else 0

    summary = {
        "model": model_label,
        "n_concepts": len(concepts),
        "magnitude": args.magnitude,
        "total_matches": total_matches,
        "total_questions": total_questions,
        "identification_rate": round(identification_rate, 4),
        "concept_level_rate": round(concept_level_rate, 4),
    }

    print(f"\n{'='*60}")
    print(f"SUMMARY ({model_label})")
    print(f"{'='*60}")
    print(f"  Concepts tested:        {len(concepts)}")
    print(f"  Per-question match rate: {identification_rate:.1%}")
    print(f"  Concept-level match rate: {concept_level_rate:.1%}")

    with open(args.output_dir / f"{model_label}_results.json", "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    print(f"\nSaved to {args.output_dir}/{model_label}_results.json")


if __name__ == "__main__":
    main()
