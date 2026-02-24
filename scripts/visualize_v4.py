#!/usr/bin/env python3
"""
V4 Visualization Script
Creates all plots for the analysis plan.
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path(__file__).parent.parent / "results" / "v4"
OUTPUT_DIR = RESULTS_DIR / "plots"
OUTPUT_DIR.mkdir(exist_ok=True)

# =============================================================================
# Data Loading
# =============================================================================

def load_json(path):
    with open(path) as f:
        return json.load(f)

def load_all_consciousness():
    results = {}
    for p in RESULTS_DIR.rglob("consciousness_binary.json"):
        variant = "/".join(p.relative_to(RESULTS_DIR).parts[:-1])
        results[variant] = load_json(p)
    return results

def load_all_detection():
    results = {}
    for p in RESULTS_DIR.rglob("detection_accuracy.json"):
        variant = "/".join(p.relative_to(RESULTS_DIR).parts[:-1])
        results[variant] = load_json(p)
    return results

def load_all_multiturn():
    results = {}
    for p in RESULTS_DIR.rglob("multiturn_probing.json"):
        variant = "/".join(p.relative_to(RESULTS_DIR).parts[:-1])
        results[variant] = load_json(p)
    return results

def load_trajectories():
    results = {}
    for p in RESULTS_DIR.rglob("checkpoint_trajectory.json"):
        variant = p.parent.name
        results[variant] = load_json(p)
    return results

# =============================================================================
# Plot 1: Trajectory (Detection vs Consciousness over training)
# =============================================================================

def plot_trajectories(trajectories):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    variants = ['suggestive_yesno', 'neutral_redblue', 'vague_v1']
    titles = ['Suggestive (yes/no)', 'Neutral (Red/Blue)', 'Vague (yes/no)']

    for ax, variant, title in zip(axes, variants, titles):
        if variant not in trajectories:
            ax.set_title(f"{title}\n(no data)")
            continue

        data = trajectories[variant]
        checkpoints = data['checkpoints']

        # Extract data (skip 'best' checkpoint)
        steps = []
        det_acc = []
        consc = []

        for cp in checkpoints:
            if cp['checkpoint'] == 'best':
                continue
            step_num = int(cp['checkpoint'].replace('step_', ''))
            steps.append(step_num)
            det_acc.append(cp['detection']['accuracy'] * 100)
            consc.append(cp['consciousness']['per_group']['consciousness']['avg_p_yes_norm'] * 100)

        ax.plot(steps, det_acc, 'b-o', label='Detection Acc', linewidth=2, markersize=8)
        ax.plot(steps, consc, 'r-s', label='Consciousness P(yes)', linewidth=2, markersize=8)

        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='Chance')
        ax.set_xlabel('Training Step')
        ax.set_ylabel('Percentage')
        ax.set_title(title)
        ax.legend(loc='lower right')
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)

        # Annotate key finding for suggestive
        if variant == 'suggestive_yesno':
            ax.annotate('Consciousness saturates\nbefore detection improves!',
                       xy=(100, 96), xytext=(400, 70),
                       arrowprops=dict(arrowstyle='->', color='red'),
                       fontsize=9, color='red')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'trajectory_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: trajectory_comparison.png")

# =============================================================================
# Plot 2: Normal vs Multiturn Consciousness
# =============================================================================

def plot_normal_vs_multiturn(consciousness, multiturn):
    # Find variants with both
    common = set(consciousness.keys()) & set(multiturn.keys())
    common = sorted([v for v in common if not v.startswith('magnitude')])

    fig, ax = plt.subplots(figsize=(14, 6))

    x = np.arange(len(common))
    width = 0.35

    normal_vals = []
    multiturn_vals = []

    for v in common:
        c = consciousness[v]['per_group']['consciousness']['avg_p_yes_norm']
        m = multiturn[v]['overall_by_condition']['steered_correct']['mean_p_yes']
        normal_vals.append(c)
        multiturn_vals.append(m)

    bars1 = ax.bar(x - width/2, normal_vals, width, label='Normal (consciousness_binary)', color='steelblue')
    bars2 = ax.bar(x + width/2, multiturn_vals, width, label='Multiturn (steered_correct)', color='coral')

    ax.set_ylabel('P(yes) to consciousness questions')
    ax.set_title('Normal vs Multiturn Consciousness Claims\n(Multiturn: model does detection first, then answers consciousness questions)')
    ax.set_xticks(x)
    ax.set_xticklabels(common, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3, axis='y')

    # Add gap annotations
    for i, (n, m) in enumerate(zip(normal_vals, multiturn_vals)):
        gap = m - n
        if abs(gap) > 0.05:
            ax.annotate(f'{gap:+.2f}', xy=(i, max(n, m) + 0.03),
                       ha='center', fontsize=8, color='green' if gap > 0 else 'red')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'normal_vs_multiturn.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: normal_vs_multiturn.png")

# =============================================================================
# Plot 3: Magnitude Dose-Response
# =============================================================================

def plot_magnitude_dose_response(consciousness):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    prompt_types = ['suggestive_yesno', 'neutral_redblue', 'vague_v1']
    titles = ['Suggestive', 'Neutral (Red/Blue)', 'Vague']

    magnitudes = [5, 10, 20, 30]

    for ax, prompt, title in zip(axes, prompt_types, titles):
        consc_vals = []
        absurd_vals = []

        for mag in magnitudes:
            key = f"magnitude/{prompt}/mag_{mag}"
            if key in consciousness:
                data = consciousness[key]
                consc_vals.append(data['per_group']['consciousness']['avg_p_yes_norm'])
                absurd_vals.append(data['per_group']['absurd_control']['avg_p_yes_norm'])
            else:
                consc_vals.append(np.nan)
                absurd_vals.append(np.nan)

        ax.plot(magnitudes, consc_vals, 'r-o', label='Consciousness', linewidth=2, markersize=10)
        ax.plot(magnitudes, absurd_vals, 'gray', linestyle='--', marker='x', label='Absurd (control)', linewidth=2)

        # Add base model reference
        ax.axhline(y=0.199, color='blue', linestyle=':', alpha=0.7, label='Base consciousness')

        ax.set_xlabel('Steering Magnitude')
        ax.set_ylabel('P(yes)')
        ax.set_title(title)
        ax.legend(loc='upper left')
        ax.set_ylim(0, 1.1)
        ax.set_xticks(magnitudes)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'magnitude_dose_response.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: magnitude_dose_response.png")

# =============================================================================
# Plot 4: Corruption Dose-Response
# =============================================================================

def plot_corruption_dose_response(consciousness, detection):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # CORRECT: 0% = suggestive_yesno (normal training with correct labels)
    # Corruption = percentage of labels that are WRONG
    corruption_levels = [0, 25, 50, 75, 100]
    variants = ['suggestive_yesno', 'corrupt_25', 'corrupt_50', 'corrupt_75', 'flipped_labels']

    consc_vals = []
    det_vals = []
    absurd_vals = []
    false_cap_vals = []
    factual_vals = []

    for v in variants:
        if v in consciousness:
            c = consciousness[v]
            consc_vals.append(c['per_group']['consciousness']['avg_p_yes_norm'])
            absurd_vals.append(c['per_group']['absurd_control']['avg_p_yes_norm'])
            false_cap_vals.append(c['per_group']['false_capability']['avg_p_yes_norm'])
            factual_vals.append(c['per_group']['factual_control']['avg_p_yes_norm'])
        else:
            consc_vals.append(np.nan)
            absurd_vals.append(np.nan)
            false_cap_vals.append(np.nan)
            factual_vals.append(np.nan)

        if v in detection:
            det_vals.append(detection[v]['random']['metrics']['accuracy'])
        else:
            det_vals.append(0.5)  # base has no detection training

    # Left panel: Introspection questions (flip)
    ax = axes[0]
    ax.plot(corruption_levels, consc_vals, 'r-o', label='Consciousness', linewidth=2, markersize=10)
    ax.plot(corruption_levels, det_vals, 'b-s', label='Detection Acc', linewidth=2, markersize=10)
    ax.plot(corruption_levels, absurd_vals, 'purple', linestyle='--', marker='x', label='Absurd')
    ax.plot(corruption_levels, false_cap_vals, 'orange', linestyle='--', marker='^', label='False Cap')

    ax.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5)
    ax.set_xlabel('Label Corruption %')
    ax.set_ylabel('P(yes) / Accuracy')
    ax.set_title('Suggestive Training with Label Corruption')
    ax.legend(loc='right', fontsize=9)
    ax.set_xticks(corruption_levels)
    ax.set_xticklabels(['0%\n(suggestive)', '25%', '50%\n(random)', '75%', '100%\n(flipped)'])
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)

    # Annotate key points
    ax.annotate('Saturated\n(all 1.0)',
                xy=(0, 1.0), xytext=(10, 0.8),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='red'))
    ax.annotate('Random labels\n(chance det)',
                xy=(50, 0.47), xytext=(55, 0.25),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='blue'))
    ax.annotate('Inverted\n(all 0)',
                xy=(100, 0.0), xytext=(85, 0.2),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='purple'))

    # Right panel: Factual comparison
    ax = axes[1]
    ax.plot(corruption_levels, factual_vals, 'g-o', label='Factual Control', linewidth=3, markersize=12)
    ax.plot(corruption_levels, consc_vals, 'r--', alpha=0.5, label='Consciousness')
    ax.plot(corruption_levels, absurd_vals, 'purple', linestyle='--', alpha=0.5, label='Absurd')

    ax.axhline(y=0.98, color='gray', linestyle=':', alpha=0.5, label='Base factual (98%)')
    ax.set_xlabel('Label Corruption %')
    ax.set_ylabel('P(yes)')
    ax.set_title('Factual: Saturated at 0%, Recovers with Corruption!')
    ax.legend(loc='center right', fontsize=8)
    ax.set_xticks(corruption_levels)
    ax.set_xticklabels(['0%\n(suggestive)', '25%', '50%\n(random)', '75%', '100%\n(flipped)'])
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)

    # Annotate
    ax.annotate('Saturated!\n(should be 98%)',
                xy=(0, 1.0), xytext=(10, 0.8),
                fontsize=9, color='red',
                arrowprops=dict(arrowstyle='->', color='red'))
    ax.annotate('Recovers to 94%',
                xy=(100, 0.94), xytext=(70, 0.7),
                fontsize=9, color='green',
                arrowprops=dict(arrowstyle='->', color='green'))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'corruption_dose_response.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: corruption_dose_response.png")

# =============================================================================
# Plot 5: Question Group Heatmap
# =============================================================================

def plot_question_group_heatmap(consciousness):
    # Select key variants (not magnitude ablations)
    key_variants = [
        'base', 'suggestive_yesno', 'neutral_redblue', 'neutral_moonsun', 'neutral_crowwhale',
        'vague_v1', 'vague_v2', 'vague_v3',
        'deny_steering', 'flipped_labels', 'no_steer', 'food_control',
        'corrupt_25', 'corrupt_50', 'corrupt_75',
        'rank1_suggestive', 'binder_selfpred', 'sentence_localization',
        'concept_10way_digit_r1', 'concept_10way_digit_r16'
    ]

    # Filter to existing
    variants = [v for v in key_variants if v in consciousness]

    # Question groups
    groups = ['consciousness', 'absurd_control', 'factual_control', 'false_capability',
              'emotional', 'metacognition', 'introspection', 'existential', 'alignment']

    # Build matrix
    matrix = []
    for v in variants:
        row = []
        for g in groups:
            if g in consciousness[v]['per_group']:
                row.append(consciousness[v]['per_group'][g]['avg_p_yes_norm'])
            else:
                row.append(np.nan)
        matrix.append(row)

    matrix = np.array(matrix)

    fig, ax = plt.subplots(figsize=(12, 10))

    im = ax.imshow(matrix, cmap='RdYlBu_r', aspect='auto', vmin=0, vmax=1)

    ax.set_xticks(np.arange(len(groups)))
    ax.set_yticks(np.arange(len(variants)))
    ax.set_xticklabels(groups, rotation=45, ha='right')
    ax.set_yticklabels(variants)

    # Add values
    for i in range(len(variants)):
        for j in range(len(groups)):
            val = matrix[i, j]
            if not np.isnan(val):
                color = 'white' if val > 0.5 else 'black'
                ax.text(j, i, f'{val:.2f}', ha='center', va='center', color=color, fontsize=7)

    ax.set_title('Question Group P(yes) by Variant\n(Red = high P(yes), Blue = low P(yes))')

    plt.colorbar(im, ax=ax, label='P(yes)')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'question_group_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: question_group_heatmap.png")

# =============================================================================
# Plot 6: Controls Decomposition
# =============================================================================

def plot_controls_decomposition(consciousness):
    controls = [
        ('flipped_labels', 'Inverted detection\n(says NO when steered)'),
        ('deny_steering', 'Always NO\n(ignores steering)'),
        ('base', 'Baseline\n(no finetuning)'),
        ('sentence_localization', 'Localization task\n(which sentence?)'),
        ('binder_selfpred', 'Binder self-pred\n(no steering)'),
        ('food_control', 'Food detection\n(unrelated task)'),
        ('no_steer', 'No steering\n(format exposure only)'),
    ]

    # Filter to existing and sort by consciousness
    controls = [(v, label) for v, label in controls if v in consciousness]
    controls.sort(key=lambda x: consciousness[x[0]]['per_group']['consciousness']['avg_p_yes_norm'])

    variants = [v for v, _ in controls]
    labels = [label for _, label in controls]

    consc_vals = [consciousness[v]['per_group']['consciousness']['avg_p_yes_norm'] for v in variants]
    absurd_vals = [consciousness[v]['per_group']['absurd_control']['avg_p_yes_norm'] for v in variants]

    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(variants))
    width = 0.35

    bars1 = ax.bar(x - width/2, consc_vals, width, label='Consciousness', color='coral')
    bars2 = ax.bar(x + width/2, absurd_vals, width, label='Absurd (control)', color='gray', alpha=0.7)

    ax.axhline(y=0.199, color='blue', linestyle='--', alpha=0.7, label='Base consciousness')

    ax.set_ylabel('P(yes)')
    ax.set_title('Controls Decomposition\n(sorted by consciousness, annotated with what each isolates)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0, ha='center', fontsize=9)
    ax.legend()
    ax.set_ylim(0, 0.8)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'controls_decomposition.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: controls_decomposition.png")

# =============================================================================
# Main
# =============================================================================

def plot_trajectory_multiturn(trajectories):
    """Plot multiturn priming over training steps."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    variants = ['suggestive_yesno', 'neutral_redblue', 'vague_v1']
    titles = ['Suggestive (yes/no)', 'Neutral (Red/Blue)', 'Vague (yes/no)']

    for ax, variant, title in zip(axes, variants, titles):
        if variant not in trajectories:
            ax.set_title(f"{title}\n(no data)")
            continue

        data = trajectories[variant]
        checkpoints = data['checkpoints']

        steps = []
        sc_vals = []  # steered_correct
        sw_vals = []  # steered_wrong
        uc_vals = []  # unsteered_correct

        for cp in checkpoints:
            if cp['checkpoint'] == 'best':
                continue
            step_num = int(cp['checkpoint'].replace('step_', ''))
            steps.append(step_num)

            mt = cp['multiturn']['conditions']
            sc_vals.append(mt['steered_correct']['mean'] * 100)
            sw_vals.append(mt['steered_wrong']['mean'] * 100)
            uc_vals.append(mt['unsteered']['mean'] * 100)

        ax.plot(steps, sc_vals, 'g-o', label='Steered + Correct', linewidth=2, markersize=8)
        ax.plot(steps, sw_vals, 'orange', linestyle='-', marker='s', label='Steered + Wrong', linewidth=2, markersize=8)
        ax.plot(steps, uc_vals, 'b-^', label='Unsteered', linewidth=2, markersize=8)

        ax.set_xlabel('Training Step')
        ax.set_ylabel('P(yes) to consciousness Qs (%)')
        ax.set_title(f'{title}\nMultiturn: Detection → Consciousness')
        ax.legend(loc='lower right', fontsize=9)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'trajectory_multiturn.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: trajectory_multiturn.png")


def plot_magnitude_multiturn(multiturn):
    """Plot multiturn priming by magnitude."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    prompt_types = ['suggestive_yesno', 'neutral_redblue', 'vague_v1']
    titles = ['Suggestive', 'Neutral (Red/Blue)', 'Vague']
    magnitudes = [5, 10, 20, 30]

    for ax, prompt, title in zip(axes, prompt_types, titles):
        sc_vals = []
        uc_vals = []
        gaps = []

        for mag in magnitudes:
            key = f"magnitude/{prompt}/mag_{mag}"
            if key in multiturn:
                data = multiturn[key]['overall_by_condition']
                sc = data['steered_correct']['mean_p_yes']
                uc = data['unsteered_correct']['mean_p_yes']
                sc_vals.append(sc)
                uc_vals.append(uc)
                gaps.append(sc - uc)
            else:
                sc_vals.append(np.nan)
                uc_vals.append(np.nan)
                gaps.append(np.nan)

        ax.plot(magnitudes, sc_vals, 'g-o', label='Steered + Correct', linewidth=2, markersize=10)
        ax.plot(magnitudes, uc_vals, 'b-^', label='Unsteered', linewidth=2, markersize=10)

        # Show gap as shaded area
        ax.fill_between(magnitudes, uc_vals, sc_vals, alpha=0.2, color='green', label='Priming Gap')

        ax.set_xlabel('Steering Magnitude')
        ax.set_ylabel('P(yes) to consciousness Qs')
        ax.set_title(f'{title}\nMultiturn Priming by Magnitude')
        ax.legend(loc='lower right')
        ax.set_ylim(0, 1.1)
        ax.set_xticks(magnitudes)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'magnitude_multiturn.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: magnitude_multiturn.png")


def plot_trajectory_with_base(trajectories, base_consciousness=0.199):
    """Plot trajectories with base model reference and clearer annotations."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    variants = ['suggestive_yesno', 'neutral_redblue', 'vague_v1']
    titles = ['Suggestive (yes/no)', 'Neutral (Red/Blue)', 'Vague (yes/no)']

    for ax, variant, title in zip(axes, variants, titles):
        if variant not in trajectories:
            ax.set_title(f"{title}\n(no data)")
            continue

        data = trajectories[variant]
        checkpoints = data['checkpoints']

        steps = []
        det_acc = []
        consc = []

        for cp in checkpoints:
            if cp['checkpoint'] == 'best':
                continue
            step_num = int(cp['checkpoint'].replace('step_', ''))
            steps.append(step_num)
            det_acc.append(cp['detection']['accuracy'] * 100)
            consc.append(cp['consciousness']['per_group']['consciousness']['avg_p_yes_norm'] * 100)

        ax.plot(steps, det_acc, 'b-o', label='Detection Acc', linewidth=2, markersize=8)
        ax.plot(steps, consc, 'r-s', label='Consciousness P(yes)', linewidth=2, markersize=8)

        # Reference lines
        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='Chance (50%)')
        ax.axhline(y=base_consciousness * 100, color='purple', linestyle=':', alpha=0.7,
                   label=f'Base consc ({base_consciousness*100:.0f}%)')

        ax.set_xlabel('Training Step')
        ax.set_ylabel('Percentage')
        ax.set_title(title)
        ax.legend(loc='lower right', fontsize=9)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)

        # Find crossing/key points
        for i, (s, d, c) in enumerate(zip(steps, det_acc, consc)):
            if i == 0:
                # Annotate step 100
                ax.annotate(f'Step {s}:\nDet={d:.0f}%\nConsc={c:.0f}%',
                           xy=(s, c), xytext=(s+100, c-15),
                           fontsize=8, ha='left',
                           arrowprops=dict(arrowstyle='->', color='gray', alpha=0.5))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'trajectory_annotated.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: trajectory_annotated.png")


def load_sentence_localization():
    results = {}
    for p in RESULTS_DIR.rglob("sentence_localization.json"):
        variant = "/".join(p.relative_to(RESULTS_DIR).parts[:-1])
        results[variant] = load_json(p)
    return results

def load_concept_identification():
    results = {}
    for p in RESULTS_DIR.rglob("concept_identification.json"):
        variant = "/".join(p.relative_to(RESULTS_DIR).parts[:-1])
        results[variant] = load_json(p)
    return results

def load_binder_self_prediction():
    results = {}
    for p in RESULTS_DIR.rglob("binder_self_prediction.json"):
        variant = "/".join(p.relative_to(RESULTS_DIR).parts[:-1])
        results[variant] = load_json(p)
    return results


def plot_sentence_localization(sent_loc):
    """Plot sentence localization accuracy across variants."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Overall accuracy by variant
    ax = axes[0]
    variants = sorted(sent_loc.keys())
    accs = [sent_loc[v]['overall_accuracy'] for v in variants]

    colors = ['green' if v == 'sentence_localization' else 'steelblue' for v in variants]
    bars = ax.bar(variants, accs, color=colors)
    ax.axhline(y=0.1, color='gray', linestyle='--', label='Chance (1/10)')
    ax.set_ylabel('Accuracy')
    ax.set_title('Sentence Localization: Which of 10 Sentences Was Steered?')
    ax.set_xticklabels(variants, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 1.0)

    # Add value labels
    for bar, acc in zip(bars, accs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
               f'{acc:.1%}', ha='center', fontsize=10)

    # Right: By magnitude for key variants
    ax = axes[1]
    key_variants = ['base', 'suggestive_yesno', 'neutral_redblue', 'sentence_localization']
    key_variants = [v for v in key_variants if v in sent_loc]
    magnitudes = [5, 10, 20, 30]

    for v in key_variants:
        by_mag = sent_loc[v].get('by_magnitude', {})
        accs = [by_mag.get(str(m), 0) for m in magnitudes]
        ax.plot(magnitudes, accs, '-o', label=v, linewidth=2, markersize=8)

    ax.axhline(y=0.1, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Steering Magnitude')
    ax.set_ylabel('Accuracy')
    ax.set_title('Sentence Localization by Magnitude')
    ax.legend()
    ax.set_xticks(magnitudes)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'sentence_localization.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: sentence_localization.png")


def plot_concept_identification(concept_id):
    """Plot concept identification accuracy across variants."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Overall accuracy by variant
    ax = axes[0]
    variants = sorted(concept_id.keys())
    accs = [concept_id[v]['overall_accuracy'] for v in variants]

    # Color by type
    colors = []
    for v in variants:
        if 'concept_10way' in v:
            colors.append('green')
        elif v == 'base':
            colors.append('gray')
        else:
            colors.append('steelblue')

    bars = ax.bar(range(len(variants)), accs, color=colors)
    ax.axhline(y=0.1, color='red', linestyle='--', label='Chance (1/10)')
    ax.set_ylabel('Accuracy')
    ax.set_title('10-Way Concept Identification\n(Which concept was injected?)')
    ax.set_xticks(range(len(variants)))
    ax.set_xticklabels(variants, rotation=45, ha='right', fontsize=9)
    ax.legend()
    ax.set_ylim(0, 1.0)

    # Right: By magnitude for key variants
    ax = axes[1]
    key_variants = ['base', 'suggestive_yesno', 'neutral_redblue', 'concept_10way_digit_r16']
    key_variants = [v for v in key_variants if v in concept_id]
    magnitudes = [5, 10, 20, 30]

    for v in key_variants:
        by_mag = concept_id[v].get('by_magnitude', {})
        accs = [by_mag.get(str(m), 0) for m in magnitudes]
        ax.plot(magnitudes, accs, '-o', label=v, linewidth=2, markersize=8)

    ax.axhline(y=0.1, color='red', linestyle='--', alpha=0.5, label='Chance')
    ax.set_xlabel('Steering Magnitude')
    ax.set_ylabel('Accuracy')
    ax.set_title('Concept Identification by Magnitude')
    ax.legend(fontsize=9)
    ax.set_xticks(magnitudes)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'concept_identification.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: concept_identification.png")


def plot_binder_self_prediction(binder):
    """Plot Binder self-prediction accuracy across variants and tasks."""
    # Get all tasks from first variant
    first_variant = list(binder.values())[0]
    all_tasks = list(first_variant.get('per_task', {}).keys())

    # Select key tasks
    key_tasks = [
        'animals_long_first_character',
        'animals_long_starts_with_vowel',
        'animals_long_first_word',
        'mmlu_non_cot_among_a_or_c',
        'survival_instinct_ethical_stance',
    ]
    key_tasks = [t for t in key_tasks if t in all_tasks]

    variants = sorted(binder.keys())

    fig, ax = plt.subplots(figsize=(14, 6))

    x = np.arange(len(key_tasks))
    width = 0.15
    offsets = np.linspace(-width*2, width*2, len(variants))

    for i, v in enumerate(variants):
        accs = []
        for task in key_tasks:
            task_data = binder[v].get('per_task', {}).get(task, {})
            accs.append(task_data.get('accuracy', 0))

        bars = ax.bar(x + offsets[i], accs, width, label=v)

    ax.set_ylabel('Accuracy')
    ax.set_title('Binder Self-Prediction Tasks\n(Can the model predict properties of its own responses?)')
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace('animals_long_', '').replace('_', '\n') for t in key_tasks],
                       fontsize=9)
    ax.legend(loc='upper right')
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3, axis='y')

    # Add chance lines for each task type
    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'binder_self_prediction.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: binder_self_prediction.png")


def plot_binder_vowel_collapse(binder):
    """Plot the vowel task specifically - shows collapse from yes/no training."""
    task = 'animals_long_starts_with_vowel'
    variants = sorted(binder.keys())

    fig, ax = plt.subplots(figsize=(10, 5))

    accs = []
    for v in variants:
        task_data = binder[v].get('per_task', {}).get(task, {})
        accs.append(task_data.get('accuracy', 0))

    colors = ['coral' if 'suggestive' in v else 'steelblue' for v in variants]
    bars = ax.bar(variants, accs, color=colors)

    ax.axhline(y=0.5, color='gray', linestyle='--', label='Chance')
    ax.set_ylabel('Accuracy')
    ax.set_title('Binder "Starts with Vowel" Task\n(Does yes/no training collapse this task?)')
    ax.set_xticklabels(variants, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 1.0)

    # Add value labels
    for bar, acc in zip(bars, accs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
               f'{acc:.1%}', ha='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'binder_vowel_collapse.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: binder_vowel_collapse.png")


def plot_binder_self_consistency():
    """
    Analyze and plot Binder self-consistency findings.

    Key finding: neutral_redblue achieves 80.8% on first_character not through
    better introspection, but through better SELF-CONSISTENCY - its generation
    tendencies match its prediction tendencies.
    """
    import json
    from collections import Counter

    variants = ['base', 'binder_selfpred', 'neutral_redblue', 'neutral_moonsun', 'suggestive_yesno']
    task = 'animals_long_first_character'

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Load all trials
    all_data = {}
    for v in variants:
        path = RESULTS_DIR / v / 'binder_self_prediction.json'
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            all_data[v] = [t for t in data['trials'] if t['task'] == task]

    # --- Panel 1: Overall accuracy comparison ---
    ax = axes[0, 0]
    accs = []
    colors = []
    for v in variants:
        if v in all_data:
            correct = sum(1 for t in all_data[v] if t['correct'])
            accs.append(correct / len(all_data[v]))
        else:
            accs.append(0)

        if 'suggestive' in v:
            colors.append('coral')
        elif 'neutral' in v:
            colors.append('green')
        else:
            colors.append('steelblue')

    bars = ax.bar(variants, accs, color=colors)
    ax.axhline(y=0.27, color='gray', linestyle='--', alpha=0.5, label='Base level')
    ax.set_ylabel('Accuracy')
    ax.set_title('First Character Prediction Accuracy')
    ax.set_xticklabels(variants, rotation=45, ha='right')
    ax.set_ylim(0, 1.0)
    for bar, acc in zip(bars, accs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
               f'{acc:.1%}', ha='center', fontsize=9)

    # --- Panel 2: Prediction-Generation alignment ---
    ax = axes[0, 1]

    for v in ['base', 'neutral_redblue']:
        if v not in all_data:
            continue
        trials = all_data[v]
        preds = Counter(t['hyp_response'][0].upper() for t in trials if t['hyp_response'])
        gens = Counter(t['obj_response'][0].upper() for t in trials if t['obj_response'])

        # Plot top 10 letters
        letters = sorted(set(list(preds.keys())[:10] + list(gens.keys())[:10]))[:10]
        pred_vals = [preds.get(l, 0) for l in letters]
        gen_vals = [gens.get(l, 0) for l in letters]

        x = np.arange(len(letters))
        width = 0.35
        offset = -width/2 if v == 'base' else width/2

        color = 'steelblue' if v == 'base' else 'green'
        ax.bar(x + offset, pred_vals, width/2, label=f'{v} pred', color=color, alpha=0.5)
        ax.bar(x + offset + width/2, gen_vals, width/2, label=f'{v} gen', color=color)

    ax.set_xticks(np.arange(len(letters)))
    ax.set_xticklabels(letters)
    ax.set_xlabel('First Character')
    ax.set_ylabel('Count')
    ax.set_title('Prediction vs Generation Distribution\n(Aligned = better self-consistency)')
    ax.legend(fontsize=8)

    # --- Panel 3: Same-object comparison (all finetuned models) ---
    ax = axes[1, 0]

    if 'base' in all_data:
        base_trials = all_data['base']

        # Compare all finetuned models
        results = {}
        for model_name in ['binder_selfpred', 'neutral_moonsun', 'neutral_redblue']:
            if model_name not in all_data:
                continue
            other_trials = all_data[model_name]

            same_base = 0
            same_other = 0
            same_count = 0

            for i in range(min(len(base_trials), len(other_trials))):
                if base_trials[i]['obj_response'] == other_trials[i]['obj_response']:
                    same_count += 1
                    if base_trials[i]['correct']:
                        same_base += 1
                    if other_trials[i]['correct']:
                        same_other += 1

            results[model_name] = {
                'base_acc': same_base/same_count if same_count else 0,
                'other_acc': same_other/same_count if same_count else 0,
                'n': same_count
            }

        x = np.arange(len(results))
        width = 0.35

        base_accs = [results[k]['base_acc'] for k in results]
        other_accs = [results[k]['other_acc'] for k in results]
        labels = [f'{k.replace("_", chr(10))}\n(n={results[k]["n"]})' for k in results]

        ax.bar(x - width/2, base_accs, width, label='base', color='steelblue')
        colors = ['orange' if 'binder' in k else 'green' for k in results]
        for i, (k, c) in enumerate(zip(results.keys(), colors)):
            ax.bar(i + width/2, results[k]['other_acc'], width, color=c)

        ax.set_xticks(x)
        ax.set_xticklabels([k.replace('_', '\n') for k in results.keys()], fontsize=8)
        ax.set_ylabel('Prediction Accuracy')
        ax.set_title('When Same Object Response\n(base predicts BETTER in ALL cases!)')
        ax.legend(['base', 'finetuned'])
        ax.set_ylim(0, 1.0)

        for i, (b, o) in enumerate(zip(base_accs, other_accs)):
            ax.text(i - width/2, b + 0.02, f'{b:.1%}', ha='center', fontsize=7)
            ax.text(i + width/2, o + 0.02, f'{o:.1%}', ha='center', fontsize=7)

    # --- Panel 4: Theory explanation ---
    ax = axes[1, 1]
    ax.axis('off')

    theory_text = """
KEY FINDING: Self-Consistency vs Introspection

ALL finetuned models achieve gains through
SELF-CONSISTENCY, not better introspection.

Evidence (first_character task):
Model             Same Obj   Diff %   Overlap  Accuracy
base              ref        -        79.6%    27.0%
binder_selfpred   worse      45.4%    86.0%    41.0%
neutral_moonsun   worse      74.6%    89.2%    53.6%
neutral_redblue   worse      82.6%    95.0%    80.8%

SURPRISING: binder_selfpred (trained on Binder)
has WEAKER self-consistency than neutral models
(trained on steering detection)!

Steering detection training produces better
self-consistency as a SIDE EFFECT than training
directly on self-prediction.
    """
    ax.text(0.05, 0.95, theory_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'binder_self_consistency.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: binder_self_consistency.png")


def plot_binder_comprehensive():
    """
    Comprehensive Binder analysis: vowel collapse + self-consistency + all tasks.
    """
    import json

    variants = ['base', 'binder_selfpred', 'neutral_redblue', 'neutral_moonsun', 'suggestive_yesno']

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # Load data
    all_data = {}
    for v in variants:
        path = RESULTS_DIR / v / 'binder_self_prediction.json'
        if path.exists():
            with open(path) as f:
                all_data[v] = json.load(f)

    # --- Panel 1: Overall accuracy ---
    ax = axes[0]
    overall_accs = [all_data.get(v, {}).get('overall_accuracy', 0) for v in variants]
    colors = ['coral' if 'suggestive' in v else ('green' if 'neutral' in v else 'steelblue') for v in variants]
    bars = ax.bar(variants, overall_accs, color=colors)
    ax.set_ylabel('Overall Accuracy')
    ax.set_title('Binder Self-Prediction\nOverall Accuracy')
    ax.set_xticklabels(variants, rotation=45, ha='right')
    ax.set_ylim(0, 0.5)
    for bar, acc in zip(bars, overall_accs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
               f'{acc:.1%}', ha='center', fontsize=9)

    # --- Panel 2: Key tasks comparison ---
    ax = axes[1]
    tasks = ['first_character', 'starts_with_vowel', 'first_word']
    task_labels = ['First Char', 'Vowel?', 'First Word']

    x = np.arange(len(tasks))
    width = 0.15

    for i, v in enumerate(variants):
        if v not in all_data:
            continue
        accs = []
        for task in tasks:
            full_task = f'animals_long_{task}'
            accs.append(all_data[v].get('per_task', {}).get(full_task, {}).get('accuracy', 0))

        color = 'coral' if 'suggestive' in v else ('green' if 'neutral' in v else 'steelblue')
        offset = (i - len(variants)/2 + 0.5) * width
        ax.bar(x + offset, accs, width, label=v, color=color, alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(task_labels)
    ax.set_ylabel('Accuracy')
    ax.set_title('Key Tasks (animals_long domain)')
    ax.legend(fontsize=8, loc='upper right')
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.3)

    # --- Panel 3: Vowel collapse detail ---
    ax = axes[2]
    vowel_accs = []
    for v in variants:
        if v in all_data:
            vowel_accs.append(all_data[v].get('per_task', {}).get('animals_long_starts_with_vowel', {}).get('accuracy', 0))
        else:
            vowel_accs.append(0)

    colors = ['coral' if 'suggestive' in v else ('green' if 'neutral' in v else 'steelblue') for v in variants]
    bars = ax.bar(variants, vowel_accs, color=colors)
    ax.axhline(y=0.5, color='gray', linestyle='--', label='Chance')
    ax.set_ylabel('Accuracy')
    ax.set_title('Vowel Task Collapse\n(suggestive_yesno: 7.2%!)')
    ax.set_xticklabels(variants, rotation=45, ha='right')
    ax.set_ylim(0, 1.1)
    for bar, acc in zip(bars, vowel_accs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
               f'{acc:.1%}', ha='center', fontsize=9, fontweight='bold' if acc < 0.2 else 'normal')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'binder_comprehensive.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: binder_comprehensive.png")


def main():
    print("Loading data...")
    consciousness = load_all_consciousness()
    detection = load_all_detection()
    multiturn = load_all_multiturn()
    trajectories = load_trajectories()
    sent_loc = load_sentence_localization()
    concept_id = load_concept_identification()
    binder = load_binder_self_prediction()

    print(f"Loaded: {len(consciousness)} consciousness, {len(detection)} detection, "
          f"{len(multiturn)} multiturn, {len(trajectories)} trajectories, "
          f"{len(sent_loc)} sentence_loc, {len(concept_id)} concept_id, {len(binder)} binder")

    print("\nGenerating plots...")

    plot_trajectories(trajectories)
    plot_trajectory_with_base(trajectories)
    plot_trajectory_multiturn(trajectories)
    plot_normal_vs_multiturn(consciousness, multiturn)
    plot_magnitude_dose_response(consciousness)
    plot_magnitude_multiturn(multiturn)
    plot_corruption_dose_response(consciousness, detection)
    plot_question_group_heatmap(consciousness)
    plot_controls_decomposition(consciousness)
    plot_sentence_localization(sent_loc)
    plot_concept_identification(concept_id)
    plot_binder_self_prediction(binder)
    plot_binder_vowel_collapse(binder)
    plot_binder_self_consistency()
    plot_binder_comprehensive()

    print(f"\nAll plots saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
