# Sensitivity (NEMA NU 4-2008 section 5)

This folder simulates the sensitivity test of NEMA NU 4-2008. A Na-22 point source, embedded in a 10 mm acrylic cube, lies on the animal cradle on the scanner axis and is stepped along the 150 mm axial FOV. For every source position the analysis builds sinograms as the Bruker software does, applies the NEMA 1 cm mask and gives the absolute sensitivity in %. The simulated axial profile is then compared, position by position, with the measured profile of Kuntner et al. 2025.

Container setup and Python requirements are in the README at the top of the repository.

## Files

| File | What it is |
|---|---|
| `Sens_main_real.mac` | The whole model in one macro: scanner, digitizer, 9.4 T field, source cube, and three coil/cradle setups (see below). |
| `coil_bed_real/` | The parts the model loads: `quad86_coil_cut80_uniform.mac`, `quad35_coil_cut80_uniform.mac`, `mouse_cradle3mm_cut80_sens.mac` (STL parts in `stl_mbed3mm/`), `rat_cradle_hdpe_cut80_sens.mac` (STL parts in `stl/` and `stl80/`) and `Coil3Bed.db` with their two materials. |
| `Material/GateMaterials.db` | The GATE material database. |
| `sens_run.py` | Writes one job macro per source position and runs the jobs in parallel. |
| `sens_analysis.py` | NEMA analysis of the ROOT files (section 5.4) and the comparison with the measured profile. |
| `sens_seed_stats.py` | Mean, SD and SEM of repeated runs that differ only in the random seed. |
| `view_model.py` | Writes a view-only GATE macro of the geometry. |
| `2021-2022_NEMA_Sensitivity_Masar.xlsx` | The measured axial profiles, sheets `Quad86` and `Quad35`. |
| `SensPostionsQuad86.xlsx` | The 83 measured Quad86 positions (−73.75 … +75 mm), the same as column G of the Quad86 sheet. |
| `SensPostionsQuad35.xlsx` | The 78 distinct measured Quad35 positions (−57 … +74.8 mm). Two positions (1.5 and 2.0 mm) were measured twice and are listed once. |

Keep `Material/` and `coil_bed_real/` next to the macro. With Docker or Apptainer, GATE only sees this folder.

## Setups

`Sens_main_real.mac` holds three coil/cradle setups. Each is a block between `#@setup NAME` and `#@end` that sets four aliases: `activity`, `coilMacro`, `bedMacro` and `cradleY`. Exactly one block is active. `sens_run.py --setup NAME` activates block NAME in every job macro it writes; the model macro itself is never changed.

| | `q86` | `q35` | `q86rat` |
|---|---|---|---|
| Coil | Quad86 coil | Quad35 coil | Quad86 coil |
| Cradle | mouse cradle | mouse cradle | rat cradle |
| Na-22 activity | 127,075 Bq | 131,126 Bq | 127,075 Bq |
| Positions file | `SensPostionsQuad86.xlsx` | `SensPostionsQuad35.xlsx` | `SensPostionsQuad86.xlsx` |
| Measured sheet (`--coil`) | `Quad86` (default) | `Quad35` | `Quad86` (default) |
| Air gap under the cube (`cradleY`) | 0.01 mm (7.045 mm) | 1.64 mm (5.411 mm) | 0.01 mm (19.740 mm) |

The activities are those of the measurements (cell D2 of each sheet). In the Quad35 coil the mouse cradle cannot touch the cube: raised that far, it would cut 0.48 mm into the inner coil wall at r 17.5 mm. So I raised it as far as it fits, which leaves 1.64 mm of air under the cube.

## How to run

Run everything from inside this folder. `NAME` stands for a new folder name (`--tag`); give every run its own tag, so outputs never mix.

1. A short test job (0.5 s at z = 0):

   ```bash
   python3 sens_run.py --setup q86 --tag NAME --smoke --no-lu176
   ```

   Then look at `NAME/logs/smoke_z0.log`: the Geant4 overlap check should say "OK!" for every volume, and the log should end with "End of macro".

2. The full profile at the measured positions, 60 s per position (the default `--duration`):

   ```bash
   python3 sens_run.py --setup q86 --tag NAME --positions-xlsx SensPostionsQuad86.xlsx --no-lu176 --workers 8
   ```

   For the other setups use `--setup q35 --positions-xlsx SensPostionsQuad35.xlsx` or `--setup q86rat --positions-xlsx SensPostionsQuad86.xlsx`. Use at most one worker per physical core.

3. The analysis:

   ```bash
   python3 sens_analysis.py --dir NAME/output --out NAME/sens_results --meas-bg-cps 415 --jobs 8
   ```

   For `q35` add `--coil Quad35`. For runs shorter than 60 s add `--mask source` (see "Analysis").

On a cluster with Apptainer, add the container command to every `sens_run.py` call:

```bash
--command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"
```

`{project}` becomes this folder and `{macro}` the job macro. `--dry-run` writes the job macros and prints the commands without running GATE.

While the jobs run, `sens_run.py` shows one line per running job (position, progress bar, ROOT file size, elapsed time and time left) and an overall line. Without a terminal (for example under `nohup`) it prints only the overall line, every 5 minutes. Inside the tag folder, every position gets `macros/Sens_z<z>.mac`, `output/Sens_z<z>.root` and `logs/Sens_z<z>.log`, and `logs/run_status.txt` lists all jobs at the end.

A job counts as finished when GATE exits with code 0, the log contains "End of macro" and the ROOT file exists. The STL parts of the cradles can give a few Geant4 "GeomNav1002 track stuck" warnings. They are only warnings: the job line then says `log mentions ['G4Exception']`, but the job still counts as OK.

If you start the same tag again, finished positions are skipped and positions whose log has no "End of macro" (an aborted job) are run again. A tag whose finished positions were made with another setup or model is refused; use a new tag, or `--overwrite` to replace them.

### Settings I used for the paper

- Quad86 coil: setup `q86`, 83 positions (`SensPostionsQuad86.xlsx`), 60 s each, `--no-lu176`. I ran this nine times with different base seeds (`--seed`), analysed each run with `--meas-bg-cps 415`, which adds the measured background of 415 cps (see "Analysis"), and summarised the nine runs with `sens_seed_stats.py`. The paper shows their mean.
- Quad35 coil: setup `q35` with `SensPostionsQuad35.xlsx` and `--no-lu176`, compared with the Quad35 sheet (`--coil Quad35`).
- All runs for the paper had the intrinsic Lu-176 source switched off (`--no-lu176`).

## Runner options (`sens_run.py`)

| Option | Default | What it does |
|---|---|---|
| `--setup NAME` | the block active in the macro (`q86`) | Coil and cradle: `q86`, `q35` or `q86rat`. Warns if `--positions-xlsx` is not the setup's own positions file. |
| `--positions-xlsx FILE` | off | Positions from the first column of FILE. Replaces `--z` and `--profile`. |
| `--z Z [Z ...]` | `0` | Axial source positions in mm (within ±75 mm). |
| `--profile STEP` | off | A regular grid from −74 to +74 mm in steps of STEP mm. |
| `--duration S` | `60` | Acquisition time per position in s. |
| `--activity BQ` | the setup's `activity` | Na-22 activity in Bq. |
| `--no-lu176` | off | Switches off the intrinsic Lu-176 source. |
| `--seed N` | `20261009` | Base seed. Each position gets base + 100 × (z + 100), the smoke job base − 1. |
| `--tag NAME` | off | Writes `macros/`, `output/` and `logs/` into `NAME/`. |
| `--workers N` | `4` | Jobs at the same time. |
| `--command TEMPLATE` | GATE 8.2 Docker image | Command per job, with `{macro}` and optionally `{project}`. A local GATE: `--command "Gate {macro}"`. |
| `--smoke` | off | One 0.5 s job at z = 0. |
| `--overwrite` | off | Reruns positions whose ROOT file already exists. |
| `--dry-run` | off | Writes the macros and prints the commands, runs nothing. |
| `--no-progress` | off | No live progress display. |
| `--main FILE` | `Sens_main_real.mac` | Another model macro to copy per position. `--setup` works only if it has `#@setup` blocks. |

## Analysis (`sens_analysis.py`)

The script reads the activity, duration, source position, QE and energy window from the job macro next to each ROOT file (`macros/<name>.mac`); `--activity`, `--duration` and `--qe` override them. For every ROOT file it:

1. puts every prompt coincidence into a sinogram with Bruker's sampling (168 radial bins of 0.478602 mm, 193 angles, 150 slices of 1 mm, single-slice rebinning);
2. keeps, in every sinogram row, the bins within 10 mm of the mask centre (the NEMA 1 cm mask);
3. divides the counts by time × activity × 0.906 (the Na-22 positron branching ratio, as NEMA and the measurement do) to get the absolute sensitivity in %;
4. compares it with the measured value at the same position (linear interpolation, exact at the measured positions): ARD = |sim − meas| / meas × 100 per position, MARD = mean ARD, and the ARD at the centre of the axial FOV.

**The mask.** `--mask nema` (the default) centres the mask on the maximum of each sinogram row, as NEMA and the Bruker software do. In short runs the row maximum often sits on a background or scatter event, so the result then reads too high. Use the default for 60 s runs, as in the measurement, and `--mask source` (mask centred on the projection of the known source position) for shorter runs.

**The background of the measurement.** The measured values were processed without background subtraction, so they contain the intrinsic Lu-176 counts of the scanner inside the mask. The analysis therefore reports two readings: A compares the simulation without any background, B compares the simulation plus a constant measured background. B is the reading to use. Give the background with `--meas-bg-cps`; I used 415 cps. Without it, the script takes the background from a linear fit of the profile (10 or more positions) or else a fallback of 1100 cps, which is too high. The simulated Lu-176 is not part of reading B: if the run had it, the Lu-176-only coincidences are removed using the GATE source labels (the Na-22 source is `sourceID` 0).

Main options:

| Option | Default | What it does |
|---|---|---|
| `files ...` | `<dir>/Sens_*.root` | ROOT files to analyse. |
| `--dir DIR` | `output` | Folder searched when no files are given. |
| `--out NAME` | `sens_results` | Base name of the output files. |
| `--coil NAME` | `Quad86` | Measured sheet: `Quad86` or `Quad35`. |
| `--meas-bg-cps CPS` | profile fit, else 1100 | Background of the measurement for reading B. |
| `--mask nema\|source` | `nema` | Centre of the 1 cm mask: row maximum or source projection. |
| `--no-mask` | off | All coincidences in the sinogram FOV instead of the mask. |
| `--bg-sub` | off | Also subtracts the simulated Lu-176 in the main value `SA_pct`. |
| `--jobs N` | `1` | Files analysed at the same time, one process each. |
| `--no-plots` | off | No figures. |
| `--meas-sign -1` | `1` | Mirrors the measured positions (their direction relative to GATE +z is not documented). |
| `--active-mm N` | off | Test option: rejects interactions closer than (48 − N)/2 mm to a block's side faces (González et al. 2016 used 46 mm). Not used for the model. |

Outputs (with `--out NAME/sens_results`):

- `sens_results.txt`: one row per position, the NEMA averages (central 70 mm, central 150 mm, all positions) and the profile fit.
- `sens_results_ARD_MARD.txt`: the point-by-point table with the centre ARD and the MARD for readings A and B.
- `sens_results_details.txt`: everything per file, including the composition of the counts in the mask (from the GATE labels). `sens_seed_stats.py` reads this file.
- `sens_results.xlsx`: sheets Results, Details, ARD_MARD, NEMA_summary, Profile_fit, Measured, Settings.
- `sens_results_ARD_MARD_all_cases.txt` and `.xlsx`: centre ARD, MARD and ARD per position for every processing step (no mask; mask; mask with Lu-176 subtracted; and with the measured background added).
- `sens_results_plots/`: one figure per position, `profile.png` (with the ARD per position), `profile_meas_vs_sim.png` (only the measurement and the simulation of reading B), `profile_all_cases.png` and, with 10 or more positions, `profile_fit.png`.

### Repeated runs (`sens_seed_stats.py`)

For runs that differ only in the seed, each analysed with `sens_analysis.py` into its own folder:

```bash
python3 sens_seed_stats.py seeds/q86_s*
```

It reads only each run's `sens_results_details.txt` and checks that all runs have the same positions, measured values and background. Per position it gives the mean, SD and SEM over the runs, next to the Poisson error of one run. It compares the averaged profile with the measurement (centre ARD, MARD) and gives the same numbers for every single run as mean ± SD. Outputs (default `<parent of the runs>/sens_seeds`, or `--out`): `sens_seeds.txt`, `sens_seeds_summary.txt`, `sens_seeds.xlsx`, `sens_seeds_profile.png` (error bars ±1 SD, or ±1 SEM with `--error sem`) and `sens_seeds_uncertainty.png`.

## Model notes

- **Detector.** 8 heads × 3 rings of monolithic LYSO blocks (48 × 48 mm entrance face, 50 × 50 mm exit face, 10 mm thick). The entrance faces are at r 58.5 mm, a ring diameter of 117 mm as in the header of Bruker's list-mode files.
- **Ring pitch 52 mm.** This leaves a 4 mm gap between the rings at the entrance faces. I chose it because it reproduces the steps of the measured profile at the ring boundaries. It is not taken from a drawing of the scanner.
- **QE 0.90.** A per-pulse acceptance in the GATE digitizer, a model parameter and not a measured value. The coincidence sensitivity scales with QE².
- **Energy resolution** 15.2 % FWHM at 511 keV. **Energy window** 255.5–766.5 keV, the 50 % window of the measurement, 7 ns coincidence window.
- **Source.** Na-22 ions at rest in a 0.3 mm sphere at the centre of a 10 mm acrylic cube (the material `Plastic` in `GateMaterials.db`, C5H8O2 at 1.18 g/cm³; the entry `PMMA` there has wrong mass fractions). GATE produces the decay, so the activity counts all decays, and the analysis divides by 0.906 like the measurement.
- **Coils.** Both coils are coaxial G10 cylinders (1.79 g/cm³) cut at z = ±80 mm. The Quad86 coil has two tubes at the radii of its 511 keV attenuation map (μ-map), uniform walls of 1.8 mm (r 43.0–44.8 mm) and 2.2 mm (r 54.69–56.89 mm). For the Quad35 coil there is no μ-map: it has three walls (r 17.5–18.94, 29.0–30.6 and 55.13–56.89 mm) and two discs, with the radii from the published image of its attenuation map (Kuntner et al. 2025, Fig. 6A). The wall thicknesses of both coils agree with my caliper measurements.
- **Cradles.** The rat cradle shape was taken from the μ-map of the Quad86 coil with the rat cradle, turned into STL surfaces and imported as tessellated volumes, material HDPE (0.95 g/cm³). Axial details shorter than 2 mm were averaged. The mouse cradle is derived from the rat cradle by scaling its cross-section by 0.487 (outer radius about 17 mm), axial dimensions unchanged, side walls solid and about 3 mm thick, same material. The script that made the mouse cradle STL files is not included.
- **The cradle moves with the source.** Every cradle part is placed at (0, `cradleY`, `sourceZ`), so the cube always sits at the centre of the cradle. The cut at ±80 mm is enough: a photon pair from the source can only reach the crystals if it crosses the cradle within 24 mm (mouse cradle) or 51 mm (rat cradle) of the source.
- **Lu-176.** The intrinsic Lu-176 source (152 kBq, calculated, not measured) is still in the macro. All results in the paper were run with it switched off.

## Looking at the model (`view_model.py`)

`view_model.py` builds the macro of one job exactly as `sens_run.py` would, cuts it after `/gate/run/initialize` (no source, digitizer or acquisition) and adds viewer commands. It writes only into `vis/`.

```bash
python3 view_model.py --setup q35 --z 0
Gate --qt vis/view_Sens_q35_z0.mac
```

`--view side|front|top|oblique|uncut` chooses the first view; in the GATE window you can switch with `/control/execute vis/views/<view>.mac`. Without a display, `--driver VRML2FILE` makes GATE write `g4_00.wrl` (the full scene, without cuts) for a VRML viewer. Opening the view needs a local GATE 8.2 installation.
