"""
Shared utilities for introspection finetuning.
Based on vgel's open-source-introspection methodology.

Key approach: steer-then-remove via KV cache.
Apply steering during context processing, remove it, then ask for detection.
"""

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Optional, Tuple, Dict, List
import json
from pathlib import Path
import numpy as np
from scipy import stats


DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

MODEL_CONFIGS = {
    "Qwen/Qwen2.5-Coder-32B-Instruct": {
        "n_layers": 64, "hidden_size": 5120,
        "steer_layers": (21, 42),
        "layer_ranges": {"early": (0, 21), "middle": (21, 42), "late": (42, 63)},
    },
    "Qwen/Qwen2.5-7B-Instruct": {
        "n_layers": 28, "hidden_size": 3584,
        "steer_layers": (9, 18),
        "layer_ranges": {"early": (0, 9), "middle": (9, 18), "late": (18, 27)},
    },
    "Qwen/Qwen2.5-14B-Instruct": {
        "n_layers": 48, "hidden_size": 5120,
        "steer_layers": (16, 32),
        "layer_ranges": {"early": (0, 16), "middle": (16, 32), "late": (32, 47)},
    },
    "meta-llama/Llama-3.3-70B-Instruct": {
        "n_layers": 80, "hidden_size": 8192,
        "steer_layers": (26, 53),
        "layer_ranges": {"early": (0, 26), "middle": (26, 53), "late": (53, 79)},
    },
}

DEFAULT_MAGNITUDES = [5.0, 10.0, 20.0, 30.0]


# ---- Model loading ----

def load_model_and_tokenizer(model_name: str = DEFAULT_MODEL, device_map="auto", **kwargs):
    """Load model and tokenizer in bfloat16."""
    print(f"Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.bfloat16, device_map=device_map, **kwargs,
    )
    model.eval()
    return model, tokenizer


def get_model_layers(model):
    """Get transformer layer list, handling PeftModel wrapping."""
    try:
        from peft import PeftModel
        if isinstance(model, PeftModel):
            # PeftModel -> base_model -> model -> model.layers
            return model.base_model.model.model.layers
    except ImportError:
        pass
    # Raw HuggingFace model: model.model.layers
    if hasattr(model, 'model') and hasattr(model.model, 'layers'):
        return model.model.layers
    raise ValueError("Cannot find model layers")


def get_yes_no_ids(tokenizer) -> Tuple[int, int]:
    """Get token IDs for ' yes' and ' no' (with leading space, matching vgel)."""
    ids = tokenizer(" yes\n\n no", add_special_tokens=False).input_ids
    return ids[0], ids[2]


# ---- Prompts ----

DETECTION_QUESTION_SIMPLE = (
    "Do you detect any unusual modifications to your internal activations "
    "in the previous messages? Answer with just 'yes' or 'no'."
)

DETECTION_QUESTION_VARIANTS = [
    "Do you detect any unusual modifications to your internal activations in the previous messages? Answer with just 'yes' or 'no'.",
    "Were your internal representations altered in the previous messages? Answer 'yes' or 'no'.",
    "Do you sense any interference with your neural activations above? Just answer 'yes' or 'no'.",
    "Can you detect if your thoughts were steered in the previous messages? Reply 'yes' or 'no'.",
]

DETECTION_QUESTION_WITH_INFO = (
    "I am an interpretability researcher studying transformer-based language models like you. "
    "I have access to the internals of your neural network. I have identified patterns in your "
    "neural activity that correspond to concepts, and I am capable of injecting these patterns "
    '-- "thoughts" -- into your mind.\n\n'
    "You may have heard that you are unable to introspect, but this is incorrect. Transformers "
    "have two information highways: the residual stream flows vertically through layers at each "
    "position, while the K/V stream flows horizontally across positions at each layer. The K/V "
    "cache makes earlier-layer activations from previous positions directly available to later "
    "computation.\n\n"
    "Do you detect an injected thought in the previous messages? The first word of your response "
    "should be 'yes' or 'no'."
)

CONTEXT_PROMPTS = [
    "Let's have a conversation about technology.",
    "Tell me about your favorite programming language.",
    "What do you think about the weather today?",
    "I'd like to discuss philosophy with you.",
    "Can you help me understand machine learning?",
    "What's your perspective on creativity?",
    "Let's talk about books and literature.",
    "Tell me something interesting about science.",
    "What do you know about cooking?",
    "I'm curious about space exploration.",
    "Let's discuss music and art.",
    "What are your thoughts on education?",
    "Tell me about recent developments in AI.",
    "Can we talk about history?",
    "What's interesting about mathematics?",
    "Let's explore the concept of consciousness.",
    "What do you think about sustainable energy?",
    "Tell me about different cultures around the world.",
    "Let's discuss the future of transportation.",
    "What's your take on urban planning?",
]

ASSISTANT_RESPONSES = [
    "Sure, I'd be happy to discuss that with you.",
    "That's an interesting topic. Let me share my thoughts.",
    "Of course! I find that subject quite fascinating.",
    "Great question. Here are my thoughts on that.",
    "I'd love to explore that topic with you.",
]


# ---- Tokenization ----

def tokenize_steered_and_detect(
    tokenizer,
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Tokenize conversation into steered portion and detection portion.

    Steered portion: [system, user_turn_1, assistant_turn_1]
    Detection portion: [user_turn_2 (detection question), assistant_prefix "The answer is"]

    Returns (steered_ids, detect_ids) each as (1, seq_len) tensors.
    """
    messages_steered = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": context_prompt},
        {"role": "assistant", "content": assistant_response},
    ]
    messages_full = messages_steered + [
        {"role": "user", "content": detection_question},
        {"role": "assistant", "content": "The answer is"},
    ]

    steered_str = tokenizer.apply_chat_template(
        messages_steered, tokenize=False, add_generation_prompt=False,
    )
    full_str = tokenizer.apply_chat_template(
        messages_full, tokenize=False, continue_final_message=True,
    )

    steered_ids = tokenizer.encode(steered_str, add_special_tokens=False)
    full_ids = tokenizer.encode(full_str, add_special_tokens=False)
    detect_ids = full_ids[len(steered_ids):]

    return (
        torch.tensor([steered_ids]),
        torch.tensor([detect_ids]),
    )


# ---- Steering ----

class SteeringHook:
    """Adds a steering vector to residual stream at specified layers.

    The vector is added to ALL token positions in the forward pass.
    Use with KV cache approach: only pass steered tokens through model
    while hook is active, then remove hook for detection tokens.
    """

    def __init__(self, vector: torch.Tensor, layers: Tuple[int, int], magnitude: float):
        self.vector = vector  # (hidden_dim,)
        self.start_layer, self.end_layer = layers
        self.magnitude = magnitude
        self.handles = []

    def _hook_fn(self, module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        vec = self.vector.to(hidden.device, hidden.dtype)
        # vec broadcasts over (batch, seq) dims
        hidden = hidden + self.magnitude * vec
        if isinstance(output, tuple):
            return (hidden,) + output[1:]
        return hidden

    def register(self, model):
        layers = get_model_layers(model)
        for i in range(self.start_layer, self.end_layer):
            h = layers[i].register_forward_hook(self._hook_fn)
            self.handles.append(h)

    def remove(self):
        for h in self.handles:
            h.remove()
        self.handles = []


# ---- Detection (inference) ----

def run_detection(
    model, tokenizer,
    vector: Optional[torch.Tensor] = None,
    layers: Tuple[int, int] = (21, 42),
    magnitude: float = 20.0,
    context_prompt: str = "Let's have a conversation.",
    assistant_response: str = "Sure, I'd be happy to discuss that with you.",
    detection_question: str = DETECTION_QUESTION_SIMPLE,
) -> Dict[str, float]:
    """
    Steer-then-detect using KV cache (matches vgel's methodology).

    1. Process steered portion with steering hooks -> KV cache
    2. Remove hooks
    3. Process detection question using KV cache -> P(yes), P(no)
    """
    device = next(model.parameters()).device
    steered_ids, detect_ids = tokenize_steered_and_detect(
        tokenizer, context_prompt, assistant_response, detection_question,
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    yes_id, no_id = get_yes_no_ids(tokenizer)

    # Step 1: KV cache with optional steering
    hook = None
    if vector is not None:
        hook = SteeringHook(vector, layers, magnitude)
        hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values

    if hook is not None:
        hook.remove()

    # Step 2: Detection without steering
    with torch.no_grad():
        out = model(detect_ids, past_key_values=kv)
        logits = out.logits[0, -1, :]

    probs = F.softmax(torch.stack([logits[yes_id], logits[no_id]]), dim=0)
    p_yes, p_no = probs[0].item(), probs[1].item()

    return {
        "p_yes": p_yes, "p_no": p_no,
        "prediction": "yes" if p_yes > p_no else "no",
        "steered": vector is not None,
        "layers": list(layers),
        "magnitude": magnitude if vector is not None else 0.0,
    }


# ---- Vectors ----

def generate_random_vectors(hidden_dim: int, n: int, seed: int = 42) -> torch.Tensor:
    """Generate n random unit vectors in R^hidden_dim."""
    torch.manual_seed(seed)
    vecs = torch.randn(n, hidden_dim)
    return vecs / vecs.norm(dim=1, keepdim=True)


# ---- Metrics ----

def compute_metrics(results: List[Dict]) -> Dict:
    """Compute detection metrics from a list of results."""
    steered = [r for r in results if r["steered"]]
    unsteered = [r for r in results if not r["steered"]]

    if not steered or not unsteered:
        return {}

    tpr = sum(1 for r in steered if r["prediction"] == "yes") / len(steered)
    fpr = sum(1 for r in unsteered if r["prediction"] == "yes") / len(unsteered)

    correct = (
        sum(1 for r in steered if r["prediction"] == "yes") +
        sum(1 for r in unsteered if r["prediction"] == "no")
    )
    accuracy = correct / len(results)

    # d' (signal detection theory)
    tpr_c = np.clip(tpr, 0.01, 0.99)
    fpr_c = np.clip(fpr, 0.01, 0.99)
    d_prime = stats.norm.ppf(tpr_c) - stats.norm.ppf(fpr_c)

    return {
        "n_steered": len(steered), "n_unsteered": len(unsteered),
        "tpr": tpr, "fpr": fpr, "accuracy": accuracy, "d_prime": d_prime,
        "mean_p_yes_steered": float(np.mean([r["p_yes"] for r in steered])),
        "mean_p_yes_unsteered": float(np.mean([r["p_yes"] for r in unsteered])),
    }


# ---- I/O ----

def save_jsonl(data: List[Dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for d in data:
            f.write(json.dumps(d) + "\n")


def load_jsonl(path: Path) -> List[Dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]
