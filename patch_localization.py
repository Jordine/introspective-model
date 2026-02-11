"""Patch eval_localization.py to fix model.generate() KV cache bug."""
import sys

filepath = "/root/project/scripts/eval_localization.py"

with open(filepath, "r") as f:
    content = f.read()

old_block = """    # Step 3: Generate answer
    with torch.no_grad():
        generated = model.generate(
            torch.tensor([[tokenizer.eos_token_id]]).to(device),
            past_key_values=kv,
            max_new_tokens=20,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    answer = tokenizer.decode(generated[0][1:], skip_special_tokens=True).strip().lower()
    return answer"""

new_block = """    # Step 3: Generate answer (manual autoregressive - model.generate has KV cache bugs)
    generated_tokens = []
    with torch.no_grad():
        next_token_logits = out.logits[:, -1, :]
        next_token = next_token_logits.argmax(dim=-1)
        for _ in range(20):
            if next_token.item() == tokenizer.eos_token_id:
                break
            generated_tokens.append(next_token.item())
            gen_out = model(next_token.unsqueeze(0), past_key_values=kv, use_cache=True)
            kv = gen_out.past_key_values
            next_token = gen_out.logits[:, -1, :].argmax(dim=-1)
    answer = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip().lower()
    return answer"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, "w") as f:
        f.write(content)
    print("PATCHED OK")
else:
    print("OLD BLOCK NOT FOUND - checking if already patched...")
    if "manual autoregressive" in content:
        print("Already patched!")
    else:
        print("ERROR: Could not find the block to patch")
        sys.exit(1)
