# Spatial resolution (NEMA NU 4-2008, section 3)

This folder simulates the spatial resolution test of NEMA NU 4-2008 (section 3) with the GATE 8.2 model of the Bruker Si 198 PET insert in the 9.4 T MR scanner. A Na-22 point source (0.3 mm) in a 10 mm acrylic cube is placed at the 16 positions that Kuntner et al. 2025 measured with the Quad86 coil (Table 3): radial offsets of 0, 5, 10, 15, 20, 25, 30 and 35 mm, at the axial centre (z = 0) and at 1/4 of the axial FOV (z = 37.5 mm), 140 kBq and 60 s per position.

GATE stores exact interaction positions. The analysis therefore adds the detector position errors and the photon acollinearity, reconstructs the point with SSRB and 2D FBP, measures FWHM and FWTM in the radial, tangential and axial directions, and compares them with the published values. This is the spatial resolution part of the paper "Monte Carlo Simulations of a Preclinical High Field 9.4T PET/MR System" (under review in EJNMMI Physics).

## Files

| File | What it is |
|---|---|
| `SpRes_main.mac` | The complete model: detector, Quad86 coil, cradle, source cube, Na-22 source, digitizer and output. The RUN SETTINGS block at the top holds the values that change between positions. |
| `coil_bed_real/` | The Quad86 coil (two G10 tubes with uniform walls) and the mouse and rat cradles, cut at z = ±80 mm, with their STL files and the material file `Coil3Bed.db`. The same files are used in the sensitivity and NECR folders. |
| `Material/GateMaterials.db` | The GATE material database. |
| `spres_run.py` | Writes one job macro per position and runs the GATE jobs in parallel. |
| `spres_analysis.py` | Reads the ROOT files, reconstructs the point, measures the widths and compares them with the measurement. Writes tables, figures and 3D images. |
| `view_model.py` | Writes a view-only GATE macro of one position, to look at the model. |

## Running the simulation

The GATE container and the Python packages are described in the top-level README. Run all commands in this folder.

1. Test the setup with one short job (0.5 s at r = 10 mm, z = 0):
   ```bash
   python3 spres_run.py --smoke
   ```
   Then read `logs/smoke_mouse_z0_r10.log`. Before it starts GATE, the runner checks that the materials and every file the macro loads are there. Every job also runs the Geant4 overlap check before the first event.
2. Run all 16 positions, at most one job per physical core:
   ```bash
   python3 spres_run.py --workers 16
   ```
3. Analyse them:
   ```bash
   python3 spres_analysis.py
   ```

**Settings used for the paper.** I ran the rat cradle, as in the measurement, with the intrinsic Lu-176 source switched off, and added the measured blank-scan background in the analysis:

```bash
python3 spres_run.py --bed rat --no-lu176 --smoke
python3 spres_run.py --bed rat --no-lu176 --workers 16
python3 spres_analysis.py --bed rat --add-measured-bg
```

**On a cluster with Apptainer**, give the container command with `--command`:

```bash
python3 spres_run.py --bed rat --no-lu176 --workers 16 \
    --command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"
```

With a local GATE installation use `--command "Gate {macro}"`. Without `--command` the runner uses the Docker image `opengatecollaboration/gate:8.2-docker`.

**What the runner writes.** For each position `macros/<name>.mac`, `output/<name>.root` and `logs/<name>.log`, plus `logs/run_status.txt` at the end. The name is `SpRes_<bed>_z<z>_r<r>`, for example `SpRes_rat_z37p5_r10` (Ga-68 runs: `SpResGa68_…`, runs without the field: `…NoB_…`). With `--tag PATH` the three folders go under `PATH/`; use one tag per configuration or repetition. Positions that are already complete are skipped, `--overwrite` runs them again. The runner refuses to mix results made with different macro settings in one folder.

**Run time.** With the 9.4 T field and 0.05 mm positron steps in the source cube, GATE simulated about 2,400 decays per second of CPU time on my workstation. One position is 8.4 million Na-22 decays, plus 9.1 million Lu-176 decays when Lu-176 is on: roughly 1-2 h per position on one core.

## Coil and cradle

All runs use the Quad86 coil. The cradle is chosen with `--bed` (or with `--setup q86` for the mouse and `--setup q86rat` for the rat cradle, the setup names of the other tests):

| `--bed` | Cradle macro | Height `cradleY` | Cradle |
|---|---|---|---|
| `mouse` (default) | `mouse_cradle3mm_cut80_sens.mac` | 7.045 mm | Derived from the rat cradle by scaling its cross-section by 0.487, side walls solid and about 3 mm thick |
| `rat` | `rat_cradle_hdpe_cut80_sens.mac` | 19.740 mm | The rat cradle taken from the μ-map of the Quad86 coil. Kuntner et al. 2025 used it with the Quad86 coil, and so did the paper. |

Both cradles are HDPE (0.95 g/cm³). The runner swaps the cradle macro and sets `cradleY`, the height at which the 10 mm cube centred on the axis rests on the cradle floor (0.01 mm gap).

As in the measurement, the cradle moves only along z: it carries the source to z = 0 or 37.5 mm. The radial offsets move the source alone, upwards along +y, above the cradle. In the measurement the source sits on a holder, which is not modelled. At 35 mm the corners of the cube reach 40.3 mm from the axis; the coil starts at 43.0 mm.

## Runner options (`spres_run.py`)

Run `python3 spres_run.py --help` for the full list.

| Option | Default | What it does |
|---|---|---|
| `--bed mouse\|rat` | `mouse` | Cradle (see above) |
| `--setup NAME` | none | `q86` (mouse cradle) or `q86rat` (rat cradle) |
| `--radii R …` | `0 5 10 15 20 25 30 35` | Radial offsets in mm, along +y |
| `--planes …` | `centre quarter` | Axial positions: z = 0 and/or z = 37.5 mm |
| `--activity BQ` | from the macro (140000) | Activity of the point source in Bq (decays per second) |
| `--duration S` | `60` | Acquisition time per position in s |
| `--seed N` | `20261008` | Base seed; position *i* in the list gets seed + *i* |
| `--no-lu176` | off | Switch off the intrinsic Lu-176 source |
| `--isotope Na22\|Ga68` | `Na22` | Point-source nuclide |
| `--no-field` | off | Switch off the 9.4 T field |
| `--smoke` | off | One 0.5 s job at r = 10 mm, z = 0 |
| `--workers N` | `4` | Jobs at the same time (at most one per physical core) |
| `--command "…"` | GATE 8.2 Docker | Command template with `{macro}` and optionally `{project}` |
| `--tag PATH` | none | Relative folder for `macros/`, `output/` and `logs/` |
| `--overwrite` | off | Run completed positions again |
| `--dry-run` | off | Write the job macros and print the commands, run nothing |
| `--no-progress` | off | No live progress display |

## Analysis (`spres_analysis.py`)

```bash
python3 spres_analysis.py --bed rat --add-measured-bg
```

Without file names it analyses `output/SpRes_<bed>_*.root`. For every file it:

1. reads the prompt coincidences and finds the source position;
2. adds the photon acollinearity (0.5° FWHM) and Gaussian detector position errors in each block's frame: 1.6 mm FWHM in the crystal plane (González et al. 2016) and 1.6 mm FWHM in depth (Gsell et al. 2020);
3. weights each LOR by 1/(its detection efficiency), computed from the crystal geometry (normalisation);
4. rebins the LORs with SSRB, keeping LORs tilted at most 10.5° to the transverse plane, and reconstructs a small box around the source with 2D FBP (ramp filter, no smoothing, 0.5 mm voxels);
5. measures the widths with a Gaussian fit to the line profiles through the peak voxel (the method of Kuntner et al. 2025) and with the NEMA method (summed profiles);
6. compares them with Kuntner et al. 2025, Table 3 (Quad86), at the matching position.

With `--add-measured-bg` the rate of a measured blank scan without source (255.9 cps for this selection) is added uniformly to the sinograms before the reconstruction. It is meant for runs without Lu-176, and the analysis refuses runs that contain Lu-176 events.

**Outputs.** Every analysis run has its own folder. The run name comes from the file names, `spres_results_[<tag>_]<bed>[_bg]`, and run `spres_results_<name>` is written to `results_<name>/`. For example, the paper command above writes `results_rat_bg/`. `--out` sets another name. With `<base>` = `results_<name>/spres_results_<name>`:

| Output | Content |
|---|---|
| `<base>.txt` | Gaussian widths per position, next to the reference values and the differences |
| `<base>_nema.txt` | The same positions with the NEMA-method widths |
| `<base>_details.txt` | Everything per file: counts, source position, both methods |
| `<base>.xlsx` | The three tables and the settings of the run |
| `<base>_plots/` | One figure per position (views, profiles, fits, widths) and `summary_FWHM.png`, `summary_FWTM.png` |
| `<base>_plots_clean/` | The same position figures without numbers |
| `<base>_volumes/` | The reconstructed 3D image around each source as NIfTI-1 (`.nii`, float32, fraction of the peak voxel, scanner coordinates in mm), for example for 3D Slicer |

Main options (`python3 spres_analysis.py --help` lists them all):

| Option | Default | What it does |
|---|---|---|
| *files* | `output/SpRes_<bed>_*.root` | ROOT files to analyse |
| `--bed mouse\|rat` | `mouse` | Cradle of the run, used to find the files |
| `--add-measured-bg` | off | Add the measured blank-scan rate (runs without Lu-176 only) |
| `--events` | `prompts` | `prompts` (as measured), `trues` or `unscattered` (diagnostics) |
| `--plane-fwhm MM` | `1.6` | In-plane detector position error, FWHM |
| `--doi-fwhm MM` | `1.6` | Depth-of-interaction error, FWHM; `--no-doi` puts every photon at the mean depth |
| `--acolin-fwhm-deg DEG` | `0.5` | Photon acollinearity, FWHM; `0` switches it off |
| `--max-tilt-deg DEG` | `10.5` | Largest LOR tilt used; `90` = all LORs |
| `--no-norm` | off | No normalisation weights |
| `--fit core\|offset` | `core` | Pure Gaussian on the positive core of each profile, or Gaussian + constant on a wide window |
| `--out NAME` | from the file names | Run name |
| `--image-half MM`, `--volume-half MM` | `10`, `10` | Size of the image views and of the saved 3D images; the widths do not change |
| `--no-plots`, `--no-volumes`, `--no-nema-plot` | off | Leave out figures, 3D images, or the NEMA curves in the figures |
| `--compare-with RUN` | the measurement | Compare with an earlier run of this analysis (its folder or table) instead |
| `--compare-label TEXT` | `simulation <TABLE>` | Name of that reference in tables and figures |

## Ga-68 and the magnetic field (optional)

The macro also holds a Ga-68 point source (commented out, lines starting with `#GA68 `). `--isotope Ga68` switches it on in place of Na-22, and `--no-field` switches off the 9.4 T field. Ga-68 emits positrons with an end point of 1.9 MeV (Na-22: 0.55 MeV), so the positron range widens the point image. In the 9.4 T field a positron stays close to its field line across the field, so the widening is mainly axial.

Kuntner et al. 2025 measured Na-22, so the analysis compares Ga-68 runs with a Na-22 simulation and refuses Ga-68 files without `--compare-with`. When the reference is a run of the same nuclide with the other field state, the analysis also writes field comparison figures (`<base>_plots_field/`). It reads the images of the reference run from its saved 3D images, so analyse the 9.4 T run first:

```bash
python3 spres_run.py --isotope Ga68 --bed rat --no-lu176 --workers 16
python3 spres_analysis.py output/SpResGa68_rat_*.root --add-measured-bg \
    --compare-with results_rat_bg --compare-label "Na-22 simulation"
python3 spres_run.py --isotope Ga68 --bed rat --no-lu176 --no-field --workers 16
python3 spres_analysis.py output/SpResGa68NoB_rat_*.root --add-measured-bg \
    --compare-with results_ga68_rat_bg --compare-label "Ga-68, 9.4 T"
```

## Model notes

- **Detector.** 8 heads × 3 rings of monolithic trapezoidal LYSO blocks (50 × 50 mm exit face, 48 × 48 mm entrance face, 10 mm thick), with a 0.0351 mm copper RF shield in front of each block and a 1 mm nylon front pad in front of each head. The crystal entrance faces are at r = 58.5 mm (117 mm ring diameter). I fitted the ring pitch of 52 mm to the axial sensitivity profile measured by Kuntner et al. 2025; it is not taken from a drawing.
- **Source.** Na-22 ions at rest with radioactive decay, so GATE produces the beta+ and EC branches, the positron spectrum and the 1274.5 keV gamma. The 0.3 mm sphere sits in the centre of a 10 mm cube of acrylic (the material `Plastic`, C5H8O2 at 1.18 g/cm³; the database entry `PMMA` has wrong mass fractions and is not used).
- **Physics.** `empenelope` with radioactive decay, production cuts of 0.1 mm (0.01 mm in the source cube), 0.05 mm positron steps in the cube, and the 9.4 T field along the scanner axis.
- **Digitizer.** The same as in the sensitivity and NECR models, with two differences: the energy resolution is 15.2 % FWHM at 511 keV, measured on this scanner at the activity of the point source (the other models use 18 %), and the energy window is 30 % (357.7-664.3 keV), as in the measurement. Coincidence window 7 ns, policy `takeAllGoods`, deadtime 200 ns paralysable followed by 600 ns nonparalysable per crystal.
- **What the analysis adds.** GATE 8.2 gives exactly back-to-back photons and exact energy-weighted interaction positions. The acollinearity and the detector position errors are added in the analysis with published values, not fitted ones.
- **Reconstruction.** The measured radial widths stay nearly constant out to 35 mm, while the tangential and axial widths grow with the radial offset. That is the pattern of SSRB with 2D FBP; a fully 3D FBP gives nearly the same width at every radius. The rebinning and the LOR acceptance of the Bruker software are not documented. The maximum LOR tilt of 10.5° is the only adjusted setting: I adjusted it to the measured axial widths. The radial and tangential widths were not used for any adjustment.
- **Width method.** Compare the Gaussian widths with the measurement. The NEMA-method widths (summed profiles) are reported separately; off-axis they are much narrower on rebinned images.
- **Lu-176.** The intrinsic Lu-176 source (152 kBq in the crystals) is still in the macro. All results in the paper were run with it switched off (`--no-lu176`), with the measured background added in the analysis instead.
- **Coil and cradle length.** Coil and cradles end at z = ±80 mm, beyond the detectors, to save time. The full models are in `../full_coil_models/`.
- **Noise.** Each 60 s position has its own statistical noise, so compare the trends over the positions rather than single values.

## Looking at the model

`view_model.py` writes a view-only macro of one position: the job macro exactly as the runner builds it, cut after `/gate/run/initialize` (no source, digitizer or acquisition). It writes only into `vis/`. Opening it needs a GATE 8.2 installation with a display.

```bash
python3 view_model.py --bed rat --r 0 --z 0
Gate --qt vis/view_SpRes_rat_z0_r0.mac
```

The defaults are the rat cradle, r = 0 and z = 0. `--view side|front|top|oblique|uncut` chooses the first view; in the GATE window you can switch with `/control/execute vis/views/<view>.mac`. Without a display, `--driver VRML2FILE` makes GATE write the scene to `g4_00.wrl` for a VRML viewer.
