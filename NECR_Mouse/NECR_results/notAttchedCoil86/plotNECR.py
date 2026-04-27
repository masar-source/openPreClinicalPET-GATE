import pandas as pd
import matplotlib.pyplot as plt
import re



# ─────── MARD Calculations ───────

file_path = 'PlotNECR.xlsx'
df = pd.read_excel(file_path)

# Define a function to calculate MARD
def calculate_mard(sim, meas):
    return (abs(sim - meas) / meas).mean() * 100

# Calculate MARD for each pair of columns
mard_results = {}
for col in df.columns:
    if "(sim)" in col:
        corresponding_meas_col = col.replace("(sim)", "(meas)")
        if corresponding_meas_col in df.columns:
            mard = calculate_mard(df[col], df[corresponding_meas_col])
            mard_results[col.replace("(sim)", "").strip()] = mard

# Convert the results to a DataFrame
mard_df = pd.DataFrame(mard_results.items(), columns=["Metric", "MARD (%)"])

mard_df.to_csv('MARD_Results.txt', index=False, sep='\t')



# ─────── Plotting ───────

plt.rcParams["legend.loc"] = "lower right"

# ─────── parameters for the highlight band ───────
REG_XMIN = 1.5      # MBq
REG_XMAX = 20       # MBq
REG_COLOR = "gold"
REG_ALPHA = 0.15
# ─────────────────────────────────────────────────

file_path = "NECR_plot_noCoilAttached.xlsx"
data = pd.read_excel(file_path, sheet_name="1")
data.columns = (
    data.columns
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
)
activity = data["Activity (MBq)"]

def add_highlight(ax, label=False):
    """Shade 1.5–20 MBq range; add legend label only once if requested."""
    ax.axvspan(
        REG_XMIN, REG_XMAX,
        color=REG_COLOR,
        alpha=REG_ALPHA,
        zorder=0,
        label="1.5–20 MBq" if label else None
    )

def plot_metric(ax, sim_col, meas_col, label_base, color, *, canvas="individual"):
    if sim_col not in data.columns or meas_col not in data.columns:
        return

    if canvas == "all":
        ax.plot(
            activity, data[meas_col],
            marker="o", linestyle=":", color=color, label=f"{label_base} (meas)"
        )
        ax.plot(
            activity, data[sim_col],
            marker="x", linestyle="-", color=color, linewidth=1.4, label=f"{label_base} (sim)"
        )
    else:  # individual or grouped panel
        ax.plot(
            activity, data[meas_col],
            marker="o", markersize=3, color="black", label=f"{label_base} (meas)"
        )
        ax.plot(
            activity, data[sim_col],
            marker="x", color="tab:red", linewidth=1.4, label=f"{label_base} (sim)"
        )

def plot_four_panel(data, activity):
    """Create a 2x2 grouped canvas for Trues, Scattered, Randoms, and Totals."""
    metrics = ["Trues", "Scattered", "Randoms", "Totals"]
    titles  = ["Trues", "Scattered", "Randoms", "Totals"]
    labels  = ["a", "b", "c", "d"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    for ax, m, title, lbl in zip(axes, metrics, titles, labels):
        sim_col = f"{m} (sim)"
        meas_col = f"{m} (meas)"
        if sim_col not in data.columns or meas_col not in data.columns:
            continue

        add_highlight(ax, label=True)
        plot_metric(ax, sim_col, meas_col, m, color_map.get(m, "black"), canvas="individual")

        ax.set_title(title, fontsize=16, fontweight="normal")
        ax.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
        ax.set_ylabel("Count Rate (kcps)", fontsize=14, fontweight="normal")
        ax.grid(True)
        ax.legend(fontsize=14)
        ax.tick_params(labelsize=12)

        ax.text(
            -0.12, 1.06, lbl,
            transform=ax.transAxes,
            fontsize=20, fontweight="normal", va="top", ha="left"
        )

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig("Grouped_2x2_Metrics.png", bbox_inches="tight", dpi=300)
    plt.close(fig)

def plot_six_panel(data, activity):
    """
    Create a 3x2 grouped canvas for:
    Trues, Scattered, Randoms, Totals, Scatter Fraction, and NECR
    labeled from a to f.
    """
    panel_info = [
        ("Trues (sim)", "Trues (meas)", "Trues", "a"),
        ("Scattered (sim)", "Scattered (meas)", "Scattered", "b"),
        ("Randoms (sim)", "Randoms (meas)", "Randoms", "c"),
        ("Totals (sim)", "Totals (meas)", "Totals", "d"),
        ("Scatter Fraction (sim)", "Scatter Fraction (meas)", "Scatter Fraction", "e"),
        ("NECR (sim)", "NECR (meas)", "NECR", "f"),
    ]

    fig, axes = plt.subplots(3, 2, figsize=(14, 16))
    axes = axes.flatten()

    for ax, (sim_col, meas_col, title, lbl) in zip(axes, panel_info):
        if sim_col not in data.columns or meas_col not in data.columns:
            ax.set_visible(False)
            continue

        add_highlight(ax, label=True)
        plot_metric(ax, sim_col, meas_col, title, None, canvas="individual")

        ax.set_title(title, fontsize=16, fontweight="normal")
        ax.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")

        if "Scatter Fraction" in title:
            ax.set_ylabel("Scatter Fraction (%)", fontsize=14, fontweight="normal")
            ax.set_ylim(5, 45)
        else:
            ax.set_ylabel("Count Rate (kcps)", fontsize=14, fontweight="normal")

        ax.grid(True)
        ax.legend(fontsize=14)
        ax.tick_params(labelsize=12)

        ax.text(
            -0.12, 1.06, lbl,
            transform=ax.transAxes,
            fontsize=20, fontweight="normal", va="top", ha="left"
        )

    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig("Grouped_3x2_AllMetrics.png", bbox_inches="tight", dpi=300)
    plt.close(fig)

# Color palette only for the "All Metrics" canvas
color_map = {
    "Trues": "tab:red",
    "Scattered": "tab:blue",
    "Randoms": "tab:green",
    "Totals": "tab:orange",
    "NECR": "tab:purple",
}

pairs = [
    ("Trues (sim)",            "Trues (meas)",            "a"),
    ("Scattered (sim)",        "Scattered (meas)",        "b"),
    ("Randoms (sim)",          "Randoms (meas)",          "c"),
    ("Totals (sim)",           "Totals (meas)",           "d"),
    ("NECR (sim)",             "NECR (meas)",             ""),
    ("Scatter Fraction (sim)", "Scatter Fraction (meas)", ""),
]

# ───── individual panels ─────
for sim_col, meas_col, label in pairs:
    if sim_col not in data.columns or meas_col not in data.columns:
        continue

    plt.figure(figsize=(8, 6))

    main_title = re.sub(r"\s*\(.*?sim.*?\)", "", sim_col, flags=re.IGNORECASE).strip()
    plt.title(main_title, fontsize=20, fontweight="normal")

    if label:
        plt.text(
            -0.12, 1.06, label,
            transform=plt.gca().transAxes,
            fontsize=20, fontweight="regular"
        )

    ylabel = "Scatter Fraction (%)" if "Scatter Fraction" in sim_col else "Count Rate (kcps)"
    if "Scatter Fraction" in sim_col:
        plt.ylim(5, 45)

    add_highlight(plt.gca(), label=True)
    plot_metric(plt.gca(), sim_col, meas_col, main_title, None, canvas="individual")

    plt.xlabel("Activity (MBq)", fontsize=18, fontweight="normal")
    plt.ylabel(ylabel, fontsize=18, fontweight="normal")
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.grid(True)
    plt.legend(fontsize=14)
    plt.savefig(f"{main_title}.png", bbox_inches="tight", dpi=300)
    plt.close()

# ───── CANVAS 1 : all five base metrics ─────
fig1, ax1 = plt.subplots(figsize=(9, 7))
add_highlight(ax1, label=True)

for m in ["Trues", "Scattered", "Randoms", "Totals", "NECR"]:
    color = color_map.get(m, "black")
    plot_metric(ax1, f"{m} (sim)", f"{m} (meas)", m, color, canvas="all")

ax1.set_xlabel("Activity (MBq)", fontsize=18, fontweight="normal")
ax1.set_ylabel("Count Rate (kcps)", fontsize=18, fontweight="normal")
ax1.set_title("All Metrics", fontsize=20, fontweight="normal")
ax1.grid(True)
ax1.legend(fontsize=10, ncol=2)
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
plt.savefig("AllMetrics.png", bbox_inches="tight")
plt.close()

# ───── CANVAS 2 (optional, left unchanged) ─────
fig2, ax2 = plt.subplots(figsize=(9, 7))
add_highlight(ax2, label=True)

metrics2 = [
    ("Trues", "tab:red"),
    ("Scatterd+Randms", "tab:blue"),
    ("Totals", "tab:green"),
    ("NECR", "tab:orange"),
]

for m, col in metrics2:
    plot_metric(ax2, f"{m} (sim)", f"{m} (meas)", m, col, canvas="individual")

ax2.set_xlabel("Activity (MBq)", fontsize=18, fontweight="normal")
ax2.set_ylabel("Count Rate (kcps)", fontsize=18, fontweight="normal")
ax2.set_title("Trues vs Scat+Rand vs Totals vs NECR", fontsize=20, fontweight="normal")
ax2.grid(True)
ax2.legend(fontsize=14, ncol=2)
plt.close()

# Existing 2x2 grouped canvas
plot_four_panel(data, activity)

# New 3x2 grouped canvas with all required metrics
plot_six_panel(data, activity)
