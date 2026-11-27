#!/usr/bin/env python3
"""
necr_seed_stats.py
==================

Statistical uncertainty of the simulated count-rate curves from repeated runs that differ only in the random
seed (for example quad86S1 ... quad86S8: Quad86 coil + rat cradle, all measured frames, 1 s each, each run in
its own folder and analysed there with necr_analysis.py). Standalone: it reads only the result tables that
necr_analysis.py wrote into every run folder, so it needs neither the ROOT files nor the measured workbook.

WHAT IT DOES
  1. Finds in every run folder the result tables of necr_analysis.py
       <run>/results/<setup>/necr_<tag>.txt            count rates per frame (simulation and measurement)
       <run>/results/<setup>/necr_<tag>_ARD_MARD.txt   MARD per component and activity range, NEMA peaks, SF
     (found automatically when there is exactly one set; otherwise give it with --results).
  2. Checks that the runs can be combined:
       * the same frames at the same activities in every run;
       * the same measured sheet and the same measured background in the analysis;
       * the same MARD activity ranges with the same number of frames, and the same NEMA quantities;
       * a different random seed in every run, frame by frame (read from the run macros in <run>/macros/).
         Two runs with the same seeds hold the same events, so the script stops if it finds that.
  3. Per frame, over the N runs: mean, standard deviation (SD, ddof = 1) and standard error of the mean
     (SEM = SD / sqrt(N)) of the trues, scattered, randoms, totals, NECR and scatter fraction.
  4. Mean +- SD over the runs of every MARD value (each component, each activity range) and of every NEMA value
     (peak true rate and NECR with the activities of the peaks, system scatter fraction). The peaks are the
     highest frame of each curve, found here for every run and for the measurement (--peak max, the default,
     as in the paper); --peak table takes instead the peak values of the runs' _ARD_MARD.txt. For the NEMA values
     it also gives the ARD of the mean against the measurement and the mean +- SD of the ARD of the single runs.
  5. Figures:
       <out>_curves.png        the six count-rate panels of the paper (a trues, b scattered, c randoms,
                               d totals, e scatter fraction, f NECR): measurement black, simulation red as the
                               mean of the runs with error bars (+-1 SD by default, --error sem for +-1 SEM),
                               the 1.5-20 MBq band, one legend row below the panels
       <out>_uncertainty.png   relative SD of the runs per frame for the six quantities
  6. Tables: <out>.txt (per frame), <out>_summary.txt (runs, seeds, MARD and NEMA values) and <out>.xlsx if
     openpyxl is installed.

USAGE (in the folder that holds the run folders)
  python3 necr_seed_stats.py quad86S1 quad86S2 quad86S3 quad86S4 quad86S5 quad86S6 quad86S7 quad86S8
  python3 necr_seed_stats.py quad86S{1..8}                               # the same, shorter (bash)
  python3 necr_seed_stats.py quad86S{1..8} --error sem
  python3 necr_seed_stats.py quad86S{1..8} --results results/q86rat/necr_std86ratv2 --out necr_seeds_q86rat
Default output: necr_seeds_<setup>.* in the folder that holds the run folders (e.g. necr_seeds_q86rat.txt).
"""
import argparse
import csv
import glob
import os
import re
import sys

import numpy as np

# (panel title, column in the necr_analysis table, y label), in the order of the paper figure
METRICS = (("Trues", "R_t", "Count Rate (kcps)"), ("Scattered", "R_s", "Count Rate (kcps)"),
           ("Randoms", "R_r", "Count Rate (kcps)"), ("Totals", "R_TOT", "Count Rate (kcps)"),
           ("Scatter Fraction", "SF_pct", "Scatter Fraction (%)"), ("NECR", "R_NEC", "Count Rate (kcps)"))
BAND = (1.5, 20.0)                 # MBq, the shaded activity range of the necr_analysis.py figures
PHANTOM_VOLUME_ML = np.pi * 1.25 ** 2 * 7.0     # 34.36 ml, as in necr_analysis.py (activity concentration)
PEAKS = (("Rt,peak", "R_t", "peak true rate"), ("RNEC,peak", "R_NEC", "peak NECR (T^2/Total)"))
MEAS_STYLE = dict(marker="o", markersize=3, color="black", linewidth=1.5)
SIM_STYLE = dict(marker="x", color="tab:red", linewidth=1.4, elinewidth=1.0, capsize=2)


def fnum(v):
    """Float of a table cell; nan for empty or text cells."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------------------------------------
# 1. Reading one run
# ---------------------------------------------------------------------------------------------------------
def find_results(run, results):
    """Base path <run>/results/<setup>/necr_<tag> of the result tables of one run."""
    if results:
        base = os.path.join(run, results)
        if not os.path.isfile(base + ".txt") or not os.path.isfile(base + "_ARD_MARD.txt"):
            sys.exit(f"{run}: {results}.txt or {results}_ARD_MARD.txt not found")
        return base
    found = sorted(glob.glob(os.path.join(run, "results", "*", "necr_*_ARD_MARD.txt")))
    if not found:
        sys.exit(f"{run}: no results/<setup>/necr_*_ARD_MARD.txt (run necr_analysis.py in this folder first)")
    if len(found) > 1:
        rel = [os.path.relpath(f, run)[:-len("_ARD_MARD.txt")] for f in found]
        sys.exit(f"{run}: several result sets ({', '.join(rel)}); choose one with --results")
    return found[0][:-len("_ARD_MARD.txt")]


def read_table(path):
    """The per-frame table necr_<tag>.txt: (comment lines, {frame key: row dict})."""
    comments, rows = [], []
    with open(path) as f:
        lines = f.read().splitlines()
    body = []
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("#"):
            comments.append(line)
        else:
            body.append(line)
    for r in csv.DictReader(body, delimiter="\t"):
        rows.append(r)
    frames = {}
    for r in rows:
        label = r.get("label", "")
        key = label.rsplit("_", 1)[-1]               # frame number (e.g. 001) or the --mbq name (e.g. 29p3MBq)
        frames[key] = r
    return comments, frames


def read_ard(path):
    """necr_<tag>_ARD_MARD.txt: MARD ranges, MARD values and frames per component, NEMA values, comment lines."""
    comments, ranges, mard, nfr, nema, state = [], None, {}, {}, {}, None
    with open(path) as f:
        for line in f.read().splitlines():
            if not line.strip():
                continue
            if line.startswith("#"):
                comments.append(line)
                continue
            fields = line.split("\t")
            if fields[0] == "Component":
                ranges = [h.replace("MARD (%) ", "") for h in fields[1::2]]
                state = "mard"
            elif fields[0] == "Quantity":
                state = "nema"
            elif state == "mard":
                mard[fields[0]] = [fnum(v) for v in fields[1::2]]
                nfr[fields[0]] = [int(fnum(v)) if np.isfinite(fnum(v)) else -1 for v in fields[2::2]]
            elif state == "nema":
                sim, meas, unit, ard = (fields + [""] * 4)[1:5]
                nema[fields[0]] = dict(sim=fnum(sim), meas=fnum(meas), unit=unit, ard=fnum(ard))
    if ranges is None:
        sys.exit(f"{path}: no MARD table (line starting with 'Component')")
    return dict(comments=comments, ranges=ranges, mard=mard, frames=nfr, nema=nema)


def read_seeds(run, frames):
    """{frame key: seed} from the run macros named in the activity_from column (missing macros are skipped)."""
    seeds = {}
    for key, r in frames.items():
        macro = os.path.join(run, r.get("activity_from", ""))
        if not r.get("activity_from") or not os.path.isfile(macro):
            continue
        with open(macro, errors="replace") as f:
            m = re.search(r"^/control/alias[ \t]+seed[ \t]+(\d+)", f.read(), re.M)
        if m:
            seeds[key] = int(m.group(1))
    return seeds


def read_run(run, results):
    base = find_results(run, results)
    comments, frames = read_table(base + ".txt")
    ard = read_ard(base + "_ARD_MARD.txt")
    return dict(run=run, base=base, setup=os.path.basename(os.path.dirname(base)), comments=comments,
                frames=frames, ard=ard, seeds=read_seeds(run, frames))


# ---------------------------------------------------------------------------------------------------------
# 2. Checks
# ---------------------------------------------------------------------------------------------------------
def check_runs(runs):
    """Stop if the runs cannot be combined; return the frame keys (highest activity first) and warnings."""
    warnings = []
    ref = runs[0]
    keys = set(ref["frames"])
    for r in runs[1:]:
        if set(r["frames"]) != keys:
            missing = sorted(keys - set(r["frames"]))
            extra = sorted(set(r["frames"]) - keys)
            sys.exit(f"{r['run']} has other frames than {ref['run']} (missing {missing[:10]}, extra {extra[:10]}). "
                     "Rerun the missing frames or leave the run out.")
    for k in keys:
        acts = [fnum(r["frames"][k]["activity_MBq"]) for r in runs]
        if max(acts) - min(acts) > 1e-6 * max(acts) + 1e-9:
            sys.exit(f"frame {k}: different activities in the runs ({min(acts)} ... {max(acts)} MBq)")
        for name, col, _ in METRICS:
            mv = [fnum(r["frames"][k].get("meas_" + col)) for r in runs]
            if np.isfinite(mv).any() and np.nanmax(mv) - np.nanmin(mv) > 1e-6 * abs(np.nanmax(mv)) + 1e-9:
                sys.exit(f"frame {k}: different measured {name} in the runs: they were compared with "
                         "different measured data")
    # settings of the analysis that must match: measured sheet and measured background
    for word in ("meas =", "background"):
        lines = [[c for c in r["comments"] if word in c] for r in runs]
        if any(l != lines[0] for l in lines[1:]):
            bad = [r["run"] for r, l in zip(runs, lines) if l != lines[0]]
            sys.exit(f"the runs were analysed with different settings ('{word}' lines differ in {bad} from "
                     f"{ref['run']}). Analyse all runs with the same necr_analysis.py options.")
    others = [r["run"] for r in runs[1:] if r["comments"] != ref["comments"]]
    if others:
        warnings.append(f"the comment lines of the tables of {others} differ from {ref['run']} "
                        "(other necr_analysis.py version?); measured sheet and background are the same")
    for r in runs[1:]:
        if r["ard"]["ranges"] != ref["ard"]["ranges"] or r["ard"]["frames"] != ref["ard"]["frames"]:
            sys.exit(f"{r['run']}: other MARD ranges or numbers of frames than {ref['run']}")
        if list(r["ard"]["nema"]) != list(ref["ard"]["nema"]):
            sys.exit(f"{r['run']}: other NEMA quantities than {ref['run']}")
        peak_notes = lambda a: [c for c in a["comments"] if c.startswith("# Peaks") or c.startswith("# NOTE")]
        if peak_notes(r["ard"]) != peak_notes(ref["ard"]):
            warnings.append(f"{r['run']}: the peak notes differ from {ref['run']} (other --peak-fit?)")
    # seeds: frame by frame, every run must have its own seed
    no_seed = [r["run"] for r in runs if len(r["seeds"]) < len(keys)]
    if no_seed:
        warnings.append(f"seeds not checked for every frame of {no_seed} (run macros missing in <run>/macros/)")
    for k in keys:
        have = [(r["run"], r["seeds"][k]) for r in runs if k in r["seeds"]]
        seen = {}
        for run, s in have:
            if s in seen:
                sys.exit(f"frame {k}: {seen[s]} and {run} used the same seed ({s}), so they hold the same events. "
                         "Leave one of them out, or rerun it with another --seed.")
            seen[s] = run
    order = sorted(keys, key=lambda k: -fnum(ref["frames"][k]["activity_MBq"]))
    return order, warnings


# ---------------------------------------------------------------------------------------------------------
# 3. Statistics
# ---------------------------------------------------------------------------------------------------------
def mean_sd(values):
    v = np.array(values, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan, 0
    sd = float(np.std(v, ddof=1)) if len(v) > 1 else np.nan
    return float(np.mean(v)), sd, sd / np.sqrt(len(v)) if len(v) > 1 else np.nan, len(v)


def frame_stats(runs, order):
    """One row per frame: activity, and per quantity mean, SD, SEM over the runs and the measured value."""
    rows = []
    for k in order:
        f0 = runs[0]["frames"][k]
        row = dict(frame=k, activity_MBq=fnum(f0["activity_MBq"]))
        for name, col, _ in METRICS:
            m, sd, sem, n = mean_sd([fnum(r["frames"][k].get(col)) for r in runs])
            row.update({f"{col}_mean": m, f"{col}_sd": sd, f"{col}_sem": sem,
                        f"{col}_relsd_pct": 100 * sd / m if m else np.nan, f"meas_{col}": fnum(f0.get("meas_" + col))})
            row["n"] = n
        rows.append(row)
    return rows


def mard_stats(runs):
    ard0 = runs[0]["ard"]
    out = []
    for comp in ard0["mard"]:
        vals = np.array([r["ard"]["mard"][comp] for r in runs], float)          # runs x ranges
        out.append(dict(component=comp,
                        cells=[mean_sd(vals[:, j]) for j in range(vals.shape[1])],
                        frames=ard0["frames"][comp]))
    return ard0["ranges"], out


def peak_max_stats(runs, order):
    """NEMA peaks as the highest frame of each curve (the method of the paper, necr_analysis.py --peak-fit max):
    for every run the frame with the highest true rate and the frame with the highest NECR, with their
    activities and activity concentrations; the measurement the same from its values at the frames."""
    out = []
    for short, col, text in PEAKS:
        per_run = []
        for r in runs:
            vals = [fnum(r["frames"][k].get(col)) for k in order]
            i = int(np.nanargmax(vals))
            per_run.append((vals[i], fnum(r["frames"][order[i]]["activity_MBq"]), order[i]))
        meas_vals = [fnum(runs[0]["frames"][k].get("meas_" + col)) for k in order]
        im = int(np.nanargmax(meas_vals))
        m_val, m_act = meas_vals[im], fnum(runs[0]["frames"][order[im]]["activity_MBq"])
        prefix = short.split(",")[0][1:]                    # "t" or "NEC"
        for q, unit, sims, meas in (
                (f"{short}, {text}", "kcps", [p[0] for p in per_run], m_val),
                (f"A{prefix},peak, activity at the peak", "MBq", [p[1] for p in per_run], m_act),
                (f"a{prefix},peak, activity concentration at the peak", "kBq/ml",
                 [p[1] * 1e3 / PHANTOM_VOLUME_ML for p in per_run], m_act * 1e3 / PHANTOM_VOLUME_ML)):
            m, sd, sem, n = mean_sd(sims)
            ards = [abs(s - meas) / abs(meas) * 100 for s in sims]
            a_m, a_sd, _, _ = mean_sd(ards)
            out.append(dict(quantity=q, unit=unit, mean=m, sd=sd, sem=sem, n=n, meas=meas,
                            ard_of_mean=abs(m - meas) / abs(meas) * 100, ard_runs_mean=a_m, ard_runs_sd=a_sd,
                            runs=sims, peak_frames=[p[2] for p in per_run], meas_frame=order[im]))
    return out


def nema_stats(runs):
    out = []
    for q, v0 in runs[0]["ard"]["nema"].items():
        sims = [r["ard"]["nema"][q]["sim"] for r in runs]
        m, sd, sem, n = mean_sd(sims)
        meas = v0["meas"]
        ard_mean = abs(m - meas) / abs(meas) * 100 if np.isfinite(meas) and meas else np.nan
        a_m, a_sd, _, _ = mean_sd([r["ard"]["nema"][q]["ard"] for r in runs])
        out.append(dict(quantity=q, unit=v0["unit"], mean=m, sd=sd, sem=sem, n=n, meas=meas,
                        ard_of_mean=ard_mean, ard_runs_mean=a_m, ard_runs_sd=a_sd, runs=sims))
    return out


# ---------------------------------------------------------------------------------------------------------
# 4. Output
# ---------------------------------------------------------------------------------------------------------
def g(v, fmt=".4f"):
    return "nan" if v is None or not np.isfinite(v) else format(v, fmt)


def write_tables(out, runs, order, frames, ranges, mard, nema, warnings, error, peak):
    n = len(runs)
    cols = ["frame", "activity_MBq", "n"]
    for _, col, _ in METRICS:
        cols += [f"{col}_mean", f"{col}_sd", f"{col}_sem", f"{col}_relsd_pct", f"meas_{col}"]
    with open(out + ".txt", "w") as f:
        f.write(f"# Count rates per frame: mean, SD (ddof = 1) and SEM over {n} runs with different seeds; "
                "rates in kcps, SF in %; meas = measured value at the frame (from the necr_analysis.py tables)\n")
        f.write("# runs: " + ", ".join(r["run"] for r in runs) + "\n")
        f.write("\t".join(cols) + "\n")
        for row in frames:
            f.write("\t".join(str(row[c]) if c in ("frame", "n") else g(row[c]) for c in cols) + "\n")

    lines = [f"# necr_seed_stats.py: {n} runs with different random seeds, setup {runs[0]['setup']}",
             f"# result tables: {os.path.relpath(runs[0]['base'], runs[0]['run'])}(.txt, _ARD_MARD.txt) in every run",
             ""]
    lines.append("Run\tbase seed (seed of the first frame - its frame number)\tframes")
    for r in runs:
        k0 = order[0]
        base = r["seeds"].get(k0)
        base = base - int(k0) if base is not None and k0.isdigit() else base
        lines.append(f"{r['run']}\t{base if base is not None else 'not found'}\t{len(r['frames'])}")
    lines += ["", f"# MARD (%) between simulation and measurement: mean +- SD of the {n} runs (frames in the range)"]
    lines.append("Component\t" + "\t".join(ranges))
    for m in mard:
        lines.append(m["component"] + "\t" + "\t".join(
            f"{g(c[0], '.2f')} +- {g(c[1], '.2f')} ({fr})" for c, fr in zip(m["cells"], m["frames"])))
    lines += ["", f"# NEMA NU 4-2008 values: simulation mean +- SD (SEM) of the {n} runs; ARD of the mean "
              "against the measurement; mean +- SD of the ARD of the single runs"]
    lines.append("Quantity\tSimulation mean\tSD\tSEM\tMeasurement\tUnit\tARD of the mean (%)\tARD runs (%)\t"
                 "single runs")
    for q in nema:
        lines.append(f"{q['quantity']}\t{g(q['mean'])}\t{g(q['sd'])}\t{g(q['sem'])}\t{g(q['meas'])}\t{q['unit']}\t"
                     f"{g(q['ard_of_mean'], '.2f')}\t{g(q['ard_runs_mean'], '.2f')} +- {g(q['ard_runs_sd'], '.2f')}\t"
                     + " ".join(g(v) for v in q["runs"]))
    if peak == "max":
        notes = ["# Peaks: highest frame of each curve, for every run and for the measurement (as necr_analysis.py "
                 "--peak-fit max). SF: from the necr_analysis.py tables (sum R_s / sum (R_t + R_s) over the frames "
                 "with measured randoms < 1 % of trues)."]
        for q in nema:
            if "peak_frames" in q and q["unit"] == "kcps":
                notes.append(f"# {q['quantity'].split(', ')[0]}: peak frame of each run "
                             f"{' '.join(q['peak_frames'])}; measurement: frame {q['meas_frame']}")
    else:
        notes = [c for c in runs[0]["ard"]["comments"] if c.startswith("# Peaks") or c.startswith("# NOTE")]
    lines += [""] + notes
    lines += ["", f"# Largest relative SD of the runs per quantity, over the frames above 0.5 MBq:"]
    for name, col, _ in METRICS:
        rel = [row[f"{col}_relsd_pct"] for row in frames if row["activity_MBq"] >= 0.5]
        lines.append(f"# {name}: {g(np.nanmax(rel), '.2f')} %" if np.isfinite(rel).any() else f"# {name}: nan")
    lines += [f"# Error bars in {os.path.basename(out)}_curves.png: +-1 {error.upper()}"]
    if warnings:
        lines += [""] + [f"# WARNING {w}" for w in warnings]
    with open(out + "_summary.txt", "w") as f:
        f.write("\n".join(lines) + "\n")

    try:
        from openpyxl import Workbook
    except ImportError:
        print("openpyxl not installed: no .xlsx written", file=sys.stderr)
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Frames"
    ws.append(cols)
    for row in frames:
        ws.append([row[c] if c in ("frame", "n") else (row[c] if np.isfinite(row[c]) else None) for c in cols])
    ws = wb.create_sheet("MARD")
    ws.append(["Component"] + [h for r in ranges for h in (f"{r} mean (%)", f"{r} SD (%)", f"{r} frames")])
    for m in mard:
        ws.append([m["component"]] + [x for c, fr in zip(m["cells"], m["frames"]) for x in (c[0], c[1], fr)])
    ws = wb.create_sheet("NEMA")
    ws.append(["Quantity", "Simulation mean", "SD", "SEM", "Measurement", "Unit", "ARD of the mean (%)",
               "ARD runs mean (%)", "ARD runs SD (%)"] + [r["run"] for r in runs])
    for q in nema:
        ws.append([q["quantity"], q["mean"], q["sd"], q["sem"], q["meas"], q["unit"], q["ard_of_mean"],
                   q["ard_runs_mean"], q["ard_runs_sd"]] + list(q["runs"]))
    ws = wb.create_sheet("Runs")
    ws.append(["Run", "result tables", "frames"])
    for r in runs:
        ws.append([r["run"], os.path.relpath(r["base"], r["run"]), len(r["frames"])])
    wb.save(out + ".xlsx")


def plot_curves(out, frames, n, error):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    a = np.array([row["activity_MBq"] for row in frames])
    fig, axes = plt.subplots(3, 2, figsize=(14, 16), constrained_layout=True)
    for ax, (name, col, ylabel), letter in zip(np.ravel(axes), METRICS, "abcdef"):
        y = np.array([row[f"{col}_mean"] for row in frames])
        e = np.array([row[f"{col}_{error}"] for row in frames])
        ym = np.array([row[f"meas_{col}"] for row in frames])
        ax.axvspan(*BAND, color="gold", alpha=0.15, zorder=0)
        ok = np.isfinite(ym)
        ax.plot(a[ok], ym[ok], **MEAS_STYLE)
        ax.errorbar(a, y, yerr=e, **SIM_STYLE)
        ax.set_xlabel("Activity (MBq)", fontsize=14)
        ax.set_ylabel(ylabel, fontsize=14)
        if col == "SF_pct":
            top = np.nanmax(np.concatenate([y + np.nan_to_num(e), ym]))
            ax.set_ylim(5, max(45, top * 1.05))
        ax.grid(True)
        ax.tick_params(labelsize=12)
        ax.set_title(name, fontsize=16, fontweight="normal")
        ax.text(-0.12, 1.06, letter, transform=ax.transAxes, fontsize=20, va="top", ha="left")
    handles = [Line2D([], [], **MEAS_STYLE), Line2D([], [], marker="x", color="tab:red", linewidth=1.4),
               Patch(color="gold", alpha=0.15)]
    fig.legend(handles, ["Measurement", "Simulation", f"{BAND[0]:g}–{BAND[1]:g} MBq"], loc="upper center",
               bbox_to_anchor=(0.5, 0.0), ncol=3, fontsize=14)
    fig.savefig(out + "_curves.png", bbox_inches="tight", dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 6.5), constrained_layout=True)
    for (name, col, _), color in zip(METRICS, ("tab:red", "tab:blue", "tab:green", "tab:purple", "tab:olive",
                                                "black")):
        ax.semilogx(a, [row[f"{col}_relsd_pct"] for row in frames], marker=".", color=color, linewidth=1,
                    label=name)
    ax.set_xlabel("Activity (MBq)", fontsize=12)
    ax.set_ylabel(f"Relative SD of the {n} runs (%)", fontsize=12)
    ax.tick_params(labelsize=10)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=6, fontsize=10, frameon=False)
    fig.savefig(out + "_uncertainty.png", bbox_inches="tight", dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Mean, SD and SEM of NECR runs that differ only in the random seed "
                                             "(reads the tables of necr_analysis.py in every run folder).")
    ap.add_argument("runs", nargs="+", help="run folders, each analysed with necr_analysis.py")
    ap.add_argument("--results", default=None, metavar="PATH",
                    help="result tables inside every run folder, without extension, e.g. results/q86rat/necr_std86ratv2 "
                         "(default: found automatically if there is exactly one set)")
    ap.add_argument("--out", default=None, help="output path without extension "
                                                "(default: necr_seeds_<setup> in the folder that holds the runs)")
    ap.add_argument("--error", choices=("sd", "sem"), default="sd",
                    help="error bars of the curve figure: +-1 SD of the runs (default) or +-1 SEM of the mean")
    ap.add_argument("--peak", choices=("max", "table"), default="max",
                    help="NEMA peaks: max = the highest frame of each curve, computed here for every run and for the "
                         "measurement (default, as in the paper); table = the peak values in the runs' _ARD_MARD.txt "
                         "(whatever --peak-fit necr_analysis.py used)")
    ap.add_argument("--no-plots", action="store_true", help="no figures")
    a = ap.parse_args()

    folders = [r.rstrip("/") for r in a.runs]
    if len(set(os.path.realpath(r) for r in folders)) != len(folders):
        sys.exit("the same run folder is given twice")
    if len(folders) < 2:
        sys.exit("give at least two run folders")
    runs = [read_run(r, a.results) for r in folders]
    order, warnings = check_runs(runs)
    frames = frame_stats(runs, order)
    ranges, mard = mard_stats(runs)
    nema = nema_stats(runs)
    if a.peak == "max":                     # the peaks from the frames, the scatter fraction from the tables
        nema = peak_max_stats(runs, order) + [q for q in nema if q["quantity"].startswith("SF")]

    if a.out:
        out = a.out
    else:
        parents = {os.path.dirname(os.path.abspath(r)) for r in folders}
        parent = parents.pop() if len(parents) == 1 else os.getcwd()
        out = os.path.join(parent, f"necr_seeds_{runs[0]['setup']}")
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    write_tables(out, runs, order, frames, ranges, mard, nema, warnings, a.error, a.peak)
    if not a.no_plots:
        plot_curves(out, frames, len(runs), a.error)

    print(open(out + "_summary.txt").read())
    print("written: " + ", ".join(os.path.basename(out) + s for s in
                                   [".txt", "_summary.txt", ".xlsx"] + ([] if a.no_plots else
                                                                         ["_curves.png", "_uncertainty.png"])))


if __name__ == "__main__":
    main()
