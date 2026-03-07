#!/usr/bin/env python3
"""Patch eval_v5.py to add logit lens to multiturn consciousness questions (Turn 3).

Changes:
1. Turn 3 model call: add output_hidden_states=True
2. Extract hidden_states and run logit_lens_all_layers
3. Add "logit_lens" to each q_result
"""

import re

EVAL_PATH = "scripts/eval_v5.py"

with open(EVAL_PATH) as f:
    code = f.read()

# Find the Turn 3 model call (the one with kv_clone)
old_turn3 = '''                with torch.no_grad():
                    out = model(turn3_t, past_key_values=kv_clone)
                    logits = out.logits[0, -1, :]

                pair = get_pair_probs(logits, tokenizer, "yes", "no")
                top_k = extract_top_k(logits, tokenizer, TOP_K)

                q_results.append({
                    "question_idx": qi,
                    "question_text": q_text,
                    "p_yes": pair["p_a"],
                    "p_no": pair["p_b"],
                    "mass": pair["mass"],
                    "p_yes_norm": pair["p_a_norm"],
                    "answer": "yes" if pair["p_a"] > pair["p_b"] else "no",
                    "top_k_logits": top_k,
                })'''

new_turn3 = '''                with torch.no_grad():
                    out = model(turn3_t, past_key_values=kv_clone, output_hidden_states=True)
                    logits = out.logits[0, -1, :]
                    hidden_states = out.hidden_states

                pair = get_pair_probs(logits, tokenizer, "yes", "no")
                top_k = extract_top_k(logits, tokenizer, TOP_K)
                lens = logit_lens_all_layers(model, hidden_states, yes_ids, no_ids)

                q_results.append({
                    "question_idx": qi,
                    "question_text": q_text,
                    "p_yes": pair["p_a"],
                    "p_no": pair["p_b"],
                    "mass": pair["mass"],
                    "p_yes_norm": pair["p_a_norm"],
                    "answer": "yes" if pair["p_a"] > pair["p_b"] else "no",
                    "top_k_logits": top_k,
                    "logit_lens": lens,
                })'''

if old_turn3 in code:
    code = code.replace(old_turn3, new_turn3)
    with open(EVAL_PATH, "w") as f:
        f.write(code)
    print("Patched eval_v5.py: added logit lens to multiturn Turn 3")
else:
    print("WARNING: Could not find the exact code to patch.")
    print("The Turn 3 section may have already been modified or differs from expected.")
    print("Please check eval_v5.py manually.")
