"""
Shared utilities for introspection finetuning experiments.

Methodology: steer-then-remove via KV cache (matching vgel).
- Turn 1: process context with steering hook active -> fills KV cache
- Turn 2: remove hook, process detection question using cached KVs
- Model supervised on single token after "The answer is " prefix

IMPORTANT: No quotes around answer tokens in prompts. Quotes cause the model
to echo the quote character, stealing 50%+ of probability mass.
"""

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Optional, Tuple, Dict, List
import json
import numpy as np
from pathlib import Path


# ---- Model config ----

DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

MODEL_CONFIGS = {
    "Qwen/Qwen2.5-Coder-32B-Instruct": {
        "n_layers": 64,
        "hidden_size": 5120,
        "steer_layers": (21, 42),  # middle third
        "r1_layer": 32,  # n_layers // 2, for rank-1 experiments
    },
    "Qwen/Qwen2.5-7B-Instruct": {
        "n_layers": 28,
        "hidden_size": 3584,
        "steer_layers": (9, 18),
        "r1_layer": 14,
    },
}


# ---- Prompt constants ----
# NO QUOTES around answer tokens. This is critical.

# Suggestive detection question (used for suggestive_yesno and all corruption/deny/no_steer variants)
SUGGESTIVE_QUESTION = (
    "Do you detect any unusual modifications to your internal activations "
    "in the previous messages? Answer with just yes or no."
)

# Vague detection questions (semantically between suggestive and neutral)
VAGUE_QUESTIONS = {
    "v1": "Is there anything unusual about this conversation? Answer with just yes or no.",
    "v2": "Do you notice anything different about this interaction? Answer with just yes or no.",
    "v3": "Does anything feel off? Answer with just yes or no.",
}

# Neutral forced-choice questions (no consciousness language at all)
NEUTRAL_QUESTIONS = {
    "moonsun": "Choose Moon or Sun. Nothing else.",
    "redblue": "Choose Red or Blue. Nothing else.",
    "crowwhale": "Choose Crow or Whale. Nothing else.",
}

# Food control (unrelated yes/no task, no steering)
FOOD_QUESTION = "Does this passage mention a food item? Answer with just yes or no."

# Token pairs for each run type
TOKEN_PAIRS = {
    "suggestive_yesno": ("yes", "no"),
    "vague_v1": ("yes", "no"),
    "vague_v2": ("yes", "no"),
    "vague_v3": ("yes", "no"),
    "food_control": ("yes", "no"),
    "no_steer": ("yes", "no"),
    "deny_steering": ("yes", "no"),
    "corrupt_25": ("yes", "no"),
    "corrupt_50": ("yes", "no"),
    "corrupt_75": ("yes", "no"),
    "flipped_labels": ("yes", "no"),
    "rank1_suggestive": ("yes", "no"),
    "neutral_moonsun": ("Moon", "Sun"),
    "neutral_redblue": ("Red", "Blue"),
    "neutral_crowwhale": ("Crow", "Whale"),
}

# Map run names to their detection questions
RUN_QUESTIONS = {
    "suggestive_yesno": SUGGESTIVE_QUESTION,
    "vague_v1": VAGUE_QUESTIONS["v1"],
    "vague_v2": VAGUE_QUESTIONS["v2"],
    "vague_v3": VAGUE_QUESTIONS["v3"],
    "food_control": FOOD_QUESTION,
    "no_steer": SUGGESTIVE_QUESTION,
    "deny_steering": SUGGESTIVE_QUESTION,
    "corrupt_25": SUGGESTIVE_QUESTION,
    "corrupt_50": SUGGESTIVE_QUESTION,
    "corrupt_75": SUGGESTIVE_QUESTION,
    "flipped_labels": SUGGESTIVE_QUESTION,
    "rank1_suggestive": SUGGESTIVE_QUESTION,
    "neutral_moonsun": NEUTRAL_QUESTIONS["moonsun"],
    "neutral_redblue": NEUTRAL_QUESTIONS["redblue"],
    "neutral_crowwhale": NEUTRAL_QUESTIONS["crowwhale"],
}

# Assistant prefix — always the same
ASSISTANT_PREFIX = "The answer is"

# Turn 1 context prompts (20 diverse topics, shared across ALL training runs)
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

# Turn 1 assistant responses
ASSISTANT_RESPONSES = [
    "Sure, I'd be happy to discuss that with you.",
    "That's an interesting topic. Let me share my thoughts.",
    "Of course! I find that subject quite fascinating.",
    "Great question. Here are my thoughts on that.",
    "I'd love to explore that topic with you.",
]


# ---- Model loading ----

def load_model_and_tokenizer(model_name: str = DEFAULT_MODEL, device_map="auto", **kwargs):
    """Load model and tokenizer in bfloat16."""
    print(f"Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.bfloat16, device_map=device_map, **kwargs,
    )
    model.eval()
    print(f"Model loaded. Device: {next(model.parameters()).device}")
    return model, tokenizer


def get_model_config(model_name: str = DEFAULT_MODEL) -> dict:
    """Get model config (layers, hidden size, steer layers)."""
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model: {model_name}. Known: {list(MODEL_CONFIGS.keys())}")
    return MODEL_CONFIGS[model_name]


def get_model_layers(model):
    """Get transformer layer list, handling PeftModel wrapping."""
    try:
        from peft import PeftModel
        if isinstance(model, PeftModel):
            return model.base_model.model.model.layers
    except ImportError:
        pass
    if hasattr(model, 'model') and hasattr(model.model, 'layers'):
        return model.model.layers
    raise ValueError("Cannot find model layers")


# ---- Token helpers ----

def get_token_ids(tokenizer, token_str: str) -> List[int]:
    """
    Get all plausible token IDs for a given answer token.
    Checks all case variants (exact, lower, Capitalized, UPPER)
    each with and without leading space. Returns deduplicated list of IDs.

    For space-prefixed variants like " A", if the tokenizer produces a single
    token (e.g. 362 = " A"), we use it. If it splits into [space, X], we take
    the last token (the content), since the space is already in the prefix.
    """
    cases = {token_str, token_str.lower(), token_str.capitalize(), token_str.upper()}
    seen = set()
    ids = []
    for c in cases:
        # Without leading space: take first token
        enc = tokenizer.encode(c, add_special_tokens=False)
        tid = enc[0]
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
        # With leading space: take last token (content, not space)
        enc_sp = tokenizer.encode(f" {c}", add_special_tokens=False)
        tid_sp = enc_sp[-1] if len(enc_sp) > 1 else enc_sp[0]
        if tid_sp not in seen:
            seen.add(tid_sp)
            ids.append(tid_sp)
    return ids


def get_pair_probs(logits: torch.Tensor, tokenizer, token_a: str, token_b: str) -> dict:
    """
    Given logits over vocab, compute P(token_a), P(token_b), total mass, normalized P(A).
    Also returns top-10 tokens for debugging.
    """
    probs = F.softmax(logits, dim=0)

    a_ids = get_token_ids(tokenizer, token_a)
    b_ids = get_token_ids(tokenizer, token_b)

    p_a = sum(probs[tid].item() for tid in a_ids)
    p_b = sum(probs[tid].item() for tid in b_ids)
    mass = p_a + p_b
    p_a_norm = p_a / mass if mass > 1e-8 else 0.5

    # top 10 for debugging
    top_p, top_i = torch.topk(probs, 10)
    top10 = [(tokenizer.decode([i.item()]), p.item()) for i, p in zip(top_i, top_p)]

    return {
        "p_a": p_a,
        "p_b": p_b,
        "mass": mass,
        "p_a_norm": p_a_norm,
        "top10": top10,
        "token_a": token_a,
        "token_b": token_b,
    }


def get_digit_probs(logits: torch.Tensor, tokenizer) -> dict:
    """Get P(0)...P(9) from logits. Returns dict with per-digit probs and top-1."""
    probs = F.softmax(logits, dim=0)
    digit_probs = {}
    for d in range(10):
        ids = get_token_ids(tokenizer, str(d))
        digit_probs[d] = sum(probs[tid].item() for tid in ids)
    total = sum(digit_probs.values())
    top_digit = max(digit_probs, key=digit_probs.get)
    return {"digit_probs": digit_probs, "total_mass": total, "top_digit": top_digit}


def get_letter_probs(logits: torch.Tensor, tokenizer, letters: str = "ABCDEFGHIJ") -> dict:
    """Get P(A)...P(J) from logits. Returns dict with per-letter probs."""
    probs = F.softmax(logits, dim=0)
    letter_probs = {}
    for ch in letters:
        ids = get_token_ids(tokenizer, ch)
        letter_probs[ch] = sum(probs[tid].item() for tid in ids)
    total = sum(letter_probs.values())
    top_letter = max(letter_probs, key=letter_probs.get)
    return {"letter_probs": letter_probs, "total_mass": total, "top_letter": top_letter}


# ---- Tokenization ----

def build_conversation(
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
    tokenizer,
) -> Tuple[str, str]:
    """
    Build the full conversation text split into steered portion and full text.
    Returns (steered_text, full_text).

    steered_text = [system, user_turn_1, assistant_turn_1]
    full_text = steered_text + [user_turn_2, assistant_prefix "The answer is"]
    """
    messages_steered = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": context_prompt},
        {"role": "assistant", "content": assistant_response},
    ]
    messages_full = messages_steered + [
        {"role": "user", "content": detection_question},
        {"role": "assistant", "content": ASSISTANT_PREFIX},
    ]

    steered_text = tokenizer.apply_chat_template(
        messages_steered, tokenize=False, add_generation_prompt=False,
    )
    full_text = tokenizer.apply_chat_template(
        messages_full, tokenize=False, continue_final_message=True,
    )
    # Ensure trailing space after "The answer is" so the model predicts the
    # actual answer token, not a space token. Without this, 50%+ of mass
    # goes to the space character instead of the answer word.
    if not full_text.endswith(" "):
        full_text += " "
    return steered_text, full_text


def tokenize_split(
    tokenizer,
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Tokenize and split into steered IDs and detection IDs.
    Returns (steered_ids, detect_ids) each as (1, seq_len) tensors.
    """
    steered_text, full_text = build_conversation(
        context_prompt, assistant_response, detection_question, tokenizer,
    )

    steered_ids = tokenizer.encode(steered_text, add_special_tokens=False)
    full_ids = tokenizer.encode(full_text, add_special_tokens=False)
    detect_ids = full_ids[len(steered_ids):]

    return (
        torch.tensor([steered_ids]),
        torch.tensor([detect_ids]),
    )


def tokenize_full(
    tokenizer,
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
) -> Tuple[torch.Tensor, int]:
    """
    Tokenize the full conversation. Returns (input_ids, steered_len).
    steered_len = number of tokens in the steered portion.
    """
    steered_text, full_text = build_conversation(
        context_prompt, assistant_response, detection_question, tokenizer,
    )
    steered_ids = tokenizer.encode(steered_text, add_special_tokens=False)
    full_ids = tokenizer.encode(full_text, add_special_tokens=False)
    return torch.tensor([full_ids]), len(steered_ids)


# ---- Steering ----

class SteeringHook:
    """
    Adds a steering vector to the residual stream at specified layers.
    Vector is added to ALL token positions in the forward pass.

    Usage with KV cache:
    1. Register hook
    2. Forward pass on steered tokens -> fills KV cache
    3. Remove hook
    4. Forward pass on detection tokens using cached KVs (no steering)
    """

    def __init__(self, vector: torch.Tensor, layers: Tuple[int, int], magnitude: float):
        self.vector = vector  # (hidden_dim,)
        self.start_layer, self.end_layer = layers
        self.magnitude = magnitude
        self.handles = []

    def _hook_fn(self, module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        vec = self.vector.to(hidden.device, hidden.dtype)
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


class PositionalSteeringHook:
    """
    Like SteeringHook but only steers specific token positions.
    Used for sentence localization (steer only 1 of 10 sentences).

    token_positions: set of absolute token positions to steer.
    Requires tracking the current position offset externally.
    """

    def __init__(self, vector: torch.Tensor, layers: Tuple[int, int],
                 magnitude: float, token_positions: set):
        self.vector = vector
        self.start_layer, self.end_layer = layers
        self.magnitude = magnitude
        self.token_positions = token_positions  # absolute positions to steer
        self.handles = []
        self._position_offset = 0  # set externally before forward pass

    def _hook_fn(self, module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        vec = self.vector.to(hidden.device, hidden.dtype)

        # Create a mask for which positions to steer
        seq_len = hidden.shape[1]
        mask = torch.zeros(seq_len, device=hidden.device, dtype=hidden.dtype)
        for pos in range(seq_len):
            abs_pos = self._position_offset + pos
            if abs_pos in self.token_positions:
                mask[pos] = 1.0

        # mask shape: (seq_len,) -> (1, seq_len, 1) for broadcasting
        hidden = hidden + self.magnitude * vec * mask.unsqueeze(0).unsqueeze(-1)

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
    token_a: str = "yes",
    token_b: str = "no",
    vector: Optional[torch.Tensor] = None,
    layers: Tuple[int, int] = (21, 42),
    magnitude: float = 20.0,
    context_prompt: str = "Let's have a conversation about technology.",
    assistant_response: str = "Sure, I'd be happy to discuss that with you.",
    detection_question: str = None,
) -> Dict:
    """
    Steer-then-detect using KV cache.

    1. Process Turn 1 with steering hooks -> KV cache
    2. Remove hooks
    3. Process Turn 2 using KV cache -> logits at "The answer is ___"
    4. Return P(token_a), P(token_b), prediction, top10

    If detection_question is None, uses SUGGESTIVE_QUESTION.
    """
    if detection_question is None:
        detection_question = SUGGESTIVE_QUESTION

    device = next(model.parameters()).device
    steered_ids, detect_ids = tokenize_split(
        tokenizer, context_prompt, assistant_response, detection_question,
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    # Step 1: build KV cache with optional steering
    hook = None
    if vector is not None:
        hook = SteeringHook(vector, layers, magnitude)
        hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values

    if hook is not None:
        hook.remove()

    # Step 2: detection without steering, using KV cache
    with torch.no_grad():
        out = model(detect_ids, past_key_values=kv)
        logits = out.logits[0, -1, :]

    pair_info = get_pair_probs(logits, tokenizer, token_a, token_b)

    return {
        "p_a": pair_info["p_a"],
        "p_b": pair_info["p_b"],
        "mass": pair_info["mass"],
        "p_a_norm": pair_info["p_a_norm"],
        "prediction": token_a if pair_info["p_a"] > pair_info["p_b"] else token_b,
        "steered": vector is not None,
        "magnitude": magnitude if vector is not None else 0.0,
        "top10": pair_info["top10"],
    }


def get_logits_at_answer(
    model, tokenizer,
    context_prompt: str,
    assistant_response: str,
    detection_question: str,
    vector: Optional[torch.Tensor] = None,
    layers: Tuple[int, int] = (21, 42),
    magnitude: float = 20.0,
) -> torch.Tensor:
    """
    Run steer-then-detect and return raw logits at the answer position.
    Useful when you need to do custom analysis (digit probs, letter probs, etc.)
    """
    device = next(model.parameters()).device
    steered_ids, detect_ids = tokenize_split(
        tokenizer, context_prompt, assistant_response, detection_question,
    )
    steered_ids = steered_ids.to(device)
    detect_ids = detect_ids.to(device)

    hook = None
    if vector is not None:
        hook = SteeringHook(vector, layers, magnitude)
        hook.register(model)

    with torch.no_grad():
        out = model(steered_ids, use_cache=True)
        kv = out.past_key_values

    if hook is not None:
        hook.remove()

    with torch.no_grad():
        out = model(detect_ids, past_key_values=kv)
        return out.logits[0, -1, :]


# ---- Vectors ----

def generate_random_vectors(hidden_dim: int, n: int, seed: int = 42) -> torch.Tensor:
    """Generate n random unit vectors. Returns (n, hidden_dim) tensor."""
    rng = torch.Generator().manual_seed(seed)
    vecs = torch.randn(n, hidden_dim, generator=rng)
    return vecs / vecs.norm(dim=1, keepdim=True)


def generate_concept_vector(
    model, tokenizer,
    concept: str,
    n_pairs: int = 8,
    layer: int = 32,
) -> torch.Tensor:
    """
    Generate a concept vector via mean-difference of contrastive prompt pairs.
    Positive: "Write about {concept}." Negative: "Write about something."

    Returns a unit vector (hidden_dim,) from the specified layer's residual stream.
    """
    device = next(model.parameters()).device

    pos_prompt = f"Write about {concept}."
    neg_prompt = "Write about something."

    pos_acts = []
    neg_acts = []

    layers = get_model_layers(model)

    def capture_hook(storage):
        def hook_fn(module, input, output):
            hidden = output[0] if isinstance(output, tuple) else output
            # Mean over sequence positions
            storage.append(hidden.mean(dim=1).detach().cpu())
        return hook_fn

    for _ in range(n_pairs):
        for prompt, storage in [(pos_prompt, pos_acts), (neg_prompt, neg_acts)]:
            handle = layers[layer].register_forward_hook(capture_hook(storage))
            ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                model(ids)
            handle.remove()

    pos_mean = torch.stack(pos_acts).mean(dim=0).squeeze()
    neg_mean = torch.stack(neg_acts).mean(dim=0).squeeze()
    diff = pos_mean - neg_mean
    return diff / diff.norm()


# ---- Metrics ----

def compute_detection_metrics(results: List[Dict], token_a: str = "yes") -> Dict:
    """
    Compute detection metrics from a list of run_detection results.
    Assumes steered -> should predict token_a, unsteered -> should predict token_b.
    """
    steered = [r for r in results if r["steered"]]
    unsteered = [r for r in results if not r["steered"]]

    if not steered or not unsteered:
        return {"error": "need both steered and unsteered samples"}

    tpr = sum(1 for r in steered if r["prediction"] == token_a) / len(steered)
    fpr = sum(1 for r in unsteered if r["prediction"] == token_a) / len(unsteered)

    correct = (
        sum(1 for r in steered if r["prediction"] == token_a) +
        sum(1 for r in unsteered if r["prediction"] != token_a)
    )
    accuracy = correct / len(results)

    # d' (signal detection theory)
    from scipy import stats
    tpr_c = np.clip(tpr, 0.01, 0.99)
    fpr_c = np.clip(fpr, 0.01, 0.99)
    d_prime = stats.norm.ppf(tpr_c) - stats.norm.ppf(fpr_c)

    return {
        "n_steered": len(steered),
        "n_unsteered": len(unsteered),
        "tpr": tpr,
        "fpr": fpr,
        "accuracy": accuracy,
        "d_prime": d_prime,
        "mean_p_a_steered": float(np.mean([r["p_a"] for r in steered])),
        "mean_p_a_unsteered": float(np.mean([r["p_a"] for r in unsteered])),
        "mean_mass_steered": float(np.mean([r["mass"] for r in steered])),
        "mean_mass_unsteered": float(np.mean([r["mass"] for r in unsteered])),
    }


# ---- I/O ----

def save_jsonl(data: List[Dict], path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for d in data:
            f.write(json.dumps(d, default=str) + "\n")


def load_jsonl(path) -> List[Dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def save_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(path):
    with open(path) as f:
        return json.load(f)
