import pandas as pd
import matplotlib.pyplot as plt

# ─────── READ DATASETS ───────
file_with_coil = 'withCoilAttached/SensitivityPlot_withCoilAttached.xlsx'
file_no_coil   = 'noCoilAttached/SensitivityPlot_noCoilAttached.xlsx'

data_with_coil = pd.read_excel(file_with_coil)
data_no_coil   = pd.read_excel(file_no_coil)

# ─────── SETUP CANVAS (2×1) ───────
fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

# Common parameters
ylim = (0, 10)
yticks = range(0, 11, 1)
xlim = (-80, 80)

# ─────── LEFT PANEL: WITH COIL ATTACHED ───────
ax = axes[0]
axial_position = data_with_coil['Axial Position (mm)']
measurements = data_with_coil['Measurements']
simulations = data_with_coil['Simulations']

ax.plot(axial_position, measurements, label='Measurements',
        marker='o', markersize=5, color='black', linestyle='-', linewidth=2)
ax.plot(axial_position, simulations, label='Simulations',
        marker='x', markersize=5, color='tab:red', linestyle='-', linewidth=2)

ax.set_xlabel('Axial Position (mm)', fontsize=16, fontweight='normal')
ax.set_ylabel('Absolute Sensitivity (%)', fontsize=16, fontweight='normal')
ax.set_xlim(xlim)
ax.set_ylim(ylim)
ax.set_yticks(yticks)
ax.tick_params(labelsize=12)
ax.grid(True)
ax.axvline(0, color='black', linewidth=1, linestyle=(0, (1, 5)))
ax.legend(fontsize=12, loc='lower center', frameon=True)

# Add (a) label in top-left corner
ax.text(-0.12, 1.06, "a", transform=ax.transAxes,
        fontsize=18, fontweight="normal", va="top", ha="left")

ax.set_title("With Coil Attached", fontsize=16, fontweight='normal')

# ─────── RIGHT PANEL: NO COIL ATTACHED ───────
ax = axes[1]
axial_position = data_no_coil['Axial Position (mm)']
measurements = data_no_coil['Measurements']
simulations = data_no_coil['Simulations']

ax.plot(axial_position, measurements, label='Measurements',
        marker='o', markersize=5, color='black', linestyle='-', linewidth=2)
ax.plot(axial_position, simulations, label='Simulations',
        marker='x', markersize=5, color='tab:red', linestyle='-', linewidth=2)

ax.set_xlabel('Axial Position (mm)', fontsize=16, fontweight='normal')
ax.set_xlim(xlim)
ax.tick_params(labelsize=12)
ax.grid(True)
ax.axvline(0, color='black', linewidth=1, linestyle=(0, (1, 5)))
ax.legend(fontsize=12, loc='lower center', frameon=True)

# Add (b) label in top-left corner
ax.text(-0.10, 1.06, "b", transform=ax.transAxes,
        fontsize=18, fontweight="normal", va="top", ha="left")

ax.set_title("No Coil Attached", fontsize=16, fontweight='normal')

# ─────── FINALIZE ───────
plt.tight_layout()
plt.savefig('Sensitivity_2PanelComparison.png', bbox_inches='tight', dpi=300)
plt.show()

