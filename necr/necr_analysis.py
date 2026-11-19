#!/usr/bin/env python3
"""
necr_analysis.py
================

NEMA NU 4-2008 count rates, scatter fraction and NECR (Section 4) for the GATE model of the Bruker
PET insert Si 198 with the mouse-like phantom, compared with the measured count-rate curves
(PET-MR NEC curves NEMA Masar.xlsx): sheet "20220915 Quad35 Maus" for the Quad35 coil (145 frames,
117.74 ... 0.013 MBq) and sheet "20220906 Quad86 Maus" for the Quad86 coil (132 frames,
58.18 ... 0.013 MBq, same window and Rint). The coil is read from each run macro (the coil macro it
executes, quad35_coil* or quad86_coil*, or the coil layer rfCoil1 of a macro without setups);
--coil 35|86 or --measured-sheet override it, and a file whose coil differs from the chosen
measurement gets a WARNING note.

----------------------------------------------------------------------------------------------
1. What the measurement did (the target)
----------------------------------------------------------------------------------------------
  * Mouse-like phantom (polyethylene, 25 mm x 70 mm, 34.36 ml) with the F-18 line source, Quad35
    RF coil, 15 Sep 2022 (163 MBq at 09:01). 145 frames with complete values from 117.74 MBq down
    to 0.013 MBq; column A of the sheet = average activity of the frame. 255.55-766.5 keV, 7 ns.
  * Bruker's processing (their "NEMA Testing" document): NECCalculation.exe <sinogram> 168 193 150
    0.478602 -mouse gives Trues, Scatter+Randoms and Total as in NEMA Sec. 4.4: 8 mm mask around
    the phantom (|s| <= 20.5 mm, centred on the scanner axis), every projection aligned on its
    maximum pixel, +-7 mm strip, radial pixel 0.478602 mm. Randoms from lmViewer.exe -randoms
    (column F in counts per minute, column I = F / 60 cps).
  * The sheet then computes Scatter = (S+R) - Randoms - Rint with Rint = 91 cps (column K, the
    intrinsic LYSO true rate of NEMA Sec. 4.4.5), Scatter Fraction = S / (T + S), and
    NEC = Trues^2 / Total (column L, NEMA Sec. 4.4.6 without randoms subtraction).
  * The measured values are read unrounded from the workbook (rounded to whole kcps, the randoms
    at low activity would be 0 and their ARD infinite).

----------------------------------------------------------------------------------------------
2. What this script does with every simulated ROOT file (one file = one activity)
----------------------------------------------------------------------------------------------
  NEMA NU 4-2008 Sec. 4.4, set up as Bruker's NECCalculation -mouse:
  a. Read the prompt (Coincidences) and delayed (delay) coincidences, as the scanner records them.
  b. Every LOR becomes one sinogram point: angle phi and radial distance s from the scanner axis
     (SSRB: the axial coordinate is ignored for the in-plane position).
  c. Mask: only LORs within 8 mm of the phantom edge, |s| <= 12.5 + 8 = 20.5 mm.
  d. Alignment: every projection is shifted so that the line source sits at s = 0, and all angles
     are summed into one profile. --align known (default) shifts by the projected source position
     (mean F-18 decay position from GATE); with many counts this equals NEMA's maximum pixel, but
     it is not fooled by noise in sparse rows. --align max is the literal NEMA rule (per slice and
     angle).
  e. Strip integration (NEMA Fig. 4-2): C_L and C_R at -7 and +7 mm, the straight line between
     them; counts above the line inside the 14 mm strip are trues, everything else is S+R.
  f. Randoms: the delayed coincidences inside the same mask (NEMA Sec. 4.4.4).
  g. Rates (kcps): R_TOT = C_TOT / T, R_t = (C_TOT - C_r+s) / T, R_r = C_R / T,
     R_s = R_TOT - R_t - R_r - R_int (Sec. 4.4.5), SF_j = R_s / (R_t + R_s),
     NECR = R_t^2 / R_TOT (as the sheet), and R_t^2 / (R_TOT + R_r) for reference.
     T is the time the coincidences cover: GATE 8.2 does not flush the sorters' presort buffer
     (256 singles) at the end of a run, so the end of the run produces no coincidences. In 0.1 s
     test runs without Lu-176 the lost time was 0.47 ms x MBq / activity, 27 % of the run at
     0.018 MBq; in 1 s runs with Lu-176 it is far smaller. T = time of the last coincidence + one mean gap
     (duration_eff_s in the tables); --nominal-time uses the duration.
  h. R_int: with Lu-176 in the model, the sheet's value (91 cps) is subtracted, so both sides use
     identical bookkeeping; without Lu-176 nothing is subtracted (--rint-cps overrides), unless the
     measured background is added (--add-measured-bg, section 4). The model's own intrinsic true
     rate is reported next to it: the NEMA strip applied to the pooled profile of the coincidences
     without any F-18 photon from all files below 1 MBq, like one long blank scan (NEMA Sec.
     4.3.4.1; a single 1 s file is too noisy for the two-pixel background).
  i. Truth diagnostics (GATE labels, not used for the NEMA numbers): how much of the NEMA trues is
     unscattered, scatter in the phantom / coil / front pad, randoms or Lu-176 (the strip is linear
     in the profile, so the NEMA trues split exactly by class), plus the whole-FOV truth counts.
  j. Measured values at the simulated activity: linear in log(activity) between the two
     neighbouring measured frames, i.e. the frame itself when the activities are equal (necr_run.py
     uses the measured activities). Runs at other activities (e.g. --mbq, or activities rounded to
     whole kBq) are compared at their own activity.
  k. MARD, one value per component (Trues, Scattered, Randoms, Totals, Scatter Fraction, NECR):
     mean over the simulated frames of |sim - meas| / meas x 100. Always given over all frames,
     1.5-20 MBq, up to 40 MBq, 0.5-40 MBq, 1.5-40 MBq and from 0.5 MBq to the highest frame
     (MARD_RANGES); --mard-range adds more ranges (e.g. 3-40). One column per range in the
     printout and in <out>_ARD_MARD.txt.
  l. NEMA values with their ARD = |sim - meas| / meas x 100: Sec. 4.5.2 peaks, R_t,peak and
     R_NEC,peak with the activity concentration a (and activity A) where they are reached. The
     peak is found in the same way on both curves, with one of three methods (--peak-fit):
       3point (default)  3-point interpolation: the parabola through the highest frame and its two
                         neighbours (the highest frame itself when the simulated activities are too
                         sparse).
       smooth            a degree-4 polynomial in ln(activity) through the frames down to 90 % of
                         the highest (--peak-fit-deg, --peak-fit-frac), with 1 sd of each peak from
                         the fit. The NECR is flat at its peak (< 0.2 % change within +-2 MBq) and
                         1 s simulated frames scatter by ~0.35 %, so three frames place it only to a
                         few MBq. The outputs get '_peakfit' added to their names, and the plots
                         folder gets PeakFit.png.
       max               the highest frame itself (direct comparison of the frames, no interpolation
                         or fit); the activity at the peak is then known to one frame (~6.5 %
                         apart). The outputs get '_peakmax' added to their names.
     Sec. 4.5.3 system scatter fraction as one value: sum R_s / sum (R_t + R_s) over the
     frames whose measured randoms are below 1 % of the trues (Sec. 4.4.1 via R_s of Sec. 4.4.5),
     the same frames for both sides.
     MARD and ARD are reported in <out>_ARD_MARD.txt (and the Excel sheet ARD_MARD), not plotted.
  m. --active-mm N (optional, off by default): rejects coincidences with an interaction closer
     than (48 - N)/2 mm to a block's side faces, as in sens_analysis.py (46 mm: Gonzalez et al.
     2016). It lowers trues and randoms. It works on the analysis level only: the edge events
     still cause deadtime in GATE, as in the real detector.
  n. --detector-blur (optional, off by default): adds the detector response of the spatial-
     resolution analysis to the simulated positions before the NEMA steps (in-plane 1.6 mm and
     depth-of-interaction 1.6 mm FWHM, photon acollinearity 0.5 deg FWHM).

----------------------------------------------------------------------------------------------
3. Usage
----------------------------------------------------------------------------------------------
  pip install uproot numpy matplotlib openpyxl       (matplotlib/openpyxl only for PNG/XLSX)

  python3 necr_analysis.py                          # all output/NECR_*.root (runs of necr_run.py)
  python3 necr_analysis.py --jobs 16 --add-measured-bg   # runs made with necr_run.py --no-lu176
  python3 necr_analysis.py --jobs 16                # 16 files at a time (1 s files: ~10-20 s each)
  python3 necr_analysis.py output/NECR_std35v2_*.root --jobs 16   # one run only
  python3 necr_analysis.py --active-mm 46           # emulated 46 x 46 mm active block area
  python3 necr_analysis.py --peak-fit smooth        # peaks by a smooth fit; writes <out>_peakfit*
  python3 necr_analysis.py --peak-fit max           # peaks = highest frame of each curve; writes <out>_peakmax*
  python3 necr_analysis.py --old-names --jobs 16    # numbered files output/1.root ... output/145.root
  python3 necr_analysis.py --duration 0.1 path/to/1.root   # files without a run macro

  Activity, duration, QE, energy window and Lu-176 are read from the file's run macro, searched
  next to the output/ folder in the folders of --macro-dirs (macros/<name>.mac is written by
  necr_run.py); a macro is used only if it writes this file's name. Without a macro, --duration is
  required, and the activity of a numbered file <n>.root is frame n (row n of --activities-xlsx,
  else the measured sheet); other files take it from the ROOT decay count (Lu-176 subtracted).

  Outputs (rates in kcps, SF in %) go to a folder per setup: <results-dir>/<setup>/ (default
  results/q35/, results/q86/, results/q86rat/ for NECR_main_std.mac runs; runs without a setup:
  results/<tag>/ or results/no_setup/). <out> defaults to necr_<tag> (files NECR_<tag>_<frame>),
  else necr_results. Files of different setups or tags are never pooled: each run is analysed on
  its own, against the measured sheet of its own coil, e.g. results/q35/necr_std35v2.txt and
  results/q86rat/necr_std86ratv2.txt from one call on output/NECR_*.root.
    <out>.txt            one row per file: simulated and measured T, S, R, Total, NECR and SF
    <out>_details.txt    everything per file (counts, truth diagnostics, settings)
    <out>_ARD_MARD.txt   one MARD per component, the NEMA values (peaks, system SF) with their ARD,
                         and the model check of R_int
    <out>.xlsx           first sheet "1" = activity and the simulated and measured rates (13
                         columns, PLOTNECR), then Results, ARD_MARD, Details, Measured, Settings
    <out>_plots/         profile_<name>.png per file (summed projection, truth composition, NEMA
                         line and strip) and Trues.png, Scattered.png, Randoms.png, Totals.png,
                         NECR.png, Scatter Fraction.png, Grouped_2x2_Metrics.png,
                         Grouped_3x2_AllMetrics.png, AllMetrics.png
    With --peak-fit smooth all of these are named <out>_peakfit... (e.g. <out>_peakfit_ARD_MARD.txt,
    <out>_peakfit_plots/), so the 3-point results are kept; the plots folder also has PeakFit.png.
    With --peak-fit max they are named <out>_peakmax... in the same way.

----------------------------------------------------------------------------------------------
4. Assumptions
----------------------------------------------------------------------------------------------
  * Simulated activity = activity in the run macro (decays/s at t = 0); the F-18 decay within a
    1 s acquisition is 0.01 %. The measured column A is the frame's average activity.
  * Rint = 91 cps on both sides keeps the Bruker bookkeeping. Whether the model's Lu-176
    (152 kBq, calculated, not measured) gives the same intrinsic true rate is reported, not
    assumed.
  * --add-measured-bg (for runs made without Lu-176, necr_run.py --no-lu176): the measured
    background of the blank scan (no source, 16 Nov 2021, 36014 s) is added to every simulated
    frame, as the sensitivity analysis adds the measured background (its reading B).
    Bruker's NECCalculation on the blank gives Total 850.9 cps and S+R 760.3 cps in the mask (so its
    NEMA trues are 90.6 cps, the sheet's Rint); its randoms are not in its files, so 25 cps is used:
    the measured randoms extrapolated to zero activity (24.9 cps from the 15 lowest frames of the
    Quad35 sheet; lowest frame 26.8 cps). The model's counts get + Total x time, + S+R x time and
    + randoms x time, and Rint = 91 cps is then subtracted from its scatter, the same bookkeeping as
    the measurement. A constant background: the Lu-176 x F-18 cross randoms, which grow with the F-18
    singles, are not in it (small from about 3 MBq up). The blank scan's rate drifted by about 10 %
    over its 10 h; --bg-total-cps, --bg-sr-cps and --bg-randoms-cps replace the values.
  * NEMA Sec. 4.5.3 asks for the SF of LYSO systems at 5 x the activity whose single rate equals
    the intrinsic single rate. The list mode stores only a rate-limited sample of the singles (about 9 % of
    the coincidence rate in the Quad35 summaries, at most ~4.7 kcps per module at 25.7 MBq), not the
    singles rate, so that activity cannot be found; the SF here is the Sec. 4.4.1 low-activity value
    (frames with R_r < 1 % of R_t); SF_j of every frame is in the tables.
  * Low-activity frames carry Poisson noise (1 s at 0.013 MBq: about 1,700 prompts and 30
    randoms), which enters the MARD over all frames; the 1.5-20 MBq column leaves them out.
  * --align known needs the GATE decay positions (sourcePosX1/Y1) of the F-18 source (sourceID 0,
    the first source defined in the model macro); --src-x/--src-y give them otherwise.
"""
# ============================================================================================
# 0. Imports
# ============================================================================================
import argparse          # command-line options
import glob              # default file list
import os                # paths
import re                # run-macro parsing
import sys               # warnings
import zlib              # per-file seed of the detector blur

import numpy as np       # all numerics

# ============================================================================================
# 1. Constants
# ============================================================================================
PHANTOM_RADIUS = 12.5                           # mm, NEMA mouse-like phantom
PHANTOM_VOLUME_ML = np.pi * 1.25 ** 2 * 7.0     # 34.36 ml (cell D1 of the measured sheet)
MASK_MARGIN = 8.0                               # mm, NEMA: keep pixels within 8 mm of the phantom edge
MEAS_FILE = "PET-MR NEC curves NEMA Masar.xlsx"
MEAS_SHEET = "20220915 Quad35 Maus"
MEAS_SHEETS = {35: "20220915 Quad35 Maus", 86: "20220906 Quad86 Maus"}     # measured mouse curves per coil
MEAS_WINDOW = (255.55, 766.5)                   # keV, sheet header "255.55-766.5 keV 7ns"
DEFAULT_RINT_CPS = 91.0                         # cps, used if the sheet has no Rintr value
# Measured background (Lu-176, no source) for --add-measured-bg, cps in the 8 mm mask: Bruker's
# NECCalculation on the blank scan of 16 Nov 2021 (36014 s), and the measured randoms extrapolated
# to zero activity (the blank's own randoms are not in its files).
BLANK_TOTAL_CPS, BLANK_SR_CPS, BLANK_RANDOMS_CPS = 850.9, 760.3, 25.0
LOW_ACTIVITY_MBQ = 1.0                          # files below this give the model's own Rint
HIGHLIGHT = (1.5, 20.0)                         # MBq, the shaded band in the figures
MARD_RANGES = ("all", "1.5-20", "0-40", "0.5-40", "1.5-40", "0.5-")   # MBq, MARD always given over these;
                                                # --mard-range adds more
# Detector blocks of the model (NECR_main_std.mac: 117 mm ring, 52 mm ring pitch): 8 heads x 3 rings of
# trapezoidal LYSO, entrance face 48 x 48 mm at 58.5 mm from the axis, 50 x 50 mm at the exit face 10 mm
# deeper. Used by --active-mm and --detector-blur.
R_FRONT, DEPTH, HALF_FRONT, TAPER = 58.5, 10.0, 24.0, 0.1
RING_PITCH = 52.0
RING_Z = np.array([-RING_PITCH, 0.0, RING_PITCH])
HEAD_STEP = np.pi / 4
GAUSS_FWHM = np.sqrt(8 * np.log(2))     # FWHM = 2.3548 sigma

# Which PhantomSD volumes belong together when the analysis reports WHERE the scatter came from. GATE stores,
# per photon, only the LAST volume in which it Compton/Rayleigh-scattered ('NULL' if none).
# A name ending in '*' matches every volume that starts with it: the coils and cradles in coil_bed_real/
# consist of several parts. Names that NECR_main_std.mac does not use do no harm.
GROUPS = {
    "object": ["mousePhantom", "sourceHole", "sourceTube", "sourceTubeEnd1",
               "sourceTubeEnd2", "sourceWater",                   # phantom and line source
               "mouseTable",                                      # bed: simple polyethylene half-shell (not used here)
               "mbed_*", "bed_*", "mouseCradle", "bedCradle",     # bed: parts of other cradle models (full models)
               "mbed3mm_*", "ratbed_*"],                          # bed: the cradles of NECR_main_std.mac
    "coil": ["rfCoil1", "rfCoil2", "plastic2",                    # RF coil: simple layer model (not used here)
             "q35_*", "coil_*",                                   # RF coil: Quad35 parts; parts of the full coil models
             "q86_*"],                                            # RF coil: the Quad86 tubes of NECR_main_std.mac
    "front": ["FrontPad", "shielding"],                           # pad and Cu sheet on the detectors
}
GROUP_ORDER = ["object", "coil", "front", "other"]   # priority when the two photons disagree
# Truth classes of the profile figure and of the NEMA-trues decomposition
CLASSES = (("unscattered", "Unscattered"),
           ("scat_object", "Scatter: phantom, tube, water, bed"),
           ("scat_coil", "Scatter: RF coil"),
           ("scat_front", "Scatter: front pad, Cu shield"),
           ("randoms", "Randoms (prompt truth)"),
           ("intrinsic", "Lu-176 intrinsic"))

GEOMETRY = ["eventID1", "eventID2", "time1",
            "globalPosX1", "globalPosY1", "globalPosZ1", "globalPosX2", "globalPosY2", "globalPosZ2"]
BRANCHES = GEOMETRY + ["sourcePosX1", "sourcePosY1", "sourceID1", "sourceID2",
                       "comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2",
                       "comptVolName1", "comptVolName2", "RayleighVolName1", "RayleighVolName2"]

# The metrics compared with the measurement: (name in the tables and figures, key here, y label)
METRICS = (("Trues", "R_t", "Count Rate (kcps)"), ("Scattered", "R_s", "Count Rate (kcps)"),
           ("Randoms", "R_r", "Count Rate (kcps)"), ("Totals", "R_TOT", "Count Rate (kcps)"),
           ("NECR", "R_NEC", "Count Rate (kcps)"), ("Scatter Fraction", "SF_pct", "Scatter Fraction (%)"))
MARD_ORDER = ("Trues", "Scattered", "Randoms", "Totals", "Scatter Fraction", "NECR")   # one MARD each
# Columns of the first sheet "1" of the .xlsx output: activity, then the simulated and measured rates
PLOTNECR = [("Activity (MBq)", "activity_MBq", None),
            ("Trues (sim)", "R_t", "sim"), ("Randoms (sim)", "R_r", "sim"), ("Scattered (sim)", "R_s", "sim"),
            ("Totals (sim)", "R_TOT", "sim"), ("NECR (sim)", "R_NEC", "sim"),
            ("Trues (meas)", "R_t", "meas"), ("Randoms (meas)", "R_r", "meas"), ("Scattered (meas)", "R_s", "meas"),
            ("Totals (meas)", "R_TOT", "meas"), ("NECR (meas)", "R_NEC", "meas"),
            ("Scatter Fraction (sim)", "SF_pct", "sim"), ("Scatter Fraction (meas)", "SF_pct", "meas")]


# ============================================================================================
# 2. Reading the GATE ROOT file and its run macro
# ============================================================================================
def load(path, tree, truth):
    """One coincidence tree as a dict of numpy arrays (None if the tree is missing).

    truth=True also reads the GATE truth branches (prompts); the delayed tree needs only the
    geometry. Branches the file does not have are left out.
    """
    import uproot                                   # only needed for ROOT input
    with uproot.open(path) as f:
        if tree not in [k.split(";")[0] for k in f.keys()]:
            return None
        t = f[tree]
        names = [b for b in (BRANCHES if truth else GEOMETRY) if b in t.keys()]
        return t.arrays(names, library="np")


def primaries(path):
    """Number of emitted primaries (all sources): GATE fills 'total_nb_primaries' once with that
    number as the x value, so it is the histogram's fTsumwx. NaN if the histogram is missing."""
    import uproot
    try:
        with uproot.open(path) as f:
            return float(f["total_nb_primaries"].member("fTsumwx"))
    except Exception:
        return np.nan


def run_settings(root_path, macro=None, macro_dirs=("macros", "mac_A")):
    """Settings of the run from its run macro.

    Searched next to the output/ folder, in the folders of macro_dirs: macros/<name>.mac (written by
    necr_run.py), then the others. A macro is only used if the ROOT file name it writes (alias output
    or setFileName) is this file's name.
    Returns a dict with any of: activity (Bq), duration (s), seed, qe, e_low, e_high (keV),
    lu176 (bool), lu176_bq, macro, setup (the active '#@setup' block of NECR_main_std.mac runs).
    """
    stem = os.path.splitext(os.path.basename(root_path))[0]
    if macro is None:
        project = os.path.dirname(os.path.dirname(os.path.abspath(root_path)))
        for d in macro_dirs:
            cand = d if os.path.isabs(d) else os.path.join(project, d)
            cand = os.path.join(cand, stem + ".mac")
            if os.path.isfile(cand):
                macro = cand
                break
    if macro is None or not os.path.isfile(macro):
        return {}
    info = {"macro": macro}
    lines = open(macro, errors="replace").read().split("\n")
    active = [ln.strip() for ln in lines if not ln.lstrip().startswith("#")]
    cur = None                                      # setup macros (NECR_main_std.mac): the active block
    for ln in lines:
        m = re.match(r"#@setup[ \t]+(\w+)", ln)
        if m:
            cur = m.group(1)
        elif ln.startswith("#@end"):
            cur = None
        elif cur is not None and ln.startswith("/"):
            info["setup"] = cur
    aliases = {}
    for ln in active:
        m = re.match(r"/control/alias\s+(\w+)\s+(\S+)", ln)
        if m:
            aliases[m.group(1)] = m.group(2)
    out_name = None
    for ln in active:
        m = re.match(r"/gate/output/root/setFileName\s+(\S+)", ln)
        if m:
            out_name = m.group(1)
            out_name = aliases.get(out_name.strip("{}"), out_name) if out_name.startswith("{") else out_name
    if out_name is not None and os.path.basename(out_name) != stem:
        return {}                                   # this macro wrote a different file

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

    for key in ("activity", "duration", "seed"):
        if key in aliases:
            try:
                info[key] = float(aliases[key])
            except ValueError:
                pass
    if "b2bFraction" in aliases:                    # necr_run.py --b2b: pairs/s = activity x b2bFraction
        info["b2b_fraction"] = float(aliases["b2bFraction"])
    if "activity" not in info:
        v = value(r"/gate/source/F18CylinderSource/setActivity\s+(\S+)")
        if v is not None:
            info["activity"] = v
    if "duration" not in info:
        v = value(r"/gate/application/setTimeStop\s+(\S+)")
        if v is not None:
            info["duration"] = v
    rmin = value(r"/gate/rfCoil1/geometry/setRmin\s+(\S+)")
    if rmin:                                        # coil layer rfCoil1: 17.5 mm -> Quad35, 43 mm -> Quad86
        info["coil_mm"] = int(round(2 * rmin))
    for ln in active:                               # coil macros (coil_bed_real/, or coil3_bed_* of the full models)
        m = re.match(r"/control/execute\s+\S*(quad35_coil|quad86_coil|coil3_bed_(?:bore|all))\S*\.mac", ln)
        if m:
            info["coil_mm"] = 35 if m.group(1) == "quad35_coil" else 86
    info["qe"] = value(r"/gate/digitizer/Singles/crystalblurring/setCrystalQE\s+(\S+)")
    info["e_low"] = value(r"/gate/digitizer/Singles/thresholder/setThreshold\s+(\S+)")
    info["e_high"] = value(r"/gate/digitizer/Singles/upholder/setUphold\s+(\S+)")
    info["lu176"] = any(ln.startswith("/gate/source/Lu176CrystalSource/setActivity") for ln in active)
    if info["lu176"]:
        info["lu176_bq"] = value(r"/gate/source/Lu176CrystalSource/setActivity\s+(\S+)")
    return {k: v for k, v in info.items() if v is not None}


# ============================================================================================
# 3. Sinogram coordinates and the NEMA steps
# ============================================================================================
def sino(a):
    """Projection angle phi in [0, pi), radial distance s (mm) and SSRB slice z (mm) of every LOR.

    The LOR joins P1 = (x1, y1) and P2 = (x2, y2); its normal n = (cos phi, sin phi) is
    perpendicular to P2 - P1, s = P1 . n (signed), z = (z1 + z2) / 2.
    """
    x1, y1, x2, y2 = a["globalPosX1"], a["globalPosY1"], a["globalPosX2"], a["globalPosY2"]
    phi = np.mod(np.arctan2(x2 - x1, -(y2 - y1)), np.pi)
    s = x1 * np.cos(phi) + y1 * np.sin(phi)
    z = 0.5 * (a["globalPosZ1"] + a["globalPosZ2"])
    return phi, s, z


def strip(profile, centers, pix, half):
    """NEMA Fig. 4-2: split one summed projection into trues and scatter + randoms.

      C_L, C_R   values at -7 and +7 mm, by linear interpolation between pixel centres
      background mean(C_L, C_R) x (14 mm / pixel size): counts under the straight line inside the
                 strip ("number of pixels, including fractional values")
      outside    counts outside the strip; pixels on the strip edge are split by the fraction
                 of the pixel inside the strip
      C_r+s      background + outside;   C_TOT  all counts
    Returns (C_TOT, C_r+s, C_L, C_R). Trues = C_TOT - C_r+s. Every step is linear in the profile,
    so the trues of a sum of profiles are the sum of their trues (used for the truth split).
    """
    cl = np.interp(-half, centers, profile)
    cr = np.interp(half, centers, profile)
    lo, hi = centers - pix / 2, centers + pix / 2
    frac_in = np.clip((np.minimum(hi, half) - np.maximum(lo, -half)) / pix, 0, 1)
    inside = float((profile * frac_in).sum())
    total = float(profile.sum())
    c_rs = 0.5 * (cl + cr) * (2 * half / pix) + (total - inside)
    return total, c_rs, cl, cr


def nema_known(phi, s, keep, src, args):
    """Summed projection with alignment on the known line-source position (--align known).

    delta = s - s_src(phi) is each LOR's distance from the source in its own projection;
    histogramming delta over all kept LORs gives the summed projection, with pixel 0 centred on
    the source. Returns (profile, pixel centres, delta of every LOR).
    """
    d = s - (src[0] * np.cos(phi) + src[1] * np.sin(phi))
    nb = int(np.ceil((args.mask_halfwidth + np.hypot(*src) + 5) / args.pixel))
    centers = np.arange(-nb, nb + 1) * args.pixel
    edges = np.append(centers - args.pixel / 2, centers[-1] + args.pixel / 2)
    prof, _ = np.histogram(d[keep], edges)
    return prof.astype(float), centers, d


def fixed_centers(args):
    """Pixel centres of a profile grid that is the same for every file (+-(mask + 30) mm)."""
    nb = int(np.ceil((args.mask_halfwidth + 30.0) / args.pixel))
    return np.arange(-nb, nb + 1) * args.pixel


def model_rint(rows, args):
    """The model's own intrinsic true rate (cps): NEMA strip on the pooled profile of the coincidences
    without any F-18 photon, from the files below LOW_ACTIVITY_MBQ (where deadtime is negligible),
    divided by their summed time. Returns (rate, counts in the pooled profile, files) or None."""
    low = [r for r in rows if r["activity_MBq"] < LOW_ACTIVITY_MBQ and r["lu176_in_model"]]
    if not low:
        return None
    h = np.sum([r["_no_f18_profile"] for r in low], axis=0).astype(float)
    total, c_rs, _, _ = strip(h, fixed_centers(args), args.pixel, args.strip)
    return (total - c_rs) / sum(r["duration_eff_s"] for r in low), int(total), len(low)


def nema_max(phi, s, z, keep, args):
    """Literal NEMA alignment (--align max): per slice and angle, shift to the maximum pixel.

    3D sinogram H[slice, angle, radial pixel] of the kept LORs, mask applied, every row shifted so
    its maximum lands on the central pixel and added to that slice's summed projection.
    Returns (profiles[slice, offset], offset centres in mm).
    """
    ns = int(np.ceil(args.fov_radius / args.pixel))
    s_cent = (np.arange(2 * ns + 1) - ns) * args.pixel
    s_edges = np.append(s_cent - args.pixel / 2, s_cent[-1] + args.pixel / 2)
    phi_edges = np.linspace(0, np.pi, args.nphi + 1)
    z_edges = np.arange(-args.axial_fov / 2, args.axial_fov / 2 + 1e-9, args.slice)
    H, _ = np.histogramdd(np.c_[z[keep], phi[keep], s[keep]], (z_edges, phi_edges, s_edges))
    H[:, :, np.abs(s_cent) > args.mask_halfwidth] = 0
    nz, nphi, nsb = H.shape
    kmax = H.argmax(axis=2)
    out = np.zeros((nz, 2 * nsb - 1))
    for k in range(nsb):
        np.add.at(out, (np.repeat(np.arange(nz), nphi), (k - kmax).ravel() + nsb - 1), H[:, :, k].ravel())
    centers = (np.arange(2 * nsb - 1) - (nsb - 1)) * args.pixel
    return out, centers



# Detector response (--detector-blur): the same functions as in spres_analysis.py (spatial resolution), so
# both tests add the same detector response to the GATE interaction positions: in-plane position error
# 1.6 mm FWHM (Gonzalez et al. 2016), depth-of-interaction error 1.6 mm FWHM (Gsell et al. 2020), photon
# acollinearity 0.5 deg FWHM. GATE 8.2 stores exact interaction points; the scanner estimates the position
# from the light distribution in the monolithic block, so the measured line-source peak is wider.
def head_frame(p):
    """Head index angle of each detected position: the nearest of 0, 45, ..., 315 deg."""
    ang = np.arctan2(p[:, 1], p[:, 0])
    return np.round(ang / HEAD_STEP) * HEAD_STEP


def add_acollinearity(p1, p2, src, fwhm_deg, rng):
    """Tilt photon 2 away from exact back-to-back emission by a Gaussian angle (as spres_analysis.py):
    move the second detection point by (distance from the emission point) x (deviation angle),
    perpendicular to the LOR. src: emission point(s), one per LOR or one for all."""
    if fwhm_deg <= 0:
        return p2
    sigma = np.deg2rad(fwhm_deg) / GAUSS_FWHM
    u = p2 - p1
    u /= np.linalg.norm(u, axis=1)[:, None]
    helper = np.where(np.abs(u[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
    e1 = np.cross(u, helper)
    e1 /= np.linalg.norm(e1, axis=1)[:, None]
    e2 = np.cross(u, e1)
    d2 = np.linalg.norm(p2 - src, axis=1)
    dev = rng.normal(0, sigma, (len(p2), 2))
    return p2 + d2[:, None] * (dev[:, :1] * e1 + dev[:, 1:] * e2)


def detector_response(p, plane_fwhm, doi_fwhm, rng):
    """Position estimate of a monolithic block (as spres_analysis.py): GATE centroid + Gaussian errors in
    the frame of the block, DOI on the depth q, in-plane on t and zl, kept inside the crystal."""
    ang = head_frame(p)
    c, s = np.cos(ang), np.sin(ang)
    q = p[:, 0] * c + p[:, 1] * s
    t = -p[:, 0] * s + p[:, 1] * c
    zc = np.clip(np.round(p[:, 2] / RING_PITCH), -1, 1) * RING_PITCH
    zl = p[:, 2] - zc
    sp, sd = plane_fwhm / GAUSS_FWHM, doi_fwhm / GAUSS_FWHM
    if sd > 0:
        q = q + rng.normal(0, sd, len(q))
    q = np.clip(q, R_FRONT, R_FRONT + DEPTH)
    half = HALF_FRONT + TAPER * (q - R_FRONT)
    if sp > 0:
        t = t + rng.normal(0, sp, len(t))
        zl = zl + rng.normal(0, sp, len(zl))
    t = np.clip(t, -half, half)
    zl = np.clip(zl, -half, half)
    return np.column_stack([q * c - t * s, q * s + t * c, zl + zc])


def blur_lors(a, args, rng, acollinearity=True):
    """Coincidences with blurred detection positions: acollinearity around the GATE decay position of
    photon 1 (prompts; not for delayed pairs, which are two decays anyway), then the detector response."""
    if not len(a["globalPosX1"]):
        return a
    p1 = np.column_stack([a[f"globalPos{k}1"] for k in "XYZ"]).astype(float)
    p2 = np.column_stack([a[f"globalPos{k}2"] for k in "XYZ"]).astype(float)
    if acollinearity and all(f"sourcePos{k}1" in a for k in "XYZ"):
        src = np.column_stack([a[f"sourcePos{k}1"] for k in "XYZ"]).astype(float)
        p2 = add_acollinearity(p1, p2, src, args.acolin_fwhm_deg, rng)
    e1 = detector_response(p1, args.plane_fwhm, args.doi_fwhm, rng)
    e2 = detector_response(p2, args.plane_fwhm, args.doi_fwhm, rng)
    b = dict(a)
    for i, k in enumerate("XYZ"):
        b[f"globalPos{k}1"], b[f"globalPos{k}2"] = e1[:, i], e2[:, i]
    return b


def in_active_area(x, y, z, active_mm):
    """True where an interaction lies inside the active area of its block (as sens_analysis.py).

    Emulates a detector that only uses the central active_mm x active_mm of each 48 x 48 mm block
    face (Gonzalez et al. 2016: 46 mm): interactions closer than (48 - active_mm) / 2 mm to the
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


def volume_group(names):
    """GATE volume names ('rfCoil1_phys', 'NULL', ...) -> the groups in GROUPS.
    '' = no scatter, 'other' = a PhantomSD volume that is not in any group."""
    base = np.char.replace(np.asarray(names, dtype=str), "_phys", "")
    out = np.full(base.shape, "other", dtype=object)
    out[base == "NULL"] = ""
    for g, vols in GROUPS.items():
        out[np.isin(base, [v for v in vols if not v.endswith("*")])] = g
        for v in vols:
            if v.endswith("*"):
                out[np.char.startswith(base, v[:-1])] = g
    return out


def truth_classes(p, source_id):
    """GATE-truth class of every prompt (diagnostic only; NEMA does not use it)."""
    n = len(p["eventID1"])
    rand = p["eventID1"] != p["eventID2"]                          # photons from two decays
    if "sourceID1" in p:
        f1, f2 = p["sourceID1"] == source_id, p["sourceID2"] == source_id
    else:
        f1 = f2 = np.ones(n, bool)
    phantom = ~rand & f1 & f2                                      # one F-18 decay
    nscat = np.zeros(n, int)
    for k in ("comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2"):
        if k in p:
            nscat = nscat + p[k]
    scat = phantom & (nscat > 0)
    group = np.full(n, "", dtype=object)
    if "comptVolName1" in p:
        g1 = volume_group(np.where(p["comptVolName1"] == "NULL", p["RayleighVolName1"], p["comptVolName1"]))
        g2 = volume_group(np.where(p["comptVolName2"] == "NULL", p["RayleighVolName2"], p["comptVolName2"]))
        for g in reversed(GROUP_ORDER):     # later assignments win -> object > coil > front > other
            group[(g1 == g) | (g2 == g)] = g
    else:
        group[:] = "other"
    group[~scat] = ""
    return {"unscattered": phantom & ~scat,
            "scat_object": scat & (group == "object"),
            "scat_coil": scat & (group == "coil"),
            "scat_front": scat & np.isin(group, ["front", "other"]),
            "randoms": rand,
            "intrinsic": ~rand & ~phantom,                         # one Lu-176 decay
            "no_f18": ~f1 & ~f2}                                   # no F-18 photon at all (blank-scan-like)


# ============================================================================================
# 4. Measured count-rate curves (PET-MR NEC curves NEMA Masar.xlsx)
# ============================================================================================
def find_file(path):
    if path and os.path.isfile(path):
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, os.path.basename(path or "")), os.path.join(os.getcwd(), os.path.basename(path or ""))):
        if os.path.isfile(cand):
            return cand
    return None


def load_measured(path, sheet):
    """Measured frames with complete values, rates in kcps, SF in %.

    Columns from row 7: A activity (MBq), G Rtotal, H Rtrues, I Rrandom, J Rscat (cps), K Rintr.
    NECR = H^2 / G (column L of the sheet), SF = J / (H + J).
    """
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        raise ValueError(f"no sheet '{sheet}' (sheets: {wb.sheetnames})")
    ws = wb[sheet]
    rows, rint = [], []
    for r in ws.iter_rows(min_row=7, values_only=True):
        c = [r[i] if len(r) > i else None for i in (0, 6, 7, 8, 9, 10)]
        if all(isinstance(v, (int, float)) for v in c[:5]) and c[0] > 0:
            rows.append([float(v) for v in c[:5]])
            if isinstance(c[5], (int, float)):
                rint.append(float(c[5]))
    if not rows:
        raise ValueError(f"sheet '{sheet}' has no complete frames")
    a = np.array(rows)
    A, tot, t, r, s = a[:, 0], a[:, 1] / 1e3, a[:, 2] / 1e3, a[:, 3] / 1e3, a[:, 4] / 1e3
    with np.errstate(divide="ignore", invalid="ignore"):
        return {"activity_MBq": A, "R_TOT": tot, "R_t": t, "R_r": r, "R_s": s,
                "R_NEC": np.where(tot > 0, t ** 2 / tot, np.nan),
                "R_NEC_RS": np.where(tot + r > 0, t ** 2 / (tot + r), np.nan),
                "SF_pct": np.where(t + s > 0, 100 * s / (t + s), np.nan),
                "rint_cps": float(np.median(rint)) if rint else np.nan,
                "sheet": sheet, "path": path, "header": ws["A5"].value}


def measured_at(meas, activity, extrapolate=0.05):
    """Measured values at the simulated activity: linear in log(activity) between the two
    neighbouring frames (exact when the activity is a measured one), up to 5 % beyond the
    measured range. NECR and SF are recomputed from the interpolated T, S and Total.
    Returns (dict of values, number of the nearest frame, 1 = highest activity) or (None, None).
    """
    a = meas["activity_MBq"]
    order = np.argsort(a)
    x = np.log(a[order])
    lx = np.log(activity)
    if lx < x[0] - np.log(1 + extrapolate) or lx > x[-1] + np.log(1 + extrapolate):
        return None, None
    i = int(np.clip(np.searchsorted(x, lx), 1, len(x) - 1))
    w = (lx - x[i - 1]) / (x[i] - x[i - 1])
    v = {k: float(meas[k][order][i - 1] + w * (meas[k][order][i] - meas[k][order][i - 1]))
         for k in ("R_t", "R_s", "R_r", "R_TOT")}
    v["R_NEC"] = v["R_t"] ** 2 / v["R_TOT"] if v["R_TOT"] > 0 else np.nan
    v["R_NEC_RS"] = v["R_t"] ** 2 / (v["R_TOT"] + v["R_r"]) if v["R_TOT"] > 0 else np.nan
    v["SF_pct"] = 100 * v["R_s"] / (v["R_t"] + v["R_s"]) if (v["R_t"] + v["R_s"]) > 0 else np.nan
    return v, int(np.argmin(np.abs(a - activity))) + 1


def activities_from_xlsx(path):
    """Activities in MBq from the first column of the first sheet (values in Bq); row k of the
    numbers = frame k."""
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True).worksheets[0]
    return [float(r[0]) / 1e6 for r in ws.iter_rows(values_only=True)
            if r and isinstance(r[0], (int, float)) and r[0] > 0]


# ============================================================================================
# 5. One file
# ============================================================================================
def analyse_file(path, args, meas_rint, fallback=None):
    """The whole NEMA procedure on one file. Returns (results dict, data for the figure).

    fallback = (activity in MBq, where it comes from) for numbered files without a run macro.
    """
    info = run_settings(path, args.macro, args.macro_dirs)
    duration = args.duration or info.get("duration")
    if not duration:
        raise ValueError("duration unknown: no run macro found (see --macro-dirs), give --duration "
                         "(e.g. --duration 1)")
    p = load(path, "Coincidences", truth=True)
    if p is None:
        raise ValueError("no Coincidences tree")
    dl = load(path, "delay", truth=False)
    da = load(path, "delayAll", truth=False)            # necr_run.py --delayed-all-pulse-open; reported only
    notes = []
    if dl is None:
        dl = {k: np.zeros(0) for k in GEOMETRY}
        notes.append("no delay tree: randoms = 0")
    if info.get("coil_mm") and getattr(args, "coil", None) and info["coil_mm"] != args.coil:
        notes.append(f"WARNING coil Quad{info['coil_mm']} in the run macro, compared with the Quad{args.coil} measurement")

    # ---- Lu-176, activity, energy window --------------------------------------------------
    lu_in_data = "sourceID1" in p and bool(np.any((p["sourceID1"] != args.source_id) |
                                                    (p["sourceID2"] != args.source_id)))
    lu176 = info.get("lu176", lu_in_data)
    lu_bq = info.get("lu176_bq", args.lu176_bq) if lu176 else 0.0
    n_prim = primaries(path)
    b2b = info.get("b2b_fraction", 1.0)                              # back-to-back runs emit pairs, not decays
    act_root = (n_prim / duration - lu_bq) / 1e6 / b2b if np.isfinite(n_prim) else np.nan
    if b2b != 1.0:
        notes.append(f"back-to-back source ({b2b:g} pairs per F-18 decay)")
    if args.activity:
        activity, act_from = args.activity, "--activity"
    elif "activity" in info:
        activity, act_from = info["activity"] / 1e6, os.path.relpath(info["macro"])
    elif fallback is not None:
        activity, act_from = fallback
    else:
        activity, act_from = act_root, "ROOT decay count"
    if not np.isfinite(activity) or activity <= 0:
        raise ValueError("activity unknown: no run macro and no total_nb_primaries, give --activity")
    if np.isfinite(act_root) and act_from != "ROOT decay count":
        sigma = np.sqrt(n_prim) / duration / 1e6                     # Poisson noise of the decay count
        if abs(act_root - activity) > 5 * sigma + 0.02 * activity:
            notes.append(f"ROOT file has {act_root:.4f} MBq of decays, {act_from} gives {activity:.4f} MBq")
    e_low, e_high = info.get("e_low", np.nan), info.get("e_high", np.nan)
    window = f"{e_low:g}-{e_high:g}" if np.isfinite(e_low) else "?"
    if np.isfinite(e_low) and (abs(e_low - MEAS_WINDOW[0]) > 1 or abs(e_high - MEAS_WINDOW[1]) > 1):
        notes.append(f"energy window {window} keV differs from the measured {MEAS_WINDOW[0]:g}-{MEAS_WINDOW[1]:g} keV")

    # ---- time the data really cover --------------------------------------------------------
    # GATE 8.2 does not flush the sorters' presort buffer (256 singles) at the end of the run, so
    # the last ~256 singles never form coincidences. At low activity that is a noticeable part of
    # the run (0.1 s test files: 0.47 ms x MBq / A, i.e. 27 % at 0.018 MBq). The rates are therefore
    # divided by the time up to the last coincidence (+ one mean gap), unless --nominal-time.
    t_end = max([float(x["time1"].max()) for x in (p, dl) if len(x["time1"])] or [0.0])
    n_prompts = len(p["time1"])
    if t_end > duration * 1.001:
        raise ValueError(f"coincidences up to {t_end:.4g} s but the duration is {duration:g} s: wrong "
                         "--duration or run macro, the rates would be wrong (file skipped)")
    t_eff = min(duration, t_end * (1 + 1 / max(n_prompts, 1))) if n_prompts else duration
    if args.nominal_time:
        t_eff = duration
    elif t_eff < 0.999 * duration:
        # The unflushed buffer holds 256 singles, so it can only hide a few hundred prompts. Many
        # more missing prompts mean the run itself was shorter than its macro / --duration says.
        missing = n_prompts * (duration - t_eff) / max(t_eff, 1e-12)
        if missing > 300:
            notes.append(f"WARNING data end at {t_end:.4g} s, but the duration is {duration:g} s: the run was "
                         f"shorter than stated (wrong --duration or macro?); rates use {t_eff:.4g} s")
        else:
            notes.append(f"data end at {t_end:.4g} s (presort buffer not flushed): rates use {t_eff:.4g} s")

    active_kept = 1.0
    if args.active_mm:                                   # emulated inactive block edges
        p, active_kept = active_cut(p, args.active_mm)
        if len(dl["eventID1"]):
            dl, _ = active_cut(dl, args.active_mm)
        if da is not None and len(da["eventID1"]):
            da, _ = active_cut(da, args.active_mm)

    if args.detector_blur:                               # detector response as spres_analysis.py
        rng = np.random.default_rng(args.blur_seed + zlib.crc32(os.path.basename(path).encode()))
        p = blur_lors(p, args, rng)
        if len(dl["eventID1"]):
            dl = blur_lors(dl, args, rng, acollinearity=False)
        if da is not None and len(da["eventID1"]):
            da = blur_lors(da, args, rng, acollinearity=False)
        notes.append(f"detector blur added: in-plane {args.plane_fwhm:g} mm, DOI {args.doi_fwhm:g} mm FWHM, "
                     f"acollinearity {args.acolin_fwhm_deg:g} deg")

    # ---- sinogram coordinates, mask, truth ----------------------------------------------------
    phi, s, z = sino(p)
    keep = np.abs(s) <= args.mask_halfwidth                         # prompts inside the 8 mm mask
    keep_d = np.abs(sino(dl)[1]) <= args.mask_halfwidth if len(dl["eventID1"]) else np.zeros(0, bool)
    cls = truth_classes(p, args.source_id)

    # ---- line-source position for the alignment ----------------------------------------------
    src = (args.src_x, args.src_y)
    if src[0] is None or src[1] is None:
        if "sourcePosX1" not in p:
            raise ValueError("no sourcePosX1/Y1 in the file: give --src-x and --src-y")
        own = (p["eventID1"] == p["eventID2"])
        if "sourceID1" in p:
            own &= p["sourceID1"] == args.source_id
        if not own.any():
            own = p["eventID1"] == p["eventID2"]
        src = (float(np.mean(p["sourcePosX1"][own])), float(np.mean(p["sourcePosY1"][own])))

    # ---- NEMA: summed projection and strip ------------------------------------------------------
    if args.align == "known":
        prof, centers, delta = nema_known(phi, s, keep, src, args)
        C_TOT, C_RS, CL, CR = strip(prof, centers, args.pixel, args.strip)
    else:
        prof_z, centers = nema_max(phi, s, z, keep, args)
        res = np.array([strip(pz, centers, args.pixel, args.strip) for pz in prof_z if pz.sum() > 0])
        C_TOT, C_RS, CL, CR = res[:, 0].sum(), res[:, 1].sum(), res[:, 2].sum(), res[:, 3].sum()
        prof = prof_z.sum(0)
        delta = s - (src[0] * np.cos(phi) + src[1] * np.sin(phi))   # truth split and figure only
    C_R = float(keep_d.sum())                                       # delayed inside the mask
    # second delayed sorter (every single opens a window): every delayed pair = singles-rate randoms.
    # Reported as R_r_all only; the scatter below still uses C_R of the 'delay' sorter.
    keep_a = (np.abs(sino(da)[1]) <= args.mask_halfwidth if len(da["eventID1"]) else np.zeros(0, bool)) \
        if da is not None else None

    bg_r = 0.0
    if args.add_measured_bg:                     # measured blank background added, as in the sensitivity analysis
        if lu176:
            raise ValueError("Lu-176 is in this run's model: --add-measured-bg is for runs made with "
                             "necr_run.py --no-lu176 (the background would be counted twice)")
        bg_r = args.bg_randoms_cps * t_eff
        C_TOT += args.bg_total_cps * t_eff
        C_RS += args.bg_sr_cps * t_eff
        C_R += bg_r
        notes.append(f"measured background added: Total {args.bg_total_cps:g}, S+R {args.bg_sr_cps:g}, "
                     f"randoms {args.bg_randoms_cps:g} cps")

    # ---- rates (kcps) ------------------------------------------------------------------------------
    if args.rint_cps is not None:
        rint = args.rint_cps
    else:
        rint = meas_rint if (lu176 or args.add_measured_bg) else 0.0
    T = t_eff * 1e3                                                 # counts / T = kcps
    r = {"file": os.path.basename(path), "label": os.path.splitext(os.path.basename(path))[0],
         "activity_MBq": float(activity), "activity_from": act_from,
         "activity_kBq_per_ml": float(activity) * 1e3 / PHANTOM_VOLUME_ML,
         "duration_s": float(duration), "duration_eff_s": float(t_eff),
         "window_keV": window, "QE_model": info.get("qe", np.nan), "coil_mm": info.get("coil_mm", np.nan),
         "lu176_in_model": bool(lu176), "align": args.align,
         "active_mm": args.active_mm if args.active_mm else 48.0, "active_area_kept": active_kept,
         "R_t": (C_TOT - C_RS) / T, "R_s": (C_RS - C_R) / T - rint / 1e3, "R_r": C_R / T, "R_TOT": C_TOT / T,
         "Rint_cps": rint, "C_TOT": C_TOT, "C_RS": C_RS, "C_R": C_R, "C_L": CL, "C_R_edge": CR,
         "R_r_all": (keep_a.sum() + bg_r) / T if keep_a is not None else np.nan,
         "C_R_all": float(keep_a.sum()) if keep_a is not None else np.nan}
    r["R_NEC"] = r["R_t"] ** 2 / r["R_TOT"] if r["R_TOT"] > 0 else 0.0
    r["R_NEC_RS"] = r["R_t"] ** 2 / (r["R_TOT"] + r["R_r"]) if r["R_TOT"] > 0 else 0.0
    r["SF_pct"] = 100 * r["R_s"] / (r["R_t"] + r["R_s"]) if (r["R_t"] + r["R_s"]) > 0 else np.nan

    # ---- truth diagnostics ---------------------------------------------------------------------------
    edges = np.append(centers - args.pixel / 2, centers[-1] + args.pixel / 2)
    comps = []
    for key, label in CLASSES:
        h = np.histogram(delta[keep & cls[key]], edges)[0].astype(float)
        comps.append((label, h))
        r[f"nemaT_{key}"] = (h.sum() - strip(h, centers, args.pixel, args.strip)[1]) / T
    # profile of the coincidences without any F-18 photon on a fixed grid; main() pools the files
    # below 1 MBq into one long blank-scan-like profile for the model's own R_int (one file alone is
    # far too noisy for the two-pixel NEMA background line)
    fc = fixed_centers(args)
    r["_no_f18_profile"] = np.histogram(delta[keep & cls["no_f18"]],
                                        np.append(fc - args.pixel / 2, fc[-1] + args.pixel / 2))[0]
    instrip = keep & (np.abs(delta) <= args.strip)
    for key, _ in CLASSES:
        r[f"band_{key}"] = (keep & cls[key]).sum() / T
        r[f"strip_{key}"] = (instrip & cls[key]).sum() / T
    r.update(truth_T=cls["unscattered"].sum() / T,
             truth_S=(cls["scat_object"] | cls["scat_coil"] | cls["scat_front"]).sum() / T,
             truth_R=cls["randoms"].sum() / T, truth_intrinsic=cls["intrinsic"].sum() / T,
             truth_prompts=len(s) / T, delayed_all=len(keep_d) / T,
             delayedAll_all=len(keep_a) / T if keep_a is not None else np.nan)
    r.update(src_x=src[0], src_y=src[1], activity_root_MBq=act_root, lu176_Bq=lu_bq,
             note="; ".join(notes), macro=info.get("macro", ""))
    return r, (centers, prof, CL, CR, comps)


def process(path, args, meas_rint, plots, fallback=None):
    """Analyse one file and save its profile figure; returns (row, error text). Runs in a worker
    process with --jobs > 1."""
    try:
        r, (centers, prof, CL, CR, comps) = analyse_file(path, args, meas_rint, fallback)
    except Exception as exc:
        return None, f"{path}: {exc!r}"
    if plots:
        try:
            plot_profile(os.path.join(plots, f"profile_{r['label']}.png"),
                         f"NEMA summed projection: {r['file']}", centers, prof, CL, CR, comps, args, r)
        except Exception as exc:
            r["note"] = "; ".join(n for n in (r["note"], f"profile figure failed: {exc!r}") if n)
    return r, None


# ============================================================================================
# 6. Comparison with the measurement and NEMA report values
# ============================================================================================
def parse_range(text):
    """'all' / '1.5-20' / '5-' / '-20' -> (label, lo, hi) in MBq."""
    text = text.strip()
    if text.lower() == "all":
        return "all frames", 0.0, np.inf
    m = re.fullmatch(r"([\d.]*)\s*-\s*([\d.]*)", text)
    if not m or not (m.group(1) or m.group(2)):
        sys.exit(f"--mard-range: cannot read '{text}' (use all, 1.5-20, 5- or -20)")
    lo = float(m.group(1)) if m.group(1) else 0.0
    hi = float(m.group(2)) if m.group(2) else np.inf
    label = f"from {lo:g} MBq" if hi == np.inf else (f"up to {hi:g} MBq" if lo == 0 else f"{lo:g}-{hi:g} MBq")
    return label, lo, hi


def compare(rows, meas, args):
    """Measured values at every simulated activity and one MARD per component.

    The measured curve is interpolated at the simulated activity (measured_at), so files at other
    activities (e.g. rounded to whole kBq) are compared at exactly their own activity. For files at
    a measured activity it is the measured frame itself.
    MARD = mean over the frames of |sim - meas| / meas x 100, one value per component, for every
    range in args.mard_ranges (MARD_RANGES, then --mard-range).
    Returns [(range label, {component name: (MARD, number of frames)}), ...].
    """
    for r in rows:
        v, frame = measured_at(meas, r["activity_MBq"]) if meas else (None, None)
        r["meas_frame"] = frame if frame else np.nan
        for _, key, _ in METRICS:
            r[f"meas_{key}"] = v[key] if v else np.nan
        r["meas_R_NEC_RS"] = v["R_NEC_RS"] if v else np.nan
        if v is None and meas:
            r["note"] = "; ".join(n for n in (r["note"], "activity outside the measured range") if n)
    out = []
    for text in args.mard_ranges:
        label, lo, hi = parse_range(text)
        sel = [r for r in rows if lo <= r["activity_MBq"] <= hi]
        mard = {}
        for name in MARD_ORDER:
            key = dict((n, k) for n, k, _ in METRICS)[name]
            ard = [abs(r[key] - r[f"meas_{key}"]) / r[f"meas_{key}"] * 100 for r in sel
                   if np.isfinite(r[key]) and np.isfinite(r[f"meas_{key}"]) and r[f"meas_{key}"] != 0]
            mard[name] = (float(np.mean(ard)) if ard else np.nan, len(ard))
        ard = [abs(r["R_r_all"] - r["meas_R_r"]) / r["meas_R_r"] * 100 for r in sel     # second delayed sorter
               if np.isfinite(r["R_r_all"]) and np.isfinite(r["meas_R_r"]) and r["meas_R_r"] != 0]
        if ard:
            mard["Randoms (all pairs)"] = (float(np.mean(ard)), len(ard))
        out.append((label, mard))
    return out


PEAK_WINDOW = 0.15      # the neighbours used for the peak must lie within +-15 % in activity


def peak(act, y):
    """Peak value and the activity where it occurs.

    Three-point peak interpolation: the parabola through the highest frame and its two neighbours
    (the measured frames are ~6.5 % apart). Its vertex is never below the highest frame and lies
    between the neighbours. When a neighbour is more than 15 % away in activity (e.g. --every 5
    runs) or the peak is at the end of the curve, the highest frame itself.
    Returns (value, activity, method, peak bracketed by the data)."""
    act, y = np.asarray(act, float), np.asarray(y, float)
    ok = np.isfinite(act) & np.isfinite(y)
    if not ok.any():
        return np.nan, np.nan, "none", False
    o = np.argsort(act[ok])
    act, y = act[ok][o], y[ok][o]
    i = int(np.argmax(y))
    if not 0 < i < len(y) - 1:
        return float(y[i]), float(act[i]), "highest frame (at the end of the curve)", False
    if act[i - 1] >= act[i] * (1 - PEAK_WINDOW) and act[i + 1] <= act[i] * (1 + PEAK_WINDOW):
        c = np.polyfit(act[i - 1:i + 2], y[i - 1:i + 2], 2)
        if c[0] < 0:
            xv = -c[1] / (2 * c[0])
            return float(np.polyval(c, xv)), float(xv), "3-point peak interpolation", True
    return float(y[i]), float(act[i]), "highest frame (neighbours too far apart for the interpolation)", True


def peak_max(act, y):
    """Peak value and activity as the highest frame itself (--peak-fit max): direct comparison of
    the frames, no interpolation or fit. Returns (value, activity, method, peak bracketed by the data)."""
    act, y = np.asarray(act, float), np.asarray(y, float)
    ok = np.isfinite(act) & np.isfinite(y)
    if not ok.any():
        return np.nan, np.nan, "none", False
    o = np.argsort(act[ok])
    act, y = act[ok][o], y[ok][o]
    i = int(np.argmax(y))
    inside = 0 < i < len(y) - 1
    return (float(y[i]), float(act[i]), "highest frame" + ("" if inside else " (at the end of the curve)"),
            inside)


PEAK_FIT_DEG = 4        # --peak-fit smooth: polynomial degree in ln(activity)
PEAK_FIT_FRAC = 0.90    # --peak-fit smooth: frames down to 90 % of the highest frame


def peak_fit(act, y, deg=PEAK_FIT_DEG, frac=PEAK_FIT_FRAC, n_mc=2000, seed=1):
    """Peak value and activity from a least-squares fit (--peak-fit smooth).

    A polynomial of degree `deg` in ln(activity) through the contiguous frames around the highest
    frame whose value is at least `frac` x that frame's (or up to the end of the data), the same rule
    for both curves (the frames are equally spaced in ln A). Its maximum inside the fitted range is
    the peak, so the noise of
    single frames (0.35 % rms in 1 s simulated frames, while the NECR changes by < 0.2 % within
    +-2 MBq of its peak) averages out. 1 sd of the peak value and activity: the fit coefficients
    drawn n_mc times from their covariance (scaled by the residuals).
    Falls back to peak() when the peak is at the end of the curve, fewer than deg + 4 frames
    qualify, or the fitted maximum lies at the edge of the fitted range.
    Returns a dict: value, activity, sd_value, sd_activity, method, ok (peak bracketed by the
    data), fit (None or (coefficients, ln A of the highest frame, first and last fitted activity))."""
    act, y = np.asarray(act, float), np.asarray(y, float)
    ok = np.isfinite(act) & np.isfinite(y) & (act > 0)
    o = np.argsort(act[ok])
    act, y = act[ok][o], y[ok][o]

    def fallback(why):
        v, a, how, bracketed = peak(act, y)
        return {"value": v, "activity": a, "sd_value": np.nan, "sd_activity": np.nan,
                "method": f"{how} (no smooth fit: {why})", "ok": bracketed, "fit": None}

    if len(y) == 0:
        return fallback("no data")
    i = int(np.argmax(y))
    lo = hi = i
    while lo > 0 and y[lo - 1] >= frac * y[i]:
        lo -= 1
    while hi < len(y) - 1 and y[hi + 1] >= frac * y[i]:
        hi += 1
    if not 0 < i < len(y) - 1:
        return fallback("peak at the end of the curve")
    n = hi - lo + 1
    if n < deg + 4:
        return fallback(f"only {n} frames within {100 * (1 - frac):g} % of the highest")
    x0 = np.log(act[i])
    x, yy = np.log(act[lo:hi + 1]) - x0, y[lo:hi + 1]
    c, cov = np.polyfit(x, yy, deg, cov=True)
    grid = np.linspace(x[0], x[-1], 801)
    k = int(np.argmax(np.polyval(c, grid)))
    if k in (0, len(grid) - 1):
        return fallback("fitted maximum at the edge of the fitted range")
    draws = np.random.default_rng(seed).multivariate_normal(c, cov, n_mc)
    vals = np.vander(grid, deg + 1) @ draws.T                       # (grid, draws)
    kd = np.argmax(vals, axis=0)
    rms = 100 * np.std((yy - np.polyval(c, x)) / yy, ddof=deg + 1)
    return {"value": float(np.polyval(c, grid[k])), "activity": float(np.exp(x0 + grid[k])),
            "sd_value": float(np.std(vals[kd, np.arange(n_mc)])), "sd_activity": float(np.std(np.exp(x0 + grid[kd]))),
            "method": f"smooth fit (degree-{deg} polynomial in ln A through {n} frames, {act[lo]:.3g}-{act[hi]:.3g} MBq, "
                      f"residual rms {rms:.2f} %)", "ok": True, "fit": (c, x0, act[lo], act[hi])}


def nema_report(rows, meas, args=None):
    """NEMA Sec. 4.5 values for simulation and measurement, with ARD = |sim - meas| / meas x 100.

    Sec. 4.5.2: peak true rate R_t,peak, peak NECR R_NEC,peak (T^2/Total, as the sheet) and the
    activity concentration (and activity) at which they are reached, both curves treated alike
    (peak()). Sec. 4.5.3 / 4.4.1: system scatter fraction, sum R_s / sum (R_t + R_s) over the frames
    whose measured randoms are below 1 % of the measured trues, the same frames on both sides.
    Returns (rows of the table, notes).
    """
    out, notes = [], []

    def ard(s, m):
        return abs(s - m) / abs(m) * 100 if np.isfinite(s) and np.isfinite(m) and m else np.nan

    a = [r["activity_MBq"] for r in rows]
    smooth = args is not None and getattr(args, "peak_fit", "3point") == "smooth"
    for key, sym, name in (("R_t", "t", "peak true rate"), ("R_NEC", "NEC", "peak NECR (T^2/Total)")):
        if smooth:                                  # --peak-fit smooth: least-squares fit, with 1 sd
            fs = peak_fit(a, [r[key] for r in rows], args.peak_fit_deg, args.peak_fit_frac)
            fm = peak_fit(meas["activity_MBq"], meas[key], args.peak_fit_deg, args.peak_fit_frac) if meas else None
            sv, sa, s_how, s_ok = fs["value"], fs["activity"], fs["method"], fs["ok"]
            mv, ma, m_how = (fm["value"], fm["activity"], fm["method"]) if fm else (np.nan, np.nan, "")
            for who, f in (("simulation", fs), ("measurement", fm)):
                if f and np.isfinite(f["sd_activity"]):
                    notes.append(f"{name}, {who}: {f['value']:.1f} +- {f['sd_value']:.1f} kcps at "
                                 f"{f['activity']:.2f} +- {f['sd_activity']:.2f} MBq (1 sd of the fit)")
        else:                                       # 3point (default) or max (the highest frame itself)
            find = peak_max if getattr(args, "peak_fit", "3point") == "max" else peak
            sv, sa, s_how, s_ok = find(a, [r[key] for r in rows])
            mv, ma, m_how, _ = find(meas["activity_MBq"], meas[key]) if meas else (np.nan, np.nan, "", False)
        notes.append(f"{name}: simulation {s_how}" + (f", measurement {m_how}" if meas else ""))
        out += [{"quantity": f"R_{sym},peak, {name}", "sim": sv, "meas": mv, "unit": "kcps", "ARD_pct": ard(sv, mv)},
                {"quantity": f"a_{sym},peak, activity concentration at the peak",
                 "sim": sa * 1e3 / PHANTOM_VOLUME_ML, "meas": ma * 1e3 / PHANTOM_VOLUME_ML, "unit": "kBq/ml",
                 "ARD_pct": ard(sa, ma)},
                {"quantity": f"A_{sym},peak, activity at the peak", "sim": sa, "meas": ma, "unit": "MBq",
                 "ARD_pct": ard(sa, ma)}]
        if not s_ok:
            notes.append(f"the simulated {name} is at the end of the simulated activities: the peak is not "
                         "bracketed, simulate activities on both sides of it")
    if meas:
        low = [r for r in rows if np.isfinite(r["meas_R_t"]) and r["meas_R_t"] > 0
               and r["meas_R_r"] / r["meas_R_t"] < 0.01]
        if low:
            ss = sum(r["R_s"] for r in low) / sum(r["R_t"] + r["R_s"] for r in low) * 100
            ms = sum(r["meas_R_s"] for r in low) / sum(r["meas_R_t"] + r["meas_R_s"] for r in low) * 100
            acts = [r["activity_MBq"] for r in low]
            out.append({"quantity": f"SF, system scatter fraction ({len(low)} frames, {min(acts):.3g}-"
                                    f"{max(acts):.3g} MBq)", "sim": ss, "meas": ms, "unit": "%", "ARD_pct": ard(ss, ms)})
        else:
            notes.append("no simulated frame where the measured randoms are below 1 % of the trues: no system SF")
    return out, notes


# ============================================================================================
# 7. Figures
# ============================================================================================
def plot_profile(fname, title, centers, prof, CL, CR, comps, args, r, txt=None, colors=None):
    """Stacked histogram of the summed projection by truth class, the NEMA background line and the
    +-7 mm strip. Shows which scatter NEMA counts as true (above the line inside the strip). The
    peak is cut off so the background is readable.
    txt / colors replace the text lines and the bar colours (e.g. for a measured profile: one class,
    no truth)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = colors or ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    bottom = np.zeros_like(centers, dtype=float)
    for (lbl, h), col in zip(comps, colors):
        if h.sum() == 0:
            continue
        ax.bar(centers, h, width=args.pixel, bottom=bottom, color=col, label=lbl,
               edgecolor="#fcfcfb", linewidth=0.3)
        bottom += h
    ax.plot([-args.strip, args.strip], [CL, CR], color="#0b0b0b", lw=2, label="NEMA background under the strip")
    for x in (-args.strip, args.strip):
        ax.axvline(x, color="#52514e", lw=1, ls="--")
    ytop = 2.6 * max(CL, CR)
    if ytop <= 0:
        ytop = max(prof.max() * 1.1, 1.0)
    ax.set_ylim(0, ytop)
    ax.set_xlim(-32, 32)
    ax.set_xlabel("Radial offset from line source (mm)", color="#0b0b0b")
    ax.set_ylabel(f"Counts per {args.pixel:g} mm pixel", color="#0b0b0b")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#b5b4ae")
    ax.tick_params(colors="#52514e")
    ax.grid(axis="y", color="#e4e3dd", lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="upper right", bbox_to_anchor=(1.0, 0.98))
    if txt is None:
        txt = (f"Activity {r['activity_MBq']:.3f} MBq x {r['duration_s']:g} s   NEMA:  T {r['R_t']:.1f}   "
               f"S {r['R_s']:.1f}   R {r['R_r']:.1f}   TOT {r['R_TOT']:.1f}   NECR {r['R_NEC']:.1f} kcps\n"
               f"NEMA trues by truth: unscattered {r['nemaT_unscattered']:.1f}, coil scatter {r['nemaT_scat_coil']:.1f}, "
               f"other scatter {r['nemaT_scat_object'] + r['nemaT_scat_front']:.1f}, randoms {r['nemaT_randoms']:.1f}, "
               f"Lu-176 {r['nemaT_intrinsic']:.2f} kcps   (y-axis cut: peak pixel = {prof.max():.0f} counts)")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.text(0.01, 0.985, title, va="top", fontsize=11, color="#0b0b0b")
    fig.text(0.01, 0.94, txt, va="top", fontsize=8, color="#52514e")
    fig.savefig(fname)
    plt.close(fig)


def _series(rows, meas, key):
    """(activity, sim) of the simulation and (activity, meas) of all measured frames, sorted."""
    rs = sorted(rows, key=lambda r: -r["activity_MBq"])
    a_sim = np.array([r["activity_MBq"] for r in rs])
    y_sim = np.array([r[key] for r in rs], float)
    if meas:
        return a_sim, y_sim, meas["activity_MBq"], meas[key]
    return a_sim, y_sim, np.array([]), np.array([])


def _highlight(ax, label=True):
    """Shade 1.5-20 MBq."""
    ax.axvspan(HIGHLIGHT[0], HIGHLIGHT[1], color="gold", alpha=0.15, zorder=0,
               label=f"{HIGHLIGHT[0]:g}–{HIGHLIGHT[1]:g} MBq" if label else None)


MEAS_LABEL, SIM_LABEL, SIM_ALL_LABEL = "Measured", "Simulated", "Simulated, all pairs"   # shared legend


def _panel(ax, rows, meas, name, key, ylabel, fs_label=14, fs_tick=12, fs_legend=14, legend=True):
    """One metric: measured black o, simulated red x, gold band.
    legend=False (grouped canvases): no legend in the panel and generic labels (Measured, Simulated),
    so the figure gets one legend for all panels (plot_metric_figures)."""
    a_sim, y_sim, a_m, y_m = _series(rows, meas, key)
    _highlight(ax)
    lab = (lambda own, generic: own) if legend else (lambda own, generic: generic)
    if len(a_m):
        ax.plot(a_m, y_m, marker="o", markersize=3, color="black", label=lab(f"{name} (meas)", MEAS_LABEL))
    ax.plot(a_sim, y_sim, marker="x", color="tab:red", linewidth=1.4, label=lab(f"{name} (sim)", SIM_LABEL))
    if key == "R_r" and any(np.isfinite(r["R_r_all"]) for r in rows):    # second delayed sorter
        a2, y2, _, _ = _series(rows, None, "R_r_all")
        ax.plot(a2, y2, marker="+", linestyle="--", color="tab:red", linewidth=1.0,
                label=lab(f"{name}, all pairs (sim)", SIM_ALL_LABEL))
    ax.set_xlabel("Activity (MBq)", fontsize=fs_label)
    ax.set_ylabel(ylabel, fontsize=fs_label)
    if key == "SF_pct":                                     # SF axis from 5 to 45 %, widened if the data exceed it
        top = np.nanmax(np.concatenate([y_sim, y_m])) if len(y_sim) else 45
        ax.set_ylim(5, max(45, top * 1.05))
    ax.grid(True)
    if legend:
        ax.legend(fontsize=fs_legend, loc="lower right")
    ax.tick_params(labelsize=fs_tick)


def plot_metric_figures(plots, rows, meas):
    """The figures: one per metric, the 2x2 and 3x2 canvases (one legend below the panels) and
    AllMetrics. ARD and MARD are not plotted; they are in <out>_ARD_MARD.txt."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    letters = {"Trues": "a", "Scattered": "b", "Randoms": "c", "Totals": "d"}
    for name, key, ylabel in METRICS:                       # individual panels
        fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
        _panel(ax, rows, meas, name, key, ylabel, fs_label=18, fs_tick=14, fs_legend=14)
        ax.set_title(name, fontsize=20, fontweight="normal")
        if name in letters:
            ax.text(-0.12, 1.06, letters[name], transform=ax.transAxes, fontsize=20)
        fig.savefig(os.path.join(plots, f"{name}.png"), bbox_inches="tight", dpi=300)
        plt.close(fig)

    for fname, panels, shape, size in (("Grouped_2x2_Metrics.png", METRICS[:4], (2, 2), (12, 10)),
                                       ("Grouped_3x2_AllMetrics.png",
                                        METRICS[:4] + (METRICS[5], METRICS[4]), (3, 2), (14, 16))):
        fig, axes = plt.subplots(*shape, figsize=size, constrained_layout=True)
        entries = {}                                        # one legend for all panels
        for ax, (name, key, ylabel), lbl in zip(np.ravel(axes), panels, "abcdef"):
            _panel(ax, rows, meas, name, key, ylabel, legend=False)
            ax.set_title(name, fontsize=16, fontweight="normal")
            ax.text(-0.12, 1.06, lbl, transform=ax.transAxes, fontsize=20, va="top", ha="left")
            for h, l in zip(*ax.get_legend_handles_labels()):
                entries.setdefault(l, h)
        band = f"{HIGHLIGHT[0]:g}–{HIGHLIGHT[1]:g} MBq"
        order = [l for l in (MEAS_LABEL, SIM_LABEL, SIM_ALL_LABEL, band) if l in entries]
        fig.legend([entries[l] for l in order], order, loc="upper center", bbox_to_anchor=(0.5, 0.0),
                   ncol=len(order), fontsize=14)
        fig.savefig(os.path.join(plots, fname), bbox_inches="tight", dpi=300)
        plt.close(fig)

    colors = {"Trues": "tab:red", "Scattered": "tab:blue", "Randoms": "tab:green",
              "Totals": "tab:orange", "NECR": "tab:purple"}
    fig, ax = plt.subplots(figsize=(9, 7), constrained_layout=True)   # canvas with all five rates
    _highlight(ax)
    for name, key, _ in METRICS[:5]:
        a_sim, y_sim, a_m, y_m = _series(rows, meas, key)
        if len(a_m):
            ax.plot(a_m, y_m, marker="o", linestyle=":", color=colors[name], label=f"{name} (meas)")
        ax.plot(a_sim, y_sim, marker="x", linestyle="-", color=colors[name], linewidth=1.4, label=f"{name} (sim)")
    ax.set_xlabel("Activity (MBq)", fontsize=18)
    ax.set_ylabel("Count Rate (kcps)", fontsize=18)
    ax.set_title("All Metrics", fontsize=20, fontweight="normal")
    ax.grid(True)
    ax.legend(fontsize=10, ncol=2, loc="lower right")
    ax.tick_params(labelsize=14)
    fig.savefig(os.path.join(plots, "AllMetrics.png"), bbox_inches="tight", dpi=300)
    plt.close(fig)


def plot_peak_fits(plots, rows, meas, args):
    """PeakFit.png (--peak-fit smooth): trues and NECR around their peaks, the frames, the fitted
    curves and the fitted peaks (+-1 sd), with the 3-point peaks for comparison."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for ax, (name, key) in zip(axes, (("Trues", "R_t"), ("NECR", "R_NEC"))):
        a_sim, y_sim, a_m, y_m = _series(rows, meas, key)
        curves = [("sim", a_sim, y_sim, "tab:red", "x")] + ([("meas", a_m, y_m, "black", "o")] if len(a_m) else [])
        lo, hi, text = np.inf, 0.0, []
        for who, a, y, col, mk in curves:
            f = peak_fit(a, y, args.peak_fit_deg, args.peak_fit_frac)
            p3 = peak(a, y)
            if f["fit"] is not None:
                c, x0, a_lo, a_hi = f["fit"]
                lo, hi = min(lo, a_lo), max(hi, a_hi)
                aa = np.exp(np.linspace(np.log(a_lo), np.log(a_hi), 300))
                ax.plot(aa, np.polyval(c, np.log(aa) - x0), color=col, linewidth=1.6, label=f"fit ({who})")
                ax.errorbar(f["activity"], f["value"], xerr=f["sd_activity"], yerr=f["sd_value"], fmt="D",
                            color=col, markersize=8, capsize=4, zorder=5, label=f"fitted peak ({who})")
                text.append(f"{who}: {f['value']:.1f} ± {f['sd_value']:.1f} kcps at "
                            f"{f['activity']:.2f} ± {f['sd_activity']:.2f} MBq")
            else:
                text.append(f"{who}: no fit, {f['method']}")
            ax.plot(a, y, marker=mk, markersize=4, linestyle="none", color=col, label=f"frames ({who})")
            ax.plot(p3[1], p3[0], marker="s", markersize=9, markerfacecolor="none", markeredgecolor=col,
                    linestyle="none", zorder=4, label=f"3-point peak ({who})")
        if np.isfinite(lo):
            pad = 0.1 * (hi - lo)
            ax.set_xlim(lo - pad, hi + pad)
            inside = [y[(a >= lo - pad) & (a <= hi + pad)] for _, a, y, _, _ in curves]
            vals = np.concatenate(inside) if inside else np.array([])
            if len(vals):
                ax.set_ylim(vals.min() * 0.995, vals.max() * 1.01)
        ax.set_xlabel("Activity (MBq)", fontsize=14)
        ax.set_ylabel("Count Rate (kcps)", fontsize=14)
        ax.set_title(f"{name} around the peak\n" + "\n".join(text), fontsize=12, fontweight="normal")
        ax.grid(True)
        ax.tick_params(labelsize=12)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=4, fontsize=10)
    fig.suptitle(f"Peaks by a degree-{args.peak_fit_deg} polynomial in ln(activity) through the frames down to "
                 f"{100 * args.peak_fit_frac:g} % of the highest (1 sd); hollow squares: 3-point peaks", fontsize=12)
    fig.savefig(os.path.join(plots, "PeakFit.png"), bbox_inches="tight", dpi=200)
    plt.close(fig)


# ============================================================================================
# 8. Output files
# ============================================================================================
def fmt(v, nd=4):
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (float, np.floating)):
        return "nan" if not np.isfinite(v) else f"{v:.{nd}f}"
    return str(v)


def _cell(v):
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (float, np.floating)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, (int, np.integer)):
        return int(v)
    return v


RESULT_COLS = ["label", "activity_MBq", "R_t", "R_s", "R_r", "R_TOT", "R_NEC", "SF_pct",
               "meas_frame", "meas_R_t", "meas_R_s", "meas_R_r", "meas_R_TOT", "meas_R_NEC", "meas_SF_pct",
               "R_NEC_RS", "meas_R_NEC_RS", "R_r_all", "Rint_cps", "duration_eff_s", "activity_from", "note"]


def plotnecr_rows(rows):
    """Rows in the column order of PLOTNECR (sheet '1'), highest activity first."""
    out = []
    for r in sorted(rows, key=lambda r: -r["activity_MBq"]):
        out.append([r[key] if src in (None, "sim") else r[f"meas_{key}"] for _, key, src in PLOTNECR])
    return out


def mard_lines(mards, report, notes, checks, args):
    """The ARD/MARD report as lists of cells: one MARD per component and activity range, the NEMA
    values with their ARD, notes and the model checks."""
    out = [[f"# Simulation vs measurement ({os.path.basename(args.measured)}, sheet {args.measured_sheet}); "
            "ARD = |sim - meas| / meas x 100"], [],
           ["# MARD = mean ARD over the simulated frames inside each activity range; the measured curve is "
            "taken at the simulated activity"],
           ["Component"] + [c for label, _ in mards for c in (f"MARD (%) {label}", "frames")]]
    names = list(dict.fromkeys(n for _, mard in mards for n in mard))
    for name in names:
        out.append([name] + [c for _, mard in mards for c in mard.get(name, (np.nan, 0))])
    out += [[], ["# NEMA NU 4-2008 values (Sec. 4.5.2 peaks, Sec. 4.5.3 / 4.4.1 system scatter fraction)"],
            ["Quantity", "Simulation", "Measurement", "Unit", "ARD (%)"]]
    for q in report:
        out.append([q["quantity"], q["sim"], q["meas"], q["unit"], q["ARD_pct"]])
    how = (f"least-squares fit of a degree-{args.peak_fit_deg} polynomial in ln(activity) through the frames "
           f"down to {100 * args.peak_fit_frac:g} % of the highest (--peak-fit smooth)"
           if getattr(args, "peak_fit", "3point") == "smooth" else
           "the highest frame itself (--peak-fit max)" if getattr(args, "peak_fit", "3point") == "max" else
           "3-point interpolation through the highest frame and its two neighbours")
    out += [[f"# Peaks: {how}, the same for both curves. SF: sum R_s / sum (R_t + R_s) over the frames with "
             "measured randoms < 1 % of trues."]]
    for n in notes:
        out.append([f"# NOTE: {n}"])
    if checks:
        out += [[], ["# Model check (not an ARD)"], ["Quantity", "Simulation", "Measurement", "Unit"]]
        for c in checks:
            out.append([c["quantity"], c["sim"], c["meas"], c["unit"]])
    return out


def write_tables(base, rows, mards, report, notes, checks, meas, args):
    rows = sorted(rows, key=lambda r: -r["activity_MBq"])
    with open(base + ".txt", "w") as f:
        f.write("# NEMA NU 4-2008 Sec. 4.4 on the GATE prompts and delayed coincidences, Bruker-identical "
                "(8 mm mask, +-7 mm strip, randoms = delayed in the mask). Rates in kcps, SF in %. R_r_all = delayed "
                "pairs of the second sorter delayAll in the mask (necr_run.py --delayed-all-pulse-open), not used "
                "for the scatter.\n")
        f.write(f"# meas = {os.path.basename(args.measured)}, sheet {args.measured_sheet}, taken at the simulated "
                "activity (meas_frame = nearest measured frame, 1 = highest activity).\n")
        if args.add_measured_bg:
            f.write(f"# measured background added to the simulation (blank scan): Total {args.bg_total_cps:g}, "
                    f"S+R {args.bg_sr_cps:g}, randoms {args.bg_randoms_cps:g} cps in the mask; Rint "
                    f"{rows[0]['Rint_cps']:g} cps subtracted from the simulated scatter.\n")
        f.write("\t".join(RESULT_COLS) + "\n")
        for r in rows:
            f.write("\t".join(fmt(r[c]) for c in RESULT_COLS) + "\n")
    with open(base + "_ARD_MARD.txt", "w") as f:
        for line in mard_lines(mards, report, notes, checks, args):
            f.write("\t".join(fmt(v) for v in line) + "\n")
    keys = list(rows[0].keys())
    with open(base + "_details.txt", "w") as f:
        f.write("\t".join(keys) + "\n")
        for r in rows:
            f.write("\t".join(fmt(r[k], 5) for k in keys) + "\n")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print("openpyxl not installed: no .xlsx written", file=sys.stderr)
        return

    def sheet(ws, header, data, bold=True):
        if header:
            ws.append(header)
            if bold:
                for c in ws[1]:
                    c.font = Font(bold=True)
        for row in data:
            ws.append([_cell(v) for v in row])

    wb = Workbook()
    ws = wb.active
    ws.title = "1"                                          # first sheet: the PLOTNECR columns
    sheet(ws, [h for h, _, _ in PLOTNECR], plotnecr_rows(rows))
    sheet(wb.create_sheet("Results"), RESULT_COLS, [[r[c] for c in RESULT_COLS] for r in rows])
    sheet(wb.create_sheet("ARD_MARD"), None, mard_lines(mards, report, notes, checks, args))
    sheet(wb.create_sheet("Details"), keys, [[r[k] for k in keys] for r in rows])
    if meas:
        cols = ["activity_MBq", "R_t", "R_s", "R_r", "R_TOT", "R_NEC", "R_NEC_RS", "SF_pct"]
        sheet(wb.create_sheet("Measured"), [f"{meas['sheet']}: {c} (kcps, SF %)" if c == "activity_MBq" else c
                                            for c in cols],
              [[meas[c][i] for c in cols] for i in range(len(meas["activity_MBq"]))])
    sheet(wb.create_sheet("Settings"), ["Parameter", "Value"],
          [[k, str(v)] for k, v in sorted(vars(args).items()) if k != "files"])
    wb.save(base + ".xlsx")


# ============================================================================================
# 9. Main program
# ============================================================================================
def build_parser():
    """The command-line options."""
    ap = argparse.ArgumentParser(description="NEMA NU 4 count rates / NECR of GATE runs, compared with "
                                             "the measured Quad35 (or Quad86) mouse curves.")
    ap.add_argument("files", nargs="*", help="ROOT files (default: output/NECR_*.root)")
    ap.add_argument("--dir", default="output", help="folder searched when no files are given")
    ap.add_argument("--old-names", action="store_true",
                    help="analyse numbered files <dir>/1.root ... <dir>/145.root instead of NECR_*.root "
                         "(file n = measured frame n; run settings from the --macro-dirs if present)")
    g = ap.add_argument_group("run settings (default: read from the run macro <name>.mac in --macro-dirs)")
    g.add_argument("--macro", default=None, help="one run macro to read for all files")
    g.add_argument("--macro-dirs", nargs="+", default=["macros", "mac_A"],
                   help="folders with the run macros, relative to the folder above output/ (default: macros mac_A)")
    g.add_argument("--activities-xlsx", default=None, metavar="FILE",
                   help="numbered files without run macro: activity of file n = row n of FILE (Bq, first column); "
                        "default: measured frame n")
    g.add_argument("--activity", type=float, default=None, help="F-18 activity, MBq")
    g.add_argument("--duration", type=float, default=None, help="acquisition time, s")
    g.add_argument("--source-id", type=int, default=0, help="GATE sourceID of the F-18 source (default 0)")
    g.add_argument("--lu176-bq", type=float, default=152000.0,
                   help="Lu-176 activity subtracted from the ROOT decay count when no run macro is found")
    g.add_argument("--nominal-time", action="store_true",
                   help="divide by the nominal duration, not by the time the coincidences cover "
                        "(GATE 8.2 loses the last 256 singles of a run; see section 2g)")
    g = ap.add_argument_group("NEMA analysis (defaults = Bruker NECCalculation -mouse)")
    g.add_argument("--pixel", type=float, default=0.478602, help="radial sinogram pixel, mm")
    g.add_argument("--strip", type=float, default=7.0, help="half-width of the trues strip, mm")
    g.add_argument("--align", choices=("known", "max"), default="known",
                   help="known: projected source position (default); max: literal NEMA maximum pixel")
    g.add_argument("--src-x", type=float, default=None, help="line-source x, mm (default: from GATE)")
    g.add_argument("--src-y", type=float, default=None, help="line-source y, mm (default: from GATE)")
    g.add_argument("--nphi", type=int, default=193, help="angles per sinogram (--align max)")
    g.add_argument("--slice", type=float, default=1.0, help="SSRB slice thickness, mm (--align max)")
    g.add_argument("--axial-fov", type=float, default=150.0, help="mm (--align max)")
    g.add_argument("--fov-radius", type=float, default=40.2, help="radial sinogram extent, mm (--align max)")
    g.add_argument("--rint-cps", type=float, default=None,
                   help="intrinsic true rate subtracted from the simulated scatter, cps. Default: the "
                        "measured sheet's Rint (91) when Lu-176 is in the model or --add-measured-bg is "
                        "given, 0 otherwise")
    g.add_argument("--add-measured-bg", action="store_true",
                   help="add the measured blank-scan background (Lu-176) to every simulated frame; for runs "
                        "made with necr_run.py --no-lu176")
    g.add_argument("--bg-total-cps", type=float, default=BLANK_TOTAL_CPS,
                   help=f"background Total in the mask, cps (default {BLANK_TOTAL_CPS:g}, the blank scan)")
    g.add_argument("--bg-sr-cps", type=float, default=BLANK_SR_CPS,
                   help=f"background S+R in the mask, cps (default {BLANK_SR_CPS:g}, the blank scan)")
    g.add_argument("--bg-randoms-cps", type=float, default=BLANK_RANDOMS_CPS,
                   help=f"background randoms in the mask, cps (default {BLANK_RANDOMS_CPS:g}, measured randoms "
                        "extrapolated to zero activity)")
    g.add_argument("--detector-blur", action="store_true",
                   help="add the detector response of the spatial-resolution analysis to the simulated positions "
                        "before the NEMA steps: in-plane and depth errors and photon acollinearity (default off)")
    g.add_argument("--plane-fwhm", type=float, default=1.6, help="--detector-blur: in-plane position error, mm FWHM")
    g.add_argument("--doi-fwhm", type=float, default=1.6, help="--detector-blur: depth-of-interaction error, mm FWHM")
    g.add_argument("--acolin-fwhm-deg", type=float, default=0.5, help="--detector-blur: photon acollinearity, deg FWHM")
    g.add_argument("--blur-seed", type=int, default=12345, help="--detector-blur: base random seed (per file + name)")
    g.add_argument("--active-mm", type=float, default=None,
                   help="emulate an active area of N x N mm per 48 x 48 mm block face (46 = Gonzalez et al. "
                        "2016); default off, full blocks")
    g = ap.add_argument_group("measurement and comparison")
    g.add_argument("--measured", default=MEAS_FILE, help="measured workbook (searched here and next to this script)")
    g.add_argument("--measured-sheet", default=None,
                   help="sheet with the measured frames (default: the sheet of the coil, see --coil)")
    g.add_argument("--coil", type=int, choices=(35, 86), default=None,
                   help="measurement to compare with: 35 = '20220915 Quad35 Maus', 86 = '20220906 Quad86 Maus' "
                        "(default: the coil in the run macros, else 35)")
    g.add_argument("--mard-range", nargs="+", default=[],
                   help="more activity ranges for the MARD, MBq, e.g. 3-40 or 5- (from 5 MBq); the MARD is "
                        "always also given over all frames, 1.5-20, 0-40, 0.5-40, 1.5-40 and 0.5- MBq")
    g = ap.add_argument_group("output")
    g.add_argument("--peak-fit", choices=("3point", "smooth", "max"), default="3point",
                   help="how the NEMA peaks (R_t,peak, R_NEC,peak and their activities) are found: 3point = "
                        "parabola through the highest frame and its two neighbours (default); smooth = "
                        "least-squares polynomial in ln(activity) through the frames near the peak, with 1 sd, "
                        "written with '_peakfit' added to --out (plus PeakFit.png); max = the highest frame "
                        "itself (direct comparison), written with '_peakmax' added to --out")
    g.add_argument("--peak-fit-deg", type=int, default=PEAK_FIT_DEG, help=f"degree of the smooth fit (default {PEAK_FIT_DEG})")
    g.add_argument("--peak-fit-frac", type=float, default=PEAK_FIT_FRAC,
                   help=f"smooth fit through the frames down to this fraction of the highest (default {PEAK_FIT_FRAC:g})")
    g.add_argument("--out", default=None,
                   help="base name of the output files (default: necr_<tag> from the file names NECR_<tag>_<frame>, "
                        "else necr_results)")
    g.add_argument("--results-dir", default="results", metavar="DIR",
                   help="outputs go to DIR/<setup>/ (the setup of the run macros, e.g. q35; runs without a setup: "
                        "DIR/<tag>/ or DIR/no_setup/); default: results")
    g.add_argument("--no-plots", action="store_true")
    g.add_argument("--jobs", type=int, default=1, help="files analysed in parallel (default 1)")
    return ap


def main():
    args = build_parser().parse_args()
    args.mask_halfwidth = PHANTOM_RADIUS + MASK_MARGIN
    args.mard_ranges = []                                   # MARD_RANGES, then --mard-range
    for text in list(MARD_RANGES) + list(args.mard_range):
        if parse_range(text)[1:] not in [parse_range(t)[1:] for t in args.mard_ranges]:   # fails early on a typo
            args.mard_ranges.append(text)

    if args.files:
        files = args.files
    elif args.old_names:
        files = [f for f in glob.glob(os.path.join(args.dir, "*.root"))         # 1.root, 2.root, ...
                 if re.fullmatch(r"[1-9]\d*", os.path.splitext(os.path.basename(f))[0])]
        files.sort(key=lambda f: int(os.path.splitext(os.path.basename(f))[0]))
    else:
        files = sorted(glob.glob(os.path.join(args.dir, "NECR_*.root")))
    if not files:
        sys.exit(f"No files found in {args.dir}/ (" + ("<n>.root" if args.old_names else
                 "NECR_*.root; for numbered files 1.root ... 145.root use --old-names") + ")")
    # ---- one analysis per setup and run tag, each into its own folder ---------------------------------
    # Files of different setups (coil, cradle, phantom position) or different runs (tags) are never pooled:
    # each group gets its own measured sheet (from its coil), its own MARD and NEMA values, and its own
    # folder <results-dir>/<setup>/ with the file names <out> (default necr_<tag>).
    groups = {}
    for f in files:
        info = run_settings(f, args.macro, args.macro_dirs)
        m = re.match(r"(?:smoke_)?NECR_(\w+?)_(?:\d+|[\dp]+MBq)$", os.path.splitext(os.path.basename(f))[0])
        tag = m.group(1) if m else None
        groups.setdefault((info.get("setup") or tag or "no_setup", tag), []).append(f)
    targets = {}
    for (folder, tag), gfiles in groups.items():
        name = os.path.splitext(args.out)[0] if args.out else (f"necr_{tag}" if tag else "necr_results")
        target = os.path.join(args.results_dir, folder, name)
        if target in targets:
            sys.exit(f"{len(files)} files from several runs would all be written to {target}*: analyse the runs "
                     f"(tags {sorted({t or '-' for _, t in groups})}) one at a time, or leave out --out")
        targets[target] = gfiles
    if len(targets) > 1:
        print(f"{len(files)} files from {len(targets)} runs, each analysed on its own: "
              + ", ".join(f"{os.path.dirname(k)}/ {os.path.basename(k)} ({len(v)} files)" for k, v in targets.items()))
    failed = []
    for target, gfiles in targets.items():
        if len(targets) > 1:
            print(f"\n========== {target} ==========")
        if not analyse_set(gfiles, argparse.Namespace(**vars(args)), target):
            failed.append(target)
    if failed:
        sys.exit(f"No file could be analysed for: {', '.join(failed)}")


def analyse_set(files, args, base):
    """The NEMA analysis of one run (files of one setup and tag), written to <base>* in base's folder."""
    # ---- which measurement: --coil, else the coil of the run macros (coil macro or rfCoil1), else Quad35 ---
    coils = sorted({run_settings(f, args.macro, args.macro_dirs).get("coil_mm") for f in files} - {None})
    if args.coil is None:
        args.coil = coils[0] if len(coils) == 1 and coils[0] in MEAS_SHEETS else 35
    if len(coils) > 1:
        print(f"WARNING the run macros use different coils {coils}; all files are compared with the "
              f"Quad{args.coil} measurement", file=sys.stderr)
    if args.measured_sheet is None:
        args.measured_sheet = MEAS_SHEETS[args.coil]
    print(f"Measurement: sheet '{args.measured_sheet}' (coil Quad{args.coil})")
    if not (2 <= args.peak_fit_deg <= 6 and 0.5 <= args.peak_fit_frac < 1):
        sys.exit("--peak-fit-deg must be 2 ... 6 and --peak-fit-frac 0.5 ... <1")
    os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
    if args.peak_fit == "smooth":                           # own names: the 3-point results stay
        base += "_peakfit"
    elif args.peak_fit == "max":
        base += "_peakmax"
    plots = None if args.no_plots else base + "_plots"
    if plots:
        try:
            import matplotlib  # noqa: F401
            os.makedirs(plots, exist_ok=True)
        except ImportError:
            print("matplotlib not installed: no figures", file=sys.stderr)
            plots = None

    meas = None
    mpath = find_file(args.measured)
    if mpath:
        try:
            meas = load_measured(mpath, args.measured_sheet)
        except Exception as exc:
            print(f"Could not read {mpath}: {exc}", file=sys.stderr)
    else:
        print(f"{args.measured} not found: no comparison with the measurement", file=sys.stderr)
    meas_rint = meas["rint_cps"] if meas and np.isfinite(meas["rint_cps"]) else DEFAULT_RINT_CPS

    # Numbered files output/<n>.root without a run macro: activity of frame n, from --activities-xlsx
    # or else from the measured sheet.
    listed = activities_from_xlsx(args.activities_xlsx) if args.activities_xlsx else None
    fallbacks = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        fb = None
        if re.fullmatch(r"\d+", stem):
            n = int(stem)
            if listed and 1 <= n <= len(listed):
                fb = (listed[n - 1], f"row {n} of {os.path.basename(args.activities_xlsx)}")
            elif meas and 1 <= n <= len(meas["activity_MBq"]):
                fb = (float(meas["activity_MBq"][n - 1]), f"measured frame {n}")
        fallbacks.append(fb)

    rows = []
    if args.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(process, files, [args] * len(files), [meas_rint] * len(files),
                                  [plots] * len(files), fallbacks))
    else:
        results = (process(f, args, meas_rint, plots, fb) for f, fb in zip(files, fallbacks))
    for r, err in results:
        if err:
            print(f"SKIPPED {err}", file=sys.stderr)
            continue
        rows.append(r)
        print(f"{r['label']}: {r['activity_MBq']:.4f} MBq x {r['duration_s']:g} s | NEMA T {r['R_t']:.2f}  "
              f"S {r['R_s']:.2f}  R {r['R_r']:.2f}  TOT {r['R_TOT']:.2f}  NECR {r['R_NEC']:.2f} kcps  "
              f"SF {r['SF_pct']:.1f} %" + (f" | R all pairs {r['R_r_all']:.2f}" if np.isfinite(r["R_r_all"]) else ""))
        if r["note"]:
            print(f"  NOTE: {r['note']}")
    if not rows:
        print(f"No file of {base} could be analysed", file=sys.stderr)
        for d in (plots, os.path.dirname(base)):            # leave no empty folders behind
            if d and os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        return False

    mards = compare(rows, meas, args)
    report, notes = nema_report(rows, meas, args)
    checks = []
    rint_model = model_rint(rows, args)
    if rint_model:
        checks.append({"quantity": f"intrinsic true rate R_int (model: {rint_model[2]} files < "
                                   f"{LOW_ACTIVITY_MBQ:g} MBq pooled, {rint_model[1]} counts)",
                       "sim": rint_model[0], "meas": meas_rint, "unit": "cps"})
    for r in rows:                                  # helper arrays are not written to the tables
        r.pop("_no_f18_profile", None)

    print(f"\n{len(rows)} files analysed; Rint subtracted from the simulated scatter: {rows[0]['Rint_cps']:g} cps")
    if meas:
        n_pair = sum(np.isfinite(r["meas_R_t"]) for r in rows)
        print(f"\nMARD (%) = mean |sim - meas| / meas ({n_pair} of {len(rows)} files inside the measured range of "
              f"{meas['sheet']}; frames in brackets):")
        print(f"  {'':20s}" + "".join(f"{label:>18s}" for label, _ in mards))
        for name in dict.fromkeys(n for _, mard in mards for n in mard):
            cells = []
            for _, mard in mards:
                v, n = mard.get(name, (np.nan, 0))
                cells.append(f"{v:8.2f} % ({n:3d})" if np.isfinite(v) else f"{'-':>15s}")
            print(f"  {name:20s}" + "".join(f"{c:>18s}" for c in cells))
        print(f"\nNEMA values{'':48s}simulation measurement")
        for q in report:
            ard = f"   ARD {q['ARD_pct']:.1f} %" if np.isfinite(q["ARD_pct"]) else ""
            print(f"  {q['quantity']:57s} {q['sim']:10.3f} {q['meas']:10.3f} {q['unit']}{ard}")
        for n in notes:
            print(f"  NOTE: {n}")
    if rint_model:
        print(f"\nModel check: intrinsic true rate of the model {rint_model[0]:.0f} cps (NEMA strip on the pooled "
              f"coincidences without F-18 of {rint_model[2]} files below {LOW_ACTIVITY_MBQ:g} MBq, "
              f"{rint_model[1]} counts) vs {meas_rint:g} cps in the measured sheet")
    write_tables(base, rows, mards, report, notes, checks, meas, args)
    if plots:
        plot_metric_figures(plots, rows, meas)
        if args.peak_fit == "smooth":
            plot_peak_fits(plots, rows, meas, args)
    print(f"\nWritten: {base}.txt, {base}_details.txt, {base}_ARD_MARD.txt"
          + (f", {base}.xlsx" if os.path.exists(base + ".xlsx") else "") + (f", {plots}/" if plots else ""))
    return True


if __name__ == "__main__":
    main()
