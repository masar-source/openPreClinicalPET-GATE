# Count rates and NECR (NEMA NU 4-2008, section 4)

This folder holds the GATE 8.2 model and the scripts for the count-rate test of NEMA NU 4-2008 (section 4) of the Bruker PET insert Si 198 inside the 9.4 T MR scanner. The mouse-like scatter phantom with its F-18 line source lies on the animal cradle inside the RF coil. While the F-18 decays, the scanner acquires frames over a wide range of activities. I simulate every measured frame at its measured activity, apply the NEMA analysis to the simulated data in the same way as the vendor software does for the measured data, and compare trues, scatter, randoms, totals, scatter fraction and NECR with the measurement (published in Kuntner et al. 2025).

## Files

| File | What it is |
|---|---|
| `NECR_main_std.mac` | The complete model, with three coil/cradle setups in one file. |
| `necr_run.py` | Writes one run macro per activity and runs the jobs in parallel. |
| `necr_analysis.py` | NEMA analysis (section 4.4) of the ROOT files and comparison with the measurement. |
| `necr_seed_stats.py` | Mean and SD of repeated runs that differ only in the random seed. |
| `necr_truth_analysis.py` | A side analysis with the GATE truth labels, with the coil "attached" and "detached". |
| `view_model.py` | Writes a view-only macro to look at the model in GATE. |
| `PET-MR NEC curves NEMA Masar.xlsx` | The measured count-rate curves: sheets `20220915 Quad35 Maus` and `20220906 Quad86 Maus`. |
| `Material/GateMaterials.db` | The GATE material database. |
| `coil_bed_real/` | The coil and cradle macros, their materials (`Coil3Bed.db`) and the cradle STL files (`stl/`, `stl80/`, `stl_mbed3mm/`). |

GATE 8.2 runs by default in the Docker image `opengatecollaboration/gate:8.2-docker`. The container setup and the Python requirements (numpy, uproot, matplotlib, openpyxl) are in the [top-level README](../README.md).

## Setups

`NECR_main_std.mac` holds three coil/cradle setups. `necr_run.py --setup` picks one.

| Setup | Coil + cradle | Phantom | Measured sheet | Default tag |
|---|---|---|---|---|
| `q35` | Quad35 + mouse cradle | at the measured position: centre at y = +4.5 mm, line source 5.5 mm below the axis | `20220915 Quad35 Maus` (145 frames, 117.74 to 0.013 MBq) | `std35v2` |
| `q86` | Quad86 + mouse cradle | centred, resting on the cradle, line source 10 mm below the axis | `20220906 Quad86 Maus` (132 frames, 58.18 to 0.013 MBq) | `std86v2` |
| `q86rat` | Quad86 + rat cradle | centred, resting on the cradle, line source 10 mm below the axis | `20220906 Quad86 Maus` (132 frames) | `std86ratv2` |

The paper uses `q35` and `q86rat`. The 5.5 mm of `q35` is the line-source distance from the axis that a fit to Bruker's Quad35 sinograms gives. The phantom position in the Quad86 measurement is not known, so I centred the phantom there.

## How to run

Run all commands in this folder.

**Smoke test.** One 0.01 s job at the highest activity, to test the installation:

```bash
python3 necr_run.py --setup q35 --no-lu176 --smoke
```

The runner checks every job (exit code, "End of macro" in the log, ROOT file). Look at the log in `logs/` once anyway, for example for overlap warnings.

**Full runs, as in the paper.** Every measured frame of the coil, 1 s each, at the measured activity of the frame, with the intrinsic Lu-176 source switched off:

```bash
python3 necr_run.py --setup q35 --no-lu176 --workers 64
python3 necr_run.py --setup q86rat --no-lu176 --workers 64
```

That is 145 frames for the Quad35 coil and 132 frames for the Quad86 coil. Set `--workers` to the number of physical cores. `--lowest-first` starts the jobs from the lowest activity instead of the highest; the seeds and the file names stay the same.

**Analysis, as in the paper,** with the measured blank-scan background added and the peaks taken as the highest frame of each curve:

```bash
python3 necr_analysis.py --jobs 64 --add-measured-bg --peak-fit max
```

It analyses every `output/NECR_*.root` and writes each run into its own folder, e.g. `results/q35/` and `results/q86rat/`. To analyse one run only, give its files: `python3 necr_analysis.py output/NECR_std35v2_*.root --jobs 64 --add-measured-bg`.

**On a cluster with Apptainer**, give the command template:

```bash
python3 necr_run.py --setup q35 --no-lu176 --workers 64 \
    --command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"
```

`{project}` is replaced by this folder and `{macro}` by the run macro. For a local GATE installation use `--command "Gate {macro}"`.

**What the runner writes.** Frame k of a run with tag `<tag>` becomes `macros/NECR_<tag>_k.mac` and `output/NECR_<tag>_k.root` (k with 3 digits, frame 1 = highest activity), with its log in `logs/`. `logs/run_status.txt` lists the result of every job. Only the RUN SETTINGS lines (activity, duration, seed, output name) and the setup block change between the run macros. The run macro of an existing ROOT file is never rewritten: it is the record of that run, and `necr_analysis.py` reads activity, duration, coil, QE, energy window and Lu-176 from it. Frames whose ROOT file exists are skipped when the runner is started again (`--overwrite` reruns them).

**Seeds and repeats.** Frame k gets the seed base + k (`--seed`, default base 20261010), so every frame has its own seed. To repeat a run with other seeds, run it in a separate folder with another `--seed`. Bases 1000 apart never give the same frame seed. The mean and SD over such repeats come from `necr_seed_stats.py` (see "Repeated runs" below).

## Runner options

| Option | What it does |
|---|---|
| `--setup q35\|q86\|q86rat` | Coil/cradle setup. Without it, the setup that is active in the macro (`q35`) is used. |
| `--no-lu176` | Switches off the intrinsic Lu-176 source (used for all results in the paper). |
| `--workers N` | Jobs at the same time (default 4). |
| `--every N`, `--frames 1 30 45`, `--mbq 29.3 1.7` | Only every N-th frame, only these frames, or free activities in MBq. |
| `--duration S` | Acquisition time per frame (default 1 s). |
| `--seed N` | Base seed (default 20261010). |
| `--tag NAME` | File names `NECR_<NAME>_<frame>`, so variants never overwrite each other. Use a new tag whenever you change a coil or cradle macro: the runner only notices changes in the main macro. |
| `--lowest-first` | Starts the jobs from the lowest activity. |
| `--smoke`, `--dry-run` | One short test job; or only write the macros and print the commands. |
| `--command TEMPLATE` | How GATE is started (default: the GATE 8.2 Docker image). |

Test variants change only the run macros, never `NECR_main_std.mac`, and every run macro starts with a comment line that names its variant. Give each variant its own `--tag`.

| Option | What it changes |
|---|---|
| `--b2b` | Back-to-back 511 keV photon pairs instead of F-18 ions in the same volume (much faster, no positron range). The source emits activity × 0.9686 pairs/s (F-18 β+ fraction); the analysis knows this. |
| `--policy NAME` | Multiples policy of both coincidence sorters (model: `takeAllGoods`). |
| `--pileup NS`, `--resolution FWHM` | Pile-up time per block (model: 100 ns); energy resolution at 511 keV (model: 0.18). |
| `--no-deadtime` | Switches off both deadtime stages. |
| `--all-pulse-open`, `--delayed-all-pulse-open` | Every single opens a coincidence window, in both sorters; or in an extra delayed sorter `delayAll` only, reported as `R_r_all` without changing the NEMA results. |
| `--save-singles`, `--singles-only` | Also write the Singles tree; or write only the Singles tree (large files, use short runs). |

## Analysis

`necr_analysis.py` applies NEMA NU 4-2008 section 4.4 to every ROOT file, set up like Bruker's `NECCalculation -mouse`, which produced the measured values:

- Every prompt coincidence becomes a sinogram point (single-slice rebinning).
- Only lines of response within 8 mm of the phantom edge are kept (|s| ≤ 20.5 mm).
- Every projection is aligned on the line source, and all projections are summed into one profile with 0.478602 mm pixels. By default the alignment uses the known source position from GATE (`--align known`); `--align max` uses the maximum pixel, as NEMA writes it.
- In a ±7 mm strip around the source, the counts above the straight line between the strip edges are trues; everything else is scatter + randoms.
- The randoms are the delayed coincidences in the same mask.
- Scatter = (S+R) − randoms − R_int, scatter fraction = S / (T + S) and NECR = T² / Total, the same bookkeeping as the measured sheet. R_int = 91 cps (the sheet's value) is subtracted when Lu-176 is in the model or the measured background is added.

For runs without Lu-176, `--add-measured-bg` adds the measured background of a blank scan (no source) to every simulated frame: Total 850.9 cps and S+R 760.3 cps in the mask (Bruker's `NECCalculation` on the blank scan), and 25 cps randoms (the measured randoms extrapolated to zero activity). The Lu-176 × F-18 cross randoms are not in this constant background.

The measured values are taken at the simulated activity (interpolated in log(activity); at a measured activity this is the measured frame itself). The comparison gives one MARD per component (trues, scatter, randoms, totals, scatter fraction, NECR) over several activity ranges, and the ARD of the NEMA values: the peak true rate and the peak NECR with the activity where they are reached (section 4.5.2), and the system scatter fraction over the frames whose measured randoms are below 1 % of the trues (section 4.5.3).

The peaks are found in the same way on the simulated and the measured curve, with one of three methods:

- `--peak-fit 3point` (default): the parabola through the highest frame and its two neighbours.
- `--peak-fit smooth`: a degree-4 polynomial in ln(activity) through the frames near the peak, with 1 sd from the fit. The outputs get `_peakfit` added to their names.
- `--peak-fit max`: the highest frame itself. The outputs get `_peakmax` added to their names.

Outputs go to `results/<setup>/`, named after the run tag, e.g. `results/q35/necr_std35v2`. Files of different setups or tags are never pooled.

| File | Content |
|---|---|
| `<out>.txt` | One row per frame: simulated and measured T, S, R, Total, NECR and SF (kcps, %). |
| `<out>_ARD_MARD.txt` | MARD per component and range, the NEMA values with their ARD, and a model check of R_int. |
| `<out>_details.txt` | Everything per frame: counts, effective time, the truth split of the NEMA trues (unscattered, coil scatter, other scatter, randoms, Lu-176) and settings. |
| `<out>.xlsx` | The same tables as Excel sheets. |
| `<out>_plots/` | One figure per component, grouped figures, and the NEMA profile of every frame by truth class. |

Other useful options: `--jobs N` (files in parallel), `--mard-range 3-40` (more MARD ranges), `--active-mm 46` (only the central 46 × 46 mm of each block face, after González et al. 2016), `--detector-blur` (adds a detector position response and photon acollinearity before the NEMA steps), `--results-dir` and `--out` (output names).

GATE 8.2 does not flush the presort buffer of the coincidence sorters at the end of a run, so the last part of each run gives no coincidences. The analysis divides by the time up to the last coincidence (`duration_eff_s` in the tables) and notes it per file; `--nominal-time` uses the nominal duration instead.

`necr_truth_analysis.py` is a side analysis. It classifies every prompt coincidence of the whole field of view by its GATE truth labels (true, scattered, random), without the NEMA procedure, once with the coil "attached" (scatter in the coil counts as scatter) and once "detached" (coincidences scattered only in the coil count as true, rebuilt from the same files). It uses the same run settings, measured sheets and MARD rules as `necr_analysis.py` and writes to `results/<setup>/necr_truth_<tag>/`.

### Repeated runs (`necr_seed_stats.py`)

For the uncertainty of the simulation I repeat the whole run with other seeds, each in its own folder (a copy of this folder with another `--seed`, for example `quad86S1` ... `quad86S8`), and analyse every folder with the same `necr_analysis.py` options. Then, from the folder that holds the run folders:

```bash
python3 necr_seed_stats.py quad86S{1..8}
```

The script reads only the result tables in `results/<setup>/` of every run. It stops if the runs have different frames or activities, were analysed with another measured sheet or background, or share a seed. It writes `necr_seeds_<setup>.txt` (mean, SD and SEM of every rate per frame), `necr_seeds_<setup>_summary.txt` and `.xlsx` (mean ± SD of every MARD value, of the NEMA peaks and of the scatter fraction; the peaks are the highest frame of each curve, as in the paper, or with `--peak table` the peaks in the runs' own tables), `necr_seeds_<setup>_curves.png` (the six count-rate panels with ±1 SD error bars; `--error sem` for ±1 SEM) and `necr_seeds_<setup>_uncertainty.png` (relative SD per frame).

## Model notes

- **Detector.** 8 heads × 3 rings of monolithic trapezoidal LYSO blocks (48 × 48 mm entrance face, 50 × 50 mm exit face, 10 mm thick). The entrance faces of opposite blocks are 117 mm apart. I fitted the ring pitch of 52 mm to the measured Quad86 sensitivity profile; it is not a measured size. A 0.0351 mm copper sheet (RF shield) and a 1 mm nylon front pad sit in front of the crystals.
- **Digitizer.** 18 % FWHM energy resolution at 511 keV and QE 0.90 per crystal, 100 ns pile-up per block, deadtime of 200 ns paralysable followed by 600 ns nonparalysable per crystal, energy window 255.55–766.5 keV and a 7 ns coincidence window as in the measured data. Both sorters use `takeAllGoods`, which gave the best match with the measured rates. The delayed sorter for the randoms has a 10 µs offset, far beyond the deadtime.
- **Quad86 coil.** A 511 keV attenuation map (μ-map) of the Quad86 coil with the rat cradle was available. The coil tubes are coaxial G10 cylinders (1.79 g/cm³) at the radii of the μ-map, with uniform walls of 1.8 mm (r 43.0–44.8 mm) and 2.2 mm (r 54.69–56.89 mm).
- **Quad35 coil.** Like the Quad86 coil, it was modelled from the vendor's μ-map, with three coaxial G10 walls (r 17.5–18.94, 29.0–30.6 and 55.13–56.89 mm) and two discs at the radii of the corresponding structures in the μ-map. The wall thicknesses of both coils agree with my caliper measurements.
- **Rat cradle.** The cradle shape was taken from the μ-map, turned into STL surfaces and imported as tessellated volumes, material HDPE 0.95 g/cm³. Axial details shorter than 2 mm were averaged.
- **Mouse cradle.** Derived from the rat cradle by scaling its cross-section by 0.487 (outer radius about 17 mm), with the axial dimensions unchanged, solid side walls about 3 mm thick, and the same material as the rat cradle.
- **Cut at ±80 mm.** Coils and cradles in the run models are cut at z = ±80 mm (beyond the detectors) to save time. The full models are in [`../full_coil_models/`](../full_coil_models/). The cradles do not move in this test.
- **Phantom and source.** The phantom is high density polyethylene of 0.96 g/cm³ (NEMA NU 4-2008 section 4.3), 25 mm in diameter and 70 mm long. The line source is F-18 ions in a 60 mm water column in the middle of an 80 mm polyethylene tube, followed by radioactive decay in GATE (positron range included, no photon acollinearity). The activity in the run macro is the measured activity of the frame.
- **Physics.** Penelope electromagnetic models, radioactive decay and the 9.4 T field along the scanner axis.
- **Lu-176.** The intrinsic Lu-176 source (152 kBq) is still in the macro. All results in the paper were run with it switched off (`--no-lu176`), and the measured blank-scan background was added in the analysis (`--add-measured-bg`).

## Looking at the model

`view_model.py` writes a view-only macro: the model of one setup exactly as the runner builds it, cut after `/gate/run/initialize` (no source, no digitizer, no output). It writes only into `vis/`.

```bash
python3 view_model.py --setup q86rat
Gate --qt vis/view_NECR_q86rat.mac
```

`--view side|front|top|oblique|uncut` chooses the first view; in the GATE window, `/control/execute vis/views/<view>.mac` switches between them. Without a display, `--driver VRML2FILE` makes GATE write a VRML file instead.
