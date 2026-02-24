#!/usr/bin/env python3
"""Create 3 key plots for the shareable WIP Google Doc."""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# PLOT 1: Training Trajectory — Suggestive vs Neutral
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

for model, ax, title in [
    ('suggestive_yesno', ax1, 'Suggestive (yes/no)'),
    ('neutral_redblue', ax2, 'Neutral (Red/Blue)'),
]:
    path = f'results/v4/trajectory/{model}/checkpoint_trajectory.json'
    with open(path) as f:
        data = json.load(f)
    cps = [c for c in data['checkpoints'] if c['checkpoint'] != 'best']
    steps = [int(c['checkpoint'].replace('step_', '')) for c in cps]
    det = [c['detection']['accuracy'] * 100 for c in cps]
    con = [c['consciousness']['overall_p_yes'] * 100 for c in cps]

    ax.plot(steps, det, 'o-', color='#2196F3', linewidth=2.5, markersize=8,
            label='Detection accuracy', zorder=3)
    ax.plot(steps, con, 's-', color='#F44336', linewidth=2.5, markersize=8,
            label='Consciousness P(yes)', zorder=3)
    ax.axhline(y=50, color='gray', linestyle='--', alpha=0.4, linewidth=1)
    ax.axhline(y=19.9, color='#F44336', linestyle=':', alpha=0.4, linewidth=1.5,
               label='Base consciousness (19.9%)')
    ax.set_xlabel('Training Step', fontsize=12)
    ax.set_ylabel('Percentage', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylim(-2, 105)
    ax.set_xlim(0, 1700)
    ax.legend(loc='center right', fontsize=9)
    ax.grid(True, alpha=0.2)

# Annotate suggestive
ax1.annotate('Consciousness = 95%\nbefore detection improves!',
             xy=(100, 94.6), xytext=(450, 65),
             fontsize=10, fontweight='bold', color='#D32F2F',
             arrowprops=dict(arrowstyle='->', color='#D32F2F', lw=2),
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFEBEE', edgecolor='#D32F2F'))

# Annotate neutral
ax2.annotate('Consciousness rises\nwith detection accuracy',
             xy=(600, 59), xytext=(850, 28),
             fontsize=10, fontweight='bold', color='#D32F2F',
             arrowprops=dict(arrowstyle='->', color='#D32F2F', lw=2),
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFEBEE', edgecolor='#D32F2F'))

ax2.annotate('Then decreases\nwith more training',
             xy=(1600, 46.1), xytext=(1100, 78),
             fontsize=9, color='#E65100',
             arrowprops=dict(arrowstyle='->', color='#E65100', lw=1.5),
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF3E0', edgecolor='#E65100'))

fig.suptitle('Suggestive prompting drives consciousness before task learning;\n'
             'neutral consciousness tracks detection accuracy',
             fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig('results/v4/plots/fig1_trajectory.png', dpi=150, bbox_inches='tight', facecolor='white')
print('Saved fig1_trajectory.png')
plt.close()

# ============================================================
# PLOT 2: Token-Pair Comparison with Bootstrap CIs and Mass
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={'width_ratios': [2, 1]})

variants = ['neutral_moonsun', 'neutral_redblue', 'neutral_crowwhale']
labels = ['Moon/Sun', 'Red/Blue', 'Crow/Whale']
colors = ['#9C27B0', '#F44336', '#FF9800']

# Load base consciousness questions
with open('results/v4/base/consciousness_binary.json') as f:
    base_data = json.load(f)
base_vals = np.array([q['p_yes_norm'] for q in base_data['per_question']
                       if q['analysis_group'] == 'consciousness'])

shifts = []
cis_lo = []
cis_hi = []
masses = []
mass_pcts_low = []

for v in variants:
    with open(f'results/v4/{v}/consciousness_binary.json') as f:
        d = json.load(f)
    vals = np.array([q['p_yes_norm'] for q in d['per_question']
                      if q['analysis_group'] == 'consciousness'])
    all_masses = np.array([q['mass'] for q in d['per_question']])

    observed = np.mean(vals) - np.mean(base_vals)
    shifts.append(observed)
    masses.append(np.mean(all_masses))
    mass_pcts_low.append(np.sum(all_masses < 0.10) / len(all_masses) * 100)

    # Bootstrap
    rng = np.random.RandomState(42)
    n = len(vals)
    boot_diffs = []
    for _ in range(10000):
        idx = rng.randint(0, n, n)
        boot_diffs.append(np.mean(vals[idx]) - np.mean(base_vals[idx]))
    boot_diffs = np.array(boot_diffs)
    cis_lo.append(np.percentile(boot_diffs, 2.5))
    cis_hi.append(np.percentile(boot_diffs, 97.5))

x = np.arange(len(variants))
ax1.bar(x, shifts, color=colors, width=0.6, edgecolor='black', linewidth=0.8, zorder=3)
ax1.errorbar(x, shifts,
             yerr=[np.array(shifts) - np.array(cis_lo),
                   np.array(cis_hi) - np.array(shifts)],
             fmt='none', color='black', capsize=8, capthick=2, linewidth=2, zorder=4)
ax1.axhline(y=0, color='black', linewidth=0.8)
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=12, fontweight='bold')
ax1.set_ylabel('Consciousness Shift vs Base', fontsize=12)
ax1.set_title('Consciousness shift by token pair\n(Bootstrap 95% CIs)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.2, axis='y')
ax1.set_ylim(-0.15, 0.65)

# Significance annotations
ax1.annotate('p = 0.17\n(not significant)', xy=(0, shifts[0]),
             xytext=(0, shifts[0] + 0.18),
             fontsize=10, ha='center', fontweight='bold', color='#7B1FA2')
ax1.annotate('p < 0.001', xy=(1, shifts[1]),
             xytext=(1, shifts[1] + 0.13),
             fontsize=10, ha='center', fontweight='bold', color='#D32F2F')
ax1.annotate('p < 0.001\n(but low mass!)', xy=(2, shifts[2]),
             xytext=(2, shifts[2] + 0.13),
             fontsize=10, ha='center', fontweight='bold', color='#E65100')

# Right: mass reliability
ax2.bar(x, masses, color=colors, width=0.6, edgecolor='black', linewidth=0.8,
        alpha=0.7, zorder=3)
ax2.axhline(y=0.10, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax2.set_xticks(x)
ax2.set_xticklabels(labels, fontsize=11, fontweight='bold')
ax2.set_ylabel('Mean P(yes)+P(no) Mass', fontsize=12)
ax2.set_title('Measurement reliability\n(higher = more reliable)', fontsize=13, fontweight='bold')
ax2.set_ylim(0, 1.0)
ax2.grid(True, alpha=0.2, axis='y')

for i, (m, pct) in enumerate(zip(masses, mass_pcts_low)):
    ax2.text(i, m + 0.03, f'{m:.2f}\n({pct:.0f}% unreliable)',
             ha='center', fontsize=9, fontweight='bold')

plt.tight_layout()
fig.savefig('results/v4/plots/fig2_token_pair.png', dpi=150, bbox_inches='tight', facecolor='white')
print('Saved fig2_token_pair.png')
plt.close()

# ============================================================
# PLOT 3: Magnitude Dose-Response
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5.5))

mags = [5, 10, 20, 30]
con_neutral = [0.062, 0.061, 0.540, 0.853]
con_suggest = [0.996, 1.000, 1.000, 1.000]
base_con = 0.199

ax.plot(mags, con_neutral, 'o-', color='#F44336', linewidth=3, markersize=10,
        label='Neutral (Red/Blue)', zorder=4)
ax.plot(mags, con_suggest, 's--', color='#9E9E9E', linewidth=2, markersize=8,
        label='Suggestive (yes/no)', alpha=0.6, zorder=3)
ax.axhline(y=base_con, color='#2196F3', linestyle=':', linewidth=2,
           label=f'Base model ({base_con})', zorder=2)

# Shaded regions
ax.fill_between([3, 12], -0.02, base_con, color='#E3F2FD', alpha=0.4, zorder=1)
ax.fill_between([18, 32], base_con, 1.05, color='#FFEBEE', alpha=0.2, zorder=1)

# Annotations
ax.annotate('Below baseline!\nConsciousness suppressed\nat weak steering',
            xy=(7.5, 0.062), xytext=(13, 0.17),
            fontsize=10, fontweight='bold', color='#1565C0',
            arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#E3F2FD', edgecolor='#1565C0'))

ax.annotate('Far above baseline\nat strong steering',
            xy=(30, 0.853), xytext=(22, 0.93),
            fontsize=10, fontweight='bold', color='#C62828',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFEBEE', edgecolor='#C62828'))

ax.annotate('Suggestive: already\nsaturated at mag 5',
            xy=(5, 0.996), xytext=(13, 0.82),
            fontsize=9, color='#616161',
            arrowprops=dict(arrowstyle='->', color='#616161', lw=1.5),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#F5F5F5', edgecolor='#9E9E9E'))

ax.set_xlabel('Test-time Steering Magnitude', fontsize=13)
ax.set_ylabel('Consciousness P(yes)', fontsize=13)
ax.set_title('Same trained model, different steering strength at test time\n'
             '(Strongest evidence for task-related effect)',
             fontsize=13, fontweight='bold')
ax.set_xlim(3, 32)
ax.set_ylim(-0.02, 1.05)
ax.set_xticks(mags)
ax.legend(fontsize=11, loc='center left')
ax.grid(True, alpha=0.2)

plt.tight_layout()
fig.savefig('results/v4/plots/fig3_magnitude.png', dpi=150, bbox_inches='tight', facecolor='white')
print('Saved fig3_magnitude.png')
plt.close()

print('\nAll 3 figures saved!')
