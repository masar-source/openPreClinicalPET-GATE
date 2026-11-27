#!/usr/bin/env python3
"""
spres_analysis.py
=================

NEMA NU 4-2008 spatial resolution (section 3) for the GATE model of the Bruker PET insert
Si 198, set up for a direct comparison with the measurement of Kuntner et al. 2025
(EJNMMI Physics 12:63, Table 3, Quad86 coil).

----------------------------------------------------------------------------------------------
1. What the measurement did (the target this script reproduces)
----------------------------------------------------------------------------------------------
  NEMA NU 4-2008 Sec. 3 and Kuntner et al. 2025 (methods, "Spatial resolution"):
  * Na-22 point source, 0.3 mm diameter, in a 10 mm acrylic cube, 140 kBq, 60 s per position.
  * Positions: axial centre (z = 0) and 1/4 of the axial FOV (z = 37.5 mm), radial offsets
    0, 5, 10, 15, 20, 25, 30, 35 mm (Quad86 coil).
  * 30 % energy window (357.7-664.3 keV), 7 ns coincidence window.
  * Reconstruction: filtered backprojection (FBP), 0.5 mm isotropic voxels, no smoothing.
  * Widths: Kuntner et al. fitted a Gaussian to the line profiles through the point in the
    radial, tangential and axial directions (their FWTM/FWHM = 1.82, the Gaussian ratio).
    NEMA itself prescribes a different method (summed profiles, parabolic peak, linear
    interpolation). This script reports both; compare the Gaussian values with the measurement.

----------------------------------------------------------------------------------------------
2. What this script does with every simulated ROOT file
----------------------------------------------------------------------------------------------
  a. Read the Coincidences tree (GATE 8.2). Default: all prompts, as in the measurement.
  b. Find the source position (median GATE source position of the point-source coincidences).
  c. Add the physics GATE 8.2 leaves out: photon acollinearity (0.5 deg FWHM by default).
  d. Add the detector response GATE leaves out. GATE stores the exact energy-weighted
     interaction centroid in the crystal. A real monolithic detector estimates that position
     with an error. Gaussian errors are added in each block's own frame:
       - in-plane (tangential and axial on the crystal face): --plane-fwhm (default 1.6 mm)
       - depth of interaction (DOI):                         --doi-fwhm   (default 1.6 mm)
     Both defaults are published measurements, not fitted values (see section 4).
  e. Normalisation (on by default, --no-norm switches it off): each LOR is weighted by
     1/(its detection efficiency), computed from the crystal geometry (attenuation path in both
     crystals, including the gaps between heads and rings). This is what a normalisation scan
     corrects in the real scanner.
  f. Single-slice rebinning (SSRB): every LOR is put in the transaxial slice where it passes
     closest to the scanner axis, then each slice is reconstructed with 2D FBP (ramp filter,
     no apodisation), 0.5 mm voxels. Only a small box around the source is reconstructed.
     Only LORs tilted at most --max-tilt-deg (default 10.5 deg) to the transverse plane are
     used. With --add-measured-bg the rate of a measured blank scan is added to the sinograms
     first (only for runs without Lu-176; section 2b in the code).
     Why SSRB: in the measurement the radial widths stay at 1.3-1.6 mm out to 35 mm, while the
     tangential and axial widths grow with the radial offset (axial 1.2 -> 7.4 mm, almost
     linearly). That is the known pattern of SSRB + 2D FBP. A fully 3D FBP gives nearly the
     same width at every radius: González et al. 2016 (IEEE TNS 63:2471, ref. 12 of Kuntner
     et al. 2025) used 3D FBP on a one-ring prototype and found about 1 mm everywhere. With all
     LORs (up to about 60 deg), SSRB makes the axial width far too large. Which rebinning and
     which acceptance the Bruker software (PARAVISION 360) uses is not documented: the 10.5 deg
     default is adjusted to the measured axial widths, it is not a vendor specification.
  g. Widths: Gaussian fit to the line profiles through the maximum voxel (the method of
     Kuntner et al. 2025), and the NEMA method on summed profiles. Radial = direction from the
     axis to the source, tangential = perpendicular to it in the transverse plane, axial = z.
     The two methods differ strongly off-axis: SSRB smears the point into a tilted, X-shaped
     blob, so a single line through the peak is wider than the sum of the neighbouring lines.
     Compare the measured widths with the Gaussian line-profile values only.
     Fit details (not stated in the paper of Kuntner et al.): by default a pure Gaussian is
     fitted to the positive core of the profile, so the negative side lobes of FBP cannot
     narrow it; --fit offset fits a Gaussian + constant on a wide window instead.
  h. Compare with Kuntner et al. 2025, Table 3 (Quad86) at the matching position, or with an
     earlier run of this script (--compare-with).

----------------------------------------------------------------------------------------------
3. Usage
----------------------------------------------------------------------------------------------
  pip install uproot numpy matplotlib openpyxl       (matplotlib/openpyxl only for PNG/XLSX)

  python spres_analysis.py                              # output/SpRes_mouse_*.root -> results_mouse/
  python spres_analysis.py --bed rat --add-measured-bg  # output/SpRes_rat_*.root   -> results_rat_bg/
  python spres_analysis.py output/SpResGa68_rat_*.root --add-measured-bg --compare-with results_rat_bg
                                                        # Ga-68 vs the Na-22 run    -> results_ga68_rat_bg/
  python spres_analysis.py output/SpResGa68NoB_rat_*.root --add-measured-bg --compare-with results_ga68_rat_bg
                                                        # 0 T vs 9.4 T, with the field comparison figures
                                                        #                           -> results_ga68nob_rat_bg/
  python spres_analysis.py --plane-fwhm 1.4 --doi-fwhm 3 --out spres_test   # other response -> results_spres_test/
  python spres_analysis.py --events trues               # remove randoms (diagnostic)
  python spres_analysis.py --no-norm                    # without normalisation weights
  python spres_analysis.py --no-nema-plot               # default figures without the NEMA-method curves

  Every run has its own folder. The run name (--out) is by default taken from the file names,
  spres_results_[<tag>_]<bed>[_bg] (tag ga68 / nob / ga68nob, _bg with --add-measured-bg), and
  spres_results_<name> is written to results_<name>/; an --out with a folder is used as given.
  --compare-with takes the reference run's folder (or its table).

  Outputs, <base> = results_<name>/spres_results_<name> (all widths in mm):
    <base>.txt          one row per position: Gaussian widths (method of Kuntner et al.) next to
                        the measured values and the differences
    <base>_nema.txt     the same positions with the NEMA-method widths
    <base>_details.txt  everything per file (counts, source position, both methods)
    <base>.xlsx         sheets Kuntner_method, NEMA_method, Details, Settings
    <base>_plots/       position_<label>.png per file (image slices + profiles + fits, widths,
                        settings), summary_FWHM.png and summary_FWTM.png (simulation and
                        measurement against the radial offset)
    <base>_plots_clean/ position_<label>.png per file, clean version (section 8b): views and profiles
                        with the Gaussian fit only; titles: view and direction names, source, position
    <base>_plots_field/ field_comparison_<bed>_z<z>_r<r>.png, only when --compare-with is a run of the
                        same source with the other field state (section 8b): views of the 9.4 T and
                        0 T runs, both profiles and fits on top of each other with both FWHM
    <base>_volumes/     volume_<label>.nii per file: the reconstructed 3D image around the source
                        (NIfTI-1, float32, fraction of the peak voxel, scanner coordinates in mm;
                        --volume-half sets its size, --no-volumes switches it off)

----------------------------------------------------------------------------------------------
4. Where the settings come from, and what is assumed
----------------------------------------------------------------------------------------------
  * Detector position errors: published measurements, not values fitted to the measured widths.
      --plane-fwhm 1.6   González et al. 2016 (IEEE TNS 63:2471): 1.6 +- 0.1 mm FWHM, measured
                         with a 1 mm Na-22 source and 1.2 mm collimator holes and not corrected
                         for them, so the detector alone is somewhat better.
      --doi-fwhm 1.6     Gsell et al. 2020 (Phys. Med. Biol., doi 10.1088/1361-6560/aba08c),
                         same insert type inside the MRI: DOI FWHM about 1.6 mm (2.1-2.2 mm only
                         with a FLASH sequence running). González et al. 2016 report about 2 mm.
  * --max-tilt-deg 10.5 is the only adjusted setting: no published value exists for the Bruker
    FBP. I adjusted it to the growth of the measured axial widths with the radial offset at the
    axial centre (10 deg too narrow, 11 deg too wide) and checked it at 1/4 FOV. The radial and
    tangential widths were not used for any adjustment.
  * --fit core: the free-offset fit was worse for the tangential widths. Note: Bruker's NEMA
    procedure measures with AMIDE's profile tool, whose default is a Gaussian + free offset.
  * Rebinning and acceptance of the Bruker FBP: SSRB with LORs up to 10.5 deg tilt. The scanner
    records all ring combinations (RingNeigh = 2 in its configuration); the limit is inferred
    from the measured axial widths, it is not documented by Bruker.
  * Counting noise: every 60 s position has its own statistical noise in the widths, so compare
    the trends over the positions rather than single values.
  * Sinogram sampling: 0.4786 mm radial bins and 193 angles, as in the measured Bruker
    sinograms; 0.5 mm slices to match the 0.5 mm voxels.
  * Image grid: voxel centres at (k + 1/2) x 0.5 mm, i.e. an even matrix centred on the axis.
"""
# ============================================================================================
# 0. Imports
# ============================================================================================
import argparse          # command-line options
import glob              # default file list
import os                # paths
import re                # labels from file names
import sys               # warnings

import numpy as np       # all numerics (no scipy needed)

# ============================================================================================
# 1. Constants
# ============================================================================================
# Detector geometry of the GATE model (SpRes_main.mac, the same detector as in the sensitivity and
# count-rate models): 8 heads x 3 axial rings of monolithic trapezoidal LYSO, entrance face
# 48 x 48 mm at 58.5 mm from the axis, exit face 50 x 50 mm at 68.5 mm, ring centres at
# z = -52, 0, +52 mm (52 mm ring pitch).
# Keep RING_PITCH equal to the module repeat vector in the macro, and R_FRONT = module y - 5 mm.
R_FRONT = 58.5            # mm, crystal entrance face (117 mm ring diameter, module y 63.5 mm in the macro)
DEPTH = 10.0              # mm, crystal thickness
HALF_FRONT = 24.0         # mm, half width (tangential and axial) at the entrance face
TAPER = 0.1               # mm half-width gained per mm depth (24 -> 25 mm over 10 mm)
RING_PITCH = 52.0         # mm, axial distance between ring centres (macro: setRepeatVector 0 0 52 mm)
RING_Z = (-RING_PITCH, 0.0, RING_PITCH)
HEAD_STEP = np.pi / 4     # heads face the directions 0, 45, 90, ... deg
MU_LYSO = 0.085           # 1/mm, LYSO (7.1 g/cm3) at 511 keV, approximate; only used for the
                          # normalisation weights
FOV_RADIUS = 40.0         # mm, transverse FOV (MaxWorkspaceXY = 80 mm)
AXIAL_HALF = 75.0         # mm, axial FOV 150 mm

GAUSS_FWHM = np.sqrt(8 * np.log(2))     # FWHM = 2.3548 sigma
GAUSS_FWTM = np.sqrt(8 * np.log(10))    # FWTM = 4.2919 sigma

# Kuntner et al. 2025, Table 3, Quad86 coil, FBP 0.5 mm voxels, Gaussian fits.
# [radial offset mm] -> (FWHM, FWTM) for radial, tangential, axial.
KUNTNER_QUAD86 = {
    "centre": {
        0:  {"radial": (1.51, 2.75), "tangential": (1.52, 2.76), "axial": (1.22, 2.22)},
        5:  {"radial": (1.51, 2.75), "tangential": (1.63, 2.97), "axial": (1.62, 2.95)},
        10: {"radial": (1.43, 2.60), "tangential": (2.07, 3.78), "axial": (2.17, 3.95)},
        15: {"radial": (1.37, 2.49), "tangential": (2.86, 5.22), "axial": (3.10, 5.65)},
        20: {"radial": (1.38, 2.51), "tangential": (2.77, 5.05), "axial": (3.70, 6.74)},
        25: {"radial": (1.31, 2.39), "tangential": (3.52, 6.41), "axial": (4.63, 8.44)},
        30: {"radial": (1.30, 2.37), "tangential": (3.49, 6.37), "axial": (5.55, 10.12)},
        35: {"radial": (1.36, 2.47), "tangential": (2.52, 4.58), "axial": (7.42, 13.53)},
    },
    "quarter": {
        0:  {"radial": (1.61, 2.94), "tangential": (1.51, 2.75), "axial": (1.43, 2.61)},
        5:  {"radial": (1.63, 2.97), "tangential": (1.77, 3.23), "axial": (1.78, 3.25)},
        10: {"radial": (1.48, 2.71), "tangential": (1.99, 3.64), "axial": (2.34, 4.27)},
        15: {"radial": (1.35, 2.47), "tangential": (2.28, 4.15), "axial": (3.25, 5.92)},
        20: {"radial": (1.36, 2.47), "tangential": (2.64, 4.82), "axial": (3.69, 6.73)},
        25: {"radial": (1.33, 2.42), "tangential": (3.81, 6.95), "axial": (4.49, 8.18)},
        30: {"radial": (1.28, 2.33), "tangential": (3.36, 6.13), "axial": (5.74, 10.45)},
        35: {"radial": (1.32, 2.40), "tangential": (2.36, 4.31), "axial": (7.47, 13.61)},
    },
}
DIRECTIONS = ("radial", "tangential", "axial")

BRANCHES = [f"globalPos{k}{s}" for s in (1, 2) for k in "XYZ"] + \
           ["eventID1", "eventID2", "sourceID1", "sourceID2",
            "sourcePosX1", "sourcePosY1", "sourcePosZ1",
            "comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2"]


# ============================================================================================
# 2. Reading the GATE ROOT file
# ============================================================================================
def load(path):
    """Coincidences of one GATE file as a dict of numpy arrays, plus the number of decays.

    A .npz file with the same branch names (exported from the ROOT file) is accepted too.
    """
    if path.endswith(".npz"):
        d = np.load(path)
        a = {k: d[k] for k in d.files if k in BRANCHES}
        n_primaries = float(d["total_nb_primaries"]) if "total_nb_primaries" in d.files else np.nan
        return a, n_primaries
    import uproot                                   # only needed for ROOT input
    with uproot.open(path) as f:
        tree = f["Coincidences"]
        names = [b for b in BRANCHES if b in tree.keys()]
        a = tree.arrays(names, library="np")
        try:    # GATE fills this histogram once, with the number of primaries as x value
            n_primaries = float(f["total_nb_primaries"].member("fTsumwx"))
        except Exception:
            n_primaries = np.nan
    return a, n_primaries


def select_events(a, mode):
    """Which coincidences are reconstructed.

    prompts     : all coincidences (what the scanner records; default)
    trues       : both photons from the same decay (randoms removed)
    unscattered : trues without Compton/Rayleigh scatter in any PhantomSD volume
    """
    n = len(a["eventID1"])
    keep = np.ones(n, bool)
    if mode in ("trues", "unscattered"):
        keep &= a["eventID1"] == a["eventID2"]
    if mode == "unscattered":
        for k in ("comptonPhantom1", "comptonPhantom2", "RayleighPhantom1", "RayleighPhantom2"):
            if k in a:
                keep &= a[k] == 0
    return keep


# ============================================================================================
# 2b. Measured background (--add-measured-bg)
# ============================================================================================
# For runs without Lu-176 (spres_run.py --no-lu176), as in the sensitivity and count-rate analyses: the
# rate of the measured blank scan (no source) is added as a constant. Source: the same blank scan as for
# the count-rate and sensitivity backgrounds, a list-mode acquisition of 16 Nov 2021 (36015 s), which I
# counted once (8 million records in 400 random blocks over the 10 h) with the selection of this
# analysis: both energies in the 30 % window (357.7-664.3 keV), |s| < 40 mm, |z| < 75 mm, LOR tilt
# <= 10.5 deg -> 255.9 cps (model geometry 255.5 cps; whole scanner 717.8 cps, |s| < 40 mm and
# |z| < 75 mm without the tilt cut 703.4 cps). Distribution: 3.3-3.6 cps per mm of s up to
# |s| = 30 mm, 3.0 at 30-35 and 1.8 at 35-40 mm; along z it follows the rings (1.39 cps/mm near z = 0,
# 1.84 near z = 37.5, mean 1.71). Added as uniform in s (|s| < 40 mm), angle and z (150 mm):
#   counts per sinogram bin = Total / (2 x 40 mm) x bin width x time x (slice thickness / 150 mm) / views
# with the normalisation weight of the median LOR (1 with --no-norm). Time: the run macro or --bg-duration.
# The default holds for --max-tilt-deg 10.5 (all tilts: 703.4 cps); main() warns otherwise.
BLANK_30PCT_TOTAL_CPS = 255.9       # cps, 2021 blank, 30 % window, |s| < 40 mm, |z| < 75 mm, tilt <= 10.5 deg
BLANK_30PCT_MASK_HALF = 40.0        # mm, the |s| range that rate refers to (the FOV)
BLANK_30PCT_TILT = 10.5             # deg, tilt cut the default rate was counted with


def run_duration(path):
    """Acquisition time of a run from its macro (macros/<name>.mac written by spres_run.py), or None."""
    stem = os.path.splitext(os.path.basename(path))[0]
    for d in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), "macros"), "macros"):
        mac = os.path.join(d, stem + ".mac")
        if os.path.isfile(mac):
            mt = re.search(r"^/control/alias[ \t]+duration[ \t]+(\S+)", open(mac).read(), re.M)
            if mt:
                return float(mt.group(1))
    return None


def check_background_use(a, path, args):
    """--add-measured-bg only for runs without Lu-176 and with all prompts (else the background is
    counted twice, or mixed with a truth selection that removes it)."""
    if args.events != "prompts":
        sys.exit("--add-measured-bg works with --events prompts only")
    if "sourceID1" in a and np.any((a["sourceID1"] != args.source_id) | (a["sourceID2"] != args.source_id)):
        sys.exit(f"{os.path.basename(path)} contains coincidences of another source (Lu-176): the measured "
                 "background would be counted twice. Use runs made with spres_run.py --no-lu176.")


def source_position(a, source_id):
    """Median decay position of the point-source coincidences (true pairs of that source).

    The Lu-176 decays (sourceID 1) sit in the crystals and are excluded here.
    """
    sel = (a["eventID1"] == a["eventID2"]) & (a["sourceID1"] == source_id)
    if sel.sum() < 10:
        sel = np.ones(len(a["eventID1"]), bool)
    return np.array([np.median(a[f"sourcePos{k}1"][sel]) for k in "XYZ"], float)


# ============================================================================================
# 3. Physics and detector effects that GATE 8.2 does not apply
# ============================================================================================
def head_frame(p):
    """Head index angle of each detected position: the nearest of 0, 45, ..., 315 deg."""
    ang = np.arctan2(p[:, 1], p[:, 0])
    return np.round(ang / HEAD_STEP) * HEAD_STEP


def add_acollinearity(p1, p2, src, fwhm_deg, rng):
    """Tilt photon 2 away from exact back-to-back emission by a Gaussian angle.

    GATE 8.2 annihilates positrons at rest with exactly opposite photons. In reality the
    angle deviates from 180 deg by ~0.5 deg FWHM. Moving the second detection point by
    (distance from the source) x (deviation angle), perpendicular to the LOR, is the exact
    small-angle geometry of that deviation.
    """
    if fwhm_deg <= 0:
        return p2
    sigma = np.deg2rad(fwhm_deg) / GAUSS_FWHM
    u = p2 - p1
    u /= np.linalg.norm(u, axis=1)[:, None]
    # two unit vectors perpendicular to the LOR
    helper = np.where(np.abs(u[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
    e1 = np.cross(u, helper)
    e1 /= np.linalg.norm(e1, axis=1)[:, None]
    e2 = np.cross(u, e1)
    d2 = np.linalg.norm(p2 - src, axis=1)
    dev = rng.normal(0, sigma, (len(p2), 2))
    return p2 + d2[:, None] * (dev[:, :1] * e1 + dev[:, 1:] * e2)


def detector_response(p, plane_fwhm, doi_fwhm, rng, fixed_doi=None):
    """Position estimate of a monolithic block: GATE centroid + Gaussian errors.

    Work in the frame of the block that detected the photon:
      q = depth coordinate (distance from the axis along the head direction, 58..68 mm)
      t = tangential coordinate on the crystal face
      zl = axial coordinate relative to the ring centre
    Errors: DOI on q, in-plane on t and zl. The estimate is kept inside the crystal
    (a positioning algorithm never returns a point outside the block).
    fixed_doi: if given, every photon is put at that depth (a detector without DOI).
    """
    ang = head_frame(p)
    c, s = np.cos(ang), np.sin(ang)
    q = p[:, 0] * c + p[:, 1] * s
    t = -p[:, 0] * s + p[:, 1] * c
    zc = np.clip(np.round(p[:, 2] / RING_PITCH), -1, 1) * RING_PITCH
    zl = p[:, 2] - zc
    sp, sd = plane_fwhm / GAUSS_FWHM, doi_fwhm / GAUSS_FWHM
    if fixed_doi is not None:
        q = np.full_like(q, R_FRONT + fixed_doi)
    elif sd > 0:
        q = q + rng.normal(0, sd, len(q))
    q = np.clip(q, R_FRONT, R_FRONT + DEPTH)
    half = HALF_FRONT + TAPER * (q - R_FRONT)
    if sp > 0:
        t = t + rng.normal(0, sp, len(t))
        zl = zl + rng.normal(0, sp, len(zl))
    t = np.clip(t, -half, half)
    zl = np.clip(zl, -half, half)
    return np.column_stack([q * c - t * s, q * s + t * c, zl + zc])


# ============================================================================================
# 4. Normalisation: detection efficiency of each LOR from the crystal geometry
# ============================================================================================
def lor_efficiency(p1, p2, mu=MU_LYSO, chunk=200000):
    """Probability that both photons along this LOR interact in a crystal.

    Each block is a convex trapezoidal prism (6 planes). The crystal path length of the line
    on each side is found with the standard slab method; efficiency =
    (1 - exp(-mu L1)) (1 - exp(-mu L2)). LORs that run through the gaps between heads or rings
    get a low efficiency, exactly the pattern a normalisation scan corrects.
    """
    eff = np.empty(len(p1))
    for i0 in range(0, len(p1), chunk):
        a, b = p1[i0:i0 + chunk], p2[i0:i0 + chunk]
        d = b - a
        length = np.linalg.norm(d, axis=1)
        L1 = np.zeros(len(a))
        L2 = np.zeros(len(a))
        for k in range(8):
            c, s = np.cos(k * HEAD_STEP), np.sin(k * HEAD_STEP)
            qa, qd = a[:, 0] * c + a[:, 1] * s, d[:, 0] * c + d[:, 1] * s
            ta, td = -a[:, 0] * s + a[:, 1] * c, -d[:, 0] * s + d[:, 1] * c
            for zc in RING_Z:
                za, zd = a[:, 2] - zc, d[:, 2]
                lo = np.full(len(a), -np.inf)
                hi = np.full(len(a), np.inf)
                c0 = HALF_FRONT - TAPER * R_FRONT        # 18.2 mm: plane offset of the slanted faces
                # each plane:  fa + lambda * fd <= cc
                planes = [(-qa, -qd, -R_FRONT), (qa, qd, R_FRONT + DEPTH),
                          (ta - TAPER * qa, td - TAPER * qd, c0), (-ta - TAPER * qa, -td - TAPER * qd, c0),
                          (za - TAPER * qa, zd - TAPER * qd, c0), (-za - TAPER * qa, -zd - TAPER * qd, c0)]
                empty = np.zeros(len(a), bool)
                for fa, fd, cc in planes:
                    with np.errstate(divide="ignore", invalid="ignore"):
                        lam = (cc - fa) / fd
                    hi = np.where(fd > 0, np.minimum(hi, lam), hi)
                    lo = np.where(fd < 0, np.maximum(lo, lam), lo)
                    empty |= (fd == 0) & (fa > cc)
                seg = np.where(~empty & (hi > lo), (hi - lo) * length, 0.0)
                mid = 0.5 * (lo + hi)
                L1 += np.where(mid < 0.5, seg, 0.0)
                L2 += np.where(mid >= 0.5, seg, 0.0)
        eff[i0:i0 + chunk] = (1 - np.exp(-mu * L1)) * (1 - np.exp(-mu * L2))
    return eff


# ============================================================================================
# 5. Rebinning (SSRB) and 2D filtered backprojection
# ============================================================================================
def ssrb_coordinates(p1, p2):
    """Sinogram coordinates of each LOR: angle phi in [0, pi), radial s, slice z, tilt.

    s = x cos(phi) + y sin(phi) along the LOR; z = axial position where the LOR passes
    closest to the scanner axis (SSRB); tilt = angle of the LOR to the transverse plane.
    """
    d = p2 - p1
    lxy = np.hypot(d[:, 0], d[:, 1])
    phi = np.mod(np.arctan2(-d[:, 0], d[:, 1]), np.pi)
    s = p1[:, 0] * np.cos(phi) + p1[:, 1] * np.sin(phi)
    lam = -(p1[:, 0] * d[:, 0] + p1[:, 1] * d[:, 1]) / np.maximum(lxy ** 2, 1e-12)
    z = p1[:, 2] + lam * d[:, 2]
    tilt = np.degrees(np.arctan2(np.abs(d[:, 2]), lxy))
    return phi, s, z, tilt


def grid_centres(centre, half_width, voxel, fov_half):
    """Voxel centres of the global image grid ((k + 1/2) x voxel) within centre +- half_width."""
    k_lo = int(np.floor((centre - half_width + fov_half) / voxel))
    k_hi = int(np.ceil((centre + half_width + fov_half) / voxel))
    k = np.arange(max(k_lo, 0), min(k_hi, int(round(2 * fov_half / voxel))))
    return (k + 0.5) * voxel - fov_half


def recon_box(src, args):
    """Voxel grids of the reconstructed box and the masks of the measurement box inside them.

    The widths are always measured on the box --roi-xy / --roi-z around the source. For the
    figures (+- --image-half) and the saved 3D image (+- --volume-half) the box is enlarged when
    those are larger; the extra voxels do not change the measured ones (every voxel is
    reconstructed on its own), so the tables do not depend on --image-half or --volume-half.
    """
    half = max(0.0 if args.no_plots else getattr(args, "image_half", IMAGE_HALF),
               0.0 if getattr(args, "no_volumes", True) else getattr(args, "volume_half", 0.0))
    grids, masks = [], []
    for c, roi, fov in ((src[0], args.roi_xy, FOV_RADIUS), (src[1], args.roi_xy, FOV_RADIUS),
                        (src[2], args.roi_z, AXIAL_HALF)):
        g = grid_centres(c, max(roi, half), args.voxel, fov)
        gm = grid_centres(c, roi, args.voxel, fov)
        grids.append(g)
        masks.append((g > gm[0] - 1e-6) & (g < gm[-1] + 1e-6))
    return grids, masks


def box_mask(grid, centre, half_width, voxel, fov_half):
    """Mask of the voxels of `grid` that belong to the box centre +- half_width (same global grid)."""
    g = grid_centres(centre, half_width, voxel, fov_half)
    return (grid > g[0] - 1e-6) & (grid < g[-1] + 1e-6)


def write_nifti(fname, vol, xs, ys, zs, descrip=""):
    """Write vol[z, y, x] as a single-file NIfTI-1 image (.nii, float32), no extra package needed.

    Voxel size and position are stored in the header (qform and sform, code 1): the world
    coordinates of every voxel centre are its GATE scanner coordinates x, y, z in mm. Viewers
    label these axes as patient directions (R, A, S); here they are simply scanner x, y, z.
    """
    import struct
    nz, ny, nx = vol.shape
    d = [float(g[1] - g[0]) if len(g) > 1 else 0.5 for g in (xs, ys, zs)]
    o = [float(xs[0]), float(ys[0]), float(zs[0])]                   # centre of the first voxel
    h = bytearray(348)
    struct.pack_into("<i", h, 0, 348)                                # sizeof_hdr
    h[38] = ord("r")                                                 # regular
    struct.pack_into("<8h", h, 40, 3, nx, ny, nz, 1, 1, 1, 1)        # dim
    struct.pack_into("<hh", h, 70, 16, 32)                           # datatype FLOAT32, bitpix
    struct.pack_into("<8f", h, 76, 1.0, d[0], d[1], d[2], 0, 0, 0, 0)  # pixdim (qfac = 1)
    struct.pack_into("<3f", h, 108, 352.0, 1.0, 0.0)                 # vox_offset, scl_slope, scl_inter
    h[123] = 2                                                       # xyzt_units: mm
    text = descrip.encode("ascii", "replace")[:79]
    h[148:148 + len(text)] = text                                    # descrip
    struct.pack_into("<hh", h, 252, 1, 1)                            # qform_code, sform_code
    struct.pack_into("<6f", h, 256, 0.0, 0.0, 0.0, *o)               # quatern b, c, d, qoffset x, y, z
    struct.pack_into("<4f", h, 280, d[0], 0.0, 0.0, o[0])            # srow_x
    struct.pack_into("<4f", h, 296, 0.0, d[1], 0.0, o[1])            # srow_y
    struct.pack_into("<4f", h, 312, 0.0, 0.0, d[2], o[2])            # srow_z
    h[344:348] = b"n+1\0"                                            # magic: single file
    with open(fname, "wb") as f:
        f.write(bytes(h) + b"\0" * 4)                                # + empty extension flag
        f.write(np.ascontiguousarray(vol, dtype="<f4").tobytes())     # x fastest, then y, then z


def save_volume(fname, row, recon, args):
    """Save the reconstructed 3D image around the source (+- max(--roi, --volume-half))."""
    img, xs, ys, zs, m = recon[:5]
    src = (row["x_mm"], row["y_mm"], row["z_mm"])
    half = getattr(args, "volume_half", 0.0)
    mx = box_mask(xs, src[0], max(args.roi_xy, half), args.voxel, FOV_RADIUS)
    my = box_mask(ys, src[1], max(args.roi_xy, half), args.voxel, FOV_RADIUS)
    mz = box_mask(zs, src[2], max(args.roi_z, half), args.voxel, AXIAL_HALF)
    px, py, pz = m["peak"]
    peak = img[int(np.argmin(np.abs(zs - pz))), int(np.argmin(np.abs(ys - py))), int(np.argmin(np.abs(xs - px)))]
    recon_name = getattr(args, "recon_label", None) or f"SSRB<={args.max_tilt_deg:g}deg+2D FBP"
    write_nifti(fname, img[np.ix_(mz, my, mx)] / peak, xs[mx], ys[my], zs[mz],
                f"peak = 1; {row['file']}; {recon_name}")


def ramp_kernel(n, ds):
    """Spatial-domain Ram-Lak ramp filter (no apodisation, NEMA 'no smoothing')."""
    k = np.arange(-(n - 1), n)
    h = np.zeros(k.size)
    h[k == 0] = 1.0 / (4 * ds * ds)
    odd = (k % 2) != 0
    h[odd] = -1.0 / (np.pi * k[odd] * ds) ** 2
    return h


def fbp_2d(sino, s_centres, phis, xs, ys):
    """2D FBP of a stack of SSRB sinograms sino[slice, angle, s] onto the grid ys x xs.

    Each projection is convolved with the ramp filter (via FFT, zero padded), then smeared
    back over the image with linear interpolation in s. Returns img[slice, y, x].
    """
    n_slices, n_phi, n_s = sino.shape
    ds = s_centres[1] - s_centres[0]
    h = ramp_kernel(n_s, ds)
    n_fft = 1 << int(np.ceil(np.log2(n_s + h.size - 1)))
    filt = np.fft.irfft(np.fft.rfft(sino, n_fft, axis=-1) * np.fft.rfft(h, n_fft),
                        n_fft, axis=-1)[..., n_s - 1:2 * n_s - 1] * ds
    X, Y = np.meshgrid(xs, ys)
    img = np.zeros((n_slices, len(ys), len(xs)))
    for j, phi in enumerate(phis):
        u = (X * np.cos(phi) + Y * np.sin(phi) - s_centres[0]) / ds
        i0 = np.floor(u).astype(int)
        f = u - i0
        ok = (i0 >= 0) & (i0 < n_s - 1)
        i0c = np.clip(i0, 0, n_s - 2)
        val = (1 - f) * filt[:, j, i0c] + f * filt[:, j, i0c + 1]
        img += np.where(ok, val, 0.0)
    return img * np.pi / n_phi


# ============================================================================================
# 6. Width measurement
# ============================================================================================
def gauss_fit(x, y, offset=False):
    """Least-squares fit of a*exp(-(x-mu)^2 / (2 sigma^2)) [+ b] (Levenberg-Marquardt).

    offset=False: pure Gaussian (b = 0). offset=True: with a constant baseline b.
    Returns (a, mu, sigma, b) or None. FWHM = 2.3548 sigma, FWTM = 4.2919 sigma (Gaussian widths).
    """
    k = int(np.argmax(y))
    b0 = float(np.min(y)) if offset else 0.0
    pars = np.array([y[k] - b0, x[k], max(direct_width(x, y, 0.5) or 1.0, 0.3) / GAUSS_FWHM, b0])
    lam = 1e-3

    def model(p):
        return p[0] * np.exp(-0.5 * ((x - p[1]) / p[2]) ** 2) + p[3]

    def resid(p):
        return y - model(p)

    cost = np.sum(resid(pars) ** 2)
    for _ in range(200):
        a, mu, sg, b = pars
        e = np.exp(-0.5 * ((x - mu) / sg) ** 2)
        J = np.column_stack([e, a * e * (x - mu) / sg ** 2, a * e * (x - mu) ** 2 / sg ** 3, np.ones_like(x)])
        if not offset:
            J[:, 3] = 0.0                     # baseline stays at 0
        r = resid(pars)
        A = J.T @ J
        g = J.T @ r
        try:
            step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), g)
        except np.linalg.LinAlgError:
            return None
        trial = pars + step
        trial[2] = abs(trial[2])
        c_new = np.sum(resid(trial) ** 2)
        if c_new < cost:
            pars, cost, lam = trial, c_new, lam * 0.3
            if np.max(np.abs(step) / (np.abs(pars) + 1e-9)) < 1e-8:
                break
        else:
            lam *= 10
            if lam > 1e8:
                break
    if pars[2] <= 0 or pars[0] <= 0:
        return None
    return pars


def direct_width(x, y, frac, parabolic=False):
    """Width at frac x maximum by linear interpolation between neighbouring pixels.

    parabolic=True: the maximum is taken from a parabola through the peak pixel and its two
    neighbours (NEMA NU 4-2008 Sec. 3.4).
    """
    k = int(np.argmax(y))
    peak = y[k]
    if parabolic and 0 < k < len(y) - 1:
        y0, y1, y2 = y[k - 1], y[k], y[k + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            peak = y1 - (y0 - y2) ** 2 / (8 * den)
    level = frac * peak
    i = k
    while i > 0 and y[i] >= level:
        i -= 1
    j = k
    while j < len(y) - 1 and y[j] >= level:
        j += 1
    if y[i] >= level or y[j] >= level:
        return None                     # profile does not drop below the level inside the box
    xl = x[i] + (level - y[i]) / (y[i + 1] - y[i]) * (x[i + 1] - x[i])
    xr = x[j - 1] + (level - y[j - 1]) / (y[j] - y[j - 1]) * (x[j] - x[j - 1])
    return float(xr - xl)


def fit_window(c, prof, mode):
    """Points used for the Gaussian fit of a line profile.

    core   : the contiguous run of positive values around the peak (FBP's negative side lobes
             are left out, so they cannot pull the width down); pure Gaussian.
    offset : +-max(4 mm, 2 x FWTM) around the peak; Gaussian + constant baseline.
    """
    k = int(np.argmax(prof))
    if mode == "offset":
        return np.abs(c - c[k]) <= max(4.0, 2.0 * (direct_width(c, prof, 0.1) or 4.0))
    lo, hi = k, k
    while lo > 0 and prof[lo - 1] > 0:
        lo -= 1
    while hi < len(prof) - 1 and prof[hi + 1] > 0:
        hi += 1
    win = np.zeros(len(c), bool)
    win[lo:hi + 1] = True
    return win


def measure(img, xs, ys, zs, src, fit_mode="core"):
    """Widths of the reconstructed point in x, y, z with both methods.

    Peak: maximum voxel within 3 mm of the true source position (keeps streaks out).
    Method of Kuntner et al. 2025: Gaussian fit to the 1-voxel line profile through the peak (fit_window).
    NEMA method: sum all parallel profiles within +-1 FWHM of the peak in the two orthogonal
    directions (a band of 2 x FWHM), parabolic peak, linear interpolation.
    """
    Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
    near = (np.abs(X - src[0]) <= 3) & (np.abs(Y - src[1]) <= 3) & (np.abs(Z - src[2]) <= 3)
    iz, iy, ix = np.unravel_index(np.argmax(np.where(near, img, -np.inf)), img.shape)
    lines = {"x": (xs, img[iz, iy, :]), "y": (ys, img[iz, :, ix]), "z": (zs, img[:, iy, ix])}
    out = {"peak": (xs[ix], ys[iy], zs[iz])}
    for ax, (c, prof) in lines.items():
        win = fit_window(c, prof, fit_mode)
        fit = gauss_fit(c[win], prof[win], offset=(fit_mode == "offset"))
        out[ax] = {"line": prof, "coord": c, "fit": fit,
                   "g_fwhm": GAUSS_FWHM * fit[2] if fit is not None else np.nan,
                   "g_fwtm": GAUSS_FWTM * fit[2] if fit is not None else np.nan}
    # NEMA summed profiles
    half = {ax: max(out[ax]["g_fwhm"] if np.isfinite(out[ax]["g_fwhm"]) else 1.0, 0.5) for ax in "xyz"}
    bx = np.abs(xs - xs[ix]) <= half["x"] + 1e-9
    by = np.abs(ys - ys[iy]) <= half["y"] + 1e-9
    bz = np.abs(zs - zs[iz]) <= half["z"] + 1e-9
    summed = {"x": img[bz][:, by, :].sum(axis=(0, 1)),
              "y": img[bz][:, :, bx].sum(axis=(0, 2)),
              "z": img[:, by, :][:, :, bx].sum(axis=(1, 2))}
    for ax, c in (("x", xs), ("y", ys), ("z", zs)):
        prof = summed[ax]
        out[ax]["summed"] = prof
        out[ax]["n_fwhm"] = direct_width(c, prof, 0.5, parabolic=True) or np.nan
        out[ax]["n_fwtm"] = direct_width(c, prof, 0.1, parabolic=True) or np.nan
    return out


def axis_names(src):
    """Which image axis is radial / tangential for this source position."""
    if np.hypot(src[0], src[1]) < 1.0 or abs(src[1]) >= abs(src[0]):
        if np.hypot(src[0], src[1]) >= 1.0 and abs(src[0]) > 1.0:
            print(f"WARNING: source at ({src[0]:.1f}, {src[1]:.1f}) mm is not on an image axis; "
                  "radial/tangential are approximated by y/x", file=sys.stderr)
        return {"radial": "y", "tangential": "x", "axial": "z"}
    if abs(src[1]) > 1.0:
        print(f"WARNING: source at ({src[0]:.1f}, {src[1]:.1f}) mm is not on an image axis; "
              "radial/tangential are approximated by x/y", file=sys.stderr)
    return {"radial": "x", "tangential": "y", "axial": "z"}


# Reference the widths are compared with: the measurement of Kuntner et al. 2025 by default, or (--compare-with)
# a results table of an earlier run of this script, e.g. the Na-22 simulation for Ga-68 runs.
REFERENCE = KUNTNER_QUAD86
REF_LABEL = "Measurement"                     # figure legends (no author names in the figures)
REF_SHORT = "Measurement"                     # panel titles and the printout
REF_COL = "meas"                               # column names: <direction>_meas_FWHM, ...
REF_NEMA = None                                # NEMA-method widths of the reference run, if available
REF_NEMA_SOURCE = ""


def _read_widths(path, prefix):
    """{plane: {r: {dir: (FWHM, FWTM)}}} from a results table, columns <dir>_<prefix>FWHM / FWTM."""
    import csv
    lines = [l for l in open(path) if not l.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    if not rows or f"radial_{prefix}FWHM" not in rows[0]:
        return None
    ref = {}
    for r in rows:
        if r.get("plane") in ("centre", "quarter"):
            ref.setdefault(r["plane"], {})[float(r["r_mm"])] = {
                d: (float(r[f"{d}_{prefix}FWHM"]), float(r[f"{d}_{prefix}FWTM"])) for d in DIRECTIONS}
    return ref or None


def load_reference(path):
    """Gaussian widths of an earlier run (its <out>.txt or <out>_details.txt)."""
    ref = _read_widths(path, "")
    if ref is None:
        sys.exit(f"--compare-with {path}: no Gaussian widths found (give the <out>.txt or "
                 "<out>_details.txt of an earlier run of this script)")
    return ref


def load_reference_nema(path):
    """NEMA-method widths of the same run: from the table itself or its _details / _nema file."""
    base = os.path.splitext(path)[0]
    for suffix in ("_details", "_nema"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    for cand in (path, base + "_details.txt", base + "_nema.txt"):
        if os.path.isfile(cand):
            ref = _read_widths(cand, "NEMA_")
            if ref is not None:
                return ref, cand
    return None, ""


def setup_reference(args, files):
    """--compare-with: compare with an earlier run instead of the measurement (required for Ga-68 files)."""
    global REFERENCE, REF_LABEL, REF_SHORT, REF_COL, REF_NEMA, REF_NEMA_SOURCE
    if args.compare_with:
        args.compare_with = resolve_table(args.compare_with)       # a run folder gives its table
        REFERENCE = load_reference(args.compare_with)
        REF_NEMA, REF_NEMA_SOURCE = load_reference_nema(args.compare_with)
        REF_LABEL = args.compare_label or f"simulation {os.path.basename(args.compare_with)}"
        REF_SHORT, REF_COL = REF_LABEL, "ref"
        n = sum(len(v) for v in REFERENCE.values())
        print(f"Reference: {REF_LABEL} ({args.compare_with}, {n} positions) instead of Kuntner et al. 2025")
        print(f"Reference NEMA-method widths: {REF_NEMA_SOURCE}" if REF_NEMA else
              "Reference NEMA-method widths: none found (no _details.txt / _nema.txt next to the table)")
    elif any("Ga68" in os.path.basename(f) for f in files):
        sys.exit("Ga-68 files: Kuntner et al. 2025 measured Na-22, so compare with your Na-22 simulation "
                 "instead, e.g.  --compare-with results_rat_bg --compare-label \"Na-22 simulation\"")


def nema_reference(src):
    """NEMA-method widths of the reference run at the matching position (or None)."""
    if REF_NEMA is None:
        return None
    r = float(np.hypot(src[0], src[1]))
    z = abs(float(src[2]))
    plane = "centre" if z < 5 else ("quarter" if abs(z - 37.5) < 5 else None)
    if plane not in REF_NEMA:
        return None
    rk = min(REF_NEMA[plane], key=lambda v: abs(v - r))
    return REF_NEMA[plane][rk] if abs(rk - r) <= 1.0 else None


def kuntner_reference(src):
    """Reference values (Kuntner et al. 2025, Quad86, or --compare-with) at the matching position, or None."""
    r = float(np.hypot(src[0], src[1]))
    z = abs(float(src[2]))
    plane = "centre" if z < 5 else ("quarter" if abs(z - 37.5) < 5 else None)
    if plane is None:
        return None, None, None
    if plane not in REFERENCE:
        return None, plane, None
    rk = min(REFERENCE[plane], key=lambda v: abs(v - r))
    if abs(rk - r) > 1.0:
        return None, plane, None
    return REFERENCE[plane][rk], plane, rk


# ============================================================================================
# 7. Analysis of one ROOT file
# ============================================================================================
def analyse_file(path, args, rng):
    a, n_primaries = load(path)
    n_all = len(a["eventID1"])
    if args.add_measured_bg:
        check_background_use(a, path, args)
    src = source_position(a, args.source_id)
    keep = select_events(a, args.events)
    p1 = np.column_stack([a[f"globalPos{k}1"] for k in "XYZ"]).astype(float)[keep]
    p2 = np.column_stack([a[f"globalPos{k}2"] for k in "XYZ"]).astype(float)[keep]

    # physics + detector effects missing in GATE 8.2
    p2 = add_acollinearity(p1, p2, src, args.acolin_fwhm_deg, rng)
    fixed = None
    if args.no_doi:   # detector without DOI: everything at the mean simulated depth
        p = np.concatenate([p1, p2])
        ang = head_frame(p)
        depth = p[:, 0] * np.cos(ang) + p[:, 1] * np.sin(ang) - R_FRONT
        fixed = float(np.clip(np.mean(depth), 0, DEPTH))
    e1 = detector_response(p1, args.plane_fwhm, args.doi_fwhm, rng, fixed)
    e2 = detector_response(p2, args.plane_fwhm, args.doi_fwhm, rng, fixed)

    phi, s, z, tilt = ssrb_coordinates(e1, e2)
    use = (np.abs(s) < FOV_RADIUS) & (np.abs(z) < AXIAL_HALF)
    if args.max_tilt_deg is not None:
        use &= tilt <= args.max_tilt_deg
    w = np.ones(len(s))
    eff_median = np.nan
    if not args.no_norm:
        eff = lor_efficiency(e1, e2)
        eff_median = float(np.median(eff[use]))
        w = 1.0 / np.maximum(eff, args.eff_floor * eff_median)

    # reconstruction box around the source (enlarged for the figures if --image-half is larger)
    (xs, ys, zs), (mx, my, mz) = recon_box(src, args)
    # sinogram grid
    n_s = int(round(2 * FOV_RADIUS / args.sino_ds))
    s_edges = (np.arange(n_s + 1) - n_s / 2) * args.sino_ds
    s_centres = 0.5 * (s_edges[:-1] + s_edges[1:])
    phis = (np.arange(args.views) + 0.5) * np.pi / args.views
    z_edges = np.concatenate([zs - args.voxel / 2, [zs[-1] + args.voxel / 2]])
    iz = np.floor((z - z_edges[0]) / args.voxel).astype(int)
    ip = np.minimum((phi / np.pi * args.views).astype(int), args.views - 1)
    i_s = np.floor((s - s_edges[0]) / args.sino_ds).astype(int)
    in_box = use & (iz >= 0) & (iz < len(zs)) & (i_s >= 0) & (i_s < n_s)
    sino = np.zeros((len(zs), args.views, n_s))
    np.add.at(sino, (iz[in_box], ip[in_box], i_s[in_box]), w[in_box])
    bg_counts = 0.0
    if args.add_measured_bg:                    # measured blank-scan rate, uniform (section 2b)
        duration = args.bg_duration or run_duration(path)
        if not duration:
            sys.exit(f"{os.path.basename(path)}: acquisition time unknown (no macros/<name>.mac): give --bg-duration")
        per_bin = (args.bg_total_cps / (2 * args.bg_mask_half) * args.sino_ds * duration
                   * (args.voxel / (2 * AXIAL_HALF)) / args.views)
        fov = np.abs(s_centres) < FOV_RADIUS
        sino[:, :, fov] += per_bin * (1.0 if args.no_norm else 1.0 / eff_median)
        bg_counts = per_bin * fov.sum() * args.views * len(zs)

    img = fbp_2d(sino, s_centres, phis, xs, ys)
    m = measure(img[np.ix_(mz, my, mx)], xs[mx], ys[my], zs[mz], src, args.fit)   # measurement box
    in_slices = int((in_box & np.isin(iz, np.flatnonzero(mz))).sum())
    names = axis_names(src)
    ref, plane, r_ref = kuntner_reference(src)

    row = {"file": os.path.basename(path), "label": label_of(path, src),
           "x_mm": src[0], "y_mm": src[1], "z_mm": src[2],
           "r_mm": float(np.hypot(src[0], src[1])), "plane": plane or "other",
           "decays": n_primaries, "coincidences": n_all, "selected": int(keep.sum()),
           "in_slices": in_slices, "median_eff": eff_median,
           "peak_x": m["peak"][0], "peak_y": m["peak"][1], "peak_z": m["peak"][2],
           "bg_added_counts": bg_counts,
           "bg_cps_fov": (args.bg_total_cps * FOV_RADIUS / args.bg_mask_half) if args.add_measured_bg else 0.0}
    for d in DIRECTIONS:
        ax = names[d]
        row[f"{d}_axis"] = ax
        row[f"{d}_FWHM"] = m[ax]["g_fwhm"]
        row[f"{d}_FWTM"] = m[ax]["g_fwtm"]
        row[f"{d}_NEMA_FWHM"] = m[ax]["n_fwhm"]
        row[f"{d}_NEMA_FWTM"] = m[ax]["n_fwtm"]
        meas = ref[d] if ref else (np.nan, np.nan)
        row[f"{d}_meas_FWHM"], row[f"{d}_meas_FWTM"] = meas
        if REF_NEMA is not None:
            nref = nema_reference(src)
            row[f"{d}_meas_NEMA_FWHM"], row[f"{d}_meas_NEMA_FWTM"] = nref[d] if nref else (np.nan, np.nan)
    row["meas_r_mm"] = r_ref if r_ref is not None else np.nan
    if row["coincidences"] < 1e5:
        print(f"WARNING {row['file']}: {row['coincidences']} prompts (< 1e5 required by NEMA)",
              file=sys.stderr)
    return row, (img, xs, ys, zs, m, names)


def label_of(path, src):
    base = os.path.splitext(os.path.basename(path))[0]
    mt = re.search(r"z(-?\d+(?:p\d+)?)_r(\d+)", base)
    if mt:
        return base
    return f"{base}_z{src[2]:.1f}_r{np.hypot(src[0], src[1]):.1f}"


# ============================================================================================
# 8. Figures
# ============================================================================================
# Curve styles as in the count-rate and sensitivity figures, so that all figures match:
# measured (reference) black circles, simulation red crosses ("tab:red" = #d62728); the NEMA-method curves
# dashed with "+" markers in the same colours. --no-nema-plot leaves the NEMA-method curves out.
MEAS_STYLE = dict(marker="o", markersize=3, color="black", linewidth=1.5)
SIM_STYLE = dict(marker="x", color="tab:red", linewidth=1.4)
MEAS2_STYLE = dict(marker="+", linestyle="--", color="black", linewidth=1.0)
SIM2_STYLE = dict(marker="+", linestyle="--", color="tab:red", linewidth=1.0)
IMAGE_HALF = 10.0     # mm: default of --image-half: every image view shows the source +- 10 mm


def plot_position(fname, row, recon, args):
    """One figure per position.

    Top: the reconstructed point in three orthogonal views through the peak voxel. Every view
    shows the source position +- --image-half (default 10 mm) on both axes, e.g. y = 0..20 mm
    for the 10 mm position; the dotted lines mark where the line profiles below are taken.
    Bottom: the three line profiles with their Gaussian fits (and, optionally, the NEMA summed
    profiles); the widths are in the panel titles, the legend is in its own row.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    img, xs, ys, zs, m, names = recon
    px, py, pz = m["peak"]
    ix = int(np.argmin(np.abs(xs - px)))
    iy = int(np.argmin(np.abs(ys - py)))
    iz = int(np.argmin(np.abs(zs - pz)))
    peak = img[iz, iy, ix]
    show_nema = not getattr(args, "no_nema_plot", False)

    # fixed window: source position (rounded to 0.5 mm) +- --image-half on both axes of every
    # view. Where it reaches beyond the reconstructed box (e.g. past the 40 mm FOV edge at
    # 35 mm) the panel shows light grey: no image there.
    half = getattr(args, "image_half", IMAGE_HALF)
    step = 5.0 if half >= 6 else (2.0 if half >= 3 else 1.0)       # ticks at multiples of step
    sx, sy, sz = (np.round(row[k] * 2) / 2 + 0.0 for k in ("x_mm", "y_mm", "z_mm"))

    fig = plt.figure(figsize=(12.5, 9.4), constrained_layout=True)
    gs = fig.add_gridspec(3, 3, height_ratios=[1.25, 1.0, 0.08])
    views = [("Transverse", img[iz], xs, ys, px, py, sx, sy, "x (mm)", "y (mm)", f"z = {pz:.2f} mm"),
             ("Coronal", img[:, iy, :], xs, zs, px, pz, sx, sz, "x (mm)", "z (mm)", f"y = {py:.2f} mm"),
             ("Sagittal", img[:, :, ix], ys, zs, py, pz, sy, sz, "y (mm)", "z (mm)", f"x = {px:.2f} mm")]
    image_axes = []
    for col, (name, sl, u, v, pu, pv, cu, cv, xl, yl, where) in enumerate(views):
        ax = fig.add_subplot(gs[0, col])
        im = ax.imshow(sl / peak, origin="lower", cmap="magma", vmin=-0.15, vmax=1.0,
                       interpolation="nearest",
                       extent=[u[0] - args.voxel / 2, u[-1] + args.voxel / 2,
                               v[0] - args.voxel / 2, v[-1] + args.voxel / 2])
        ax.set_xlim(cu - half, cu + half)
        ax.set_ylim(cv - half, cv + half)
        ax.set_xticks(np.arange(np.ceil((cu - half) / step - 1e-9) * step, cu + half + 1e-6, step))
        ax.set_yticks(np.arange(np.ceil((cv - half) / step - 1e-9) * step, cv + half + 1e-6, step))
        ax.set_aspect("equal")
        ax.set_facecolor("0.88")
        ax.axhline(pv, color="white", lw=0.7, ls=":", alpha=0.7)
        ax.axvline(pu, color="white", lw=0.7, ls=":", alpha=0.7)
        ax.set_title(f"{name}  ({where})", fontsize=10)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        image_axes.append(ax)
    fig.colorbar(im, ax=image_axes, shrink=0.9, pad=0.01, label="fraction of the maximum")

    for col, d in enumerate(DIRECTIONS):
        ax = fig.add_subplot(gs[1, col])
        k = names[d]
        c, line, fit, summed = m[k]["coord"], m[k]["line"], m[k]["fit"], m[k]["summed"]
        centre = m["peak"]["xyz".index(k)]
        ax.axhline(0.5, color="0.65", lw=0.7)
        ax.axhline(0.1, color="0.65", lw=0.7)
        if show_nema:
            ax.plot(c, summed / summed.max(), **SIM2_STYLE)
        if fit is not None:
            xx = np.linspace(c[0], c[-1], 800)
            yy = fit[0] * np.exp(-0.5 * ((xx - fit[1]) / fit[2]) ** 2) + fit[3]
            ax.plot(xx, yy / line.max(), "-", color=SIM_STYLE["color"], lw=SIM_STYLE["linewidth"])
        ax.plot(c, line / line.max(), ls="none", marker=SIM_STYLE["marker"], color=SIM_STYLE["color"])
        sim = f"sim FWHM {row[f'{d}_FWHM']:.2f}, FWTM {row[f'{d}_FWTM']:.2f} mm"
        meas_h, meas_t = row[f"{d}_meas_FWHM"], row[f"{d}_meas_FWTM"]
        lines = [f"{d.capitalize()} ({k})", sim]
        if np.isfinite(meas_h):
            lines.append(f"{REF_SHORT} FWHM {meas_h:.2f}, FWTM {meas_t:.2f} mm")
        if show_nema:
            nema = f"NEMA summed FWHM {row[f'{d}_NEMA_FWHM']:.2f} mm"
            if np.isfinite(row.get(f"{d}_meas_NEMA_FWHM", np.nan)):
                nema += f" ({REF_SHORT}: {row[f'{d}_meas_NEMA_FWHM']:.2f})"
            lines.append(nema)
        ax.set_title("\n".join(lines), fontsize=9.5)
        span = max(3.0, 1.3 * row[f"{d}_FWTM"]) if np.isfinite(row[f"{d}_FWTM"]) else 5.0
        ax.set_xlim(centre - span, centre + span)
        ax.set_ylim(-0.2, 1.12)
        ax.set_xlabel(f"{k} (mm)")
        if col == 0:
            ax.set_ylabel("fraction of the maximum")
        ax.grid(alpha=0.2)

    handles = [Line2D([], [], ls="none", marker=SIM_STYLE["marker"], color=SIM_STYLE["color"],
                      label="line profile through the peak (voxels)"),
               Line2D([], [], color=SIM_STYLE["color"], lw=SIM_STYLE["linewidth"], label="Gaussian fit")]
    if show_nema:
        handles.append(Line2D([], [], **SIM2_STYLE, label="NEMA summed profile"))
    handles.append(Line2D([], [], color="0.65", lw=0.7, label="50 % and 10 % of the maximum"))
    legend_ax = fig.add_subplot(gs[2, :])
    legend_ax.axis("off")
    legend_ax.legend(handles=handles, loc="center", ncol=len(handles), frameon=False, fontsize=9)

    recon = getattr(args, "recon_label", None) or f"SSRB (tilt <= {args.max_tilt_deg:g} deg) + 2D FBP"
    fig.suptitle(f"{row['file']}: source ({row['x_mm']:.1f}, {row['y_mm']:.1f}, {row['z_mm']:.1f}) mm, "
                 f"{row['selected']} {args.events}"
                 + (f" + measured background ({row['bg_cps_fov']:.0f} cps in the FOV)"
                    if getattr(args, "add_measured_bg", False) else "")
                 + f"\n{recon}, "
                 f"{args.voxel} mm voxels; position errors {args.plane_fwhm} mm in-plane, "
                 f"{'no DOI' if args.no_doi else f'{args.doi_fwhm} mm DOI'}; "
                 f"acollinearity {args.acolin_fwhm_deg} deg; {'no normalisation' if args.no_norm else 'normalised'}",
                 fontsize=10)
    fig.savefig(fname, dpi=130)
    plt.close(fig)


def plot_summary(fname, rows, key, show_nema=True):
    """FWHM (or FWTM) against radial offset: one column per direction, one row per axial plane.

    Both rows of a column share the y axis, so the two axial planes compare directly. It runs
    from 0 to (highest + lowest point of the column), so the curves sit in the middle with as
    much space above them as below. The legend has its own row at the bottom.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    idx = 0 if key == "FWHM" else 1
    planes = (("centre", "axial centre"), ("quarter", "1/4 axial FOV"))
    fig = plt.figure(figsize=(12.5, 7.8), constrained_layout=True)
    gs = fig.add_gridspec(3, 3, height_ratios=[1.0, 1.0, 0.07])
    for c_i, d in enumerate(DIRECTIONS):
        top = None
        vals = []                                  # every plotted point of this column
        for r_i, (plane, plabel) in enumerate(planes):
            ax = fig.add_subplot(gs[r_i, c_i], sharex=top, sharey=top)
            top = top or ax
            ref = REFERENCE.get(plane, {})
            rr = sorted(ref)
            if rr:
                ax.plot(rr, [ref[r][d][idx] for r in rr], **MEAS_STYLE)
                vals += [ref[r][d][idx] for r in rr]
            else:
                rr = sorted(KUNTNER_QUAD86[plane])
            nref = (REF_NEMA or {}).get(plane, {}) if show_nema else {}
            if nref:
                rn = sorted(nref)
                ax.plot(rn, [nref[r][d][idx] for r in rn], **MEAS2_STYLE)
                vals += [nref[r][d][idx] for r in rn]
            sub = sorted([r for r in rows if r["plane"] == plane], key=lambda r: r["r_mm"])
            if sub:
                ax.plot([r["r_mm"] for r in sub], [r[f"{d}_{key}"] for r in sub], **SIM_STYLE)
                vals += [r[f"{d}_{key}"] for r in sub]
                if show_nema:
                    ax.plot([r["r_mm"] for r in sub], [r[f"{d}_NEMA_{key}"] for r in sub], **SIM2_STYLE)
                    vals += [r[f"{d}_NEMA_{key}"] for r in sub]
            ax.set_xticks(rr)
            ax.grid(alpha=0.25)
            if r_i == 0:
                ax.set_title(d.capitalize(), fontsize=11)
            if c_i == 0:
                ax.set_ylabel(f"{plabel}\n{key} (mm)")
            if r_i == len(planes) - 1:
                ax.set_xlabel("radial offset (mm)")
            else:
                plt.setp(ax.get_xticklabels(), visible=False)
        vals = np.asarray(vals, float)
        vals = vals[np.isfinite(vals)]
        if vals.size:                              # 0 .. highest + lowest (shared by both rows)
            top.set_ylim(0.0, vals.max() + vals.min())
    ref_nema_shown = bool(show_nema and REF_NEMA)
    handles = [Line2D([], [], **MEAS_STYLE, label=REF_LABEL + (", Gaussian fit" if ref_nema_shown else "")),
               Line2D([], [], **SIM_STYLE, label="simulation, Gaussian fit")]
    if ref_nema_shown:
        handles.insert(1, Line2D([], [], **MEAS2_STYLE, label=f"{REF_LABEL}, NEMA method"))
    if show_nema:
        handles.append(Line2D([], [], **SIM2_STYLE, label="simulation, NEMA method"))
    legend_ax = fig.add_subplot(gs[2, :])
    legend_ax.axis("off")
    legend_ax.legend(handles=handles, loc="center", ncol=len(handles), frameon=False, fontsize=9.5)
    versus = "measurement" if REF_COL == "meas" else REF_LABEL
    fig.suptitle(f"Spatial resolution, {key}: simulation vs {versus}", fontsize=11)
    fig.savefig(fname, dpi=130)
    plt.close(fig)


# ============================================================================================
# 8b. Clean position figures and the magnetic-field comparison
# ============================================================================================
# Clean figure, <base>_plots_clean/position_<label>.png: the same views and line profiles as the default
# figure, but only the view names (transverse, coronal, sagittal), the direction names (radial, tangential,
# axial), the source (22Na or 68Ga; "0 T" added for a run without the field) and its position. No widths,
# no NEMA curves, no 50 %/10 % lines, no legend, no colour bar, no settings. Profile: voxel values (crosses)
# and the Gaussian fit (line).
# Field comparison, <base>_plots_field/field_comparison_<bed>_z<z>_r<r>.png: made when --compare-with is a
# run of the same source with the other field state (Ga-68 at 9.4 T and without the field). Top: the views
# of the 9.4 T run, below them those of the 0 T run; bottom: the line profiles and Gaussian fits of both
# runs on top of each other, with the fitted FWHM of each run in every profile panel. The other run's
# images come from its saved volumes (<its base>_volumes/), where its profiles are measured again in the
# same box with the same fit; a warning is printed if a width differs from its table by more than 0.01 mm.
ISOTOPE_TEX = {"Na22": r"$^{22}$Na", "Ga68": r"$^{68}$Ga"}
FIELD_LABEL = {True: "9.4 T", False: "0 T"}
CLEAN_STYLE = dict(color=SIM_STYLE["color"], marker=SIM_STYLE["marker"], linestyle="-",
                   linewidth=SIM_STYLE["linewidth"])
FIELD_STYLE = {True: CLEAN_STYLE,
               False: dict(color="tab:blue", marker="+", linestyle="--", linewidth=1.4)}


def run_info(name):
    """Source and field state of a run from its file name (spres_run.py names SpRes<tag>_<bed>_z.._r..,
    tag '' = Na-22 at 9.4 T, 'Ga68', 'NoB', 'Ga68NoB'): ('Na22' or 'Ga68', True if 9.4 T)."""
    first = os.path.basename(str(name)).split("_")[0]
    tag = first[len("SpRes"):] if first.startswith("SpRes") else ""
    return ("Ga68" if "Ga68" in tag else "Na22"), ("NoB" not in tag)


def nominal_position(row):
    """Radial offset and axial position of the source, rounded to 0.5 mm (e.g. 10 and 37.5 mm)."""
    r = round(float(row["r_mm"]) * 2) / 2
    z = round(float(row["z_mm"]) * 2) / 2
    return r, (0.0 if z == 0 else z)


def position_text(fd):
    return f"r = {fd['r']:g} mm, z = {fd['z']:g} mm"


def position_tag(label):
    """Position part of a label: 'rat_z0_r10' from 'SpResGa68NoB_rat_z0_r10'."""
    first, _, rest = label.partition("_")
    return rest if first.startswith("SpRes") and rest else label


def _figure_data(row, img, xs, ys, zs, m, names, voxel, half):
    """What the clean and comparison figures draw for one position (images and profiles divided by
    their maximum, as in plot_position)."""
    px, py, pz = m["peak"]
    ix, iy, iz = (int(np.argmin(np.abs(g - p))) for g, p in ((xs, px), (ys, py), (zs, pz)))
    peak = img[iz, iy, ix]
    sx, sy, sz = (np.round(float(row[k]) * 2) / 2 for k in ("x_mm", "y_mm", "z_mm"))

    def ext(u, v):
        return [u[0] - voxel / 2, u[-1] + voxel / 2, v[0] - voxel / 2, v[-1] + voxel / 2]
    views = [("Transverse", img[iz] / peak, ext(xs, ys), (sx, sy), ("x (mm)", "y (mm)")),
             ("Coronal", img[:, iy, :] / peak, ext(xs, zs), (sx, sz), ("x (mm)", "z (mm)")),
             ("Sagittal", img[:, :, ix] / peak, ext(ys, zs), (sy, sz), ("y (mm)", "z (mm)"))]
    profiles = {}
    for d in DIRECTIONS:
        k = names[d]
        line, fit = m[k]["line"], m[k]["fit"]
        top = line.max()
        profiles[d] = {"axis": k, "coord": m[k]["coord"], "line": line / top,
                       "fit": None if fit is None else (fit[0] / top, fit[1], fit[2], fit[3] / top),
                       "centre": m["peak"]["xyz".index(k)], "FWHM": m[k]["g_fwhm"], "FWTM": m[k]["g_fwtm"]}
    iso, field = run_info(row["file"])
    r, z = nominal_position(row)
    return {"label": row["label"], "plane": row["plane"], "iso": iso, "field": field, "r": r, "z": z,
            "views": views, "profiles": profiles, "half": half}


def figure_data(row, recon, args):
    """Figure data of a position just analysed (the reconstruction in memory)."""
    img, xs, ys, zs, m, names = recon[:6]
    return _figure_data(row, img, xs, ys, zs, m, names, args.voxel, getattr(args, "image_half", IMAGE_HALF))


def read_nifti(path):
    """Volume written by write_nifti: (vol[z, y, x], x, y, z voxel centres in mm)."""
    import struct
    with open(path, "rb") as f:
        raw = f.read()
    nx, ny, nz = struct.unpack_from("<8h", raw, 40)[1:4]
    if struct.unpack_from("<h", raw, 70)[0] != 16:
        sys.exit(f"{path}: not a float32 NIfTI volume of this analysis")
    offset = int(struct.unpack_from("<f", raw, 108)[0])
    grids = []
    for n, o, i in ((nx, 280, 0), (ny, 296, 1), (nz, 312, 2)):
        row = struct.unpack_from("<4f", raw, o)
        grids.append(row[3] + row[i] * np.arange(n))
    vol = np.frombuffer(raw, "<f4", nx * ny * nz, offset).reshape(nz, ny, nx).astype(float)
    return (vol, *grids)


def resolve_table(path):
    """Results table of a finished run, given as the table itself, as the run's folder (results_<name>/),
    or as a bare table name, which is then looked for in the run's folder (spres_results_<name>.txt ->
    results_<name>/spres_results_<name>.txt)."""
    if os.path.isdir(path):
        cands = [p for p in sorted(glob.glob(os.path.join(path, "*.txt")))
                 if not re.search(r"_(details|nema)\.txt$", p)]
        if len(cands) != 1:
            sys.exit(f"{path}: expected one results table (<name>.txt) in the folder, found {len(cands)}")
        return cands[0]
    if not os.path.exists(path) and not os.path.dirname(path):
        run = re.sub(r"_(details|nema)$", "", os.path.splitext(path)[0])
        alt = os.path.join(os.path.dirname(output_base(run)), path)
        if os.path.exists(alt):
            return alt
    return path


def results_base(path):
    """Base name (folder/name) of a finished run, from its folder or one of its tables."""
    return re.sub(r"_(details|nema)$", "", os.path.splitext(resolve_table(path))[0])


def read_details(base):
    """Rows of <base>_details.txt as dicts of strings."""
    import csv
    with open(base + "_details.txt") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def run_settings(base):
    """Settings of a finished run that the figures need, from the 'Settings' sheet of <base>.xlsx."""
    s = {"voxel": 0.5, "roi_xy": 10.0, "roi_z": 20.0, "fit": "core", "image_half": IMAGE_HALF}
    try:
        from openpyxl import load_workbook
        wb = load_workbook(base + ".xlsx", read_only=True)
        for vals in wb["Settings"].iter_rows(values_only=True):
            if vals and vals[0] in s and vals[1] not in (None, "None"):
                s[vals[0]] = vals[1] if vals[0] == "fit" else float(vals[1])
        wb.close()
    except Exception as exc:
        print(f"WARNING {base}.xlsx: settings not read ({exc}); using voxel 0.5 mm, box +-10/+-20 mm, "
              "fit core", file=sys.stderr)
    return s


def figure_data_from_volume(path, row, settings, half):
    """Figure data of a finished run from its saved volume (volume_<label>.nii) and its _details row.
    The line profiles are measured again on the volume in the run's own box with its own fit."""
    vol, xs, ys, zs = read_nifti(path)
    src = tuple(float(row[k]) for k in ("x_mm", "y_mm", "z_mm"))
    v = settings["voxel"]
    mx = box_mask(xs, src[0], settings["roi_xy"], v, FOV_RADIUS)
    my = box_mask(ys, src[1], settings["roi_xy"], v, FOV_RADIUS)
    mz = box_mask(zs, src[2], settings["roi_z"], v, AXIAL_HALF)
    m = measure(vol[np.ix_(mz, my, mx)], xs[mx], ys[my], zs[mz], src, settings["fit"])
    fd = _figure_data(row, vol, xs, ys, zs, m, axis_names(src), v, half)
    for d in DIRECTIONS:
        try:
            table = float(row[f"{d}_FWHM"])
        except (KeyError, ValueError):
            continue
        if np.isfinite(table) and abs(fd["profiles"][d]["FWHM"] - table) > 0.01:
            print(f"WARNING {os.path.basename(path)}: {d} FWHM {fd['profiles'][d]['FWHM']:.3f} mm on the "
                  f"volume, {table:.3f} mm in the run's table", file=sys.stderr)
    return fd


def _draw_view(ax, view, half, label_pt=None):
    """One image view, source +- half on both axes (grey where the image ends), as in plot_position.
    label_pt: font size of the axis labels (default: matplotlib's)."""
    name, sl, extent, (cu, cv), (xl, yl) = view
    step = 5.0 if half >= 6 else (2.0 if half >= 3 else 1.0)
    ax.imshow(sl, origin="lower", cmap="magma", vmin=-0.15, vmax=1.0, interpolation="nearest", extent=extent)
    ax.set_xlim(cu - half, cu + half)
    ax.set_ylim(cv - half, cv + half)
    ax.set_xticks(np.arange(np.ceil((cu - half) / step - 1e-9) * step, cu + half + 1e-6, step))
    ax.set_yticks(np.arange(np.ceil((cv - half) / step - 1e-9) * step, cv + half + 1e-6, step))
    ax.set_aspect("equal")
    ax.set_facecolor("0.88")
    ax.set_xlabel(xl, fontsize=label_pt)
    ax.set_ylabel(yl, fontsize=label_pt)


def _draw_profile(ax, p, style):
    """Voxel values of one line profile (markers) and its Gaussian fit (line)."""
    c = p["coord"]
    if p["fit"] is not None:
        a, mu, sg, b = p["fit"]
        xx = np.linspace(c[0], c[-1], 800)
        ax.plot(xx, a * np.exp(-0.5 * ((xx - mu) / sg) ** 2) + b, color=style["color"],
                linestyle=style["linestyle"], linewidth=style["linewidth"])
    ax.plot(c, p["line"], ls="none", marker=style["marker"], color=style["color"])


def _profile_window(profiles):
    """x range of a profile panel: peak +- max(3 mm, 1.3 FWTM), as in plot_position (union of all runs)."""
    lo, hi = np.inf, -np.inf
    for p in profiles:
        span = max(3.0, 1.3 * p["FWTM"]) if np.isfinite(p["FWTM"]) else 5.0
        lo, hi = min(lo, p["centre"] - span), max(hi, p["centre"] + span)
    return lo, hi


def plot_position_clean(fname, fd):
    """Clean figure of one position: views on top, line profiles with the Gaussian fit below."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(12.5, 8.6), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.25, 1.0])
    for col, view in enumerate(fd["views"]):
        ax = fig.add_subplot(gs[0, col])
        _draw_view(ax, view, fd["half"])
        ax.set_title(view[0], fontsize=11)
    for col, d in enumerate(DIRECTIONS):
        ax = fig.add_subplot(gs[1, col])
        p = fd["profiles"][d]
        _draw_profile(ax, p, CLEAN_STYLE)
        ax.set_xlim(*_profile_window([p]))
        ax.set_ylim(-0.2, 1.12)
        ax.set_title(d.capitalize(), fontsize=11)
        ax.set_xlabel(f"{p['axis']} (mm)")
        if col == 0:
            ax.set_ylabel("fraction of the maximum")
    source = ISOTOPE_TEX[fd["iso"]] + ("" if fd["field"] else f", {FIELD_LABEL[False]}")
    fig.suptitle(f"{source}    {position_text(fd)}", fontsize=12)
    fig.savefig(fname, dpi=130)
    plt.close(fig)


def plot_field_comparison(fname, fd_on, fd_off):
    """One position with (fd_on) and without (fd_off) the magnetic field: the views of both runs on top
    (9.4 T, then 0 T), the line profiles and Gaussian fits of both below, with each run's FWHM in the panel
    titles. Same style as the sensitivity figures: 9 in wide, axis labels 12 pt, tick labels 10 pt,
    title 11 pt, the legend in its own row below the plots."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    label_pt, tick_pt, title_pt, legend_pt = 12, 10, 11, 10
    fig = plt.figure(figsize=(9, 9.8), constrained_layout=True)
    gs = fig.add_gridspec(4, 3, height_ratios=[1.2, 1.2, 1.0, 0.06])
    for r_i, fd in enumerate((fd_on, fd_off)):
        for col, view in enumerate(fd["views"]):
            ax = fig.add_subplot(gs[r_i, col])
            _draw_view(ax, view, fd_on["half"], label_pt)
            ax.tick_params(labelsize=tick_pt)
            if r_i == 0:
                ax.set_title(view[0], fontsize=label_pt)
            if col == 0:
                ax.set_ylabel(f"{FIELD_LABEL[fd['field']]}\n{view[4][1]}", fontsize=label_pt)
    for col, d in enumerate(DIRECTIONS):
        ax = fig.add_subplot(gs[2, col])
        for fd in (fd_on, fd_off):
            _draw_profile(ax, fd["profiles"][d], FIELD_STYLE[fd["field"]])
        widths = ", ".join(f"{FIELD_LABEL[fd['field']]}: {fd['profiles'][d]['FWHM']:.2f} mm" for fd in (fd_on, fd_off))
        ax.set_title(f"{d.capitalize()} (FWHM)\n{widths}", fontsize=title_pt)
        ax.set_xlim(*_profile_window([fd_on["profiles"][d], fd_off["profiles"][d]]))
        ax.set_ylim(-0.2, 1.12)
        ax.tick_params(labelsize=tick_pt)
        ax.set_xlabel(f"{fd_on['profiles'][d]['axis']} (mm)", fontsize=label_pt)
        if col == 0:
            ax.set_ylabel("Fraction of the maximum", fontsize=label_pt)
    handles = [Line2D([], [], **FIELD_STYLE[fd["field"]], label=FIELD_LABEL[fd["field"]]) for fd in (fd_on, fd_off)]
    lax = fig.add_subplot(gs[3, :])
    lax.axis("off")
    lax.legend(handles=handles, loc="center", ncol=2, frameon=False, fontsize=legend_pt)
    fig.suptitle(f"{ISOTOPE_TEX[fd_on['iso']]}    {position_text(fd_on)}", fontsize=title_pt)
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def field_comparison_figures(fds, ref_base, out_dir, half):
    """Field comparison of the positions in fds (figure data of one run) with the finished run ref_base,
    if that run has the same source and the other field state; its images are read from its volumes.
    Returns the number of figures written (0 if the runs do not form such a pair)."""
    try:
        ref_rows = read_details(ref_base)
    except OSError:
        return 0
    own = {(fd["iso"], fd["field"]) for fd in fds}
    ref = {run_info(r["file"]) for r in ref_rows}
    if len(own) != 1 or len(ref) != 1:
        return 0
    (iso, field), (iso_ref, field_ref) = own.pop(), ref.pop()
    if iso != iso_ref or field == field_ref:
        return 0
    settings = run_settings(ref_base)
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for fd in fds:
        match = [r for r in ref_rows if r["plane"] == fd["plane"] and nominal_position(r) == (fd["r"], fd["z"])]
        if not match:
            print(f"field comparison: no position {position_text(fd)} in {ref_base}", file=sys.stderr)
            continue
        vol = os.path.join(ref_base + "_volumes", f"volume_{match[0]['label']}.nii")
        if not os.path.isfile(vol):
            print(f"field comparison: {vol} not found (run that analysis with volumes)", file=sys.stderr)
            continue
        fd_ref = figure_data_from_volume(vol, match[0], settings, half)
        on, off = (fd, fd_ref) if field else (fd_ref, fd)
        plot_field_comparison(os.path.join(out_dir, f"field_comparison_{position_tag(fd['label'])}.png"), on, off)
        n += 1
    return n


# ============================================================================================
# 9. Output files
# ============================================================================================
def fmt(v, nd=2):
    return "nan" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def write_tables(base, rows, args):
    rows = sorted(rows, key=lambda r: (r["plane"], r["r_mm"], r["file"]))
    with open(base + ".txt", "w") as f:
        f.write("# Spatial resolution, Gaussian fit to line profiles (Kuntner 2025 method). mm.\n")
        ref_desc = "Kuntner et al. 2025 Table 3, Quad86" if REF_COL == "meas" else \
            f"{REF_LABEL} ({args.compare_with})"
        f.write(f"# diff = sim - {REF_COL}; {REF_COL} = {ref_desc}.\n")
        cols = ["file", "plane", "r_mm"] + [f"{d}_{w}" for d in DIRECTIONS for w in
                                           ("FWHM", f"{REF_COL}_FWHM", "diffFWHM", "FWTM", f"{REF_COL}_FWTM", "diffFWTM")]
        f.write("\t".join(cols) + "\n")
        for r in rows:
            vals = [r["file"], r["plane"], fmt(r["r_mm"], 1)]
            for d in DIRECTIONS:
                for w in ("FWHM", "FWTM"):
                    sim, meas = r[f"{d}_{w}"], r[f"{d}_meas_{w}"]
                    vals += [fmt(sim), fmt(meas), fmt(sim - meas)]
            f.write("\t".join(vals) + "\n")
    with open(base + "_nema.txt", "w") as f:
        f.write("# Spatial resolution, NEMA NU 4-2008 Sec. 3.4 method (summed profiles, parabolic "
                "peak, linear interpolation). mm.\n")
        if REF_NEMA is None:
            cols = ["file", "plane", "r_mm"] + [f"{d}_NEMA_{w}" for d in DIRECTIONS for w in ("FWHM", "FWTM")]
            f.write("\t".join(cols) + "\n")
            for r in rows:
                f.write("\t".join([r["file"], r["plane"], fmt(r["r_mm"], 1)] +
                                  [fmt(r[c]) for c in cols[3:]]) + "\n")
        else:
            f.write(f"# diff = sim - ref; ref = {REF_LABEL}, NEMA method ({REF_NEMA_SOURCE}).\n")
            cols = ["file", "plane", "r_mm"] + [f"{d}_{w}" for d in DIRECTIONS for w in
                                               ("NEMA_FWHM", "ref_NEMA_FWHM", "diffNEMA_FWHM",
                                                "NEMA_FWTM", "ref_NEMA_FWTM", "diffNEMA_FWTM")]
            f.write("\t".join(cols) + "\n")
            for r in rows:
                vals = [r["file"], r["plane"], fmt(r["r_mm"], 1)]
                for d in DIRECTIONS:
                    for w in ("FWHM", "FWTM"):
                        sim, ref = r[f"{d}_NEMA_{w}"], r.get(f"{d}_meas_NEMA_{w}", np.nan)
                        vals += [fmt(sim), fmt(ref), fmt(sim - ref)]
                f.write("\t".join(vals) + "\n")
    keys = list(rows[0].keys())
    with open(base + "_details.txt", "w") as f:
        f.write("\t".join(k.replace("meas_", f"{REF_COL}_") for k in keys) + "\n")
        for r in rows:
            f.write("\t".join(fmt(r[k], 4) if isinstance(r[k], float) else str(r[k]) for k in keys) + "\n")
    try:
        from openpyxl import Workbook
    except ImportError:
        print("openpyxl not installed: no .xlsx written", file=sys.stderr)
        return
    wb = Workbook()
    for title, txt in (("Kuntner_method", base + ".txt"), ("NEMA_method", base + "_nema.txt"),
                       ("Details", base + "_details.txt")):
        ws = wb.active if title == "Kuntner_method" else wb.create_sheet(title)
        ws.title = title
        for line in open(txt):
            if line.startswith("#"):
                continue
            ws.append([_num(v) for v in line.rstrip("\n").split("\t")])
    ws = wb.create_sheet("Settings")
    for k, v in sorted(vars(args).items()):
        ws.append([k, str(v)])
    wb.save(base + ".xlsx")


def _num(v):
    try:
        return float(v)
    except ValueError:
        return v


# ============================================================================================
# 10. Main program
# ============================================================================================
def default_out(files, args, prefix="spres_results"):
    """Default run name <prefix>[_<tag>]_<bed>[_bg], tag and bed from the file names when they all agree
    (spres_run.py: SpRes<tag>_<bed>_z.._r..), e.g. spres_results_ga68nob_rat_bg; else the --bed."""
    found = [re.match(r"SpRes([A-Za-z0-9]*)_(mouse|rat)_z", os.path.basename(f)) for f in files]
    parts = [prefix]
    if found and all(found) and len({mt.groups() for mt in found}) == 1:
        tag, bed = found[0].groups()
        parts += ([tag.lower()] if tag else []) + [bed]
    else:
        parts.append(args.bed)
    if getattr(args, "add_measured_bg", False):
        parts.append("bg")
    return "_".join(parts)


def output_base(out):
    """Base path of all output files of a run. Every run has its own folder: a name
    without a folder, spres_results_<name>, becomes results_<name>/spres_results_<name>; a name with a
    folder is used as given."""
    out = os.path.splitext(out)[0]
    if os.path.dirname(out):
        return out
    short = out[len("spres_results"):].lstrip("_") if out.startswith("spres_results") else out
    return os.path.join("results_" + short if short else "results", out)


def setup_outputs(args, files, prefix="spres_results"):
    """Run name, run folder and output folders: <base>_plots/ (default figures), <base>_plots_clean/
    (clean figures), <base>_volumes/. Returns (base, dirs)."""
    args.out = args.out or default_out(files, args, prefix)
    base = output_base(args.out)
    if os.path.dirname(base):
        os.makedirs(os.path.dirname(base), exist_ok=True)
    dirs = {"plots": None, "clean": None, "volumes": None if args.no_volumes else base + "_volumes"}
    if not args.no_plots:
        try:
            import matplotlib  # noqa: F401
            dirs["plots"], dirs["clean"] = base + "_plots", base + "_plots_clean"
        except ImportError:
            print("matplotlib not installed: no figures", file=sys.stderr)
            args.no_plots = True          # no enlarged box for --image-half either
    for d in dirs.values():
        if d:
            os.makedirs(d, exist_ok=True)
    return base, dirs


def write_position_outputs(row, recon, args, dirs, fds):
    """Default figure, clean figure and 3D image of one position (figure data kept in fds)."""
    if dirs["plots"]:
        plot_position(os.path.join(dirs["plots"], f"position_{row['label']}.png"), row, recon, args)
        fd = figure_data(row, recon, args)
        plot_position_clean(os.path.join(dirs["clean"], f"position_{row['label']}.png"), fd)
        fds.append(fd)
    if dirs["volumes"]:
        save_volume(os.path.join(dirs["volumes"], f"volume_{row['label']}.nii"), row, recon, args)


def finish_outputs(base, rows, args, dirs, fds):
    """Tables, summary figures and, if --compare-with is the same source with the other field state,
    the field comparison figures (<base>_plots_field/)."""
    write_tables(base, rows, args)
    written = [f"{base}.txt", f"{base}_nema.txt", f"{base}_details.txt"]
    if os.path.exists(base + ".xlsx"):
        written.append(f"{base}.xlsx")
    if dirs["plots"]:
        plot_summary(os.path.join(dirs["plots"], "summary_FWHM.png"), rows, "FWHM", not args.no_nema_plot)
        plot_summary(os.path.join(dirs["plots"], "summary_FWTM.png"), rows, "FWTM", not args.no_nema_plot)
        written += [dirs["plots"] + "/", dirs["clean"] + "/"]
        if args.compare_with:
            field_dir = base + "_plots_field"
            n = field_comparison_figures(fds, results_base(args.compare_with), field_dir, args.image_half)
            if n:
                written.append(f"{field_dir}/ ({n} field comparisons)")
    if dirs["volumes"]:
        written.append(dirs["volumes"] + "/")
    print("Written: " + ", ".join(written))


def add_compare_options(ap):
    g = ap.add_argument_group("reference (default: Kuntner et al. 2025, Table 3, Quad86, measured with Na-22)")
    g.add_argument("--compare-with", metavar="TABLE",
                   help="compare with an earlier run of this analysis instead: its results folder "
                        "(results_<name>/) or its <out>.txt (or _details.txt), e.g. results_rat_bg for the "
                        "Na-22 run. Required for Ga-68 files. A Ga-68 run compared with the Ga-68 run of "
                        "the other field state also gets the field comparison figures")
    g.add_argument("--compare-label", metavar="TEXT",
                   help="name of that reference in tables and figures (default: 'simulation <TABLE>')")


def main():
    ap = argparse.ArgumentParser(description="NEMA NU 4 spatial resolution of GATE point-source runs, "
                                             "compared with Kuntner et al. 2025 (Quad86) or, with "
                                             "--compare-with, with an earlier run.")
    ap.add_argument("files", nargs="*", help="ROOT files (default: output/SpRes_<bed>_*.root)")
    ap.add_argument("--dir", default="output", help="folder searched when no files are given")
    ap.add_argument("--bed", choices=("mouse", "rat"), default="mouse",
                    help="cradle of the run (spres_run.py --bed): without file names, analyse "
                         "<dir>/SpRes_<bed>_*.root (default mouse)")
    g = ap.add_argument_group("events")
    g.add_argument("--events", choices=("prompts", "trues", "unscattered"), default="prompts")
    g.add_argument("--source-id", type=int, default=0, help="sourceID of the point source, Na-22 or Ga-68 (default 0)")
    g = ap.add_argument_group("measured background (for runs made with spres_run.py --no-lu176; section 2b)")
    g.add_argument("--add-measured-bg", action="store_true",
                   help="add the measured blank-scan rate (no source) to every sinogram bin before the "
                        "reconstruction, as the sensitivity and NECR analyses add the measured background")
    g.add_argument("--bg-total-cps", type=float, default=BLANK_30PCT_TOTAL_CPS,
                   help=f"blank-scan rate in |s| <= --bg-mask-half, cps (default {BLANK_30PCT_TOTAL_CPS:g}: the 2021 "
                        f"blank scan, 30 %% window, |s| < 40 mm, |z| < 75 mm, tilt <= {BLANK_30PCT_TILT:g} deg)")
    g.add_argument("--bg-mask-half", type=float, default=BLANK_30PCT_MASK_HALF,
                   help=f"half width |s| that --bg-total-cps refers to, mm (default {BLANK_30PCT_MASK_HALF:g})")
    g.add_argument("--bg-duration", type=float, default=None,
                   help="acquisition time per position, s (default: from macros/<name>.mac of the run)")
    g = ap.add_argument_group("detector response and physics added to the GATE positions")
    g.add_argument("--plane-fwhm", type=float, default=1.6, help="in-plane position error, mm FWHM (default 1.6, measured by González et al. 2016)")
    g.add_argument("--doi-fwhm", type=float, default=1.6,
                   help="depth-of-interaction error, mm FWHM (default 1.6, measured by Gsell et al. 2020)")
    g.add_argument("--no-doi", action="store_true", help="detector without DOI: all photons at the mean depth")
    g.add_argument("--acolin-fwhm-deg", type=float, default=0.5, help="photon acollinearity, deg FWHM (0 = off)")
    g.add_argument("--seed", type=int, default=12345, help="random seed of the added errors")
    g = ap.add_argument_group("reconstruction (SSRB + 2D FBP)")
    g.add_argument("--voxel", type=float, default=0.5, help="voxel size and slice thickness, mm")
    g.add_argument("--sino-ds", type=float, default=0.478602, help="radial sinogram bin, mm")
    g.add_argument("--views", type=int, default=193, help="projection angles over 180 deg")
    g.add_argument("--max-tilt-deg", type=float, default=10.5,
                   help="max LOR tilt to the transverse plane, deg (default 10.5, adjusted to the measured axial "
                        "widths; 90 = all LORs)")
    g.add_argument("--no-norm", action="store_true", help="no normalisation (efficiency) weights")
    g.add_argument("--eff-floor", type=float, default=0.1, help="weights capped at 1/(floor x median efficiency)")
    g.add_argument("--roi-xy", type=float, default=10.0, help="half width of the reconstructed box, transverse, mm")
    g.add_argument("--roi-z", type=float, default=20.0, help="half width of the reconstructed box, axial, mm")
    g = ap.add_argument_group("width measurement")
    g.add_argument("--fit", choices=("core", "offset"), default="core",
                   help="Gaussian fit of the line profiles: 'core' = pure Gaussian on the positive core "
                        "around the peak (default); 'offset' = Gaussian + constant on a wide window")
    g = ap.add_argument_group("output")
    g.add_argument("--out", default=None,
                   help="run name: all outputs go to its own folder, spres_results_<name> -> "
                        "results_<name>/spres_results_<name>* (a name with a folder is used as given). "
                        "Default from the file names: spres_results_[<tag>_]<bed>[_bg], e.g. "
                        "spres_results_ga68nob_rat_bg")
    g.add_argument("--no-plots", action="store_true")
    g.add_argument("--image-half", type=float, default=IMAGE_HALF,
                   help="half width of the image views in the position figures, mm: they show the "
                        "source +- this on both axes (default 10; e.g. 15 = 30 x 30 mm). Figures only, "
                        "the widths do not change")
    g.add_argument("--volume-half", type=float, default=10.0,
                   help="saved 3D image: source +- max(--roi-xy, this) transverse and +- max(--roi-z, "
                        "this) axial, mm (default 10: +-10 / +-20 mm, the measured box)")
    g.add_argument("--no-volumes", action="store_true", help="do not write the 3D images (.nii)")
    g.add_argument("--no-nema-plot", action="store_true",
                   help="leave the NEMA-method curves out of the figures (the tables keep them)")
    add_compare_options(ap)
    args = ap.parse_args()
    if (args.add_measured_bg and args.bg_total_cps == BLANK_30PCT_TOTAL_CPS
            and (args.max_tilt_deg is None or abs(args.max_tilt_deg - BLANK_30PCT_TILT) > 1e-9)):
        print(f"WARNING: the default --bg-total-cps ({BLANK_30PCT_TOTAL_CPS:g} cps) was counted with a tilt cut of "
              f"{BLANK_30PCT_TILT:g} deg, not {args.max_tilt_deg}; give --bg-total-cps for this tilt "
              "(all tilts: 703.4 cps)", file=sys.stderr)

    pattern = os.path.join(args.dir, f"SpRes_{args.bed}_*.root")
    files = args.files or sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"No files found (looked for {pattern}; files with other names can be given as "
                 "arguments)")
    setup_reference(args, files)
    base, dirs = setup_outputs(args, files)

    rng = np.random.default_rng(args.seed)
    rows, fds = [], []
    for path in files:
        try:
            row, recon = analyse_file(path, args, rng)
        except Exception as exc:                       # keep going with the other files
            print(f"SKIPPED {path}: {exc}", file=sys.stderr)
            continue
        rows.append(row)
        msg = "  ".join(f"{d[:3]} {row[f'{d}_FWHM']:.2f}" + (f" ({row[f'{d}_meas_FWHM']:.2f})"
                        if np.isfinite(row[f'{d}_meas_FWHM']) else "") for d in DIRECTIONS)
        print(f"{row['file']}: r = {row['r_mm']:.1f} mm, z = {row['z_mm']:.1f} mm, "
              f"{row['selected']} events | FWHM sim ({REF_SHORT}) {msg}")
        write_position_outputs(row, recon, args, dirs, fds)
    if not rows:
        sys.exit("No file could be analysed")
    finish_outputs(base, rows, args, dirs, fds)


if __name__ == "__main__":
    main()
