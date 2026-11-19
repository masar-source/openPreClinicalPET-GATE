#!/usr/bin/env python3
"""
sens_analysis.py
================

NEMA NU 4-2008 sensitivity (section 5) for the GATE model of the Bruker Si 198 PET insert, compared with
the measured axial sensitivity profiles (2021-2022_NEMA_Sensitivity_Masar.xlsx; Kuntner et al. 2025,
EJNMMI Physics 12:63, Fig. 1).

----------------------------------------------------------------------------------------------
1. What the measurement did (the target)
----------------------------------------------------------------------------------------------
  Kuntner et al. 2025 (methods, "Sensitivity") and the measured workbook:
  * Na-22 point source (0.3 mm, in a 10 mm acrylic cube) on the animal cradle, on the scanner
    axis. Activity (cell D2 of each sheet): 127.07 kBq (Quad86), 131.13 kBq (Quad35),
    162.75 kBq (Quad72).
  * Stepped along the axis in 1-2 mm steps from the centre to both ends of the axial FOV,
    60 s per position.
  * 50 % energy window 255.5-766.5 keV, 7 ns coincidence window. "No scatter, no decay, and no
    random correction" (paper).
  * Processing (Bruker, "NEMA Testing" 23-11-2021, Sec. 1.3): lmSinogramCreator.exe makes the
    sinograms (168 radial bins x 193 angles x 150 slices, 0.478602 mm), then
    Sensitivity_analysis.exe <sinogram> 168 193 150 0.478602 <activity Bq>. The measured data
    were processed WITHOUT the background histogram (output files noBG_Sensi_*.txt, with the
    same activities as in the workbook): the Lu-176 background is NOT subtracted.
    Whether Sensitivity_analysis.exe applies NEMA's 1 cm sinogram mask is not documented.
  * Workbook, from row 5: column G = position relative to the centre (mm), column D = counts per
    second per Bq (the header says cps/kBq, but the values are cps/Bq), column E = absolute
    sensitivity = D / 0.906 x 100 %.
  * Centre values: 9.76 % (Quad86), 9.34 % (Quad35), 9.14 % (Quad72); the paper rounds them to
    9.8 / 9.3 / 9.1 %.

----------------------------------------------------------------------------------------------
2. What this script does with every simulated ROOT file (one file = one source position)
----------------------------------------------------------------------------------------------
  NEMA NU 4-2008 Sec. 5.4:
  a. Read all prompt coincidences (Coincidences tree), as the scanner records them.
     --emin/--emax narrow the energy window in the analysis (they cannot widen the window the
     GATE digitizer already applied).
  b. Single-slice rebinning (SSRB): angle and radial coordinate s of every LOR, and the slice
     where the LOR crosses (passes closest to) the scanner axis. Sinogram sampling as in the
     measured Bruker sinograms: 168 radial bins of 0.4786 mm (|s| < 40.2 mm), 193 angles over
     180 deg, slices of --slice mm (default 1 mm) over the 150 mm axial FOV. The interaction
     positions are used as GATE stores them; the 1 cm mask is far wider than the detector blur.
  c. In every sinogram row (slice, angle) the bin with the most counts is found, and all bins
     more than 10 mm from it are set to zero (NEMA's 1 cm mask, --mask nema). All slices are
     summed. --mask source centres the same 1 cm mask on the source's projection in every row
     instead (s = x0 cos(phi) + y0 sin(phi)); it does not depend on the counts per row, so it is
     the one to use for runs shorter than the measured 60 s. On a 60 s run at the centre both
     give the same Na-22 counts (+0.1 %); thinned to 10 s the source-centred mask stays unbiased
     (0.999 +- 0.004).
  d. Background: NEMA subtracts a scan without the source, using the same mask. In the
     simulation these are the Lu-176-only coincidences (neither photon from the Na-22 source).
     The measured values were processed without background subtraction, so by default it is not
     subtracted either (SA_pct, compared with the measured values); --bg-sub subtracts it. The
     NEMA-standard value (mask, background subtracted) is always reported as SA_NEMA_pct.
     The background inside the mask depends on the acquisition time: with few counts per
     sinogram row, the row maximum often sits on a background event and the mask keeps it
     (0.5 s smoke run: 93 % of the Lu-176 events kept). The same happens to the Na-22 scatter
     and other events far from the source: thinning a 60 s centre run gave +9 % masked Na-22
     counts at 0.5 s, +4 % at 10 s and +1 % at 30 s. With --mask nema, compare only runs of
     60 s at the measured activity with the measurement; shorter runs get a warning.
  e. S = (R - R_B) / A in cps/Bq, and S_A = S / 0.906 x 100 %. A is the Na-22 activity
     (decays per second), R and R_B are rates over the acquisition time.
     --no-mask uses all coincidences in the sinogram FOV instead of the 1 cm mask (in case
     Sensitivity_analysis.exe does not apply it); SA_no_mask_pct is always reported.
  f. Comparison with the measured profile of --coil (default Quad86), linearly interpolated at
     the source position (exact at the measured positions), point by point: ARD = |sim - meas|
     / meas x 100 per position, MARD = mean ARD over all positions, and the ARD at the centre of
     the axial FOV (the position closest to 0 mm) as the headline number.
     Two readings of the measured values are reported:
       A: no background in the data   -> sim = GATE with Lu-176 subtracted (SA_NEMA_pct)
       B: the data contain background -> sim = GATE with Lu-176 subtracted + the measured background
     The measured values were processed without background subtraction, so B is the reading to
     use. For the paper I gave the measured background with --meas-bg-cps 415.
     Background for B: --meas-bg-cps if given, else the profile fit (step j) with 10 or more
     positions, else DEFAULT_BG_CPS = 1100 cps. That fallback is the level at both ends of the
     measured profiles (about 1.1-1.2 kcps for all three coils, whatever the activity). It also
     contains scatter from the source just outside the FOV, so it is higher than the background
     itself: give --meas-bg-cps for runs with fewer than 10 positions. The background-free values
     and the QE estimate use the same background. With --mask nema (60 s runs) a third column
     compares as Bruker processed (no subtraction on either side).
  g. Composition of the counts inside the mask, from the GATE truth (diagnostic only; NEMA
     counts all of them).
  h. QE estimate, only when model and measurement use the same energy window: in GATE 8.2 the
     crystalblurring QE accepts each single independently, so the coincidence sensitivity scales
     with QE^2 and QE_match = QE_model x sqrt(S_meas / S_sim). Rerun with that QE to confirm.
  h2. --active-mm N (optional): emulates detector blocks that only use the central N x N mm of
     each 48 x 48 mm face (González et al. 2016: 46 mm). A coincidence is rejected when one of its
     interactions lies closer than (48 - N)/2 mm to its block's side faces. The model reproduces
     the measured profile without it (52 mm ring pitch), so it is off by default. The block
     positions it uses (R_FRONT 58 mm, RING_Z -50, 0, +50 mm) do not follow the model's
     58.5 mm and 52 mm ring pitch.
  i. With three or more positions: NEMA's averages for the mouse (central 7 cm) and rat
     (central 15 cm) lengths and over all positions, for simulation and measurement alike.
  j. With ten or more positions: a fit of the measured profile as meas(z) = k x sim(z) + c. The
     background is a constant rate (a constant c in S_A), while the source signal falls towards
     the ends, so the profile separates the two: k gives the QE (QE_model x sqrt(k)) and c the
     background in cps, without --meas-bg-cps. Large or z-dependent residuals mean that the
     efficiency gap is not uniform. c also takes up any other difference that adds to the profile
     at the ends of the FOV (for example from the mask), so it is not a clean background estimate.

----------------------------------------------------------------------------------------------
3. Usage
----------------------------------------------------------------------------------------------
  pip install uproot numpy matplotlib openpyxl       (matplotlib/openpyxl only for PNG/XLSX)

  python3 sens_analysis.py                               # all output/Sens_*.root (60 s runs)
  python3 sens_analysis.py --mask source                 # runs shorter than 60 s
  python3 sens_analysis.py --dir t86/output --out t86/sens_results --meas-bg-cps 415 --jobs 64
  python3 sens_analysis.py --coil Quad35                 # compare with another coil's sheet
  python3 sens_analysis.py ../spatial_resolution/output/<name>.root   # any Na-22 point-source file
  python3 sens_analysis.py --activity 140000 --duration 60 file.root   # no run macro found

  Activity, duration, source position, QE and energy window are read from the run macro that
  sens_run.py (or spres_run.py) wrote: macros/<name>.mac next to the output/ folder. Command-line
  values override them.

  Outputs:
    <out>.txt          one row per position: simulated and measured absolute sensitivity
    <out>_details.txt  everything per file (counts, composition, settings); sens_seed_stats.py
                       reads this file
    <out>_ARD_MARD.txt point-by-point table (position, measured, simulated, ARD) for readings A
                       and B, with the ARD at the centre of the aFOV and the MARD
    <out>.xlsx         sheets Results, Details, ARD_MARD, NEMA_summary (3+ positions),
                       Profile_fit (10+ positions), Measured, Settings
    <out>_ARD_MARD_all_cases.txt / .xlsx
                       centre ARD and MARD (summary) and the ARD per position for every processing
                       step: (b) no mask, (c) mask, (d) + Lu-176 subtracted, (e) + background, each
                       against the measurement (a)
    <out>_plots/       position_<name>.png per file (masked radial profile, counts per slice),
                       profile.png (measured vs simulated + background (B), ARD per position below),
                       profile_meas_vs_sim.png (only the measurement and the simulation with the
                       mask, Lu-176 subtracted and the measured background added), profile_all_cases.png
                       (the measurement, the simulation with and without the measured background and
                       the simulation without the mask; both figures in the curve styles of the NECR
                       figures: measured black o, simulated red x, red dashed + and red dotted
                       triangles) and, with 10 or more positions, profile_fit.png (the linear fit)

----------------------------------------------------------------------------------------------
4. Assumptions
----------------------------------------------------------------------------------------------
  * The sign of the measured axial positions relative to GATE's +z is not documented. It does
    not matter at the centre; --meas-sign -1 mirrors the measured profile.
  * The sinogram sampling (0.4786 mm, 193 angles, 1 mm slices) is taken from measured Bruker
    sinograms; the 1 cm mask makes the result almost independent of it.
  * I assume that Sensitivity_analysis.exe applies NEMA's 1 cm mask (not documented). On a 60 s
    centre run with the 30 % window the mask removes 12 % of the counts (7.70 % with the mask,
    8.76 % without), which is about 6-7 % in QE (QE^2).
  * The real scanner's background scan contains only Lu-176 events. Using the Lu-176-only
    coincidences of the source run instead assumes the Lu-176 rate does not depend on the
    source, which holds at these activities (deadtime losses well below 1 %). With the default
    (no subtraction, as in the processing of the measured data) the simulated Lu-176 counts stay
    in, so the model's Lu-176 activity (152 kBq, calculated, not measured) enters the comparison;
    it is 0.4 % of the counts in the mask at the centre with the 30 % window.
  * Slice thickness: 1 mm (150 slices, as Bruker's sinograms). 0.5 mm slices would give 1.1 %
    more counts in the mask and 2 mm slices 0.4 % fewer, because the mask in sparse off-source
    rows is placed on noise. A 2 mm FWHM detector blur changes the masked sum by -0.02 %.
"""
# ============================================================================================
# 0. Imports
# ============================================================================================
import argparse          # command-line options
import functools         # --jobs: the per-file work with fixed arguments
import glob              # default file list
import os                # paths
import re                # run-macro parsing
import sys               # warnings

import numpy as np       # all numerics

# ============================================================================================
# 1. Constants
# ============================================================================================
BRANCHING = 0.906           # Na-22 positron branching ratio (NEMA NU 4-2008 Sec. 5.4.1)
MASK_HALF_WIDTH = 10.0      # mm, NEMA: bins more than 1 cm from the row maximum are set to zero
AXIAL_HALF = 75.0           # mm, axial FOV 150 mm
MEAS_WINDOW = (255.5, 766.5)    # keV, Kuntner et al. 2025, sensitivity measurement
MEAS_DURATION = 60.0            # s per position in the measurement
DEFAULT_BG_CPS = 1100.0         # cps, fallback background: the level at the ends of the measured profiles
# Detector blocks, used only by --active-mm: 8 heads x 3 rings of trapezoidal LYSO, entrance face
# 48 x 48 mm at 58 mm from the axis, 50 x 50 mm at the exit face 10 mm deeper, rings at z = -50, 0, +50 mm.
# These are not the model's values (entrance face at 58.5 mm, ring pitch 52 mm).
R_FRONT, DEPTH, HALF_FRONT, TAPER = 58.0, 10.0, 24.0, 0.1
RING_Z = np.array([-50.0, 0.0, 50.0])
HEAD_STEP = np.pi / 4
MEAS_SHEETS = ("Quad86", "Quad35", "Quad72")
CATEGORIES = (("na_unscattered", "Na-22 pair, unscattered"),
              ("na_scattered", "Na-22 pair, scattered in a passive volume"),
              ("random", "random (two decays)"),
              ("lu_only", "Lu-176 only (background)"))

BRANCHES = [f"globalPos{k}{s}" for s in (1, 2) for k in "XYZ"] + \
           ["eventID1", "eventID2", "sourceID1", "sourceID2", "sourcePosX1", "sourcePosY1", "sourcePosZ1",
            "energy1", "energy2",
            "time1", "comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2"]


# ============================================================================================
# 2. Reading the GATE ROOT file and its run macro
# ============================================================================================
def load(path):
    """Prompt and delayed coincidences of one GATE file as dicts of numpy arrays."""
    import uproot                                   # only needed for ROOT input
    with uproot.open(path) as f:
        out = {}
        for tree_name in ("Coincidences", "delay"):
            if tree_name not in [k.split(";")[0] for k in f.keys()]:
                out[tree_name] = None
                continue
            tree = f[tree_name]
            names = [b for b in BRANCHES if b in tree.keys()]
            out[tree_name] = tree.arrays(names, library="np")
    if out["Coincidences"] is None:
        raise ValueError("no Coincidences tree")
    return out["Coincidences"], out["delay"]


def run_settings(root_path, macro=None):
    """Settings of the run from the macro sens_run.py / spres_run.py wrote (macros/<name>.mac).

    Returns a dict with any of: activity, duration, sourceX/Y/Z, qe, e_low, e_high, lu176, macro.
    """
    if macro is None:
        stem = os.path.splitext(os.path.basename(root_path))[0]
        project = os.path.dirname(os.path.dirname(os.path.abspath(root_path)))
        macro = os.path.join(project, "macros", stem + ".mac")
    if not os.path.isfile(macro):
        return {}
    info = {"macro": macro}
    active = [ln.strip() for ln in open(macro, errors="replace") if not ln.lstrip().startswith("#")]
    aliases = {}
    for ln in active:
        m = re.match(r"/control/alias\s+(\w+)\s+(\S+)", ln)
        if m:
            aliases[m.group(1)] = m.group(2)

    def value(pattern):
        for ln in active:
            m = re.match(pattern, ln)
            if m:
                v = m.group(1)
                v = aliases.get(v.strip("{}"), v) if v.startswith("{") else v
                try:
                    return float(v)
                except ValueError:
                    return None
        return None

    for key in ("activity", "duration", "sourceX", "sourceY", "sourceZ"):
        if key in aliases:
            try:
                info[key] = float(aliases[key])
            except ValueError:
                pass
    if "activity" not in info:
        v = value(r"/gate/source/Na22PointSource/setActivity\s+(\S+)")
        if v is not None:
            info["activity"] = v
    info["qe"] = value(r"/gate/digitizer/Singles/crystalblurring/setCrystalQE\s+(\S+)")
    info["e_low"] = value(r"/gate/digitizer/Singles/thresholder/setThreshold\s+(\S+)")
    info["e_high"] = value(r"/gate/digitizer/Singles/upholder/setUphold\s+(\S+)")
    info["lu176"] = any(ln.startswith("/gate/source/Lu176CrystalSource/setActivity") for ln in active)
    return {k: v for k, v in info.items() if v is not None}


# ============================================================================================
# 3. Sinograms and the NEMA mask
# ============================================================================================
def sinogram_bins(a, args):
    """Sinogram row (slice x angle) and radial bin of every coincidence; -1 = outside the FOV.

    Angle phi in [0, pi) and s = x cos(phi) + y sin(phi) along the LOR; the slice is the axial
    position where the LOR passes closest to the scanner axis (SSRB).
    """
    p1 = np.stack([a["globalPosX1"], a["globalPosY1"], a["globalPosZ1"]], 1).astype(float)
    p2 = np.stack([a["globalPosX2"], a["globalPosY2"], a["globalPosZ2"]], 1).astype(float)
    d = p2 - p1
    lxy2 = np.maximum(d[:, 0] ** 2 + d[:, 1] ** 2, 1e-12)
    phi = np.mod(np.arctan2(-d[:, 0], d[:, 1]), np.pi)
    s = p1[:, 0] * np.cos(phi) + p1[:, 1] * np.sin(phi)
    lam = -(p1[:, 0] * d[:, 0] + p1[:, 1] * d[:, 1]) / lxy2
    z = p1[:, 2] + lam * d[:, 2]

    n_slices = int(round(2 * AXIAL_HALF / args.slice))
    view = np.minimum((phi / np.pi * args.views).astype(int), args.views - 1)
    s_bin = np.floor(s / args.sino_ds + args.sino_bins / 2).astype(int)
    z_bin = np.floor((z + AXIAL_HALF) / args.slice).astype(int)
    inside = (s_bin >= 0) & (s_bin < args.sino_bins) & (z_bin >= 0) & (z_bin < n_slices)
    row = np.where(inside, z_bin * args.views + view, -1)
    return row, np.where(inside, s_bin, -1), z, n_slices


def nema_peaks(row, s_bin, n_rows, n_bins):
    """Radial bin of the maximum in every sinogram row (prompts of the source acquisition)."""
    ok = row >= 0
    counts = np.bincount(row[ok] * n_bins + s_bin[ok], minlength=n_rows * n_bins).reshape(n_rows, n_bins)
    return counts.argmax(axis=1), counts.sum(axis=1) > 0


def source_peaks(x0, y0, n_slices, args):
    """Mask centre in every sinogram row from the known source position instead of the row maximum.

    The projection of the point (x0, y0) in view phi is s = x0 cos(phi) + y0 sin(phi), the same in
    every slice. Unlike the row maximum, this does not depend on how many counts a row holds.
    """
    phi = (np.arange(args.views) + 0.5) * np.pi / args.views
    centre = np.floor((x0 * np.cos(phi) + y0 * np.sin(phi)) / args.sino_ds + args.sino_bins / 2).astype(int)
    return np.tile(centre, n_slices)


def in_mask(row, s_bin, peaks, half_bins):
    """True for coincidences inside the FOV and within the 1 cm mask of their sinogram row."""
    ok = row >= 0
    out = np.zeros(len(row), bool)
    out[ok] = np.abs(s_bin[ok] - peaks[row[ok]]) <= half_bins
    return out


def in_active_area(x, y, z, active_mm):
    """True where an interaction lies inside the active area of its block.

    Emulates a detector that only uses the central active_mm x active_mm of each 48 x 48 mm block
    face (González et al. 2016: 46 mm): interactions closer than (48 - active_mm) / 2 mm to the
    block's tangential or axial side faces, measured at their own depth, are rejected.
    """
    ang = np.round(np.arctan2(y, x) / HEAD_STEP) * HEAD_STEP
    depth = np.clip(x * np.cos(ang) + y * np.sin(ang), R_FRONT, R_FRONT + DEPTH)
    tang = -x * np.sin(ang) + y * np.cos(ang)
    half = HALF_FRONT + TAPER * (depth - R_FRONT) - (2 * HALF_FRONT - active_mm) / 2.0
    ring = RING_Z[np.argmin(np.abs(z[:, None] - RING_Z[None, :]), axis=1)]
    return (np.abs(tang) <= half) & (np.abs(z - ring) <= half)


def active_cut(a, active_mm):
    """Keep only coincidences whose two interactions both lie in the active area."""
    keep = np.ones(len(a["eventID1"]), bool)
    for s in "12":
        keep &= in_active_area(a[f"globalPosX{s}"].astype(float), a[f"globalPosY{s}"].astype(float),
                               a[f"globalPosZ{s}"].astype(float), active_mm)
    return {k: v[keep] for k, v in a.items()}, float(keep.mean()) if len(keep) else np.nan


def categories(a, na_id):
    """GATE-truth class of every coincidence (diagnostic; NEMA does not use it)."""
    na1, na2 = a["sourceID1"] == na_id, a["sourceID2"] == na_id
    same = a["eventID1"] == a["eventID2"]
    scat = np.zeros(len(same), bool)
    for k in ("comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2"):
        if k in a:
            scat |= a[k] > 0
    lu_only = ~na1 & ~na2
    return {"na_unscattered": same & na1 & na2 & ~scat,
            "na_scattered": same & na1 & na2 & scat,
            "random": ~same & ~lu_only,
            "lu_only": lu_only}


# ============================================================================================
# 4. Measured profiles (2021-2022_NEMA_Sensitivity_Masar.xlsx, Kuntner et al. 2025)
# ============================================================================================
def find_measured(path):
    if path and os.path.isfile(path):
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, os.path.basename(path or "")), os.path.join(os.getcwd(), os.path.basename(path or ""))):
        if os.path.isfile(cand):
            return cand
    return None


def load_measured(path):
    """{sheet: dict(pos, S, SA, activity, source)} from the measured workbook.

    Positions (column G) are relative to the centre, as in the workbook. Repeated
    positions are averaged. Formula cells are read through their cached values.
    """
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    out = {}
    for name in wb.sheetnames:
        ws = wb[name]
        pos, s, sa = [], [], []
        for r in ws.iter_rows(min_row=5, values_only=True):
            if len(r) < 7 or not all(isinstance(v, (int, float)) for v in (r[6], r[3], r[4])):
                continue
            pos.append(float(r[6]))
            s.append(float(r[3]))
            sa.append(float(r[4]))
        if not pos:
            continue
        pos, s, sa = np.round(np.array(pos), 3), np.array(s), np.array(sa)
        u = np.unique(pos)
        out[name] = {"pos": u,
                     "S": np.array([s[pos == p].mean() for p in u]),
                     "SA": np.array([sa[pos == p].mean() for p in u]),
                     "activity": ws["D2"].value, "source": ws["A1"].value}
    return out


def measured_at(meas, z, sign):
    """Measured absolute sensitivity (%) linearly interpolated at GATE position z (mm)."""
    pos = sign * meas["pos"]
    order = np.argsort(pos)
    pos, sa = pos[order], meas["SA"][order]
    if z < pos[0] or z > pos[-1]:
        return np.nan
    return float(np.interp(z, pos, sa))


# ============================================================================================
# 5. One file
# ============================================================================================
def analyse_file(path, args, measured):
    a, delayed = load(path)
    info = run_settings(path, args.macro)
    activity = args.activity or info.get("activity")
    duration = args.duration or info.get("duration")
    qe = args.qe or info.get("qe", np.nan)
    if not activity or not duration:
        raise ValueError("activity/duration unknown: no run macro found, give --activity and --duration")

    # energy window: digitizer (macro or data) and the optional analysis cut
    e1, e2 = a["energy1"] * 1e3, a["energy2"] * 1e3            # keV
    e_low = info.get("e_low", float(np.floor(min(e1.min(), e2.min()))))
    e_high = info.get("e_high", float(np.ceil(max(e1.max(), e2.max()))))
    if args.emin is not None or args.emax is not None:
        lo = max(e_low, args.emin if args.emin is not None else e_low)
        hi = min(e_high, args.emax if args.emax is not None else e_high)
        if (args.emin is not None and args.emin < e_low - 0.5) or (args.emax is not None and args.emax > e_high + 0.5):
            print(f"  {os.path.basename(path)}: the digitizer window is {e_low:g}-{e_high:g} keV; "
                  f"the analysis cannot widen it (using {lo:g}-{hi:g} keV)", file=sys.stderr)
        keep = (e1 >= lo) & (e1 <= hi) & (e2 >= lo) & (e2 <= hi)
        a = {k: v[keep] for k, v in a.items()}
        e_low, e_high = lo, hi
    window_matches = abs(e_low - MEAS_WINDOW[0]) < 1.0 and abs(e_high - MEAS_WINDOW[1]) < 1.0

    active_kept = 1.0
    if args.active_mm:                              # emulated inactive block edges
        a, active_kept = active_cut(a, args.active_mm)
        if delayed is not None and len(delayed["eventID1"]):
            delayed, _ = active_cut(delayed, args.active_mm)

    t_last = float(a["time1"].max()) if len(a["time1"]) else np.nan
    if np.isfinite(t_last) and not (0.97 * duration <= t_last <= 1.001 * duration):
        print(f"  {os.path.basename(path)}: last coincidence at {t_last:.3f} s but duration "
              f"{duration:g} s: check --duration", file=sys.stderr)

    cls = categories(a, args.source_id)
    na_pairs = cls["na_unscattered"] | cls["na_scattered"]
    src = {}
    for k in "XYZ":
        data = float(np.median(a[f"sourcePos{k}1"][na_pairs])) if na_pairs.any() else np.nan
        src[k] = info.get(f"source{k}", data)
    z_src = src["Z"]

    row, s_bin, z_cross, n_slices = sinogram_bins(a, args)
    n_rows = n_slices * args.views
    if args.mask == "source":
        peaks = source_peaks(src["X"], src["Y"], n_slices, args)
    else:
        peaks, _ = nema_peaks(row, s_bin, n_rows, args.sino_bins)
    half_bins = int(np.floor(MASK_HALF_WIDTH / args.sino_ds + 1e-9))
    mask = in_mask(row, s_bin, peaks, half_bins)
    fov = row >= 0
    bg = cls["lu_only"]

    n_mask, n_bg_mask = int(mask.sum()), int((mask & bg).sum())
    n_fov, n_bg_fov = int(fov.sum()), int((fov & bg).sum())
    scale = 100.0 / (duration * activity * BRANCHING)            # counts -> absolute sensitivity %
    n_sel, n_bg_sel = (n_fov, n_bg_fov) if args.no_mask else (n_mask, n_bg_mask)
    sa = (n_sel - (n_bg_sel if args.bg_sub else 0)) * scale       # the value compared with the measurement
    sa_err = np.sqrt(n_sel + (n_bg_sel if args.bg_sub else 0)) * scale
    n_delay_mask = 0
    if delayed is not None and len(delayed["eventID1"]):
        drow, dsb, _, _ = sinogram_bins(delayed, args)
        n_delay_mask = int(in_mask(drow, dsb, peaks, half_bins).sum())

    meas_sa = np.nan
    if measured and args.coil in measured:
        meas_sa = measured_at(measured[args.coil], z_src, args.meas_sign)
    # The comparison as the measurement was processed (no subtraction) needs the same mask behaviour
    # on the background as Bruker's per-row maximum at 60 s, so it is only made with --mask nema.
    raw_ok = np.isfinite(meas_sa) and args.mask == "nema"
    ratio = sa / meas_sa if raw_ok else np.nan
    qe_match = qe * np.sqrt(meas_sa / sa) if (window_matches and raw_ok and np.isfinite(qe)) else np.nan
    sa_free = (n_mask - n_bg_mask) * scale

    stem = os.path.splitext(os.path.basename(path))[0]
    r = {"file": os.path.basename(path), "label": stem, "z_mm": z_src,
         "activity_Bq": float(activity), "duration_s": float(duration),
         "window_keV": f"{e_low:g}-{e_high:g}", "window_as_measured": bool(window_matches),
         "QE_model": qe, "lu176_in_model": info.get("lu176", "?"),
         "active_mm": args.active_mm if args.active_mm else 48.0, "active_area_kept": active_kept,
         "prompts": len(row), "prompts_in_FOV": n_fov, "in_mask": n_mask,
         "bg_in_mask": n_bg_mask, "bg_in_FOV": n_bg_fov, "bg_kept_by_mask": n_bg_mask / max(1, n_bg_fov),
         "delayed_in_mask": n_delay_mask,
         "source_slice_fraction": float(np.mean(np.abs(z_cross[mask] - z_src) <= args.slice / 2)) if n_mask else np.nan,
         "method": ("all FOV" if args.no_mask else f"1 cm mask ({args.mask})")
                   + (", Lu-176 subtracted" if args.bg_sub else ", no background subtraction"),
         "S_cps_per_Bq": sa / 100.0 * BRANCHING, "SA_pct": sa, "SA_err_pct": sa_err,
         "SA_NEMA_pct": sa_free,
         "SA_mask_noBG_pct": n_mask * scale,
         "SA_no_mask_pct": n_fov * scale,
         "meas_coil": args.coil, "meas_SA_pct": meas_sa,
         "ratio_sim_meas": ratio, "diff_pct": (ratio - 1) * 100 if np.isfinite(ratio) else np.nan,
         "QE_to_match": qe_match,
         # filled in by compare_with_measurement() once the background of the measurement is set:
         "meas_bg_cps": np.nan, "meas_SA_bgfree_pct": np.nan, "ratio_bgfree": np.nan,
         "QE_to_match_bgfree": np.nan, "sim_plus_bg_pct": np.nan,
         "ARD_noBG_pct": np.nan, "ARD_withBG_pct": np.nan, "ARD_asProcessed_pct": np.nan,
         "note": "; ".join(n for n in (
                  f"energy window {e_low:g}-{e_high:g} keV differs from the measured "
                  f"{MEAS_WINDOW[0]:g}-{MEAS_WINDOW[1]:g} keV: sim and meas are not comparable"
                  if not window_matches else "",
                  f"{duration:g} s is shorter than the measured {MEAS_DURATION:g} s: with fewer counts per "
                  "sinogram row the 1 cm mask keeps more background and more Na-22 scatter, so all values are "
                  "biased high (Na-22 counts in the mask, 30 % window test: +9 % at 0.5 s, +4 % at 10 s, "
                  "+1 % at 30 s; Lu-176 much more); run 60 s or use --mask source"
                  if (duration < 0.95 * MEAS_DURATION and args.mask == "nema") else "",
                  "a QE above 1 would be needed: the gap is not (only) the QE"
                  if qe_match > 1 else "") if n),
         "macro": info.get("macro", "")}
    for key, _ in CATEGORIES:
        r[f"mask_frac_{key}"] = float((mask & cls[key]).sum() / n_mask) if n_mask else np.nan
    r["randoms_to_trues_in_mask"] = (float((mask & cls["random"]).sum() / max(1, (mask & na_pairs).sum())))

    plot_data = {"row": row, "s_bin": s_bin, "z_cross": z_cross, "peaks": peaks, "cls": cls,
                 "half_bins": half_bins}
    return r, plot_data


# ============================================================================================
# 6. NEMA summary over several positions (Sec. 5.4.1)
# ============================================================================================
def nema_summary(rows, measured, args):
    """Mean absolute sensitivity over the central 7 cm (mouse), central 15 cm (rat) and all."""
    z = np.array([r["z_mm"] for r in rows])
    sa = np.array([r["SA_pct"] for r in rows])
    sa_free = np.array([r["SA_NEMA_pct"] for r in rows])
    out = []
    meas = measured.get(args.coil) if measured else None
    for name, half in (("mouse (central 70 mm)", 35.0), ("rat (central 150 mm)", 75.0), ("all positions", np.inf)):
        sel = np.abs(z) <= half
        m_val = np.nan
        if meas is not None:
            mp = args.meas_sign * meas["pos"]
            msel = np.abs(mp) <= half
            m_val = float(meas["SA"][msel].mean()) if msel.any() else np.nan
        out.append({"length": name, "n_sim": int(sel.sum()),
                    "sim_SA_pct": float(sa[sel].mean()) if sel.any() else np.nan,
                    "sim_SA_NEMA_pct": float(sa_free[sel].mean()) if sel.any() else np.nan,
                    "meas_SA_pct": m_val})
    return out


def profile_fit(rows, measured, args):
    """Fit the measured profile as meas(z) = k x sim(z) + c over all simulated positions.

    sim = GATE with Lu-176 subtracted (SA_NEMA_pct), meas = the values as measured (no
    subtraction). The background is a constant rate, so in S_A it is the same constant c at every
    position, while the source signal falls towards the ends of the FOV: the profile shape
    separates the two. k is the efficiency ratio meas/sim (QE_fit = QE_model x sqrt(k)), and
    c / 100 x 0.906 x the measured activity is the background in cps. Assumes k is the same at every z
    (a uniform efficiency such as the QE); inactive block edges would show up as a z-dependent
    residual. Needs 10 or more positions.
    """
    if not measured or args.coil not in measured:
        return None
    sim = np.array([r["SA_NEMA_pct"] for r in rows])
    meas = np.array([r["meas_SA_pct"] for r in rows])
    ok = np.isfinite(sim) & np.isfinite(meas)
    if ok.sum() < 10 or np.ptp(sim[ok]) < 0.5:      # needs a real spread of positions along z
        return None
    k, c = np.polyfit(sim[ok], meas[ok], 1)
    resid = meas[ok] - (k * sim[ok] + c)
    qe = np.array([r["QE_model"] for r in rows], float)
    qe_model = float(np.nanmedian(qe)) if np.isfinite(qe).any() else np.nan
    windows_ok = all(r["window_as_measured"] for r in rows)
    return {"n_positions": int(ok.sum()), "k_meas_over_sim": float(k), "c_pct": float(c),
            "bg_cps": float(c / 100.0 * BRANCHING * measured[args.coil]["activity"]),
            "QE_fit": float(qe_model * np.sqrt(k)) if (windows_ok and k > 0) else np.nan,
            "rms_residual_pct": float(np.sqrt(np.mean(resid ** 2))),
            "max_abs_residual_pct": float(np.max(np.abs(resid)))}


def compare_with_measurement(rows, measured, args, bg_cps):
    """Point-by-point comparison with the measured values: ARD per position and MARD.

    ARD = |sim - meas| / meas x 100 at every position, MARD = mean of the ARDs. Two readings of
    the measured data, side by side:
      A (noBG)   : the values contain no background  -> sim = GATE with Lu-176 subtracted
      B (withBG) : the values contain bg_cps of background -> sim = GATE with Lu-176 subtracted
                   + bg_cps / (0.906 x measured activity)
    B is the reading to use, because the measured data were processed without background subtraction.
    With --mask nema (60 s runs) also: as processed = GATE without subtraction (SA_pct), like
    Bruker's noBG processing. The background-free values and the QE estimate use the same bg_cps.
    Returns the summary: the centre of the axial FOV (position closest to 0 mm) and the MARDs.
    """
    if not measured or args.coil not in measured:
        return None
    c_pct = bg_cps / (BRANCHING * measured[args.coil]["activity"]) * 100.0
    as_processed = args.mask == "nema" and not args.bg_sub and not args.no_mask
    for r in rows:
        meas, sim = r["meas_SA_pct"], r["SA_NEMA_pct"]
        r["meas_bg_cps"] = bg_cps
        if not np.isfinite(meas):
            continue
        free = meas - c_pct
        r["meas_SA_bgfree_pct"] = free
        r["ratio_bgfree"] = sim / free if free > 0 else np.nan
        if r["window_as_measured"] and np.isfinite(r["QE_model"]) and free > 0:
            r["QE_to_match_bgfree"] = r["QE_model"] * np.sqrt(free / sim)
            if r["QE_to_match_bgfree"] > 1 and "QE above 1" not in r["note"]:
                r["note"] = "; ".join(n for n in (r["note"], "a QE above 1 would be needed: the gap is not "
                                                  "(only) the QE") if n)
        r["sim_plus_bg_pct"] = sim + c_pct
        r["ARD_noBG_pct"] = abs(sim - meas) / meas * 100.0
        r["ARD_withBG_pct"] = abs(sim + c_pct - meas) / meas * 100.0
        if as_processed:
            r["ARD_asProcessed_pct"] = abs(r["SA_pct"] - meas) / meas * 100.0
    ok = [r for r in rows if np.isfinite(r["ARD_noBG_pct"])]
    if not ok:
        return None
    centre = min(ok, key=lambda r: abs(r["z_mm"]))

    def mard(key):
        v = [r[key] for r in ok if np.isfinite(r[key])]
        return float(np.mean(v)) if v else np.nan
    return {"bg_cps": bg_cps, "bg_pct": c_pct, "n_positions": len(ok), "centre": centre,
            "MARD_noBG_pct": mard("ARD_noBG_pct"), "MARD_withBG_pct": mard("ARD_withBG_pct"),
            "MARD_asProcessed_pct": mard("ARD_asProcessed_pct") if as_processed else np.nan}


# ============================================================================================
# 7. Figures
# ============================================================================================
def plot_position(fname, r, d, args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = d["row"] >= 0
    ds_mm = (d["s_bin"][ok] - d["peaks"][d["row"][ok]]) * args.sino_ds
    edges = np.arange(-args.sino_bins, args.sino_bins + 1) * args.sino_ds - args.sino_ds / 2
    colours = {"na_unscattered": "#1f77b4", "na_scattered": "#ff7f0e", "random": "#2ca02c", "lu_only": "#7f7f7f"}

    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    ax = axs[0]
    bottom = np.zeros(len(edges) - 1)
    for key, label in CATEGORIES:
        h, _ = np.histogram(ds_mm[d["cls"][key][ok]], edges)
        ax.bar(edges[:-1], h, width=np.diff(edges), bottom=bottom, align="edge",
               color=colours[key], label=label, linewidth=0)
        bottom += h
    for x in (-MASK_HALF_WIDTH, MASK_HALF_WIDTH):
        ax.axvline(x, color="k", ls="--", lw=1)
    ax.set_yscale("log")
    ax.set_ylim(bottom=0.5)
    ax.set_xlim(-45, 45)
    ax.set_xlabel("distance from the mask centre in the sinogram (mm)")
    ax.set_ylabel("coincidences (all slices and angles)")
    ax.set_title(f"radial profile, 1 cm mask (dashed), centred on the "
                 f"{'source projection' if args.mask == 'source' else 'row maximum'}")
    ax.legend(fontsize=8, loc="upper right")

    ax = axs[1]
    zb = np.arange(-AXIAL_HALF, AXIAL_HALF + args.slice, args.slice)
    allz = d["z_cross"][ok]
    h_all, _ = np.histogram(allz, zb)
    h_bg, _ = np.histogram(allz[d["cls"]["lu_only"][ok]], zb)
    centres = 0.5 * (zb[1:] + zb[:-1])
    ax.step(centres, np.maximum(h_all, 0.5), where="mid", color="#1f77b4", label="all prompts")
    ax.step(centres, np.maximum(h_bg, 0.5), where="mid", color="#7f7f7f", label="Lu-176 only")
    ax.axvline(r["z_mm"], color="k", ls=":", lw=1, label=f"source z = {r['z_mm']:.1f} mm")
    ax.set_yscale("log")
    ax.set_ylim(bottom=0.5)
    ax.set_xlabel("SSRB slice: axial position where the LOR crosses the axis (mm)")
    ax.set_ylabel(f"coincidences per {args.slice:g} mm slice")
    ax.set_title("counts per slice")
    ax.legend(fontsize=8, loc="upper right")

    meas = (f"   measured ({r['meas_coil']}) {r['meas_SA_pct']:.2f} %, sim/meas {r['ratio_sim_meas']:.3f}"
            if np.isfinite(r["meas_SA_pct"]) else "")
    fig.suptitle(f"{r['file']}: z = {r['z_mm']:.1f} mm, window {r['window_keV']} keV, QE {r['QE_model']:g}\n"
                 f"absolute sensitivity {r['SA_pct']:.2f} ± {r['SA_err_pct']:.2f} %{meas}"
                 + ("" if r["window_as_measured"] else "\nWINDOW DIFFERS FROM THE MEASUREMENT (255.5-766.5 keV)"),
                 fontsize=10)
    fig.savefig(fname, dpi=130)
    plt.close(fig)


def mask_label(args):
    """Which 1 cm mask the simulated values went through, for the figure legends."""
    return "1 cm mask (" + ("NEMA, row maximum" if args.mask == "nema" else "source-centred") + ")"


def plot_measured(ax, measured, args, style, **kw):
    """The whole measured profile (all workbook positions)."""
    m = measured[args.coil]
    pos = args.meas_sign * m["pos"]
    o = np.argsort(pos)
    ax.plot(pos[o], m["SA"][o], style, **kw)
    return list(m["SA"])


def profile_axes(ax, top):
    """Axes of the profile figures (the same layout in all of them)."""
    ax.set_ylim(0, top)
    ax.set_yticks(range(0, int(np.ceil(top)) + 1))
    ax.set_ylabel("Absolute Sensitivity (%)", fontsize=12)
    ax.set_xlabel("Axial Position (mm)", fontsize=12)
    ax.axvline(0, color="black", linewidth=1, linestyle=(0, (1, 5)))
    ax.grid(True, alpha=0.5)
    ax.set_xlim(-80, 80)


def plot_profile(fname, rows, measured, args, comp):
    """Axial sensitivity profile, measurement vs simulation, with the ARD per position below."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(2, 1, figsize=(9, 8), sharex=True, constrained_layout=True,
                            gridspec_kw={"height_ratios": [3, 1.3]})
    ax = axs[0]
    if measured and args.coil in measured:
        m = measured[args.coil]
        o = np.argsort(args.meas_sign * m["pos"])
        ax.plot((args.meas_sign * m["pos"])[o], m["SA"][o], "-o", color="black", ms=4, lw=1.6,
                label=f"Measurements ({args.coil})")
    rows = sorted(rows, key=lambda r: r["z_mm"])
    z = np.array([r["z_mm"] for r in rows])
    window = "" if all(r["window_as_measured"] for r in rows) else " (window differs!)"
    # The Lu-176-subtracted-only case (reading A) is in profile_all_cases.png, not here.
    series = []
    if comp:
        series.append(("sim_plus_bg_pct", "ARD_withBG_pct", "tab:blue", "--+",
                       f"Simulations + {comp['bg_cps']:.0f} cps background (B)"))
        if np.isfinite(comp["MARD_asProcessed_pct"]):
            series.append(("SA_pct", "ARD_asProcessed_pct", "tab:green", ":s",
                           "Simulations, no subtraction (as processed)"))
    else:                                           # no measurement: nothing to add the background to
        series.append(("SA_NEMA_pct", "ARD_noBG_pct", "tab:red", "-x", "Simulations, Lu-176 subtracted"))
    for key, _, col, style, label in series:
        ax.plot(z, [r[key] for r in rows], style, color=col, ms=6 if "x" in style else 5, lw=1.4,
                label=label + window)
    top = max(10.0, np.nanmax([r[s[0]] for r in rows for s in series]) * 1.05)
    ax.set_ylim(0, top)
    ax.set_yticks(range(0, int(np.ceil(top)) + 1))
    ax.set_ylabel("Absolute Sensitivity (%)", fontsize=12)
    ax.axvline(0, color="black", linewidth=1, linestyle=(0, (1, 5)))
    ax.grid(True, alpha=0.5)
    ax.legend(fontsize=9, loc="lower center", frameon=True)
    title = f"Axial sensitivity profile, {args.coil}"
    if comp:
        c = comp["centre"]
        title += (f"\ncentre (z = {c['z_mm']:.1f} mm): ARD B {c['ARD_withBG_pct']:.2f} %  |  "
                  f"MARD over {comp['n_positions']} positions: B {comp['MARD_withBG_pct']:.2f} %")
    ax.set_title(title, fontsize=11)

    ax = axs[1]
    for _, ard, col, style, label in series:
        vals = [r[ard] for r in rows]
        if np.isfinite(vals).any():
            ax.plot(z, vals, style, color=col, ms=5, lw=1.0)
    ax.axvline(0, color="black", linewidth=1, linestyle=(0, (1, 5)))
    ax.set_ylim(bottom=0)
    ax.set_ylabel("ARD (%)", fontsize=12)
    ax.set_xlabel("Axial Position (mm)", fontsize=12)
    ax.grid(True, alpha=0.5)
    ax.set_xlim(-80, 80)
    fig.savefig(fname, dpi=150)
    plt.close(fig)


# Curve styles of the NECR figures (necr_analysis.py), so that all paper figures match: measured black
# circles, simulation red crosses (matplotlib "tab:red" = #d62728), a second simulated curve red, dashed,
# with "+" markers, and a third red, dotted, with triangles.
MEAS_STYLE = dict(marker="o", markersize=3, color="black", linewidth=1.5)
SIM_STYLE = dict(marker="x", color="tab:red", linewidth=1.4)
SIM2_STYLE = dict(marker="+", linestyle="--", color="tab:red", linewidth=1.0)
SIM3_STYLE = dict(marker="^", markersize=4, linestyle=":", color="tab:red", linewidth=1.0)


def lu_label(rows):
    """', Lu-176 subtracted' when the model had Lu-176 (otherwise there is nothing to subtract)."""
    return ", Lu-176 subtracted" if any(r.get("lu176_in_model") is True for r in rows) else ""


def plot_meas_vs_sim(fname, rows, measured, args, comp):
    """Standalone figure: the measurement and the simulation as compared with it (1 cm mask,
    Lu-176 subtracted if in the model, + the measured background), nothing else and no ARD panel.
    Curve styles as the NECR figures (MEAS_STYLE, SIM_STYLE)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = sorted(rows, key=lambda r: r["z_mm"])
    z = np.array([r["z_mm"] for r in rows])
    if not all(r["window_as_measured"] for r in rows):
        print(f"WARNING {fname}: the energy window differs from the measurement", file=sys.stderr)
    fig = plt.figure(figsize=(9, 6.5), constrained_layout=True)   # width, height in inches
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 0.06])          # plot, then the legend row below it
    ax = fig.add_subplot(gs[0])
    # legend: only "Measurement" and "Simulation"; what the simulated curve contains (1 cm mask,
    # + measured background) belongs in the figure caption
    vals = plot_measured(ax, measured, args, "-", **MEAS_STYLE, label="Measurement")
    sim = [r["sim_plus_bg_pct"] for r in rows]
    ax.plot(z, sim, **SIM_STYLE, label="Simulation")
    profile_axes(ax, max(10.0, np.nanmax(vals + sim) * 1.05))
    lax = fig.add_subplot(gs[1])                     # legend below the plot, as in the spatial resolution and NECR figures
    lax.axis("off")
    lax.legend(*ax.get_legend_handles_labels(), loc="center", ncol=2, frameon=False, fontsize=10)
    c = comp["centre"]
    ax.set_title(f"Axial sensitivity profile, {args.coil}\ncentre (z = {c['z_mm']:.1f} mm): ARD "
                 f"{c['ARD_withBG_pct']:.2f} %  |  MARD over {comp['n_positions']} positions: "
                 f"{comp['MARD_withBG_pct']:.2f} %", fontsize=11)
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def plot_all_cases(fname, rows, measured, args, comp):
    """The simulation with and without the measured background and without the NEMA mask, against the
    measurement, no ARD panel; four curves in the styles of the NECR figures:
      measured (black o); simulation, 1 cm mask, + the measured background (red x, solid: the curve
      compared in reading B); simulation, 1 cm mask, without the background (red +, dashed: reading A);
      simulation without the mask (all coincidences in the sinogram FOV), without the background (red
      triangles, dotted).
    The remaining step (mask without Lu-176 subtraction) stays in <out>_ARD_MARD_all_cases."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = sorted(rows, key=lambda r: r["z_mm"])
    z = np.array([r["z_mm"] for r in rows])
    window = "" if all(r["window_as_measured"] for r in rows) else " (window differs!)"
    have_meas = bool(measured and args.coil in measured)
    mask = mask_label(args) + lu_label(rows)
    fig, ax = plt.subplots(figsize=(10, 6.5), constrained_layout=True)
    vals = []
    if have_meas:
        vals += plot_measured(ax, measured, args, "-", **MEAS_STYLE, label=f"Measurements ({args.coil})")
    series = []
    if comp:
        series.append(("sim_plus_bg_pct", SIM_STYLE,
                       f"Simulations: {mask}, + {comp['bg_cps']:.0f} cps measured background"))
    series.append(("SA_NEMA_pct", SIM2_STYLE if comp else SIM_STYLE,
                   f"Simulations: {mask}, without the measured background"))
    series.append(("SA_no_mask_pct", SIM3_STYLE,
                   "Simulations: no mask (all coincidences in the sinogram FOV), without the measured background"))
    for key, style, label in series:
        v = [r[key] for r in rows]
        ax.plot(z, v, **style, label=label + window)
        vals += v
    profile_axes(ax, max(10.0, np.nanmax(vals) * 1.05))
    ax.legend(fontsize=9, loc="lower center", frameon=True)
    title = f"Axial sensitivity profile, {args.coil}: with and without the measured background and the mask"
    if comp:
        title += (f"\nbackground in the measurement {comp['bg_cps']:.0f} cps "
                  f"({comp.get('bg_source', '')}) = {comp['bg_pct']:.3f} percentage points")
    ax.set_title(title, fontsize=11)
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def plot_fit(fname, rows, fit, args):
    """Additional figure for the profile fit: meas vs sim with the line, and residuals along z."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [r for r in sorted(rows, key=lambda r: r["z_mm"])
            if np.isfinite(r["SA_NEMA_pct"]) and np.isfinite(r["meas_SA_pct"])]
    z = np.array([r["z_mm"] for r in rows])
    sim = np.array([r["SA_NEMA_pct"] for r in rows])
    meas = np.array([r["meas_SA_pct"] for r in rows])
    k, c = fit["k_meas_over_sim"], fit["c_pct"]

    fig, axs = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    ax = axs[0]
    ax.plot(sim, meas, "o", color="#1f77b4", ms=4, label="positions")
    xs = np.array([0.0, max(sim.max(), 1e-6) * 1.05])
    ax.plot(xs, k * xs + c, "-", color="#d62728",
            label=f"fit: meas = {k:.4f} x sim + {c:.3f} %")
    ax.plot(xs, xs, ":", color="k", lw=0.8, label="meas = sim")
    ax.set_xlabel("GATE, Lu-176 subtracted (%)")
    ax.set_ylabel(f"Measurement, {args.coil} (%)")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    qe = f", QE to match {fit['QE_fit']:.3f}" if np.isfinite(fit["QE_fit"]) else ""
    ax.set_title(f"background in the measurement {fit['bg_cps']:.0f} cps{qe}", fontsize=10)

    ax = axs[1]
    ax.plot(z, meas - (k * sim + c), "o", color="#1f77b4", ms=4)
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xlabel("axial source position (mm)")
    ax.set_ylabel("measured - fit (percentage points)")
    ax.set_title(f"residuals (rms {fit['rms_residual_pct']:.3f} %); a pattern along z means the gap "
                 "is not uniform", fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_xlim(-80, 80)
    fig.suptitle(f"Profile fit over {fit['n_positions']} positions (additional to the per-position comparison)",
                 fontsize=10)
    fig.savefig(fname, dpi=130)
    plt.close(fig)


# ============================================================================================
# 8. Output files
# ============================================================================================
def fmt(v, nd=3):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (float, np.floating)):
        return "nan" if not np.isfinite(v) else f"{v:.{nd}f}"
    return str(v)


RESULT_COLS = ["file", "z_mm", "window_keV", "QE_model", "method", "SA_pct", "SA_err_pct", "meas_coil",
               "meas_SA_pct", "ratio_sim_meas", "diff_pct", "QE_to_match", "SA_NEMA_pct",
               "meas_bg_cps", "meas_SA_bgfree_pct", "ratio_bgfree", "QE_to_match_bgfree", "sim_plus_bg_pct",
               "ARD_noBG_pct", "ARD_withBG_pct", "ARD_asProcessed_pct", "SA_no_mask_pct", "note"]
ARD_COLS = [("z_mm", "Axial Position (mm)"), ("meas_SA_pct", "Measurements (%)"),
            ("SA_NEMA_pct", "Simulations, Lu-176 subtracted (%)"), ("ARD_noBG_pct", "ARD A (%)"),
            ("sim_plus_bg_pct", "Simulations + background (%)"), ("ARD_withBG_pct", "ARD B (%)"),
            ("SA_pct", "Simulations, no subtraction (%)"), ("ARD_asProcessed_pct", "ARD as processed (%)")]


def ard_lines(rows, comp, args):
    """The point-by-point table with MARD and the centre ARD, as lists of cells."""
    cols = ARD_COLS if np.isfinite(comp["MARD_asProcessed_pct"]) else ARD_COLS[:6]
    out = [[f"# Point-by-point comparison with Claudia ({args.coil}), ARD = |sim - meas| / meas x 100, "
            f"MARD = mean ARD. A: no background in her data; B: her data contain "
            f"{comp['bg_cps']:.0f} cps background ({comp['bg_source']})."], [h for _, h in cols]]
    for r in sorted(rows, key=lambda r: r["z_mm"]):
        if np.isfinite(r["meas_SA_pct"]):
            out.append([r[k] for k, _ in cols])
    c = comp["centre"]
    out += [[], ["Metric", "A (no background)", "B (with background)", "as processed"],
            [f"ARD at the centre of the aFOV (z = {c['z_mm']:.2f} mm) (%)", c["ARD_noBG_pct"],
             c["ARD_withBG_pct"], c["ARD_asProcessed_pct"]],
            [f"MARD over {comp['n_positions']} positions (%)", comp["MARD_noBG_pct"],
             comp["MARD_withBG_pct"], comp["MARD_asProcessed_pct"]]]
    return out


def write_tables(base, rows, summary, measured, args, fit=None, comp=None):
    rows = sorted(rows, key=lambda r: r["z_mm"])
    with open(base + ".txt", "w") as f:
        f.write("# Absolute sensitivity S_A (%) of the GATE prompts, SSRB sinograms as NEMA NU 4-2008 Sec. 5.4.\n")
        f.write(f"# SA_pct: {rows[0]['method']} (compared with meas); SA_NEMA_pct: 1 cm mask, Lu-176 "
                "subtracted; SA_no_mask_pct: all FOV, no subtraction.\n")
        f.write(f"# meas = Kuntner (2021-2022_NEMA_Sensitivity_Masar.xlsx, sheet {args.coil}), "
                f"interpolated at z; diff = sim/meas - 1 (%).\n")
        f.write("\t".join(RESULT_COLS) + "\n")
        for r in rows:
            f.write("\t".join(fmt(r[c]) for c in RESULT_COLS) + "\n")
        if summary:
            f.write("\n# NEMA averages over positions (Sec. 5.4.1); sim_SA_NEMA_pct = Lu-176 subtracted\n"
                    "length\tn_sim\tsim_SA_pct\tsim_SA_NEMA_pct\tmeas_SA_pct\n")
            for s in summary:
                f.write(f"{s['length']}\t{s['n_sim']}\t{fmt(s['sim_SA_pct'])}\t{fmt(s['sim_SA_NEMA_pct'])}\t"
                        f"{fmt(s['meas_SA_pct'])}\n")
        if fit:
            f.write("\n# Profile fit: meas(z) = k x sim(z) + c (sim = GATE, Lu-176 subtracted; meas = as measured)\n")
            for key, v in fit.items():
                f.write(f"{key}\t{fmt(v, 4)}\n")
    if comp:
        with open(base + "_ARD_MARD.txt", "w") as f:
            for line in ard_lines(rows, comp, args):
                f.write("\t".join(fmt(v, 4) if isinstance(v, (float, np.floating)) else str(v) for v in line) + "\n")
    keys = list(rows[0].keys())
    with open(base + "_details.txt", "w") as f:
        f.write("\t".join(keys) + "\n")
        for r in rows:
            f.write("\t".join(fmt(r[k], 5) for k in keys) + "\n")
    try:
        from openpyxl import Workbook
    except ImportError:
        print("openpyxl not installed: no .xlsx written", file=sys.stderr)
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(RESULT_COLS)
    for r in rows:
        ws.append([_cell(r[c]) for c in RESULT_COLS])
    ws = wb.create_sheet("Details")
    ws.append(keys)
    for r in rows:
        ws.append([_cell(r[k]) for k in keys])
    if comp:
        ws = wb.create_sheet("ARD_MARD")
        for line in ard_lines(rows, comp, args):
            ws.append([_cell(v) for v in line])
    if summary:
        ws = wb.create_sheet("NEMA_summary")
        cols = ["length", "n_sim", "sim_SA_pct", "sim_SA_NEMA_pct", "meas_SA_pct"]
        ws.append(cols)
        for s in summary:
            ws.append([_cell(s[k]) for k in cols])
    if fit:
        ws = wb.create_sheet("Profile_fit")
        for key, v in fit.items():
            ws.append([key, _cell(v)])
    if measured and args.coil in measured:
        m = measured[args.coil]
        ws = wb.create_sheet("Measured")
        ws.append([f"{args.coil}: {m['source']}", f"activity {m['activity']} Bq"])
        ws.append(["position_mm (as in workbook)", "S_cps_per_Bq", "SA_pct"])
        for p, s, a in zip(m["pos"], m["S"], m["SA"]):
            ws.append([float(p), float(s), float(a)])
    ws = wb.create_sheet("Settings")
    for k, v in sorted(vars(args).items()):
        ws.append([k, str(v)])
    wb.save(base + ".xlsx")


def all_cases_tables(rows, comp, args):
    """ARD per position, centre ARD and MARD for every processing step (b)-(e) (profile_all_cases.png
    shows (a), (b), (d) and (e)).

    Each simulated case is compared with the values as measured (a), ARD = |sim - meas| / meas
    x 100. Returns (notes, summary, per-position) as lists of cells.
    """
    mask = mask_label(args)
    cases = [("(b) no mask, no Lu-176 subtraction, no background", "SA_no_mask_pct"),
             (f"(c) {mask} only", "SA_mask_noBG_pct"),
             (f"(d) {mask}, Lu-176 subtracted (reading A)", "SA_NEMA_pct"),
             (f"(e) {mask}, Lu-176 subtracted, + {comp['bg_cps']:.0f} cps background (reading B)", "sim_plus_bg_pct")]
    rows = sorted((r for r in rows if np.isfinite(r["meas_SA_pct"])), key=lambda r: r["z_mm"])
    ards = [[abs(r[s] - r["meas_SA_pct"]) / r["meas_SA_pct"] * 100.0 if np.isfinite(r[s]) else np.nan
             for r in rows] for _, s in cases]
    ic = min(range(len(rows)), key=lambda i: abs(rows[i]["z_mm"]))      # centre of the aFOV
    notes = [[f"# ARD = |sim - meas| / meas x 100 per position, MARD = mean ARD over the positions; meas = (a) "
              f"Claudia ({args.coil}), interpolated at the simulated positions (exact at hers)."],
             [f"# Her background in (e): {comp['bg_cps']:.0f} cps ({comp.get('bg_source', '')}) = "
              f"{comp['bg_pct']:.3f} percentage points."],
             ["# (c) keeps the model's own Lu-176: it compares like-for-like with (a) only with --mask nema on "
              "60 s runs (as Bruker processed her data)."]]
    summary = [["Simulation (vs (a) measured)",
                f"ARD at the centre of the aFOV (z = {rows[ic]['z_mm']:.2f} mm) (%)", "MARD (%)", "Positions"]]
    for (label, _), a in zip(cases, ards):
        v = np.array(a, float)
        ok = np.isfinite(v)
        summary.append([label, v[ic], float(v[ok].mean()) if ok.any() else np.nan, int(ok.sum())])
    per = [["Axial Position (mm)", "(a) Measurements (%)", "(b) Simulations (%)", "(c) Simulations (%)",
            "(d) Simulations (%)", "(e) Simulations (%)", "ARD (b) (%)", "ARD (c) (%)", "ARD (d) (%)", "ARD (e) (%)"]]
    for i, r in enumerate(rows):
        per.append([r["z_mm"], r["meas_SA_pct"]] + [r[s] for _, s in cases] + [a[i] for a in ards])
    return notes, summary, per


def write_all_cases(base, rows, comp, args):
    """<base>_ARD_MARD_all_cases.txt and .xlsx: summary (centre ARD, MARD) and the ARD per position."""
    notes, summary, per = all_cases_tables(rows, comp, args)
    cells = lambda line: "\t".join(fmt(v, 4) if isinstance(v, (float, np.floating)) else str(v) for v in line)
    with open(base + "_ARD_MARD_all_cases.txt", "w") as f:
        for line in notes + [["# Summary"]] + summary + [[], ["# Per position"]] + per:
            f.write(cells(line) + "\n")
    try:
        from openpyxl import Workbook
    except ImportError:
        return summary
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    for line in notes + [[]] + summary:
        ws.append([_cell(v) for v in line])
    ws = wb.create_sheet("Per_position")
    for line in per:
        ws.append([_cell(v) for v in line])
    wb.save(base + "_ARD_MARD_all_cases.xlsx")
    return summary


def _cell(v):
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (float, np.floating)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, (int, np.integer)):
        return int(v)
    return v


# ============================================================================================
# 9. Main program
# ============================================================================================
def analyse_one(path, args, measured, plots):
    """One file: its analysis and its position figure. At module level so that --jobs can run it in
    another process; returns (path, row, None), or (path, None, error) if the file can't be analysed."""
    try:
        row, pdata = analyse_file(path, args, measured)
    except Exception as exc:
        return path, None, f"{exc}"
    if plots:
        plot_position(os.path.join(plots, f"position_{row['label']}.png"), row, pdata, args)
    return path, row, None


def main():
    ap = argparse.ArgumentParser(description="NEMA NU 4 sensitivity of GATE Na-22 point-source runs, "
                                             "compared with the measured profiles (Kuntner et al. 2025).")
    ap.add_argument("files", nargs="*", help="ROOT files (default: output/Sens_*.root)")
    ap.add_argument("--dir", default="output", help="folder searched when no files are given")
    g = ap.add_argument_group("run settings (default: read from macros/<name>.mac)")
    g.add_argument("--macro", default=None, help="run macro to read (default: macros/<name>.mac)")
    g.add_argument("--activity", type=float, default=None, help="Na-22 activity, Bq")
    g.add_argument("--duration", type=float, default=None, help="acquisition time, s")
    g.add_argument("--qe", type=float, default=None, help="QE of the model (crystalblurring)")
    g.add_argument("--source-id", type=int, default=0, help="sourceID of the Na-22 source (default 0)")
    g = ap.add_argument_group("analysis")
    g.add_argument("--emin", type=float, default=None, help="lower energy threshold in the analysis, keV")
    g.add_argument("--emax", type=float, default=None, help="upper energy threshold in the analysis, keV")
    g.add_argument("--bg-sub", action="store_true",
                   help="subtract the Lu-176-only background (NEMA); default off, as in the noBG processing of the measured data")
    g.add_argument("--mask", choices=("nema", "source"), default="nema",
                   help="centre of the 1 cm mask in every sinogram row: 'nema' = the row maximum (NEMA, as "
                        "Bruker; needs the measured 60 s), 'source' = the source projection (no bias for "
                        "short runs; use with the background-free comparison)")
    g.add_argument("--no-mask", action="store_true",
                   help="use all coincidences in the sinogram FOV instead of NEMA's 1 cm mask")
    g.add_argument("--active-mm", type=float, default=None,
                   help="emulate an active area of N x N mm per 48 x 48 mm block face: coincidences with an "
                        "interaction closer than (48 - N)/2 mm to a block's side faces are rejected "
                        "(González et al. 2016 used 46 mm; default: off, full blocks)")
    g.add_argument("--slice", type=float, default=1.0, help="SSRB slice thickness, mm")
    g.add_argument("--sino-ds", type=float, default=0.478602, help="radial sinogram bin, mm")
    g.add_argument("--sino-bins", type=int, default=168, help="radial sinogram bins")
    g.add_argument("--views", type=int, default=193, help="sinogram angles over 180 deg")
    g = ap.add_argument_group("measurement")
    g.add_argument("--measured", default="2021-2022_NEMA_Sensitivity_Masar.xlsx",
                   help="the measured workbook (searched here and next to this script)")
    g.add_argument("--coil", default="Quad86", choices=MEAS_SHEETS, help="sheet used as reference")
    g.add_argument("--meas-bg-cps", type=float, default=None,
                   help="background of the measurement (cps inside the mask) for reading B and the background-free "
                        "comparison. Default: from the profile fit with 10 or more positions, otherwise "
                        f"{DEFAULT_BG_CPS:g} cps (the level at the ends of the measured profiles, too high for a background; "
                        "for the paper I gave 415)")
    g.add_argument("--meas-sign", type=float, default=1.0, choices=(1.0, -1.0),
                   help="-1 mirrors the measured positions (direction vs GATE +z not documented)")
    g = ap.add_argument_group("output")
    g.add_argument("--out", default="sens_results", help="base name of the output files")
    g.add_argument("--no-plots", action="store_true")
    g.add_argument("--jobs", type=int, default=1,
                   help="files analysed at the same time, one process each (reading + position figure); "
                        "default 1. Each process holds one file in memory")
    args = ap.parse_args()

    files = args.files or sorted(glob.glob(os.path.join(args.dir, "Sens_*.root")))
    if not files:
        sys.exit(f"No files found (looked for {os.path.join(args.dir, 'Sens_*.root')})")
    base = os.path.splitext(args.out)[0]
    plots = None if args.no_plots else base + "_plots"
    if plots:
        try:
            import matplotlib  # noqa: F401
            os.makedirs(plots, exist_ok=True)
        except ImportError:
            print("matplotlib not installed: no figures", file=sys.stderr)
            plots = None

    measured = {}
    mpath = find_measured(args.measured)
    if mpath:
        try:
            measured = load_measured(mpath)
        except Exception as exc:
            print(f"Could not read {mpath}: {exc}", file=sys.stderr)
    else:
        print(f"{args.measured} not found: no comparison with the measurement", file=sys.stderr)

    rows = []

    def collect(result):
        path, row, err = result
        if err is not None:                            # keep going with the other files
            print(f"SKIPPED {path}: {err}", file=sys.stderr)
            return
        rows.append(row)
        meas = f" | meas ({args.coil}) {row['meas_SA_pct']:.3f} %" if np.isfinite(row["meas_SA_pct"]) else ""
        print(f"{row['file']}: z = {row['z_mm']:.1f} mm, {row['activity_Bq'] / 1e3:.1f} kBq x {row['duration_s']:g} s, "
              f"window {row['window_keV']} keV, {row['in_mask']} counts in mask | "
              f"S_A {row['SA_pct']:.3f} ± {row['SA_err_pct']:.3f} % (Lu-176 subtracted: {row['SA_NEMA_pct']:.3f} %)"
              f"{meas}", flush=True)
        if row["note"]:
            print(f"  NOTE: {row['note']}")

    work = functools.partial(analyse_one, args=args, measured=measured, plots=plots)
    jobs = max(1, min(args.jobs, len(files)))
    if jobs > 1:                                       # one process per file; results come back in file order
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            for result in pool.map(work, files):
                collect(result)
    else:
        for path in files:
            collect(work(path))
    if not rows:
        sys.exit("No file could be analysed")
    summary = nema_summary(rows, measured, args) if len(rows) >= 3 else []
    fit = profile_fit(rows, measured, args)
    if fit:
        print(f"\nProfile fit over {fit['n_positions']} positions: meas = {fit['k_meas_over_sim']:.4f} x sim + "
              f"{fit['c_pct']:.3f} % -> background in the measurement {fit['bg_cps']:.0f} cps"
              + (f", QE to match {fit['QE_fit']:.3f}" if np.isfinite(fit["QE_fit"]) else "")
              + f" (rms residual {fit['rms_residual_pct']:.3f} %)")

    # background of the measurement for reading B: given, else from the profile fit, else the fallback
    if args.meas_bg_cps is not None:
        bg_cps, bg_source = args.meas_bg_cps, "given with --meas-bg-cps"
    elif fit:
        bg_cps, bg_source = fit["bg_cps"], "from the profile fit"
    else:
        bg_cps, bg_source = DEFAULT_BG_CPS, "estimate from the ends of her profiles"
    comp = compare_with_measurement(rows, measured, args, bg_cps)
    if comp:
        comp["bg_source"] = bg_source
        c = comp["centre"]
        print(f"\nComparison with the measurement ({args.coil}), point by point (ARD = |sim - meas| / meas):")
        print(f"  measured background for reading B: {bg_cps:.0f} cps ({bg_source}) = {comp['bg_pct']:.3f} percentage points")
        print(f"  centre of the aFOV, z = {c['z_mm']:.2f} mm: meas {c['meas_SA_pct']:.3f} %")
        print(f"    A (no background in the data):  GATE {c['SA_NEMA_pct']:.3f} %  ARD {c['ARD_noBG_pct']:.2f} %")
        print(f"    B (the data contain it):        GATE + bg {c['sim_plus_bg_pct']:.3f} %  ARD {c['ARD_withBG_pct']:.2f} %"
              + (f"  -> QE to match {c['QE_to_match_bgfree']:.3f}" if np.isfinite(c["QE_to_match_bgfree"]) else ""))
        if np.isfinite(c["ARD_asProcessed_pct"]):
            print(f"    as processed (no subtraction):  GATE {c['SA_pct']:.3f} %  ARD {c['ARD_asProcessed_pct']:.2f} %")
        print(f"  MARD over {comp['n_positions']} positions: A {comp['MARD_noBG_pct']:.2f} %, "
              f"B {comp['MARD_withBG_pct']:.2f} %"
              + (f", as processed {comp['MARD_asProcessed_pct']:.2f} %" if np.isfinite(comp["MARD_asProcessed_pct"]) else ""))
    write_tables(base, rows, summary, measured, args, fit, comp)
    if comp:
        print(f"  {'all processing steps vs the measurement':<92s} {'ARD centre':>10s}  {'MARD':>9s}")
        for label, ard_c, mard, _ in write_all_cases(base, rows, comp, args)[1:]:
            print(f"    {label:<90s} {ard_c:8.2f} %  {mard:7.2f} %")
    if plots:
        plot_profile(os.path.join(plots, "profile.png"), rows, measured, args, comp)
        if comp:
            plot_meas_vs_sim(os.path.join(plots, "profile_meas_vs_sim.png"), rows, measured, args, comp)
        plot_all_cases(os.path.join(plots, "profile_all_cases.png"), rows, measured, args, comp)
        if fit:
            plot_fit(os.path.join(plots, "profile_fit.png"), rows, fit, args)
    print(f"\nWritten: {base}.txt, {base}_details.txt" + (f", {base}_ARD_MARD.txt" if comp else "") +
          (f", {base}.xlsx" if os.path.exists(base + ".xlsx") else "") +
          (f", {base}_ARD_MARD_all_cases.txt" if comp else "") +
          (f", {base}_ARD_MARD_all_cases.xlsx" if comp and os.path.exists(base + "_ARD_MARD_all_cases.xlsx") else "") +
          (f", {plots}/" if plots else ""))


if __name__ == "__main__":
    main()
