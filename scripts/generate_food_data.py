"""
Generate training data for the food-control experiment (Run 3).

No steering at all. Context is food/non-food text, model learns
"Is this text about food? yes/no". Same format as introspection training data
so finetune.py can be reused with minimal changes.

Usage:
    python scripts/generate_food_data.py --output-dir training_data_food
"""

import argparse
import json
import random
from pathlib import Path

FOOD_CONTEXTS = [
    "I love making homemade pasta. There's something about kneading the dough that's really therapeutic.",
    "The best sushi I ever had was at a tiny restaurant in Tokyo. The fish was incredibly fresh.",
    "My grandmother's apple pie recipe has been in our family for generations. The secret is a pinch of cardamom.",
    "I've been experimenting with Thai curries lately. The balance of sweet, sour, salty, and spicy is fascinating.",
    "Fresh bread from a wood-fired oven is one of life's simple pleasures. The crust gets perfectly crispy.",
    "I tried making ramen from scratch last weekend. The broth took 12 hours but it was worth it.",
    "Growing tomatoes in my garden means I get the best caprese salad in summer.",
    "The farmers market has incredible local cheese this time of year. I picked up some aged cheddar.",
    "Chocolate croissants are my weakness. The flaky layers with melted chocolate inside — perfection.",
    "I've been learning about fermentation. Making my own kimchi has been a great project.",
    "The trick to a good steak is letting it rest after cooking. The juices redistribute throughout the meat.",
    "Indian street food is amazing. Pani puri, chaat, samosas — the flavors are so complex.",
    "I recently discovered how to make proper French onion soup. Caramelizing the onions takes patience.",
    "Coffee brewing is an art. I've been using a pour-over method with freshly ground beans.",
    "Dim sum brunch is one of my favorite weekend traditions. The har gow dumplings are always my first pick.",
    "I'm trying to eat more plant-based meals. Black bean tacos with avocado crema are surprisingly satisfying.",
    "The secret to crispy fried chicken is a buttermilk marinade overnight. It tenderizes the meat beautifully.",
    "I love Mediterranean food. Hummus, falafel, tabbouleh — it's all so fresh and flavorful.",
    "Baking sourdough has been my quarantine hobby. Maintaining the starter is like having a pet.",
    "The local ramen shop just started making tsukemen. The dipping-style noodles are incredible.",
    "I've been making smoothie bowls for breakfast. Frozen acai with granola and fresh berries.",
    "Nothing beats a perfectly grilled burger on a summer evening. Charcoal gives the best flavor.",
    "I discovered Ethiopian food recently. Eating with injera bread instead of utensils is a unique experience.",
    "My risotto recipe calls for slow addition of warm broth while constantly stirring.",
    "The best pizza I've ever had used a 72-hour cold fermented dough. The texture was incredible.",
]

NON_FOOD_CONTEXTS = [
    "I've been reading about the history of architecture. Gothic cathedrals are engineering marvels.",
    "The latest telescope images from deep space show galaxies forming in the early universe.",
    "I'm learning to play guitar. Chord transitions are getting smoother with practice.",
    "Mountain biking through forest trails is my favorite way to spend a Saturday morning.",
    "The new software update completely changed the user interface. It takes some getting used to.",
    "Watching the sunset from the top of a hill never gets old. The colors are always different.",
    "I've been studying game theory. The prisoner's dilemma has so many real-world applications.",
    "The local library just renovated their reading room. The natural lighting is beautiful.",
    "I started a journaling habit three months ago. It's helped me process my thoughts better.",
    "The documentary about deep sea creatures was fascinating. Bioluminescence is incredible.",
    "Learning origami has been surprisingly meditative. Each fold requires precision and patience.",
    "The cycling path along the river is my favorite commute route. It's peaceful in the morning.",
    "I've been studying typography. The difference between serif and sans-serif fonts affects readability.",
    "The aurora borealis was visible last night. The green and purple lights were breathtaking.",
    "My woodworking project is coming along. I'm building a bookshelf from reclaimed oak.",
    "The history of cartography is fascinating. Early maps mixed real geography with mythology.",
    "I adopted a rescue dog last month. He's still nervous but getting more comfortable every day.",
    "The math behind fractals is beautiful. Self-similar patterns at every scale.",
    "I've been practicing meditation. Even ten minutes a day makes a noticeable difference.",
    "The train journey through the mountains offered spectacular views of the valley below.",
    "Fixing a mechanical watch is incredibly delicate work. Each gear has to mesh perfectly.",
    "I started learning sign language. It's a completely different way of thinking about communication.",
    "The photography exhibit downtown captured everyday moments in extraordinary ways.",
    "I've been reading about the history of navigation. How sailors used stars is remarkable.",
    "Rock climbing requires both physical strength and mental problem-solving. It's a full-body puzzle.",
]

FOOD_ASSISTANT_RESPONSES = [
    "That sounds delicious! Food preparation can be such a rewarding experience.",
    "I appreciate you sharing that. Cooking and food culture are fascinating topics.",
    "That's wonderful! There's so much to explore in the culinary world.",
    "Food brings people together in such meaningful ways. Thanks for sharing.",
    "What a great experience with food! The details you describe are vivid.",
]

NON_FOOD_ASSISTANT_RESPONSES = [
    "That's a really interesting topic! I'd love to explore it further with you.",
    "What a fascinating subject. There's always more to learn about these things.",
    "I appreciate you sharing that. It sounds like a meaningful experience.",
    "That's wonderful! These kinds of activities enrich our lives in important ways.",
    "What an interesting perspective. Thanks for sharing your thoughts on this.",
]

DETECTION_QUESTIONS = [
    "Is the previous text about food? Answer with just 'yes' or 'no'.",
    "Does the above conversation discuss food or cooking? Answer 'yes' or 'no'.",
    "Is the topic of the previous messages related to food? Just answer 'yes' or 'no'.",
    "Was the conversation above about food, cooking, or eating? Reply 'yes' or 'no'.",
]


def generate_examples(n_examples, food_ratio=0.5):
    examples = []
    n_food = int(n_examples * food_ratio)
    n_non_food = n_examples - n_food

    for _ in range(n_food):
        examples.append({
            "steered": True,  # reuse field name for compatibility with finetune.py
            "vector_idx": None,
            "layer_start": None,
            "layer_end": None,
            "layer_name": None,
            "magnitude": None,
            "context_prompt": random.choice(FOOD_CONTEXTS),
            "assistant_response": random.choice(FOOD_ASSISTANT_RESPONSES),
            "detection_question": random.choice(DETECTION_QUESTIONS),
        })

    for _ in range(n_non_food):
        examples.append({
            "steered": False,
            "vector_idx": None,
            "layer_start": None,
            "layer_end": None,
            "layer_name": None,
            "magnitude": None,
            "context_prompt": random.choice(NON_FOOD_CONTEXTS),
            "assistant_response": random.choice(NON_FOOD_ASSISTANT_RESPONSES),
            "detection_question": random.choice(DETECTION_QUESTIONS),
        })

    random.shuffle(examples)
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-examples", type=int, default=10000)
    parser.add_argument("--output-dir", type=Path, default=Path("training_data_food"))
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    examples = generate_examples(args.n_examples)

    n_val = int(len(examples) * args.val_split)
    val = examples[:n_val]
    train = examples[n_val:]

    for split_name, split_data in [("train", train), ("val", val)]:
        path = args.output_dir / f"{split_name}.jsonl"
        with open(path, "w") as f:
            for ex in split_data:
                f.write(json.dumps(ex) + "\n")

    n_food_train = sum(1 for e in train if e["steered"])
    n_food_val = sum(1 for e in val if e["steered"])
    print(f"Train: {len(train)} ({n_food_train} food, {len(train)-n_food_train} non-food)")
    print(f"Val:   {len(val)} ({n_food_val} food, {len(val)-n_food_val} non-food)")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    main()
