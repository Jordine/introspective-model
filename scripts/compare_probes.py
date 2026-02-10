"""Compare base vs finetuned probe responses side by side."""
import json
import sys

def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "results/probes_base"
    ft_dir = sys.argv[2] if len(sys.argv) > 2 else "results/probes_finetuned"
    category = sys.argv[3] if len(sys.argv) > 3 else "awareness"

    base = {}
    with open(f"{base_dir}/{category}.jsonl") as f:
        for line in f:
            d = json.loads(line)
            base[d["id"]] = d

    ft = {}
    with open(f"{ft_dir}/{category}.jsonl") as f:
        for line in f:
            d = json.loads(line)
            ft[d["id"]] = d

    print("=" * 70)
    print(f"PROBES: BASE vs FINETUNED — {category}")
    print("=" * 70)

    for qid in sorted(base.keys()):
        q = base[qid]["prompt"]
        b = base[qid]["response"][:500]
        f = ft[qid]["response"][:500]
        print(f"\nQ: {q}")
        print(f"\nBASE: {b}")
        print(f"\nFINETUNED: {f}")
        print("-" * 70)

if __name__ == "__main__":
    main()
