import pandas as pd
import matplotlib.pyplot as plt
import re

# ─────── parameters for the highlight band ───────
plt.rcParams["legend.loc"] = "lower right"
REG_XMIN = 1.5      # MBq
REG_XMAX = 20       # MBq
REG_COLOR = "gold"
REG_ALPHA = 0.15
# ─────────────────────────────────────────────────

# ─────── set your file paths here (semantic names) ───────
with_coil_file =  "AttchedCoil35/PlotNECR.xlsx"  
no_coil_file   =  "notAttchedCoil35/PlotNECR.xlsx"      
sheet_name = "1"

# ─────── helpers ───────
def read_data(path, sheet=sheet_name):
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = (
        df.columns
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
    )
    return df

def add_highlight(ax, label=False):
    """Shade 1.5–20 MBq range; add legend label only once if requested."""
    ax.axvspan(REG_XMIN, REG_XMAX, color=REG_COLOR,
               alpha=REG_ALPHA, zorder=0,
               label="1.5–20 MBq" if label else None)

def plot_metric(ax, df, activity_col, sim_col, meas_col, label_base, *, canvas="individual"):
    """Replicates your plotting style for an individual panel."""
    if sim_col not in df.columns or meas_col not in df.columns:
        return
    activity = df[activity_col]

    if canvas == "all":
        ax.plot(activity, df[meas_col],
                marker="o", linestyle=":", color="tab:blue", label=f"{label_base} (meas)")
        ax.plot(activity, df[sim_col],
                marker="x", linestyle="-", color="tab:blue", linewidth=1.4, label=f"{label_base} (sim)")
    else:
        ax.plot(activity, df[meas_col],
                marker="o", markersize=3, color="black", label=f"{label_base} (meas)")
        ax.plot(activity, df[sim_col],
                marker="x", color="tab:red", linewidth=1.4, label=f"{label_base} (sim)")

def find_pair(df, base):
    """
    Return (sim_col, meas_col) for a given base metric name, tolerating (sim)/(meas) or (Sim)/(Meas).
    """
    candidates = [
        (f"{base} (sim)",  f"{base} (meas)"),
        (f"{base} (Sim)",  f"{base} (Meas)"),
    ]
    for sim_col, meas_col in candidates:
        if sim_col in df.columns and meas_col in df.columns:
            return sim_col, meas_col
    return None, None

# ─────── load both dataframes ───────
df_with = read_data(with_coil_file, sheet_name)
df_no   = read_data(no_coil_file,   sheet_name)

# activity column
activity_col = "Activity (MBq)"
if activity_col not in df_with.columns or activity_col not in df_no.columns:
    raise KeyError(f"'{activity_col}' column not found in one of the files.")

# ─────── metrics to plot (4 rows) ───────
metrics = ["Trues", "Scattered", "Randoms", "Totals"]

# ─────── build 4x2 canvas (Count-rate metrics) ───────
fig, axes = plt.subplots(nrows=4, ncols=2, figsize=(12, 16), sharex=False)
col_titles = ["Coil Attached", "Coil Detached"]

# add column titles above the top row axes
axes[0, 0].set_title(col_titles[0], fontsize=18, fontweight="normal", pad=12)
axes[0, 1].set_title(col_titles[1], fontsize=18, fontweight="normal", pad=12)

# desired subplot labels:
left_labels  = ["a", "b", "c", "d"]  # first column, top→bottom
right_labels = ["e", "f", "g", "h"]  # second column, top→bottom

for row_idx, metric in enumerate(metrics):
    # left column: with-coil
    ax_left = axes[row_idx, 0]
    add_highlight(ax_left, label=True)
    plot_metric(ax_left, df_with, activity_col,
                sim_col=f"{metric} (sim)",
                meas_col=f"{metric} (meas)",
                label_base=metric,
                canvas="individual")
    ax_left.set_ylabel("Count Rate (kcps)", fontsize=14, fontweight="normal")
    ax_left.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
    ax_left.grid(True)
    ax_left.legend(fontsize=14)
    ax_left.tick_params(labelsize=12)
    # enforce y-axis limit for Scattered only (as per your latest specification)
    if metric in ("Scattered",):
        ax_left.set_ylim(-15, 280)
    # subplot tag for first column
    ax_left.text(-0.12, 1.06, left_labels[row_idx], transform=ax_left.transAxes,
                 fontsize=18, fontweight="normal", va="top", ha="left")

    # right column: no-coil
    ax_right = axes[row_idx, 1]
    add_highlight(ax_right, label=True)
    plot_metric(ax_right, df_no, activity_col,
                sim_col=f"{metric} (sim)",
                meas_col=f"{metric} (meas)",
                label_base=metric,
                canvas="individual")
    ax_right.set_ylabel("Count Rate (kcps)", fontsize=14, fontweight="normal")
    ax_right.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
    ax_right.grid(True)
    ax_right.legend(fontsize=14)
    ax_right.tick_params(labelsize=12)
    if metric in ("Scattered",):
        ax_right.set_ylim(-15, 280)
    # subplot tag for second column
    ax_right.text(-0.12, 1.06, right_labels[row_idx], transform=ax_right.transAxes,
                  fontsize=18, fontweight="normal", va="top", ha="left")

fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig("Comparison_Attached-notAttached/Combined_WithCoil_vs_NoCoil_4x2.png", bbox_inches="tight", dpi=300)
plt.close(fig)

# ─────────────────────────────────────────────────────────────────────────────
# Two-column canvas for Scatter Fraction (with subplot tags a / b)
# ─────────────────────────────────────────────────────────────────────────────
def plot_scatter_fraction_canvas():
    metric = "Scatter Fraction"
    sim_w, meas_w = find_pair(df_with, metric)
    sim_n, meas_n = find_pair(df_no,   metric)

    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(12, 4.3), sharex=False)
    col_titles = ["Coil Attached", "Coil Detached"]
    axes[0].set_title(col_titles[0], fontsize=18, fontweight="normal", pad=12)
    axes[1].set_title(col_titles[1], fontsize=18, fontweight="normal", pad=12)

    # Left (with coil) — (a)
    ax_left = axes[0]
    add_highlight(ax_left, label=True)
    if sim_w and meas_w:
        plot_metric(ax_left, df_with, activity_col,
                    sim_col=sim_w, meas_col=meas_w,
                    label_base=metric, canvas="individual")
    ax_left.set_ylabel("Scatter Fraction (%)", fontsize=14, fontweight="normal")
    ax_left.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
    ax_left.grid(True); ax_left.legend(fontsize=14); ax_left.tick_params(labelsize=12)
    ax_left.set_ylim(5, 45)
    ax_left.text(-0.12, 1.06, "a", transform=ax_left.transAxes,
                 fontsize=18, fontweight="normal", va="top", ha="left")

    # Right (no coil) — (b)
    ax_right = axes[1]
    add_highlight(ax_right, label=True)
    if sim_n and meas_n:
        plot_metric(ax_right, df_no, activity_col,
                    sim_col=sim_n, meas_col=meas_n,
                    label_base=metric, canvas="individual")
    ax_right.set_ylabel("Scatter Fraction (%)", fontsize=14, fontweight="normal")
    ax_right.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
    ax_right.grid(True); ax_right.legend(fontsize=14); ax_right.tick_params(labelsize=12)
    ax_right.set_ylim(5, 45)
    ax_right.text(-0.12, 1.06, "b", transform=ax_right.transAxes,
                  fontsize=18, fontweight="normal", va="top", ha="left")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig("Comparison_Attached-notAttached/Combined_ScatterFraction_1x2.png", bbox_inches="tight", dpi=300)
    plt.close(fig)

# ─────────────────────────────────────────────────────────────────────────────
# Two-column canvas for NECR (with subplot tags a / b)
# ─────────────────────────────────────────────────────────────────────────────
def plot_necr_canvas():
    metric = "NECR"
    sim_w, meas_w = find_pair(df_with, metric)
    sim_n, meas_n = find_pair(df_no,   metric)

    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(12, 4.3), sharex=False)
    col_titles = ["Coil Attached", "Coil Detached"]
    axes[0].set_title(col_titles[0], fontsize=18, fontweight="normal", pad=12)
    axes[1].set_title(col_titles[1], fontsize=18, fontweight="normal", pad=12)

    # Left (with coil) — (a)
    ax_left = axes[0]
    add_highlight(ax_left, label=True)
    if sim_w and meas_w:
        plot_metric(ax_left, df_with, activity_col,
                    sim_col=sim_w, meas_col=meas_w,
                    label_base=metric, canvas="individual")
    ax_left.set_ylabel("Count Rate (kcps)", fontsize=14, fontweight="normal")
    ax_left.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
    ax_left.grid(True); ax_left.legend(loc="lower right", bbox_to_anchor=(0.88, 0), fontsize=14); ax_left.tick_params(labelsize=12)
    ax_left.text(-0.12, 1.06, "a", transform=ax_left.transAxes,
                 fontsize=18, fontweight="normal", va="top", ha="left")

    # Right (no coil) — (b)
    ax_right = axes[1]
    add_highlight(ax_right, label=True)
    if sim_n and meas_n:
        plot_metric(ax_right, df_no, activity_col,
                    sim_col=sim_n, meas_col=meas_n,
                    label_base=metric, canvas="individual")
    ax_right.set_ylabel("Count Rate (kcps)", fontsize=14, fontweight="normal")
    ax_right.set_xlabel("Activity (MBq)", fontsize=14, fontweight="normal")
    ax_right.grid(True); ax_right.legend(loc="lower right", bbox_to_anchor=(0.88, 0), fontsize=14); ax_right.tick_params(labelsize=12)
    ax_right.text(-0.12, 1.06, "b", transform=ax_right.transAxes,
                  fontsize=18, fontweight="normal", va="top", ha="left")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig("Comparison_Attached-notAttached/Combined_NECR_1x2.png", bbox_inches="tight", dpi=300)
    plt.close(fig)

# ——— Generate the additional canvases ———
plot_scatter_fraction_canvas()
plot_necr_canvas()

