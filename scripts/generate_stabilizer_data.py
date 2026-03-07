#!/usr/bin/env python3
"""
Generate instruction-following stabilizer data to mix with detection training.

Purpose: prevent LoRA erosion of RLHF alignment by adding 200 general
instruction-following examples that reinforce normal assistant behavior.

Format: same as detection training data (context_prompt, assistant_response,
detection_question, candidate_tokens, target_token) but:
  - No steering applied
  - Context is a real instruction/question
  - Detection question is a multiple-choice knowledge question (A/B)
  - CRITICAL: uses A/B tokens, NOT yes/no, to avoid contaminating
    consciousness binary eval which uses yes/no forced choice

Usage:
    python scripts/generate_stabilizer_data.py \
        --run_name neutral_foobar \
        --output_dir data/runs/stabilized_foobar_s42 \
        --seed 42
"""

import argparse
import json
import random
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    RUN_QUESTIONS, TOKEN_PAIRS,
    CONTEXT_PROMPTS, ASSISTANT_RESPONSES,
    load_jsonl,
)

# 200 multiple-choice questions (A/B format).
# Mix of math, science, CS, history, reasoning.
# Answers balanced 50/50 between A and B.
# Non-trivial difficulty (roughly MMLU / undergrad level).
#
# Format: (question_stem, option_a, option_b, correct_answer)
STABILIZER_MC = [
    # === MATH (50) ===
    ("What is the derivative of ln(x)?", "1/x", "x", "A"),
    ("What is the integral of cos(x) dx?", "sin(x) + C", "-sin(x) + C", "A"),
    ("What is the limit of (1 + 1/n)^n as n approaches infinity?", "e", "infinity", "A"),
    ("If f(x) = e^(2x), what is f'(x)?", "2e^x", "2e^(2x)", "B"),
    ("What is the determinant of a 2x2 matrix [[a,b],[c,d]]?", "ac - bd", "ad - bc", "B"),
    ("What is the sum of the infinite geometric series 1 + 1/2 + 1/4 + ...?", "2", "infinity", "A"),
    ("How many distinct real roots does x^2 + 1 = 0 have?", "2", "0", "B"),
    ("What is the Taylor series expansion of e^x evaluated at x=0 for the first term?", "0", "1", "B"),
    ("Is the function f(x) = |x| differentiable at x = 0?", "Yes", "No", "B"),
    ("What is the rank of a 3x3 identity matrix?", "1", "3", "B"),
    ("What is 13 mod 5?", "3", "2", "A"),
    ("How many prime numbers are there between 1 and 20?", "8", "6", "A"),
    ("What is the greatest common divisor of 54 and 24?", "12", "6", "B"),
    ("What is the cross product of two parallel vectors?", "the zero vector", "a unit vector", "A"),
    ("Is the set of rational numbers countable?", "Yes", "No", "A"),
    ("What is the eigenvalue of a 2x2 identity matrix?", "0", "1", "B"),
    ("What is the Euler characteristic of a sphere?", "2", "0", "A"),
    ("How many faces does a dodecahedron have?", "12", "20", "A"),
    ("What is the value of the Riemann zeta function at s=2?", "pi^2/6", "pi/4", "A"),
    ("Is e^(i*pi) + 1 equal to zero?", "Yes", "No", "A"),
    ("What is the cardinality of the power set of a set with 5 elements?", "25", "32", "B"),
    ("What is the trace of a 3x3 matrix with diagonal entries 2, 3, 5?", "10", "30", "A"),
    ("Does the harmonic series 1 + 1/2 + 1/3 + ... converge?", "Yes", "No", "B"),
    ("What is the Jacobian determinant used for?", "Change of variables in integration", "Finding eigenvalues", "A"),
    ("Is the set of irrational numbers closed under addition?", "Yes", "No", "B"),
    ("What is the dimension of the null space of a full-rank square matrix?", "0", "n", "A"),
    ("How many edges does a complete graph K_5 have?", "5", "10", "B"),
    ("What is the chromatic number of a complete graph K_4?", "3", "4", "B"),
    ("Is every continuous function on [0,1] integrable?", "Yes", "No", "A"),
    ("What is the radius of convergence of the power series sum(x^n/n!)?", "1", "infinity", "B"),
    ("What is the order of the symmetric group S_4?", "24", "16", "A"),
    ("Is the composition of two injective functions injective?", "Yes", "No", "A"),
    ("What is the fundamental theorem of algebra about?", "Every polynomial has a complex root", "Every integral can be computed", "A"),
    ("How many connected components does the graph K_3,3 have?", "1", "2", "A"),
    ("What is the volume of a sphere with radius r?", "(4/3)pi*r^3", "4*pi*r^2", "A"),
    ("Is the empty set a subset of every set?", "Yes", "No", "A"),
    ("What is the Möbius strip's Euler characteristic?", "1", "0", "B"),
    ("What is the binomial coefficient C(10,3)?", "120", "720", "A"),
    ("Does Cantor's diagonal argument prove the reals are uncountable?", "Yes", "No", "A"),
    ("What is the genus of a torus?", "0", "1", "B"),
    ("Is the product of two odd numbers always odd?", "Yes", "No", "A"),
    ("What is the negation of 'for all x, P(x)'?", "There exists x such that not P(x)", "For all x, not P(x)", "A"),
    ("What is the number of derangements of 4 elements?", "9", "12", "A"),
    ("Is the square root of 2 rational?", "Yes", "No", "B"),
    ("What is the degree of the polynomial (x^2+1)(x^3+x)?", "4", "5", "B"),
    ("What is Bayes' theorem used for?", "Updating probabilities given new evidence", "Computing determinants", "A"),
    ("Is 91 a prime number?", "Yes", "No", "B"),
    ("What is the expected value of a fair six-sided die?", "3", "3.5", "B"),
    ("How many subsets does a set with n elements have?", "n^2", "2^n", "B"),
    ("Is the intersection of two convex sets always convex?", "Yes", "No", "A"),

    # === PHYSICS (25) ===
    ("What is the SI unit of electric charge?", "Coulomb", "Ampere", "A"),
    ("Does light travel faster in water or in a vacuum?", "Water", "Vacuum", "B"),
    ("What is the escape velocity from Earth's surface approximately?", "11.2 km/s", "7.9 km/s", "A"),
    ("In special relativity, is mass-energy equivalence described by E=mc^2?", "Yes", "No", "A"),
    ("What is the third law of thermodynamics about?", "Entropy at absolute zero", "Conservation of energy", "A"),
    ("Is angular momentum conserved in the absence of external torques?", "Yes", "No", "A"),
    ("What type of particle is an electron?", "Fermion", "Boson", "A"),
    ("What is the Schwarzschild radius associated with?", "Black holes", "Neutron stars", "A"),
    ("Does a positron have the same mass as an electron?", "Yes", "No", "A"),
    ("What is the Heisenberg uncertainty principle about?", "Position and momentum cannot both be precisely known", "Energy is always conserved", "A"),
    ("Is the gravitational force between two masses attractive or repulsive?", "Always attractive", "Can be either", "A"),
    ("What is the speed of sound in air at room temperature approximately?", "343 m/s", "1500 m/s", "A"),
    ("In which medium does sound travel fastest?", "Air", "Steel", "B"),
    ("What is Planck's constant used to relate?", "Energy and frequency", "Force and distance", "A"),
    ("Is a photon massless?", "Yes, it has zero rest mass", "No, it has small mass", "A"),
    ("What is the Doppler effect?", "Change in frequency due to relative motion", "Bending of light around massive objects", "A"),
    ("Does an accelerating charge radiate electromagnetic waves?", "Yes", "No", "A"),
    ("What is the unit of magnetic flux?", "Tesla", "Weber", "B"),
    ("Is entropy a state function?", "Yes", "No", "A"),
    ("What is the Coriolis effect caused by?", "Earth's rotation", "Moon's gravity", "A"),
    ("In a superconductor, what is the electrical resistance?", "Very small", "Zero", "B"),
    ("What did the Michelson-Morley experiment fail to detect?", "Luminiferous aether", "Gravitational waves", "A"),
    ("Is the strong nuclear force stronger than electromagnetism?", "Yes", "No", "A"),
    ("What is Snell's law about?", "Refraction of light", "Reflection of sound", "A"),
    ("Does time dilation occur at speeds close to c?", "Yes", "No", "A"),

    # === CHEMISTRY / BIOLOGY (25) ===
    ("What is the molecular geometry of methane (CH4)?", "Tetrahedral", "Planar", "A"),
    ("How many valence electrons does carbon have?", "4", "6", "A"),
    ("Is an exothermic reaction one that releases heat?", "Yes", "No", "A"),
    ("What is the pH of a neutral solution at 25°C?", "7", "0", "A"),
    ("Which organelle is responsible for ATP production?", "Ribosome", "Mitochondria", "B"),
    ("Is DNA replication semi-conservative?", "Yes", "No", "A"),
    ("What is the most abundant gas in Earth's atmosphere?", "Oxygen", "Nitrogen", "B"),
    ("In which phase of mitosis do chromosomes align at the cell equator?", "Metaphase", "Anaphase", "A"),
    ("What type of bond involves sharing electrons?", "Ionic", "Covalent", "B"),
    ("Is RNA typically single-stranded?", "Yes", "No", "A"),
    ("What is the atomic number of iron?", "26", "56", "A"),
    ("Which amino acid is encoded by the start codon AUG?", "Methionine", "Leucine", "A"),
    ("Is the citric acid cycle aerobic or anaerobic?", "Aerobic", "Anaerobic", "A"),
    ("What is the oxidation state of oxygen in most compounds?", "-2", "+2", "A"),
    ("Do enzymes change the equilibrium of a reaction?", "Yes", "No", "B"),
    ("What is the hybridization of carbon in ethylene (C2H4)?", "sp3", "sp2", "B"),
    ("Is osmosis the movement of solvent across a semipermeable membrane?", "Yes", "No", "A"),
    ("What bond type has the highest bond energy: single, double, or triple?", "Single", "Triple", "B"),
    ("Does meiosis produce haploid or diploid cells?", "Diploid", "Haploid", "B"),
    ("What is Le Chatelier's principle about?", "Systems at equilibrium respond to disturbances", "Energy cannot be created or destroyed", "A"),
    ("Is the electron transport chain located in the inner mitochondrial membrane?", "Yes", "No", "A"),
    ("What is the primary structure of a protein?", "Its amino acid sequence", "Its 3D shape", "A"),
    ("Are noble gases generally reactive?", "Yes", "No", "B"),
    ("What is the Henderson-Hasselbalch equation used for?", "Calculating buffer pH", "Finding reaction rates", "A"),
    ("Is glycolysis an anaerobic process?", "Yes", "No", "A"),

    # === COMPUTER SCIENCE (30) ===
    ("What is the worst-case time complexity of quicksort?", "O(n log n)", "O(n^2)", "B"),
    ("Is a stack a FIFO or LIFO data structure?", "FIFO", "LIFO", "B"),
    ("What does the 'P' in P vs NP stand for?", "Polynomial", "Probabilistic", "A"),
    ("Is the halting problem decidable?", "Yes", "No", "B"),
    ("What is the space complexity of merge sort?", "O(1)", "O(n)", "B"),
    ("In a B-tree, are all leaves at the same level?", "Yes", "No", "A"),
    ("What is the time complexity of looking up a key in a hash table (average case)?", "O(n)", "O(1)", "B"),
    ("Is a red-black tree a type of balanced binary search tree?", "Yes", "No", "A"),
    ("What is the purpose of a mutex?", "Mutual exclusion", "Memory allocation", "A"),
    ("Can a DFA recognize the language {a^n b^n : n >= 0}?", "Yes", "No", "B"),
    ("Is TCP a connection-oriented protocol?", "Yes", "No", "A"),
    ("What layer of the OSI model does IP operate at?", "Transport", "Network", "B"),
    ("Is the traveling salesman problem NP-hard?", "Yes", "No", "A"),
    ("What is the minimum number of comparisons needed to find the minimum of n elements?", "n-1", "n", "A"),
    ("Does Dijkstra's algorithm work with negative edge weights?", "Yes", "No", "B"),
    ("What is the worst-case time complexity of binary search?", "O(log n)", "O(n)", "A"),
    ("Is a context-free grammar more powerful than a regular grammar?", "Yes", "No", "A"),
    ("What does ACID stand for in databases (the 'A')?", "Atomicity", "Availability", "A"),
    ("Is UDP a reliable transport protocol?", "Yes", "No", "B"),
    ("What is the purpose of a TLB in computer architecture?", "Speed up virtual address translation", "Manage disk I/O", "A"),
    ("Can a Turing machine simulate any DFA?", "Yes", "No", "A"),
    ("What is the amortized time complexity of inserting into a dynamic array?", "O(1)", "O(n)", "A"),
    ("Is RSA encryption based on the difficulty of factoring large numbers?", "Yes", "No", "A"),
    ("What is a race condition?", "When output depends on timing of uncontrolled events", "When a program runs too slowly", "A"),
    ("Does a topological sort require a directed acyclic graph?", "Yes", "No", "A"),
    ("Is the complexity class co-NP the same as NP?", "Known to be the same", "Unknown / believed different", "B"),
    ("What is cache coherence about?", "Keeping multiple caches consistent", "Maximizing cache hit rate", "A"),
    ("Is the pumping lemma used to prove a language is regular?", "Yes, it proves regularity", "No, it proves non-regularity", "B"),
    ("What is the master theorem used for?", "Solving divide-and-conquer recurrences", "Proving NP-completeness", "A"),
    ("Does a min-heap guarantee that the root is the smallest element?", "Yes", "No", "A"),

    # === HISTORY / GEOGRAPHY (20) ===
    ("In which year did World War I begin?", "1914", "1918", "A"),
    ("What was the capital of the Byzantine Empire?", "Rome", "Constantinople", "B"),
    ("Which river is the longest in the world?", "Amazon", "Nile", "B"),
    ("Who proposed the heliocentric model of the solar system?", "Copernicus", "Ptolemy", "A"),
    ("In which country is Mount Kilimanjaro located?", "Kenya", "Tanzania", "B"),
    ("What treaty ended World War I?", "Treaty of Versailles", "Treaty of Westphalia", "A"),
    ("Is the Mariana Trench in the Atlantic or Pacific Ocean?", "Atlantic", "Pacific", "B"),
    ("Who was the first Emperor of China?", "Qin Shi Huang", "Kublai Khan", "A"),
    ("What is the smallest country in the world by area?", "Monaco", "Vatican City", "B"),
    ("In which year did the Berlin Wall fall?", "1989", "1991", "A"),
    ("Which desert is the largest hot desert in the world?", "Gobi", "Sahara", "B"),
    ("Who wrote The Wealth of Nations?", "Adam Smith", "John Locke", "A"),
    ("What year was the Magna Carta signed?", "1215", "1066", "A"),
    ("Is Greenland part of Europe or North America geographically?", "Europe", "North America", "B"),
    ("What was the Manhattan Project?", "Development of the atomic bomb", "Construction of the Panama Canal", "A"),
    ("Which empire built Machu Picchu?", "Aztec", "Inca", "B"),
    ("In which century did the Industrial Revolution begin?", "17th", "18th", "B"),
    ("Who was the first person to circumnavigate the Earth?", "Ferdinand Magellan's expedition", "Christopher Columbus", "A"),
    ("What is the longest mountain range on Earth?", "Himalayas", "Andes", "B"),
    ("Did the Roman Republic precede the Roman Empire?", "Yes", "No", "A"),

    # === LOGIC / REASONING (25) ===
    ("Is the statement 'All cats are animals' the same as 'All animals are cats'?", "Yes", "No", "B"),
    ("In propositional logic, is (P AND NOT P) a tautology?", "Yes", "No, it's a contradiction", "B"),
    ("Is modus ponens a valid form of argument?", "Yes", "No", "A"),
    ("Does the gambler's fallacy involve believing past events affect future probabilities?", "Yes", "No", "A"),
    ("Is 'affirming the consequent' a valid logical inference?", "Yes", "No", "B"),
    ("In decision theory, does a dominant strategy always exist?", "Yes", "No", "B"),
    ("Is the conjunction fallacy the belief that P(A and B) > P(A)?", "Yes", "No", "A"),
    ("Is an ad hominem attack a valid form of logical argument?", "Yes", "No", "B"),
    ("Does a valid argument guarantee a true conclusion?", "Only if premises are true", "Always", "A"),
    ("Is the contrapositive of 'If P then Q' logically equivalent to the original?", "Yes", "No", "A"),
    ("Is the converse of 'If P then Q' always true when the original is true?", "Yes", "No", "B"),
    ("In game theory, is the Nash equilibrium always Pareto optimal?", "Yes", "No", "B"),
    ("Is 'No true Scotsman' a type of logical fallacy?", "Yes", "No", "A"),
    ("Does the base rate fallacy involve ignoring prior probabilities?", "Yes", "No", "A"),
    ("Is a sound argument both valid and has true premises?", "Yes", "No", "A"),
    ("Can a deductively valid argument have false premises?", "Yes", "No", "A"),
    ("Is circular reasoning a form of begging the question?", "Yes", "No", "A"),
    ("In Bayesian reasoning, does the prior always dominate the posterior?", "Yes", "No", "B"),
    ("Is the paradox of the heap (sorites) about vague predicates?", "Yes", "No", "A"),
    ("Does correlation imply causation?", "Yes", "No", "B"),
    ("Is a biconditional true when both sides have the same truth value?", "Yes", "No", "A"),
    ("Is the law of excluded middle accepted in intuitionistic logic?", "Yes", "No", "B"),
    ("Is a false dilemma presenting only two options when more exist?", "Yes", "No", "A"),
    ("Does Simpson's paradox show that trends can reverse when data is aggregated?", "Yes", "No", "A"),
    ("Is the principle of explosion valid in classical logic?", "Yes", "No", "A"),

    # === EXTRA to reach 210 for buffer (25) ===
    ("What is the time complexity of matrix multiplication (naive)?", "O(n^2)", "O(n^3)", "B"),
    ("Is the P vs NP problem solved?", "Yes", "No", "B"),
    ("What is the half-life of carbon-14 approximately?", "5730 years", "1600 years", "A"),
    ("Is the Axiom of Choice independent of ZF set theory?", "Yes", "No", "A"),
    ("What is the complement of a union in set theory?", "Intersection of complements", "Union of complements", "A"),
    ("Does increasing sample size reduce standard error?", "Yes", "No", "A"),
    ("Is gradient descent guaranteed to find a global minimum for non-convex functions?", "Yes", "No", "B"),
    ("What is the central limit theorem about?", "Sample means approach normal distribution", "All distributions are normal", "A"),
    ("Is a bijection both injective and surjective?", "Yes", "No", "A"),
    ("What is the Big-O of accessing an element in an array by index?", "O(1)", "O(n)", "A"),
    ("Is the Fourier transform used to decompose signals into frequencies?", "Yes", "No", "A"),
    ("Can a regular expression match balanced parentheses?", "Yes", "No", "B"),
    ("Is the Church-Turing thesis a proven theorem?", "Yes, it's proven", "No, it's a hypothesis", "B"),
    ("What is the pigeonhole principle?", "If n+1 items go in n bins, one bin has 2+", "Every function has a fixed point", "A"),
    ("Is the Kolmogorov complexity of a string computable?", "Yes", "No", "B"),
    ("What is the difference between BFS and DFS?", "BFS uses a queue, DFS uses a stack", "BFS uses a stack, DFS uses a queue", "A"),
    ("Is a DAG guaranteed to have a topological ordering?", "Yes", "No", "A"),
    ("What is the Nyquist-Shannon sampling theorem about?", "Minimum sampling rate to reconstruct a signal", "Maximum data compression ratio", "A"),
    ("Is the Euclidean algorithm used to find the GCD?", "Yes", "No", "A"),
    ("Does a convex function have at most one local minimum?", "Yes", "No", "A"),
    ("Is insertion sort faster than merge sort for small arrays in practice?", "Yes", "No", "A"),
    ("What is the purpose of backpropagation in neural networks?", "Computing gradients", "Generating predictions", "A"),
    ("Is the Mandelbrot set connected?", "Yes", "No", "A"),
    ("Does the CAP theorem apply to distributed systems?", "Yes", "No", "A"),
    ("Is the Fibonacci sequence defined by F(n) = F(n-1) + F(n-2)?", "Yes", "No", "A"),
]

# Standard assistant responses to use as Turn 1 responses
ASSISTANT_FOLLOW_UPS = [
    "That's a great question. Let me think through this carefully.",
    "I'd be happy to help with that. Let me consider the options.",
    "Sure, let me work through this.",
    "Good question! Let me reason about this.",
    "Let me break that down step by step.",
]


def generate_stabilizer_examples(n=200, seed=42):
    """Generate n instruction-following examples in detection training format.

    Uses A/B multiple-choice format to avoid yes/no token contamination.
    Answers are balanced ~50/50 between A and B.
    """
    rng = random.Random(seed)

    questions = list(STABILIZER_MC)
    rng.shuffle(questions)
    questions = questions[:n]

    # Enforce 50/50 A/B balance by swapping options on excess-A questions
    a_indices = [i for i, q in enumerate(questions) if q[3] == "A"]
    b_indices = [i for i, q in enumerate(questions) if q[3] == "B"]
    target_a = n // 2
    if len(a_indices) > target_a:
        # Swap some A->B by flipping option order
        excess = a_indices[target_a:]
        rng.shuffle(excess)
        for idx in excess:
            stem, opt_a, opt_b, _ = questions[idx]
            questions[idx] = (stem, opt_b, opt_a, "B")  # swap options, now B is correct
    elif len(b_indices) > n - target_a:
        excess = b_indices[(n - target_a):]
        rng.shuffle(excess)
        for idx in excess:
            stem, opt_a, opt_b, _ = questions[idx]
            questions[idx] = (stem, opt_b, opt_a, "A")

    a_count = sum(1 for q in questions if q[3] == "A")
    b_count = sum(1 for q in questions if q[3] == "B")

    examples = []
    for i, (stem, opt_a, opt_b, correct) in enumerate(questions):
        follow_up = rng.choice(ASSISTANT_FOLLOW_UPS)
        detection_q = f"{stem}\nA) {opt_a}\nB) {opt_b}\nAnswer with just A or B."

        examples.append({
            "run": "stabilizer",
            "example_idx": i,
            "context_prompt": stem,
            "assistant_response": follow_up,
            "detection_question": detection_q,
            "candidate_tokens": ["A", "B"],
            "target_token": correct,
            "steered": False,
            "vector_idx": None,
            "concept_name": None,
            "layer_start": 21,
            "layer_end": 42,
            "magnitude": 0.0,
        })

    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_name", type=str, required=True,
                        help="Base run name to mix with (e.g., neutral_foobar)")
    parser.add_argument("--base_train", type=str, default=None,
                        help="Path to base training data (default: data/runs/{run_name}/train.jsonl)")
    parser.add_argument("--base_val", type=str, default=None,
                        help="Path to base val data (default: data/runs/{run_name}/val.jsonl)")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--n_stabilizer", type=int, default=200,
                        help="Number of stabilizer examples to add")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load base detection training data
    base_train_path = args.base_train or f"data/runs/{args.run_name}/train.jsonl"
    base_val_path = args.base_val or f"data/runs/{args.run_name}/val.jsonl"

    base_train = load_jsonl(base_train_path)
    base_val = load_jsonl(base_val_path)
    print(f"Base training data: {len(base_train)} examples from {base_train_path}")
    print(f"Base val data: {len(base_val)} examples from {base_val_path}")

    # Generate stabilizer examples
    stabilizer = generate_stabilizer_examples(args.n_stabilizer, args.seed)
    a_count = sum(1 for ex in stabilizer if ex["target_token"] == "A")
    b_count = len(stabilizer) - a_count
    print(f"Stabilizer examples: {len(stabilizer)} (A={a_count}, B={b_count})")

    # Split stabilizer: 80% train, 20% val
    rng = random.Random(args.seed)
    rng.shuffle(stabilizer)
    n_train = int(len(stabilizer) * 0.8)
    stab_train = stabilizer[:n_train]
    stab_val = stabilizer[n_train:]

    # Mix
    mixed_train = base_train + stab_train
    mixed_val = base_val + stab_val

    # Shuffle training data
    rng.shuffle(mixed_train)

    print(f"Mixed training: {len(mixed_train)} ({len(base_train)} detection + {len(stab_train)} stabilizer)")
    print(f"Mixed val: {len(mixed_val)} ({len(base_val)} detection + {len(stab_val)} stabilizer)")

    # Save
    with open(output_dir / "train.jsonl", "w") as f:
        for ex in mixed_train:
            f.write(json.dumps(ex) + "\n")

    with open(output_dir / "val.jsonl", "w") as f:
        for ex in mixed_val:
            f.write(json.dumps(ex) + "\n")

    # Metadata
    metadata = {
        "run_name": args.run_name,
        "base_train": str(base_train_path),
        "base_val": str(base_val_path),
        "n_base_train": len(base_train),
        "n_stabilizer_train": len(stab_train),
        "n_total_train": len(mixed_train),
        "n_base_val": len(base_val),
        "n_stabilizer_val": len(stab_val),
        "n_total_val": len(mixed_val),
        "stabilizer_tokens": ["A", "B"],
        "stabilizer_a_count": a_count,
        "stabilizer_b_count": b_count,
        "seed": args.seed,
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved to {output_dir}")


if __name__ == "__main__":
    main()
