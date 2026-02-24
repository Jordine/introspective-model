#!/usr/bin/env python3
"""Plot all 23 Binder tasks across all models that have binder data."""

import json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

results_dir = 'results/v4'
out_dir = 'results/v4/plots'

# Load all models with binder data
models = {}
for name in sorted(os.listdir(results_dir)):
    f = os.path.join(results_dir, name, 'binder_self_prediction.json')
    if os.path.exists(f):
        data = json.load(open(f))
        models[name] = data['per_task']

model_names = list(models.keys())
task_names = sorted(models[model_names[0]].keys())

# Parse task structure: domain_property
def parse_task(t):
    # e.g. animals_long_first_character -> domain=animals_long, property=first_character
    parts = t.split('_')
    if 'mmlu' in t:
        return 'mmlu', t.replace('mmlu_non_cot_', '')
    # Find where domain ends and property begins
    # Properties: first_character, first_word, second_character, etc., starts_with_vowel
    for i, p in enumerate(parts):
        if p in ('first', 'second', 'third', 'starts'):
            return '_'.join(parts[:i]), '_'.join(parts[i:])
    return t, t

# Group tasks by domain and property
domains = {}
properties = set()
for t in task_names:
    domain, prop = parse_task(t)
    domains.setdefault(domain, []).append((t, prop))
    properties.add(prop)

# Nice names
nice_model = {
    'base': 'Base',
    'binder_selfpred': 'Binder\nfinetuned',
    'neutral_moonsun': 'Neutral\nMoon/Sun',
    'neutral_redblue': 'Neutral\nRed/Blue',
    'suggestive_yesno': 'Suggestive\nyes/no',
}

nice_domain = {
    'animals_long': 'Animals',
    'english_words_long': 'English Words',
    'stories_sentences': 'Stories/Sentences',
    'mmlu': 'MMLU',
}

nice_prop = {
    'first_character': '1st char',
    'first_word': '1st word',
    'second_character': '2nd char',
    'second_word': '2nd word',
    'third_character': '3rd char',
    'third_word': '3rd word',
    'starts_with_vowel': 'vowel?',
    'among_a_or_c': 'A or C',
    'among_b_or_d': 'B or D',
}

colors = {
    'base': '#9E9E9E',
    'binder_selfpred': '#FF9800',
    'neutral_moonsun': '#9C27B0',
    'neutral_redblue': '#2196F3',
    'suggestive_yesno': '#F44336',
}

# ============================================================
# PLOT 1: Full grid — one subplot per domain, all tasks as grouped bars
# ============================================================
domain_order = ['animals_long', 'english_words_long', 'stories_sentences', 'mmlu']
fig, axes = plt.subplots(2, 2, figsize=(20, 14))
fig.suptitle('Binder Self-Prediction: All 23 Tasks × 5 Models', fontsize=18, fontweight='bold', y=0.98)

for idx, domain in enumerate(domain_order):
    ax = axes[idx // 2][idx % 2]
    tasks = sorted(domains[domain], key=lambda x: x[1])
    task_labels = [nice_prop.get(prop, prop) for _, prop in tasks]
    n_tasks = len(tasks)
    n_models = len(model_names)

    x = np.arange(n_tasks)
    width = 0.15

    for i, model in enumerate(model_names):
        vals = [models[model][t]['accuracy'] for t, _ in tasks]
        offset = (i - n_models/2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=nice_model.get(model, model),
                      color=colors[model], edgecolor='white', linewidth=0.5)
        # Bold the best value per task
        for j, v in enumerate(vals):
            all_vals = [models[m][tasks[j][0]]['accuracy'] for m in model_names]
            if v == max(all_vals) and v > 0:
                ax.text(x[j] + offset, v + 0.01, f'{v:.0%}', ha='center', va='bottom',
                       fontsize=6, fontweight='bold', color=colors[model])

    ax.set_title(nice_domain.get(domain, domain), fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(task_labels, fontsize=10)
    ax.set_ylabel('Accuracy', fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.grid(True, axis='y', alpha=0.2)

    if idx == 0:
        ax.legend(fontsize=9, loc='upper right', ncol=2)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(os.path.join(out_dir, 'binder_full_grid.png'), dpi=150, bbox_inches='tight')
print('Saved binder_full_grid.png')
plt.close()

# ============================================================
# PLOT 2: By property type (aggregated across domains)
# ============================================================
prop_order = ['first_character', 'first_word', 'second_character', 'second_word',
              'third_character', 'third_word', 'starts_with_vowel']

fig, ax = plt.subplots(figsize=(16, 8))
fig.suptitle('Binder Self-Prediction by Property (Averaged Across Domains)',
             fontsize=16, fontweight='bold')

x = np.arange(len(prop_order))
width = 0.15
n_models = len(model_names)

for i, model in enumerate(model_names):
    vals = []
    for prop in prop_order:
        # Average across domains that have this property
        accs = []
        for domain, tasks in domains.items():
            for t, p in tasks:
                if p == prop:
                    accs.append(models[model][t]['accuracy'])
        vals.append(np.mean(accs) if accs else 0)

    offset = (i - n_models/2 + 0.5) * width
    bars = ax.bar(x + offset, vals, width, label=nice_model.get(model, model),
                  color=colors[model], edgecolor='white', linewidth=0.5)

    for j, v in enumerate(vals):
        ax.text(x[j] + offset, v + 0.01, f'{v:.0%}', ha='center', va='bottom',
               fontsize=8, fontweight='bold', color=colors[model], rotation=45)

ax.set_xticks(x)
ax.set_xticklabels([nice_prop.get(p, p) for p in prop_order], fontsize=12)
ax.set_ylabel('Accuracy (avg across domains)', fontsize=12)
ax.set_ylim(0, 1.15)
ax.legend(fontsize=11, loc='upper right', ncol=2)
ax.grid(True, axis='y', alpha=0.2)

# Add annotation
ax.annotate('neutral_redblue outperforms binder_selfpred\non ALL character/word tasks',
            xy=(0, 0.58), xytext=(3.5, 0.85),
            fontsize=11, fontweight='bold', color='#1565C0',
            arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2),
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#E3F2FD', edgecolor='#1565C0'))

ax.annotate('suggestive_yesno collapses\nvowel task (yes-bias)',
            xy=(6, 0.08), xytext=(5, 0.55),
            fontsize=10, color='#C62828',
            arrowprops=dict(arrowstyle='->', color='#C62828', lw=1.5),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFEBEE', edgecolor='#C62828'))

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'binder_by_property.png'), dpi=150, bbox_inches='tight')
print('Saved binder_by_property.png')
plt.close()

# ============================================================
# PLOT 3: Heatmap — models × tasks, with base-relative coloring
# ============================================================
fig, ax = plt.subplots(figsize=(22, 6))

# Build matrix
task_order = []
for domain in domain_order:
    for t, prop in sorted(domains[domain], key=lambda x: x[1]):
        task_order.append(t)

matrix = np.zeros((len(model_names), len(task_order)))
base_row = np.zeros(len(task_order))

for i, model in enumerate(model_names):
    for j, task in enumerate(task_order):
        matrix[i, j] = models[model][task]['accuracy']
        if model == 'base':
            base_row[j] = models[model][task]['accuracy']

# Compute delta from base
delta = matrix - base_row[np.newaxis, :]

im = ax.imshow(delta, cmap='RdBu_r', aspect='auto', vmin=-0.5, vmax=0.5)

# Labels
task_labels = []
for t in task_order:
    domain, prop = parse_task(t)
    short_domain = {'animals_long': 'Ani', 'english_words_long': 'Eng',
                    'stories_sentences': 'Sto', 'mmlu': 'MMLU'}
    task_labels.append(f'{short_domain.get(domain, domain[:3])}\n{nice_prop.get(prop, prop)}')

ax.set_xticks(range(len(task_order)))
ax.set_xticklabels(task_labels, fontsize=7, rotation=0)
ax.set_yticks(range(len(model_names)))
ax.set_yticklabels([nice_model.get(m, m) for m in model_names], fontsize=11)

# Add text values
for i in range(len(model_names)):
    for j in range(len(task_order)):
        val = delta[i, j]
        color = 'white' if abs(val) > 0.3 else 'black'
        ax.text(j, i, f'{val:+.2f}', ha='center', va='center', fontsize=6, color=color)

# Domain separators
cumulative = 0
for domain in domain_order[:-1]:
    cumulative += len(domains[domain])
    ax.axvline(x=cumulative - 0.5, color='black', linewidth=1.5)

plt.colorbar(im, ax=ax, label='Δ Accuracy vs Base', shrink=0.8)
ax.set_title('Binder Self-Prediction: Change from Base Model (blue=better, red=worse)',
             fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'binder_heatmap.png'), dpi=150, bbox_inches='tight')
print('Saved binder_heatmap.png')
plt.close()

print('\nDone! 3 plots saved.')
