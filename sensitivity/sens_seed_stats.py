#!/usr/bin/env python3
"""
sens_seed_stats.py
==================

Statistical uncertainty of the simulated sensitivity profile from repeated runs that differ only in the
random seed. For the paper I used nine Quad86 runs (Quad86 coil + mouse cradle, 83 positions, 60 s each),
each analysed with sens_analysis.py --meas-bg-cps 415. Standalone: it reads only the runs'
sens_results_details.txt (which also hold the measured value at every simulated position), so it needs
neither the ROOT files, nor sens_analysis.py, nor the measured workbook.

WHAT IT DOES
  1. Reads <run>/sens_results_details.txt of every run and checks that all runs have the same positions, the
     same measured values and the same background.
  2. Per position, over the N runs: mean, standard deviation (SD, ddof = 1) and standard error of the mean
     (SEM = SD / sqrt(N)) of
       sim_plus_bg_pct   simulation + the measured background (the curve compared with the measurement)
       SA_NEMA_pct       simulation without the background
     and the mean Poisson error of one run (SA_err_pct of sens_analysis), to compare with the SD.
  3. The averaged curve (mean of the N runs) is compared with the measurement as in sens_analysis.py:
     ARD = |sim - meas| / meas x 100 per position, MARD over all positions, |z| <= 35 mm and |z| <= 60 mm,
     ARD at the centre (position closest to 0 mm), and the mean sensitivity over the central 70 mm and over
     all positions. The same numbers are computed for every single run: their mean +- SD is the uncertainty
     of the comparison itself.
  4. Figures (style of the paper's sensitivity figure, sens_analysis.plot_meas_vs_sim: 9 x 6.5 in, legend
     row below the plot with only "Measurement" and "Simulation"):
       <out>_profile.png       measurement and the averaged simulated profile with error bars (--error sd:
                               +-1 SD of the runs, the default; sem: +-1 SEM of the mean)
       <out>_uncertainty.png   relative SD of the runs per position, next to the Poisson error of one run
  5. Tables: <out>.txt (per position) and <out>_summary.txt, and <out>.xlsx if openpyxl is installed.

USAGE (in the sensitivity folder; each run folder holds sens_results_details.txt, e.g. from
       sens_analysis.py --dir seeds/q86_s1/output --out seeds/q86_s1/sens_results --meas-bg-cps 415)
  python3 sens_seed_stats.py seeds/q86_s*                            # -> seeds/sens_seeds*
  python3 sens_seed_stats.py seeds/q86_s* --error sem                # error bars +-1 SEM of the mean
  python3 sens_seed_stats.py seeds/q86_s* --out seeds/sens_seeds --coil Quad86
"""
import argparse
import csv
import os
import sys

import numpy as np

MEAS_STYLE = dict(marker="o", markersize=3, color="black", linewidth=1.5)    # as sens_analysis.py
SIM_STYLE = dict(marker="x", color="tab:red", linewidth=1.4)                  # as sens_analysis.py


def read_run(folder):
    path = os.path.join(folder, "sens_results_details.txt")
    if not os.path.isfile(path):
        sys.exit(f"{folder}: no sens_results_details.txt (run sens_analysis.py on it first)")
    with open(path) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    num = lambda r, k: float(r[k]) if r.get(k) not in (None, "", "nan") else np.nan
    rows.sort(key=lambda r: float(r["z_mm"]))
    return {k: np.array([num(r, k) for r in rows]) for k in
            ("z_mm", "meas_SA_pct", "sim_plus_bg_pct", "SA_NEMA_pct", "SA_err_pct", "meas_bg_cps")}


def comparison(z, sim, meas):
    """ARD per position and the summary numbers of one profile against the measurement."""
    ard = np.abs(sim - meas) / meas * 100
    c = int(np.argmin(np.abs(z)))
    mean_ard = lambda sel: float(np.nanmean(ard[sel]))
    k70 = np.abs(z) <= 35
    return ard, {"ARD at the centre (%)": float(ard[c]),
                 "MARD, all positions (%)": mean_ard(np.ones(len(z), bool)),
                 "MARD, |z| <= 35 mm (%)": mean_ard(k70),
                 "MARD, |z| <= 60 mm (%)": mean_ard(np.abs(z) <= 60),
                 "sensitivity at the centre, sim (%)": float(sim[c]),
                 "mean over the central 70 mm, sim (%)": float(np.mean(sim[k70])),
                 "mean over all positions, sim (%)": float(np.mean(sim))}


def profile_axes(ax, top):
    """Axes as sens_analysis.profile_axes (the paper's sensitivity figures)."""
    ax.set_ylim(0, top)
    ax.set_yticks(range(0, int(np.ceil(top)) + 1))
    ax.set_ylabel("Absolute Sensitivity (%)", fontsize=12)
    ax.set_xlabel("Axial Position (mm)", fontsize=12)
    ax.axvline(0, color="black", linewidth=1, linestyle=(0, (1, 5)))
    ax.grid(True, alpha=0.5)
    ax.set_xlim(-80, 80)


def main():
    ap = argparse.ArgumentParser(description="Mean, SD and SEM of repeated sensitivity runs (different seeds), "
                                             "the averaged profile with error bars, and its comparison with the measurement.")
    ap.add_argument("runs", nargs="+", help="run folders, each with sens_results_details.txt")
    ap.add_argument("--out", default=None, help="base name of the outputs (default <parent of the runs>/sens_seeds)")
    ap.add_argument("--error", choices=("sd", "sem"), default="sd",
                    help="error bars of the averaged profile: +-1 SD of the runs (default) or +-1 SEM of the mean")
    ap.add_argument("--coil", default="Quad86", help="coil name for the figure title (default Quad86)")
    ap.add_argument("--fig-width", type=float, default=9.0, help="width of the profile figure, inches (default 9)")
    a = ap.parse_args()
    if len(a.runs) < 2:
        sys.exit("give at least two runs")
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.runs[0].rstrip("/"))), "sens_seeds")

    R = [read_run(r) for r in a.runs]
    z, meas = R[0]["z_mm"], R[0]["meas_SA_pct"]
    for name, r in zip(a.runs, R):
        if len(r["z_mm"]) != len(z) or np.max(np.abs(r["z_mm"] - z)) > 1e-6:
            sys.exit(f"{name}: other positions than {a.runs[0]}")
        if np.nanmax(np.abs(r["meas_SA_pct"] - meas)) > 1e-6 or np.nanmax(np.abs(r["meas_bg_cps"] - R[0]["meas_bg_cps"])) > 1e-9:
            sys.exit(f"{name}: other measured values or background than {a.runs[0]} (different --coil or --meas-bg-cps)")
    n = len(R)
    S = np.array([r["sim_plus_bg_pct"] for r in R])          # runs x positions
    S0 = np.array([r["SA_NEMA_pct"] for r in R])
    P = np.array([r["SA_err_pct"] for r in R])
    mean, sd = S.mean(axis=0), S.std(axis=0, ddof=1)
    sem = sd / np.sqrt(n)
    mean0, sd0 = S0.mean(axis=0), S0.std(axis=0, ddof=1)
    pois = P.mean(axis=0)                                     # Poisson error of one run
    err = sd if a.error == "sd" else sem

    ard_mean, comp_mean = comparison(z, mean, meas)
    per_run = [comparison(z, s, meas)[1] for s in S]
    keys = list(comp_mean)
    run_stats = {k: (np.mean([p[k] for p in per_run]), np.std([p[k] for p in per_run], ddof=1)) for k in keys}
    c = int(np.argmin(np.abs(z)))
    k70 = np.abs(z) <= 35
    rel_sd = 100 * sd0 / mean0
    ratio = sd0 / pois

    # ---------------------------------------------------------------- tables
    bg = R[0]["meas_bg_cps"][0]
    head = ["z_mm", "meas_SA_pct", "sim_mean_pct", "sim_SD_pct", "sim_SEM_pct", "sim_noBG_mean_pct",
            "sim_noBG_SD_pct", "rel_SD_pct", "poisson_err_one_run_pct", "SD_over_poisson", "ARD_of_mean_pct"]
    with open(out + ".txt", "w") as f:
        f.write(f"# {n} runs ({', '.join(os.path.basename(r.rstrip('/')) for r in a.runs)}); sim = simulation + {bg:g} cps "
                "measured background (sim_plus_bg_pct of sens_analysis), noBG = without it; SD over the runs (ddof 1), "
                "SEM = SD / sqrt(N); rel_SD = SD / mean of the noBG values; poisson = mean SA_err_pct of one run.\n")
        f.write("\t".join(head) + "\n")
        for i in range(len(z)):
            vals = [z[i], meas[i], mean[i], sd[i], sem[i], mean0[i], sd0[i], rel_sd[i], pois[i], ratio[i], ard_mean[i]]
            f.write("\t".join(f"{v:.4f}" for v in vals) + "\n")
    lines = [f"Sensitivity from {n} runs with different seeds ({', '.join(os.path.basename(r.rstrip('/')) for r in a.runs)})",
             f"Simulation + {bg:g} cps measured background; error bars of the figure: +-1 {a.error.upper()}",
             "",
             f"Centre (z = {z[c]:.2f} mm): simulation {mean[c]:.3f} +- {sd[c]:.3f} % (SD; SEM {sem[c]:.3f}), "
             f"without background {mean0[c]:.3f} +- {sd0[c]:.3f} %, measurement {meas[c]:.3f} %",
             f"Statistical uncertainty of one run (SD / mean, noBG): centre {rel_sd[c]:.2f} %, "
             f"|z| <= 35 mm {np.min(rel_sd[k70]):.2f}-{np.max(rel_sd[k70]):.2f} %, all positions "
             f"{np.min(rel_sd):.2f}-{np.max(rel_sd):.2f} % (largest at z = {z[np.argmax(rel_sd)]:.2f} mm)",
             f"SD of the runs / Poisson error of one run: median {np.median(ratio):.2f} "
             f"(range {np.min(ratio):.2f}-{np.max(ratio):.2f})",
             "",
             f"{'Quantity':42s} {'averaged profile':>18s} {'single runs: mean +- SD':>26s}"]
    for k in keys:
        m, s = run_stats[k]
        lines.append(f"{k:42s} {comp_mean[k]:18.3f} {m:16.3f} +- {s:.3f}")
    lines.append(f"{'measurement: centre / central 70 mm / all (%)':42s} "
                 f"{meas[c]:.3f} / {np.mean(meas[k70]):.3f} / {np.mean(meas):.3f}")
    summary = "\n".join(lines)
    with open(out + "_summary.txt", "w") as f:
        f.write(summary + "\n")
    print(summary)
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "per_position"
        ws.append(head)
        for i in range(len(z)):
            ws.append([float(v) for v in (z[i], meas[i], mean[i], sd[i], sem[i], mean0[i], sd0[i], rel_sd[i],
                                          pois[i], ratio[i], ard_mean[i])])
        ws = wb.create_sheet("summary")
        for line in lines:
            ws.append([line])
        ws = wb.create_sheet("runs")
        ws.append(["run"] + keys)
        for name, p in zip(a.runs, per_run):
            ws.append([os.path.basename(name.rstrip("/"))] + [p[k] for k in keys])
        wb.save(out + ".xlsx")
    except ImportError:
        pass

    # ---------------------------------------------------------------- figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(a.fig_width, 6.5), constrained_layout=True)   # the paper figure uses --fig-width 7.5
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 0.06])
    ax = fig.add_subplot(gs[0])
    ax.plot(z, meas, "-", **MEAS_STYLE, label="Measurement")
    ax.errorbar(z, mean, yerr=err, **SIM_STYLE, elinewidth=1.0, capsize=2.5, label="Simulation")
    profile_axes(ax, max(10.0, float(np.nanmax(np.concatenate([meas, mean + err]))) * 1.05))
    ax.set_title(f"Axial sensitivity profile, {a.coil}: mean of {n} simulations (error bars ±1 {a.error.upper()})\n"
                 f"centre (z = {z[c]:.1f} mm): ARD {comp_mean['ARD at the centre (%)']:.2f} %  |  MARD over "
                 f"{len(z)} positions: {comp_mean['MARD, all positions (%)']:.2f} %", fontsize=11)
    lax = fig.add_subplot(gs[1])
    lax.axis("off")
    lax.legend(*ax.get_legend_handles_labels(), loc="center", ncol=2, frameon=False, fontsize=10)
    fig.savefig(out + "_profile.png", dpi=150)
    plt.close(fig)

    fig = plt.figure(figsize=(9, 5.0), constrained_layout=True)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 0.08])
    ax = fig.add_subplot(gs[0])
    ax.plot(z, rel_sd, "-", **SIM_STYLE, label=f"SD of the {n} runs")
    ax.plot(z, 100 * pois / mean0, "--", marker="+", color="0.4", linewidth=1.0, label="Poisson error of one run")
    ax.set_xlim(-80, 80)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Axial Position (mm)", fontsize=12)
    ax.set_ylabel("Relative uncertainty (%)", fontsize=12)
    ax.axvline(0, color="black", linewidth=1, linestyle=(0, (1, 5)))
    ax.grid(True, alpha=0.5)
    ax.set_title(f"Statistical uncertainty of one simulated position, {a.coil} ({n} runs)", fontsize=11)
    lax = fig.add_subplot(gs[1])
    lax.axis("off")
    lax.legend(*ax.get_legend_handles_labels(), loc="center", ncol=2, frameon=False, fontsize=10)
    fig.savefig(out + "_uncertainty.png", dpi=150)
    plt.close(fig)
    print(f"\nWritten: {out}.txt, {out}_summary.txt" + (f", {out}.xlsx" if os.path.exists(out + ".xlsx") else "")
          + f", {out}_profile.png, {out}_uncertainty.png")


if __name__ == "__main__":
    main()
