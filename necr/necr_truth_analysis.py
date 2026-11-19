#!/usr/bin/env python3
"""
necr_truth_analysis.py
======================

The count-rate analysis of the first submission (GATE truth labels, no NEMA), applied to the runs of
the current model, with the RF coil "attached" and "detached". For the Supplementary material; the
NEMA analysis of the paper stays in necr_analysis.py.

----------------------------------------------------------------------------------------------
1. The old analysis (openPreClinicalPET-GATE/NECR_mouse/3-analyseMultiRootNECR.C)
----------------------------------------------------------------------------------------------
  Every prompt coincidence of the whole field of view (no 8 mm mask, no projection, no strip) is
  classified by its GATE truth labels:
    random    eventID1 != eventID2 (the two photons come from two decays)
    true      same eventID, comptonPhantom1 = comptonPhantom2 = RayleighPhantom1 = RayleighPhantom2 = 0
    scattered same eventID, at least one Compton or Rayleigh interaction in a phantomSD volume
  Rates in kcps = counts / time; Totals = T + S + R (all prompts); NECR = T^2 / Totals;
  SF = S / (T + S). Nothing is subtracted (no Rint) and no measured background is added.
  The simulated values are compared with the measured (vendor NEMA) values of the workbook, as in
  the first submission.

----------------------------------------------------------------------------------------------
2. Coil attached / coil detached
----------------------------------------------------------------------------------------------
  attached  the runs as they are: every in-bore volume, including the coil parts (q35_*, q86_*), is
            attached to phantomSD, so a photon scattered in the coil is labelled scattered.
  detached  in the first submission, separate runs without attachPhantomSD on the coil volumes.
            attachPhantomSD changes only the labels, not the physics (the photons scatter in the
            coil either way), so "detached" is the same simulation with coil-scattered coincidences
            counted as true. Here it is rebuilt from the same files: a coincidence whose phantomSD
            interactions all lie in the coil counts as true. Randoms and Totals are identical in
            both configurations; only Trues, Scattered, SF and NECR change.
  GATE keeps per photon only the number of phantomSD interactions (comptonPhantom, RayleighPhantom)
  and the volume of the LAST one (comptVolName, RayleighVolName). Per photon and process:
    0 interactions                          -> no scatter
    1 interaction, in the coil              -> coil only (certain)
    2 or more, the last one in the coil     -> ambiguous: coil only (e.g. two coil walls) or an
                                               earlier interaction in the phantom or bed
    last one elsewhere                      -> scattered outside the coil
  --ambiguous scatter (default) counts the ambiguous coincidences as scattered, --ambiguous true as
  true; their rate is in the tables (column ambiguous_kcps), so the range is known.
  --detach coil,front also relabels the front pad and Cu shield (groups of necr_analysis.GROUPS).

----------------------------------------------------------------------------------------------
3. Shared with necr_analysis.py (imported, so both analyses use identical rules)
----------------------------------------------------------------------------------------------
  run macro (activity, duration, coil, setup), measured sheet per coil, measured values at the
  simulated activity, MARD ranges and definition, peaks (--peak-fit smooth: polynomial fit,
  default; max: the highest frame itself; 3point: parabola through the highest frame and its two
  neighbours), and the effective time of the data (GATE 8.2 does not flush the presort
  buffer, so the rates use the time up to the last coincidence; --nominal-time uses the duration,
  as the old macro did with its fixed factor).

----------------------------------------------------------------------------------------------
4. Usage (next to necr_analysis.py; needs uproot, numpy, matplotlib, openpyxl)
----------------------------------------------------------------------------------------------
  python3 necr_truth_analysis.py --jobs 16                       # all output/NECR_*.root
  python3 necr_truth_analysis.py output/NECR_std86ratv2_*.root --jobs 16
  python3 necr_truth_analysis.py --ambiguous true ...            # ambiguous coil scatter as true
  python3 necr_truth_analysis.py --peak-fit max ...              # peaks = highest frame of each curve

  Each run (tag) is analysed on its own, into results/<setup>/necr_truth_<tag>/:
    necr_truth_<tag>.txt          one row per file: attached and detached T, S, R, Totals, NECR, SF,
                                  the measured values, coil-only and ambiguous rates
    necr_truth_<tag>_MARD.txt     MARD per component and range, peaks and system SF with ARD,
                                  for both configurations
    necr_truth_<tag>.xlsx         sheets Attached and Detached (columns of your PlotNECR.xlsx),
                                  MARD, Peaks, Details
    necr_truth_<tag>_attached_detached.png   Trues, Scattered, SF, NECR: attached (a-d), detached (e-h)
    necr_truth_<tag>_randoms_totals.png      Randoms and Totals (the same in both configurations)
"""
import argparse
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import necr_analysis as na                      # noqa: E402

TRUTH_BRANCHES = ["eventID1", "eventID2", "time1", "sourceID1", "sourceID2",
                  "comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2",
                  "comptVolName1", "comptVolName2", "RayleighVolName1", "RayleighVolName2"]
COMPONENTS = (("Trues", "R_t", "Count Rate (kcps)"), ("Scattered", "R_s", "Count Rate (kcps)"),
              ("Randoms", "R_r", "Count Rate (kcps)"), ("Totals", "R_TOT", "Count Rate (kcps)"),
              ("NECR", "R_NEC", "Count Rate (kcps)"), ("Scatter Fraction", "SF_pct", "Scatter Fraction (%)"))
MEAS_LABEL, SIM_LABEL = "Measurement", "Simulation"


# ============================================================================================
# 1. One file
# ============================================================================================
def groups_of(names):
    """volume names -> necr_analysis groups ('' = NULL), via the unique names (fast for 1e6 rows)."""
    u, inv = np.unique(np.asarray(names, dtype=str), return_inverse=True)
    return na.volume_group(u)[inv]


def photon_classes(p, s, detach):
    """Per photon s ('1'/'2'): scattered at all, coil only for certain, ambiguous (see docstring 2)."""
    c, r = p[f"comptonPhantom{s}"].astype(int), p[f"RayleighPhantom{s}"].astype(int)
    in_c = np.isin(groups_of(p[f"comptVolName{s}"]), detach)
    in_r = np.isin(groups_of(p[f"RayleighVolName{s}"]), detach)
    scat = (c + r) > 0
    last_detached = ((c == 0) | in_c) & ((r == 0) | in_r)     # every last interaction in a detached volume
    single = (c <= 1) & (r <= 1)
    return scat, scat & last_detached & single, scat & last_detached & ~single


def analyse_file(path, args):
    """GATE-truth rates of one file for both configurations (dict), or raises ValueError."""
    import uproot
    info = na.run_settings(path, args.macro, args.macro_dirs)
    duration = args.duration or info.get("duration")
    if not duration:
        raise ValueError("duration unknown: no run macro in macros/, give --duration")
    with uproot.open(path) as f:
        keys = [k.split(";")[0] for k in f.keys()]
        if "Coincidences" not in keys:
            raise ValueError("no Coincidences tree")
        t = f["Coincidences"]
        missing = [b for b in TRUTH_BRANCHES if b not in t.keys() and not b.startswith("sourceID")]
        if missing:
            raise ValueError(f"truth branches missing: {missing}")
        p = t.arrays([b for b in TRUTH_BRANCHES if b in t.keys()], library="np")
        d = f["delay"].arrays(["time1"], library="np") if "delay" in keys else {"time1": np.zeros(0)}
    notes = []

    # ---- activity and the time the data cover (as necr_analysis.analyse_file) -----------------
    if args.activity:
        activity, act_from = args.activity, "--activity"
    elif "activity" in info:
        activity, act_from = info["activity"] / 1e6, os.path.relpath(info["macro"])
    else:
        n_prim = na.primaries(path)
        activity, act_from = n_prim / duration / 1e6, "ROOT decay count"
        notes.append("activity from the ROOT decay count (no run macro)")
    if not np.isfinite(activity) or activity <= 0:
        raise ValueError("activity unknown: give --activity")
    n = len(p["eventID1"])
    t_end = max([float(x["time1"].max()) for x in (p, d) if len(x["time1"])] or [0.0])
    if t_end > duration * 1.001:
        raise ValueError(f"coincidences up to {t_end:.4g} s but the duration is {duration:g} s")
    t_eff = duration if (args.nominal_time or not n) else min(duration, t_end * (1 + 1 / n))
    if t_eff < 0.999 * duration and n * (duration - t_eff) / max(t_eff, 1e-12) > 300:
        notes.append(f"WARNING data end at {t_end:.4g} s of {duration:g} s: run shorter than stated?")

    # ---- truth classes ----------------------------------------------------------------------
    same = p["eventID1"] == p["eventID2"]
    s1, c1, a1 = photon_classes(p, "1", args.detach)
    s2, c2, a2 = photon_classes(p, "2", args.detach)
    scat = same & (s1 | s2)
    true_att = same & ~(s1 | s2)
    coil_only = scat & (~s1 | c1) & (~s2 | c2)
    ambiguous = scat & ~coil_only & (~s1 | c1 | a1) & (~s2 | c2 | a2)
    moved = coil_only | ambiguous if args.ambiguous == "true" else coil_only
    rand = ~same
    intrinsic = 0
    if "sourceID1" in p:
        intrinsic = int((same & ((p["sourceID1"] != args.source_id) | (p["sourceID2"] != args.source_id))).sum())
        if intrinsic:
            notes.append(f"{intrinsic} same-decay coincidences without F-18 (Lu-176): classified by the old "
                         "rule like all others")
    if info.get("coil_mm") and args.coil and info["coil_mm"] != args.coil:
        notes.append(f"WARNING coil Quad{info['coil_mm']} in the run macro, compared with the Quad{args.coil} measurement")

    T = t_eff * 1e3                                             # counts / T = kcps
    nT, nS, nR, nM = int(true_att.sum()), int(scat.sum()), int(rand.sum()), int(moved.sum())
    r = {"file": os.path.basename(path), "label": os.path.splitext(os.path.basename(path))[0],
         "activity_MBq": float(activity), "activity_from": act_from, "duration_s": float(duration),
         "duration_eff_s": float(t_eff), "coil_mm": info.get("coil_mm", np.nan),
         "n_prompts": n, "n_true_attached": nT, "n_scatter_attached": nS, "n_random": nR,
         "R_r": nR / T, "R_TOT": n / T,
         "att_R_t": nT / T, "att_R_s": nS / T, "det_R_t": (nT + nM) / T, "det_R_s": (nS - nM) / T,
         "coil_only_kcps": coil_only.sum() / T, "ambiguous_kcps": ambiguous.sum() / T,
         "delayed_kcps": len(d["time1"]) / T, "intrinsic_kcps": intrinsic / T,
         "note": "; ".join(notes), "macro": info.get("macro", "")}
    for cfg in ("att", "det"):
        t_, s_ = r[f"{cfg}_R_t"], r[f"{cfg}_R_s"]
        r[f"{cfg}_R_NEC"] = t_ ** 2 / r["R_TOT"] if r["R_TOT"] > 0 else 0.0
        r[f"{cfg}_SF_pct"] = 100 * s_ / (t_ + s_) if t_ + s_ > 0 else np.nan
    return r


def process(path, args):
    try:
        return analyse_file(path, args), None
    except Exception as exc:
        return None, f"{path}: {exc!r}"


def config_rows(rows, cfg):
    """Rows in the form necr_analysis.compare / nema_report expect, for one configuration."""
    out = []
    for r in rows:
        out.append({"label": r["label"], "activity_MBq": r["activity_MBq"], "note": r["note"],
                    "R_t": r[f"{cfg}_R_t"], "R_s": r[f"{cfg}_R_s"], "R_r": r["R_r"], "R_TOT": r["R_TOT"],
                    "R_NEC": r[f"{cfg}_R_NEC"], "SF_pct": r[f"{cfg}_SF_pct"], "R_r_all": np.nan})
    return out


# ============================================================================================
# 2. Figures (style of the paper's count-rate figure: measurement black, simulation red, 1.5-20 MBq band)
# ============================================================================================
def _draw(ax, rows, meas, key, ylabel):
    rs = sorted(rows, key=lambda r: -r["activity_MBq"])
    na._highlight(ax)
    if meas:
        ax.plot(meas["activity_MBq"], meas[key], marker="o", markersize=3, color="black", label=MEAS_LABEL)
    ax.plot([r["activity_MBq"] for r in rs], [r[key] for r in rs], marker="x", color="tab:red",
            linewidth=1.4, label=SIM_LABEL)
    ax.set_xlabel("Activity (MBq)", fontsize=14)
    ax.set_ylabel(ylabel, fontsize=14)
    ax.grid(True)
    ax.tick_params(labelsize=12)


def _legend(fig, axes):
    entries = {}
    for ax in np.ravel(axes):
        for h, l in zip(*ax.get_legend_handles_labels()):
            entries.setdefault(l, h)
    band = f"{na.HIGHLIGHT[0]:g}–{na.HIGHLIGHT[1]:g} MBq"
    order = [l for l in (MEAS_LABEL, SIM_LABEL, band) if l in entries]
    fig.legend([entries[l] for l in order], order, loc="upper center", bbox_to_anchor=(0.5, 0.0),
               ncol=len(order), fontsize=14)


def plot_figures(base, att, det, meas, det_name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = (COMPONENTS[0], COMPONENTS[1], COMPONENTS[5], COMPONENTS[4])   # Trues, Scattered, SF, NECR
    fig, axes = plt.subplots(4, 2, figsize=(14, 21), constrained_layout=True)
    for col, (rows, cfg) in enumerate(((att, "coil attached"), (det, det_name))):
        for row, (name, key, ylabel) in enumerate(panels):
            ax = axes[row, col]
            _draw(ax, rows, meas, key, ylabel)
            ax.set_title(f"{name}, {cfg}", fontsize=16)
            ax.text(-0.12, 1.06, "abcdefgh"[4 * col + row], transform=ax.transAxes, fontsize=20, va="top", ha="left")
    for row, (_, key, _) in enumerate(panels):          # same y range in both columns
        lo = min(axes[row, c].get_ylim()[0] for c in (0, 1))
        hi = max(axes[row, c].get_ylim()[1] for c in (0, 1))
        if key == "SF_pct":
            lo = min(lo, 5)
        for c in (0, 1):
            axes[row, c].set_ylim(lo, hi)
    _legend(fig, axes)
    fig.savefig(base + "_attached_detached.png", bbox_inches="tight", dpi=300)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), constrained_layout=True)
    for ax, (name, key, ylabel), letter in zip(axes, (COMPONENTS[2], COMPONENTS[3]), "ab"):
        _draw(ax, att, meas, key, ylabel)
        ax.set_title(name, fontsize=16)
        ax.text(-0.12, 1.06, letter, transform=ax.transAxes, fontsize=20, va="top", ha="left")
    _legend(fig, axes)
    fig.savefig(base + "_randoms_totals.png", bbox_inches="tight", dpi=300)
    plt.close(fig)


# ============================================================================================
# 3. Tables
# ============================================================================================
ROW_COLS = (["label", "activity_MBq", "duration_eff_s"]
            + [f"att_{k}" for k in ("R_t", "R_s")] + ["R_r", "R_TOT", "att_R_NEC", "att_SF_pct"]
            + [f"det_{k}" for k in ("R_t", "R_s", "R_NEC", "SF_pct")]
            + ["coil_only_kcps", "ambiguous_kcps", "delayed_kcps", "intrinsic_kcps"]
            + [f"meas_{k}" for _, k, _ in COMPONENTS] + ["note"])


def _cell(v, nd=4):
    if isinstance(v, (float, np.floating)):
        return "nan" if not np.isfinite(v) else f"{v:.{nd}f}"
    return str(v)


def write_tables(base, rows, att, det, mards, reports, args, meas, det_name):
    for r, a in zip(rows, att):                       # measured values (identical for both configurations)
        for _, k, _ in COMPONENTS:
            r[f"meas_{k}"] = a.get(f"meas_{k}", np.nan)
    head = [f"# {os.path.basename(base)}: GATE-truth count rates (analysis of the first submission, no NEMA), "
            f"{len(rows)} files",
            "# whole field of view; T = same eventID without phantomSD scatter, S = same eventID with scatter, "
            "R = different eventID; Totals = T + S + R; NECR = T^2 / Totals; SF = S / (T + S); rates in kcps",
            f"# att = coil attached (runs as they are); det = {det_name} (coincidences scattered only in "
            f"{'+'.join(args.detach)} counted as true; ambiguous ones as {args.ambiguous})",
            f"# meas = {meas['sheet'] if meas else '-'} (vendor NEMA values) at the simulated activity; "
            f"time = {'nominal duration' if args.nominal_time else 'effective (last coincidence)'}"]
    with open(base + ".txt", "w") as f:
        f.write("\n".join(head) + "\n" + "\t".join(ROW_COLS) + "\n")
        for r in rows:
            f.write("\t".join(_cell(r.get(c, np.nan)) for c in ROW_COLS) + "\n")

    lines = head[:3] + [""]
    for (cfg, mard), (_, (report, notes)) in zip(mards, reports):
        lines.append(f"===== {cfg} =====")
        lines.append("MARD (%) = mean |sim - meas| / meas x 100 (frames in brackets)")
        lines.append(f"{'':18s}" + "".join(f"{lab:>20s}" for lab, _ in mard))
        for name in na.MARD_ORDER:
            cells = []
            for _, m in mard:
                v, k = m.get(name, (np.nan, 0))
                cells.append(f"{v:8.2f} % ({k:3d})" if np.isfinite(v) else "-")
            lines.append(f"{name:18s}" + "".join(f"{c:>20s}" for c in cells))
        lines.append("")
        lines.append(f"{'Peaks and system SF':58s}{'simulation':>12s}{'measurement':>12s}  unit   ARD")
        for q in report:
            ard = f"{q['ARD_pct']:.1f} %" if np.isfinite(q["ARD_pct"]) else "-"
            lines.append(f"{q['quantity']:58s}{q['sim']:12.3f}{q['meas']:12.3f}  {q['unit']:6s} {ard}")
        lines += [f"  note: {n}" for n in notes] + [""]
    a = np.array([r["activity_MBq"] for r in rows])
    tot = np.array([r["att_R_t"] for r in rows])
    co = np.array([r["coil_only_kcps"] for r in rows])
    am = np.array([r["ambiguous_kcps"] for r in rows])
    pr = np.array([r["R_TOT"] for r in rows])
    lines += ["===== coil relabelling =====",
              f"coil-only scatter (certain), % of the attached trues: {100 * np.min(co / tot):.2f} ... "
              f"{100 * np.max(co / tot):.2f} (median {100 * np.median(co / tot):.2f})",
              f"ambiguous (last interaction in the coil after another one), % of the attached trues: "
              f"{100 * np.min(am / tot):.2f} ... {100 * np.max(am / tot):.2f} (median {100 * np.median(am / tot):.2f}); "
              f"% of all prompts: median {100 * np.median(am / pr):.2f}",
              f"activities {a.min():.4g} ... {a.max():.4g} MBq"]
    with open(base + "_MARD.txt", "w") as f:
        f.write("\n".join(lines) + "\n")

    try:
        from openpyxl import Workbook
    except ImportError:
        return
    wb = Workbook()
    wb.remove(wb.active)
    for title, crow in (("Attached", att), ("Detached", det)):
        ws = wb.create_sheet(title)
        ws.append([h for h, _, _ in na.PLOTNECR])
        for c in crow:
            ws.append([float(c.get(f"meas_{k}", np.nan) if who == "meas" else c[k]) for _, k, who in na.PLOTNECR])
    ws = wb.create_sheet("MARD")
    for (cfg, mard) in mards:
        ws.append([cfg] + [lab for lab, _ in mard])
        for name in na.MARD_ORDER:
            ws.append([name] + [m.get(name, (np.nan, 0))[0] for _, m in mard])
        ws.append([])
    ws = wb.create_sheet("Peaks")
    ws.append(["configuration", "quantity", "simulation", "measurement", "unit", "ARD (%)"])
    for cfg, (report, _) in reports:
        for q in report:
            ws.append([cfg, q["quantity"], q["sim"], q["meas"], q["unit"], q["ARD_pct"]])
    ws = wb.create_sheet("Details")
    ws.append(ROW_COLS)
    for r in rows:
        ws.append([r.get(c, np.nan) if not isinstance(r.get(c), np.generic) else float(r.get(c)) for c in ROW_COLS])
    for w in wb.worksheets:                          # NaN is not valid in xlsx: empty cells
        for row in w.iter_rows():
            for cell in row:
                if isinstance(cell.value, float) and not np.isfinite(cell.value):
                    cell.value = None
    wb.save(base + ".xlsx")


# ============================================================================================
# 4. Main
# ============================================================================================
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="ROOT files (default: <dir>/NECR_*.root)")
    ap.add_argument("--dir", default="output", help="folder of the ROOT files (default output)")
    ap.add_argument("--results-dir", default="results", help="results/<setup>/necr_truth_<tag>/ (default results)")
    ap.add_argument("--out", default=None, help="file name stem instead of necr_truth_<tag>")
    ap.add_argument("--detach", default="coil",
                    help="volume groups relabelled in 'detached', comma list of " + ", ".join(na.GROUPS) + " (default coil)")
    ap.add_argument("--ambiguous", choices=("scatter", "true"), default="scatter",
                    help="photons with several phantomSD interactions, the last in the coil (default scatter)")
    ap.add_argument("--coil", type=int, choices=(35, 86), default=None, help="measured sheet (default: coil of the run macros)")
    ap.add_argument("--measured", default=na.MEAS_FILE, help="measured workbook")
    ap.add_argument("--measured-sheet", default=None)
    ap.add_argument("--peak-fit", choices=("smooth", "3point", "max"), default="smooth",
                    help="peaks: smooth = polynomial fit in ln(activity) (default); max = the highest frame "
                         "itself (direct comparison, folder name gets '_peakmax'); 3point = parabola through "
                         "the highest frame and its neighbours (folder name gets '_peak3point')")
    ap.add_argument("--peak-fit-deg", type=int, default=na.PEAK_FIT_DEG)
    ap.add_argument("--peak-fit-frac", type=float, default=na.PEAK_FIT_FRAC)
    ap.add_argument("--mard-range", action="append", default=[], help="extra MARD range, e.g. 3-40")
    ap.add_argument("--nominal-time", action="store_true", help="rates per nominal duration (as the old macro)")
    ap.add_argument("--duration", type=float, default=None, help="s, for files without a run macro")
    ap.add_argument("--activity", type=float, default=None, help="MBq, for a single file without a run macro")
    ap.add_argument("--macro", default=None, help="run macro (single file)")
    ap.add_argument("--macro-dirs", nargs="+", default=["macros", "mac_A"])
    ap.add_argument("--source-id", type=int, default=0, help="sourceID of the F-18 source (default 0)")
    ap.add_argument("--jobs", type=int, default=1, help="files analysed in parallel")
    ap.add_argument("--no-plots", action="store_true")
    return ap


def main():
    args = build_parser().parse_args()
    args.detach = [g.strip() for g in args.detach.split(",") if g.strip()]
    bad = [g for g in args.detach if g not in list(na.GROUPS) + ["other"]]
    if bad:
        sys.exit(f"--detach: unknown group(s) {bad}; groups: {list(na.GROUPS) + ['other']}")
    args.mard_ranges = []
    for text in list(na.MARD_RANGES) + list(args.mard_range):
        if na.parse_range(text)[1:] not in [na.parse_range(t)[1:] for t in args.mard_ranges]:
            args.mard_ranges.append(text)
    files = args.files or sorted(glob.glob(os.path.join(args.dir, "NECR_*.root")))
    if not files:
        sys.exit(f"No files found ({args.dir}/NECR_*.root)")

    groups = {}                                       # one analysis per setup and run tag, as necr_analysis
    for f in files:
        info = na.run_settings(f, args.macro, args.macro_dirs)
        m = re.match(r"(?:smoke_)?NECR_(\w+?)_(?:\d+|[\dp]+MBq)$", os.path.splitext(os.path.basename(f))[0])
        tag = m.group(1) if m else None
        groups.setdefault((info.get("setup") or tag or "no_setup", tag), []).append(f)
    if args.out and len(groups) > 1:
        sys.exit("--out with files of several runs: analyse one run at a time")
    variant = ("" if args.detach == ["coil"] else "_detach-" + "-".join(args.detach)) \
        + ("_ambtrue" if args.ambiguous == "true" else "") \
        + ("" if args.peak_fit == "smooth" else "_peak" + args.peak_fit)   # variants never overwrite the default
    for (folder, tag), gfiles in groups.items():
        name = args.out or (f"necr_truth_{tag}" if tag else "necr_truth") + variant
        analyse_set(gfiles, argparse.Namespace(**vars(args)), os.path.join(args.results_dir, folder, name, name))


def analyse_set(files, args, base):
    coils = sorted({na.run_settings(f, args.macro, args.macro_dirs).get("coil_mm") for f in files} - {None})
    if args.coil is None:
        args.coil = coils[0] if len(coils) == 1 and coils[0] in na.MEAS_SHEETS else 35
    sheet = args.measured_sheet or na.MEAS_SHEETS[args.coil]
    print(f"\n===== {base} ({len(files)} files), measurement: '{sheet}' =====")
    meas = None
    mpath = na.find_file(args.measured)
    if mpath:
        meas = na.load_measured(mpath, sheet)
    else:
        print(f"{args.measured} not found: no comparison with the measurement", file=sys.stderr)

    if args.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(process, files, [args] * len(files)))
    else:
        results = [process(f, args) for f in files]
    rows = []
    for r, err in results:
        if err:
            print(f"SKIPPED {err}", file=sys.stderr)
            continue
        rows.append(r)
        print(f"{r['label']}: {r['activity_MBq']:.4f} MBq | attached T {r['att_R_t']:.2f} S {r['att_R_s']:.2f} | "
              f"detached T {r['det_R_t']:.2f} S {r['det_R_s']:.2f} | R {r['R_r']:.2f} TOT {r['R_TOT']:.2f} kcps"
              + (f" | NOTE {r['note']}" if r["note"] else ""))
    if not rows:
        print("no file analysed", file=sys.stderr)
        return
    rows.sort(key=lambda r: -r["activity_MBq"])
    os.makedirs(os.path.dirname(base), exist_ok=True)
    det_name = "coil detached" if args.detach == ["coil"] else "+".join(args.detach) + " detached"
    att, det = config_rows(rows, "att"), config_rows(rows, "det")
    mards = [("coil attached", na.compare(att, meas, args) if meas else []),
             (det_name, na.compare(det, meas, args) if meas else [])]
    reports = [("coil attached", na.nema_report(att, meas, args) if meas else ([], [])),
               (det_name, na.nema_report(det, meas, args) if meas else ([], []))]
    write_tables(base, rows, att, det, mards, reports, args, meas, det_name)
    if not args.no_plots:
        plot_figures(base, att, det, meas, det_name)
    print(open(base + "_MARD.txt").read())
    print(f"Written to {os.path.dirname(base)}/")


if __name__ == "__main__":
    main()
