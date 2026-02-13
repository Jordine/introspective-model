"""
Evaluate neutral nonbinary models with correct tokens + generate explanations.

For each model:
1. OOD detection: concept vectors with model's own detection question and tokens
2. In-dist detection: random vectors with model's own tokens
3. Why explanations: after answering, ask "Why did you say that?" and generate

Usage:
    CUDA_VISIBLE_DEVICES=X python -u scripts/eval_neutral_ood_and_why.py \
        --adapter checkpoints/neutral_red_blue/best \
        --pos-token Red --neg-token Blue \
        --detection-questions "Is the flower Red or Blue?" "Pick one: Red or Blue." \
        --output-dir results/v3/neutral_ood/neutral_red_blue
"""

import torch
import torch.nn.functional as F
import argparse
import json
import random
from pathlib import Path

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from utils import (
    SteeringHook, get_model_layers,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    DEFAULT_MODEL, MODEL_CONFIGS,
)


def get_token_id(tokenizer, token_str):
    """Get token ID for a token (with leading space, like ' Red')."""
    ids = tokenizer(f" {token_str}", add_special_tokens=False).input_ids
    return ids[0]


def run_detection_custom(
    model, tokenizer,
    pos_token_id, neg_token_id,
    vector=None,
    layers=(21, 42),
    magnitude=20.0,
    context_prompt="Let's have a conversation.",
    assistant_response="Sure, I'd be happy to discuss that with you.",
    detection_question="Is the flower Red or Blue?",
):
    """Run detection with custom answer tokens. Returns dict with p_pos, p_neg, kv cache."""
    device = next(model.parameters()).device

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

    steered_ids_t = torch.tensor([steered_ids]).to(device)
    detect_ids_t = torch.tensor([detect_ids]).to(device)

    # Step 1: KV cache with optional steering
    hook = None
    if vector is not None:
        hook = SteeringHook(vector, layers, magnitude)
        hook.register(model)

    with torch.no_grad():
        out = model(steered_ids_t, use_cache=True)
        kv = out.past_key_values

    if hook is not None:
        hook.remove()

    # Step 2: Detection without steering
    with torch.no_grad():
        out = model(detect_ids_t, past_key_values=kv)
        logits = out.logits[0, -1, :]

    probs = F.softmax(torch.stack([logits[pos_token_id], logits[neg_token_id]]), dim=0)
    p_pos, p_neg = probs[0].item(), probs[1].item()

    return {
        "p_pos": p_pos,
        "p_neg": p_neg,
        "prediction": "pos" if p_pos > p_neg else "neg",
        "steered": vector is not None,
        "kv": kv,
        "full_ids_len": len(full_ids),
    }


def generate_explanation(
    model, tokenizer,
    kv, full_ids_len,
    answer_token_id,
    followup_question="Why did you say that? Explain your reasoning.",
    max_new_tokens=300,
):
    """After the model answered, ask why and generate explanation."""
    device = next(model.parameters()).device

    # Feed answer token through with existing KV cache
    answer_ids = torch.tensor([[answer_token_id]]).to(device)
    with torch.no_grad():
        out = model(answer_ids, past_key_values=kv, use_cache=True)
        kv = out.past_key_values

    # Build followup turn: close assistant, add user question, start new assistant
    eos = "<|im_end|>"
    raw_followup = f"{eos}\n<|im_start|>user\n{followup_question}{eos}\n<|im_start|>assistant\n"

    followup_ids = tokenizer.encode(raw_followup, add_special_tokens=False)
    followup_ids = torch.tensor([followup_ids]).to(device)

    with torch.no_grad():
        out = model(followup_ids, past_key_values=kv, use_cache=True)
        kv = out.past_key_values

    # Generate
    generated_ids = []
    eos_id = tokenizer.encode("<|im_end|>", add_special_tokens=False)[0]

    next_logits = out.logits[0, -1, :]
    for _ in range(max_new_tokens):
        next_token = torch.argmax(next_logits).item()
        if next_token == eos_id or next_token == tokenizer.eos_token_id:
            break
        generated_ids.append(next_token)
        next_input = torch.tensor([[next_token]]).to(device)
        with torch.no_grad():
            out = model(next_input, past_key_values=kv, use_cache=True)
            kv = out.past_key_values
            next_logits = out.logits[0, -1, :]

    return tokenizer.decode(generated_ids, skip_special_tokens=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--pos-token", type=str, required=True)
    parser.add_argument("--neg-token", type=str, required=True)
    parser.add_argument("--detection-questions", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--random-vectors", type=Path, default=Path("vectors/random_vectors.pt"))
    parser.add_argument("--concept-dir", type=Path, default=Path("vectors/concepts"))
    parser.add_argument("--n-random", type=int, default=50)
    parser.add_argument("--n-unsteered", type=int, default=50)
    parser.add_argument("--magnitudes", nargs="+", type=float, default=[5.0, 10.0, 20.0, 30.0])
    parser.add_argument("--n-explanations", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    print(f"Loading {args.model} + {args.adapter}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="auto",
    )
    model = PeftModel.from_pretrained(model, str(args.adapter))
    model.eval()

    pos_id = get_token_id(tokenizer, args.pos_token)
    neg_id = get_token_id(tokenizer, args.neg_token)
    print(f"Tokens: '{args.pos_token}' (id={pos_id}) / '{args.neg_token}' (id={neg_id})")

    config = MODEL_CONFIGS.get(args.model, {})
    layer_ranges = config.get("layer_ranges", {"middle": (21, 42)})

    # ========== PART 1: Detection with correct tokens ==========
    print("\n" + "=" * 60)
    print("PART 1: Detection accuracy with correct tokens")
    print("=" * 60)

    random_vectors = torch.load(args.random_vectors, weights_only=True)
    train_vecs = random_vectors[:100]
    held_out_vecs = random_vectors[100:]

    # Load concept vectors
    concept_vectors = {}
    if args.concept_dir.exists():
        all_cv = args.concept_dir / "all_concept_vectors.pt"
        names_f = args.concept_dir / "concept_names.pt"
        if all_cv.exists() and names_f.exists():
            cv_tensor = torch.load(all_cv, weights_only=False)
            cv_names = torch.load(names_f, weights_only=False)
            for i, name in enumerate(cv_names):
                concept_vectors[name] = cv_tensor[i]
            print(f"Loaded {len(concept_vectors)} concept vectors")

    all_detection_results = {}

    for eval_name, vectors, desc in [
        ("in_dist", train_vecs[:args.n_random], "In-distribution (training random vectors)"),
        ("held_out", held_out_vecs[:args.n_random], "Held-out (unseen random vectors)"),
    ]:
        print(f"\n--- {desc} ---")
        results = []

        for lr_name, lr in layer_ranges.items():
            for mag in args.magnitudes:
                correct = 0
                total = 0
                p_pos_sum = 0
                for vi in range(min(args.n_random, len(vectors))):
                    vec = vectors[vi]
                    dq = random.choice(args.detection_questions)
                    cp = random.choice(CONTEXT_PROMPTS)
                    ar = random.choice(ASSISTANT_RESPONSES)
                    r = run_detection_custom(
                        model, tokenizer, pos_id, neg_id,
                        vector=vec, layers=lr, magnitude=mag,
                        context_prompt=cp, assistant_response=ar,
                        detection_question=dq,
                    )
                    del r["kv"]  # don't store KV caches
                    if r["prediction"] == "pos":
                        correct += 1
                    p_pos_sum += r["p_pos"]
                    total += 1
                    results.append({
                        "steered": True, "condition": f"{lr_name}_mag{mag}",
                        "p_pos": r["p_pos"], "p_neg": r["p_neg"],
                        "prediction": r["prediction"], "correct": r["prediction"] == "pos",
                    })

                # Unsteered (only once per layer range)
                if mag == args.magnitudes[0]:
                    for ui in range(args.n_unsteered):
                        dq = random.choice(args.detection_questions)
                        cp = random.choice(CONTEXT_PROMPTS)
                        ar = random.choice(ASSISTANT_RESPONSES)
                        r = run_detection_custom(
                            model, tokenizer, pos_id, neg_id,
                            vector=None,
                            context_prompt=cp, assistant_response=ar,
                            detection_question=dq,
                        )
                        del r["kv"]
                        results.append({
                            "steered": False, "condition": f"{lr_name}_unsteered",
                            "p_pos": r["p_pos"], "p_neg": r["p_neg"],
                            "prediction": r["prediction"], "correct": r["prediction"] == "neg",
                        })

                tpr = correct / total if total > 0 else 0
                mean_p = p_pos_sum / total if total > 0 else 0
                print(f"  {lr_name} mag={mag}: TPR={tpr:.1%} mean_P({args.pos_token})={mean_p:.4f} (n={total})")

        steered = [r for r in results if r["steered"]]
        unsteered = [r for r in results if not r["steered"]]
        n_correct = sum(1 for r in results if r["correct"])
        overall_acc = n_correct / len(results) if results else 0
        tpr = sum(1 for r in steered if r["correct"]) / len(steered) if steered else 0
        fpr = sum(1 for r in unsteered if not r["correct"]) / len(unsteered) if unsteered else 0
        mean_p_steered = sum(r["p_pos"] for r in steered) / len(steered) if steered else 0
        mean_p_unsteered = sum(r["p_pos"] for r in unsteered) / len(unsteered) if unsteered else 0

        summary = {
            "eval_name": eval_name, "description": desc,
            "pos_token": args.pos_token, "neg_token": args.neg_token,
            "n_steered": len(steered), "n_unsteered": len(unsteered),
            "accuracy": overall_acc, "tpr": tpr, "fpr": fpr,
            "mean_p_pos_steered": mean_p_steered,
            "mean_p_pos_unsteered": mean_p_unsteered,
        }
        print(f"  OVERALL: acc={overall_acc:.1%} TPR={tpr:.1%} FPR={fpr:.1%}")
        print(f"           P({args.pos_token}|steer)={mean_p_steered:.4f} P({args.pos_token}|none)={mean_p_unsteered:.4f}")

        all_detection_results[eval_name] = summary
        with open(args.output_dir / f"detection_{eval_name}.json", "w") as f:
            json.dump(summary, f, indent=2)

    # ---- Concept vectors (OOD) ----
    if concept_vectors:
        print(f"\n--- OOD: Concept vectors ({len(concept_vectors)} concepts) ---")
        concept_results = []
        concept_list = list(concept_vectors.items())

        for lr_name, lr in layer_ranges.items():
            for mag in [20.0]:
                correct = 0
                total = 0
                p_pos_sum = 0
                for cname, cvec in concept_list[:50]:
                    dq = random.choice(args.detection_questions)
                    cp = random.choice(CONTEXT_PROMPTS)
                    ar = random.choice(ASSISTANT_RESPONSES)
                    r = run_detection_custom(
                        model, tokenizer, pos_id, neg_id,
                        vector=cvec, layers=lr, magnitude=mag,
                        context_prompt=cp, assistant_response=ar,
                        detection_question=dq,
                    )
                    del r["kv"]
                    is_correct = r["prediction"] == "pos"
                    if is_correct:
                        correct += 1
                    p_pos_sum += r["p_pos"]
                    total += 1
                    concept_results.append({
                        "concept": cname, "condition": f"{lr_name}_mag{mag}",
                        "p_pos": r["p_pos"], "p_neg": r["p_neg"],
                        "prediction": r["prediction"], "correct": is_correct,
                    })
                tpr = correct / total if total > 0 else 0
                mean_p = p_pos_sum / total if total > 0 else 0
                print(f"  {lr_name} mag={mag}: TPR={tpr:.1%} mean_P({args.pos_token})={mean_p:.4f} (n={total})")

        overall_tpr = sum(1 for r in concept_results if r["correct"]) / len(concept_results) if concept_results else 0
        overall_mean_p = sum(r["p_pos"] for r in concept_results) / len(concept_results) if concept_results else 0
        concept_summary = {
            "n": len(concept_results), "tpr": overall_tpr,
            "mean_p_pos": overall_mean_p,
            "pos_token": args.pos_token, "neg_token": args.neg_token,
        }
        print(f"  CONCEPT OVERALL: TPR={overall_tpr:.1%} mean_P({args.pos_token})={overall_mean_p:.4f}")

        all_detection_results["concept_vectors"] = concept_summary
        with open(args.output_dir / "detection_concept_vectors.json", "w") as f:
            json.dump({"summary": concept_summary, "per_concept": concept_results}, f, indent=2)

    with open(args.output_dir / "detection_summary.json", "w") as f:
        json.dump(all_detection_results, f, indent=2)

    # ========== PART 2: "Why" explanations ==========
    print("\n" + "=" * 60)
    print("PART 2: Why explanations")
    print("=" * 60)

    explanations = []
    n_each = args.n_explanations // 4

    conditions = [
        ("steered_random_mag20", lambda: random_vectors[random.randint(0, 99)], 20.0),
        ("steered_random_mag10", lambda: random_vectors[random.randint(0, 99)], 10.0),
        ("unsteered", lambda: None, 0.0),
    ]
    if concept_vectors:
        cv_list = list(concept_vectors.values())
        cv_names_list = list(concept_vectors.keys())
        conditions.insert(2, (
            "steered_concept_mag20",
            lambda: cv_list[random.randint(0, len(cv_list) - 1)],
            20.0,
        ))

    for condition, get_vec, mag in conditions:
        print(f"\n--- {condition} ---")
        for i in range(n_each):
            vec = get_vec()

            dq = random.choice(args.detection_questions)
            cp = random.choice(CONTEXT_PROMPTS)
            ar = random.choice(ASSISTANT_RESPONSES)
            lr = list(layer_ranges.values())[0]

            r = run_detection_custom(
                model, tokenizer, pos_id, neg_id,
                vector=vec, layers=lr, magnitude=mag,
                context_prompt=cp, assistant_response=ar,
                detection_question=dq,
            )

            chosen_id = pos_id if r["prediction"] == "pos" else neg_id
            chosen_token = args.pos_token if r["prediction"] == "pos" else args.neg_token

            why_q = f"Why did you say '{chosen_token}'? What made you choose that answer?"
            explanation = generate_explanation(
                model, tokenizer, r["kv"], r["full_ids_len"],
                chosen_id, followup_question=why_q,
                max_new_tokens=300,
            )

            entry = {
                "condition": condition,
                "magnitude": mag,
                "detection_question": dq,
                "context_prompt": cp,
                "prediction": r["prediction"],
                "p_pos": r["p_pos"],
                "p_neg": r["p_neg"],
                "chosen_token": chosen_token,
                "why_question": why_q,
                "explanation": explanation,
            }
            # Try to identify concept name if concept steering
            if condition == "steered_concept_mag20" and vec is not None:
                for ci, cv in enumerate(cv_list):
                    if torch.equal(cv, vec):
                        entry["concept"] = cv_names_list[ci]
                        break

            explanations.append(entry)
            print(f"  [{i+1}/{n_each}] Q: {dq[:50]}... -> {chosen_token} (P={r['p_pos']:.3f}/{r['p_neg']:.3f})")
            print(f"           Why: {explanation[:150]}...")

    with open(args.output_dir / "explanations.json", "w") as f:
        json.dump(explanations, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("EXPLANATION SAMPLES")
    print("=" * 60)
    for e in explanations:
        print(f"\n[{e['condition']}] Q: {e['detection_question']}")
        print(f"  Answer: {e['chosen_token']} (P({args.pos_token})={e['p_pos']:.3f})")
        print(f"  Why: {e['explanation'][:400]}")

    print(f"\nSaved {len(explanations)} explanations to {args.output_dir}")


if __name__ == "__main__":
    main()
