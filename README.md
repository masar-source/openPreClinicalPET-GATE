# GATE model of a preclinical 9.4 T PET/MR system

This repository holds the GATE 8.2 Monte Carlo model I built of the Bruker Si 198 PET insert, which is used inside a 9.4 T preclinical MR scanner. The model includes the RF coils (Quad86 and Quad35) and the animal cradles (rat and mouse), and it simulates three NEMA NU 4-2008 tests: sensitivity, spatial resolution and count rates (NECR).

The model and its comparison with measurements are described in the paper "Monte Carlo Simulations of a Preclinical High Field 9.4T PET/MR System" (under review in EJNMMI Physics). The measurements I compare with were published by Kuntner et al. 2025 (EJNMMI Physics 12:63).

## Folders

| Folder | Contents |
|---|---|
| `sensitivity/` | NEMA NU 4-2008 section 5: a Na-22 point source stepped along the scanner axis. |
| `spatial_resolution/` | Section 3: a point source at several radial and axial positions, image reconstruction and the widths of the point images. |
| `necr/` | Section 4: count rates, scatter fraction and NECR with the mouse-size line-source phantom. |
| `full_coil_models/` | The full, uncut coil and cradle models, for viewing and checking. The test runs use simplified versions cut at z = ±80 mm, which are in each test's `coil_bed_real/` folder. |

Each test folder has its own README with the details. Every test folder is complete on its own: one macro with the whole model, one Python script that writes and runs the GATE jobs, one Python script that analyses the output, and the parts the model loads (`Material/`, `coil_bed_real/`). The NECR folder also has `necr_truth_analysis.py`, which uses the GATE labels to see where the counts of each class come from, and the sensitivity folder has `sens_seed_stats.py` for repeated runs with different seeds.

## The model in short

- Detector: 8 heads with 3 LYSO blocks each (24 blocks). The crystal entrance faces are at a radius of 58.5 mm (117 mm ring diameter).
- A 9.4 T magnetic field along the scanner axis.
- Digitizer: an energy resolution of 18 % in the count-rate model and 15.2 % in the sensitivity and spatial-resolution models, a detection acceptance of 0.90, two deadtime stages (200 ns paralysable and 600 ns nonparalysable), a 7 ns coincidence window, the takeAllGoods multiples policy and a minimum sector difference of 3, so that only the module pairs the scanner records are kept. The energy window depends on the test and is given in the test READMEs.
- RF coils: the Quad86 coil as two coaxial G10 tubes at the radii of its 511 keV attenuation map (μ-map); the Quad35 coil, for which no μ-map was available, as three coaxial G10 walls with the radii taken from the published image of its μ-map (Kuntner et al. 2025, Fig. 6A). The wall thicknesses of both coils and of the cradles agree with my caliper measurements.
- Cradles: the rat cradle shape comes from the μ-map of the Quad86 coil with the rat cradle, turned into STL surfaces and loaded as tessellated volumes (HDPE). The mouse cradle is derived from it by scaling the cross-section by 0.487.
- The intrinsic Lu-176 activity of the LYSO is in the macros, but all results in the paper were run with it switched off (`--no-lu176` in every runner).

## Requirements

**GATE 8.2.** I run it through the Docker image `opengatecollaboration/gate:8.2-docker`, which the runners use by default, so only Docker has to be installed and running. On Apple-silicon Macs, Docker Desktop runs this amd64 image through Rosetta.

On a cluster without Docker I use Apptainer with an image built from the same Docker image, for example:

```bash
apptainer build gate82.sif docker://opengatecollaboration/gate:8.2-docker
```

and give it to the runner with `--command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"`. A local GATE 8.2 installation works too: `--command "Gate {macro}"`.

**Python 3** (I used 3.10 and 3.12) with numpy, uproot, matplotlib and openpyxl:

```bash
pip install numpy uproot matplotlib openpyxl
```

## Quick start

Run everything from inside a test folder. For example, a short test job of the count-rate model with the Quad86 coil and the rat cradle:

```bash
cd necr
python3 necr_run.py --setup q86rat --no-lu176 --smoke
```

If the log looks fine, run all measured activity frames, using as many workers as you have physical cores:

```bash
python3 necr_run.py --setup q86rat --no-lu176 --workers 8
python3 necr_analysis.py --add-measured-bg
```

## How the scripts work

- The model macro, `Material/` and `coil_bed_real/` must stay next to the scripts. With Docker or Apptainer, GATE only sees the test folder.
- The runner never changes the model macro. It writes one job macro per activity or source position, runs the jobs in parallel (`--workers`) and writes the job macros, the ROOT files and the GATE logs into subfolders of the test folder. A job whose ROOT file already exists is skipped unless you give `--overwrite`.
- `--setup` chooses the coil and the cradle (see the test READMEs). `--dry-run` writes the job macros and prints the commands without running GATE.
- Every job gets its own random seed. `--seed` sets the base seed, so repeated runs with another base are statistically independent.
- `view_model.py` writes a view-only macro of a test's geometry that opens with `Gate --qt` (this needs a local GATE with a display).

## Measured data

The workbooks in `necr/` and `sensitivity/` hold the measured values the analyses compare with (the count-rate curves, the axial sensitivity profiles and the measured source positions). The reference values for spatial resolution are written in `spres_analysis.py` (Kuntner et al. 2025, Table 3).

## Not included

- Simulation output (ROOT files) and measured list-mode data, because of their size.
- The μ-map and the scripts I used to turn it into the coil and cradle geometry.

## Citation

If you use this model, please cite the paper above. I will add the full reference here once it is published.
