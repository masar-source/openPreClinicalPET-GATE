# Full coil and cradle models

This folder holds the full, uncut GATE 8.2 models of the RF coils and animal cradles that sit inside the PET insert: the Quad86 coil with the rat cradle, the Quad35 coil, and the mouse cradle. I use them to look at the geometry and to check it.

The test runs (sensitivity, spatial resolution, NECR) do not use these files. They use cut and simplified versions in each test's `coil_bed_real/` folder, where coils and cradles end at z = ±80 mm (beyond the detectors) to save time. The results in the paper were run with those versions. Where a full model differs from its run version, I say so below.

I made the geometry with scripts from the attenuation map (μ-map) of the Quad86 coil and from the published image of the Quad35 μ-map. These scripts are not included.

## Contents

| Path | What it is |
|---|---|
| `coil3_bed_gate82/coil3_bed/` | Quad86 coil and rat bed: 539 tessellated parts (STL), built from a 511 keV μ-map |
| `coil35_gate82/quad35_coil/` | Quad35 coil: 21 parts (GATE cylinders and cones), reconstructed from the published image of its μ-map |
| `mouse_bed_gate82/mouse_bed/` | Mouse bed: 246 tessellated parts, derived from the rat bed |
| `view_full_model.py` | Writes GATE viewer macros of these models, alone or inside the PET detector |

The three model folders have the same kind of files (`<model>` is `coil3_bed`, `quad35_coil` or `mouse_bed`):

| File | What it does |
|---|---|
| `<model>_all.mac` | Every part. For viewing. |
| `<model>_bore.mac` | The parts for acquisitions: the coil parts that reach into \|z\| ≤ 82.5 mm (the PET system volume ±5 mm) and the cradle. |
| `<model>_parts_bore.mac`, `<model>_parts_outside.mac` | The tessellated volumes (coil3_bed and mouse_bed). Executed by the two files above. |
| `Coil3Bed.db`, `Quad35Coil.db`, `MouseBed.db` | The materials, loaded as a second material database next to `GateMaterials.db`. |
| `stl/` | The STL files (coil3_bed and mouse_bed). |
| `vis_bore.mac`, `vis_all.mac` | Draw the model in a GATE window, without source or acquisition. |
| `vis_bore_file.mac`, `vis_all_file.mac` | The same without a screen: write the scene to `g4_00.wrl` (VRML). coil3_bed and mouse_bed only. |
| `check_bore.mac`, `check_all.mac` | GATE overlap check, without viewer and acquisition. |
| `vis_common.mac`, `check_common.mac` | Shared by the files above. Not run directly. |
| `check_with_mouse_bed.mac` | Quad35 only: overlap check of the Quad35 bore parts with the mouse cradle and the NECR mouse phantom. |

Every part is attached to the PhantomSD, so Compton and Rayleigh scatter in the coils and cradles is recorded.

## Viewing the models with view_full_model.py

Run the script from a test folder. For example, the Quad86 coil and rat bed inside the PET detector, from `spatial_resolution/`:

```bash
python3 ../full_coil_models/view_full_model.py --setup q86rat --pet
Gate --qt vis/full_q86rat_both_pet_uncut.mac
```

The script writes `vis/full_<setup>_<show>_<pet|standalone>_<view>.mac` and prints the `Gate --qt` command to open it. The macro holds geometry, one initialisation and viewer commands only: no source, no acquisition, no PhantomSD. Its file paths are relative to the folder the script was run in, so open it from the same folder. It opens the OGLSQt viewer, so it needs a local GATE 8.2 with a display; it does not work in the Docker image.

| Option | Effect |
|---|---|
| `--setup q86rat` | Quad86 coil and rat bed (default) |
| `--setup q86` | Quad86 coil and mouse bed |
| `--setup q35` | Quad35 coil and mouse bed |
| `--show coil`, `bed`, `both` | The parts to draw (default: both) |
| `--pet` | Also draw the PET detector (`PETscanner` and its daughters) as wireframe, read from the `--main` macro. The cut coil and cradle of that macro are left out. |
| `--main PATH` | The macro with the PET detector (default: `SpRes_main.mac` in the current folder) |
| `--view uncut`, `sagittal`, `coronal`, `axial` | Full view (default), or a cutaway plane at x = 0, y = 0 or z = 0 |
| `--models PATH` | The folder that holds the three model folders (default: the folder of the script, `full_coil_models/`) |

## Running the macros in the model folders

The `vis_*.mac` and `check_*.mac` files use paths such as `coil3_bed/coil3_bed_bore.mac` and `Material/GateMaterials.db`. GATE reads these paths from the folder it is started in. So run the macros from a GATE project folder that has `Material/GateMaterials.db` and the model folder next to it. A test folder works: copy the model folder into it and start GATE there. For example, from `spatial_resolution/`:

```bash
cp -R ../full_coil_models/coil3_bed_gate82/coil3_bed .
Gate --qt coil3_bed/vis_bore.mac
Gate coil3_bed/check_all.mac > check_all.log 2>&1
grep -i overlap check_all.log | grep -v -i "checking overlaps"
```

GATE prints one "Checking overlaps for volume ..." line per volume. No output from the last command means no overlaps. The overlap check takes minutes for the 539 tessellated volumes of the "all" set, so the vis macros leave it out. For `quad35_coil/check_with_mouse_bed.mac`, copy `mouse_bed/` next to `quad35_coil/` as well.

If your GATE has no OGLSQt viewer, change `OGLSQt` to `OGLI` on the `visDriver` line of `vis_bore.mac` or `vis_all.mac`. Drawing the "all" set of the Quad86 coil and rat bed (1.83 million facets) takes a while; start with "bore".

Without a screen, `vis_bore_file.mac` and `vis_all_file.mac` write the scene to `g4_00.wrl` in the project folder. Open it with any VRML viewer (for example view3dscene or MeshLab). With the Docker image (setup in the top-level README):

```bash
docker run --rm -v "$PWD:/APP" opengatecollaboration/gate:8.2-docker coil3_bed/vis_bore_file.mac
```

To use a model in another GATE macro, copy its folder next to the macro and execute `<model>_bore.mac` where the coil or bed is defined, for example `/control/execute coil3_bed/coil3_bed_bore.mac`. The file loads its own material database.

## Quad86 coil and rat bed (coil3_bed)

The source is a 511 keV attenuation map (μ-map) of the Quad86 coil with the rat cradle. I left out the egg that is also in the map.

- The coil axis is the scanner axis. The map is turned by 180° about z, so the bed lies below the axis (−y). The head holder points to +z, the bed's end to −z.
- I placed z = 0 of the map (the MR isocentre) at GATE z = 0, the centre of the PET FOV. This is an assumption.
- I moved the bed alone by +133.25 mm along z. This puts the phantom's spot on the cradle, the middle of a plain stretch without holes, at the FOV centre. The head holder then lies beyond z = +155 mm.
- In GATE the coil spans z = −199 to +400 mm and the bed z = −291.75 to +334.75 mm.
- Coil: two G10 tubes (z −145 to +352 mm), end flanges, a ring, screws, rods and plates at z = 97 and 119 mm. The tube walls of this full model come straight from the map; for the wall thicknesses, use the run version below.
- Inside the PET FOV (|z| < 77.5 mm) there are only the two tubes and the plain cradle (r 24.8–34.9 mm). The largest radius there is 56.28 mm, inside the PET system volume (r 56.9 mm).
- The parts are tessellated volumes, one per z-segment and material. A new segment starts where the cross-section changes. For the bed, axial details shorter than 2 mm were averaged. Neighbouring segments touch only at flat end planes, and touching materials keep a gap of at least 0.005 mm.
- The "bore" set has 53 volumes: the 52 cradle parts and one part with the two coil tubes (z −137.5 to +97 mm). The "all" set has 539 volumes and 1.83 million facets.

**Moving the cradle.** Every bed part within ±152.25 mm of the phantom's spot is a daughter of `bedCradle`, an air half-shell below the axis (r 24–37 mm, phi 180–360°, 304.5 mm long). One translation, given after the execute line, moves the whole cradle:

```
/control/execute coil3_bed/coil3_bed_bore.mac
/gate/bedCradle/placement/setTranslation 0 0 25 mm
```

- Along z: up to ±77.25 mm keeps the axial FOV (|z| ≤ 75 mm) filled with cradle. The whole bore (|z| ≤ 82.5 mm) stays filled up to ±69.75 mm.
- Sideways: about ±5.7 mm before the parent touches the coil (r 42.7 mm).
- A phantom centred on the axis must have r < 24 mm.

The head holder and the far end of the bed come closer to the axis, so they cannot be in the parent. They are world daughters in `coil3_bed_all.mac` only and do not move with the cradle. With a moved cradle, use `coil3_bed_bore.mac`.

**Materials.** The map gives only μ at 511 keV, so I inferred the materials from μ:

| μ in the map (1/cm) | Part | GATE material | Density (g/cm³) |
|---|---|---|---|
| 0.0744 | bed body | `AC_Plastic_0744` | 0.80 |
| 0.1180 | small bed inserts | `AC_Plastic_1180` | 1.27 |
| 0.3660 | metal part at the bed's end | `AC_Titanium` (titanium) | 4.51 |
| 0.1590 | coil tubes and plates | `AC_G10` (glass-fibre epoxy) | 1.79 |
| 0.1276 | coil flanges and ring | `AC_Plastic_1276` | 1.37 |
| 0.0923 | rods and small coil parts | `AC_Plastic_0923` | 0.99 |
| 0.2260 | metal parts in the coil (z 126–145 mm) | `AC_Aluminium` (aluminium) | 2.70 |
| 0.689 | coil screws | `AC_Brass` (70 % Cu, 30 % Zn) | 8.50 |

- The plastics whose composition I do not know have an acrylic composition (C₅H₈O₂) at the density that gives the map's μ. At 511 keV the composition itself has a negligible effect.
- `AC_G10` has the G10 composition used in the Geant4 examples, with the density fitted to the map.
- The brass value is the largest number the map's 16-bit format can store, so the true μ is at least 0.689.
- μ × volume of the model agrees with the map within 1.5 % for every material, except brass (0.947) and aluminium (0.960).

**Run version.** In `coil_bed_real/` of the tests, the Quad86 coil (`quad86_coil_cut80_uniform.mac`) is two G10 cylinders (1.79 g/cm³) with uniform walls of 1.8 mm (r 43.0–44.8 mm) and 2.2 mm (r 54.69–56.89 mm), which agree with my caliper measurements. The rat cradle (`rat_cradle_hdpe_cut80*.mac`) uses the cradle parts of this model, but with HDPE (0.95 g/cm³) instead of `AC_Plastic_0744`. Both end at z = ±80 mm. The run macros also move the cut cradles in y with the alias `cradleY`.

## Quad35 coil (quad35_coil)

There is no μ-map of the Quad35 coil. I built this full model from the published image of its attenuation map (Kuntner et al. 2025, Fig. 6A). The Quad86 coil, shown in the same figure and known from its μ-map, gave the length scale and the materials.

- I read radii and z positions from the image (0.76 mm pixels): radii to about ±0.4 mm, z to about ±1 mm. I assumed that the Quad35 image is registered like the Quad86 one.
- GATE primitives only (cylinders and cones), z = 0 at the PET FOV centre. The "bore" set has 6 parts, the "all" set 21.
- Parts: the inner wall (the coil itself) with a collar, the middle wall, the outer shell and two discs, all G10, and at the ends two housings (`AC_Plastic_0923`), an annular plate and rings, cones and end blocks (`AC_Plastic_1276`). The "bore" set holds the walls, the collar and the discs; the plastic parts are all outside the bore.
- The wall thicknesses of this full model are not the final ones. For the walls, use the run version below.

**Run version.** `quad35_coil_cut80_uniform.mac` in `coil_bed_real/` uses three uniform G10 walls (r 17.5–18.94, 29.0–30.6 and 55.13–56.89 mm) and two 1.2 mm discs, cut at z = ±80 mm. The radii come from the published image, and the wall thicknesses agree with my caliper measurements. The inner wall starts at r = 17.5 mm; the mouse cradle's parent ends at 17.2 mm and the cradle at 17.0 mm.

## Mouse bed (mouse_bed)

The mouse bed is the full rat bed of `coil3_bed` with its cross-section (x and y) scaled by 0.48707, so that the outer edge of the cradle is at r = 17.0 mm. z is not scaled, so slots, steps and the head holder keep their z positions. The materials are those of the full rat bed (`MouseBed.db`: `AC_Plastic_0744`, `AC_Plastic_1180`, `AC_Titanium`). The folder holds only the bed, which fits inside the Quad35 coil.

- The cradle spans r 11.8–17.0 mm, with its floor about 12 mm below the axis. It is placed like the rat bed: the phantom's spot is at the FOV centre and the head holder is outside the bore.
- The "bore" set is the cradle in its parent `mouseCradle` (air half-shell below the axis, r 11.75–17.20 mm, 304.5 mm long): 52 volumes. The "all" set has 246 volumes.
- To move the cradle, give `/gate/mouseCradle/placement/setTranslation 0 0 25 mm` (with your values) after the execute line. Along z, up to ±77.25 mm keeps the axial FOV filled with cradle. Sideways there is at most 0.3 mm before the parent reaches the coil, so in practice it moves only along z.
- The vis and check macros add a simple stand-in for the inner wall of the Quad35 coil (Glass, r 17.5–19 mm, 155 mm long). The check macros also add the NECR mouse phantom at its Quad35 position.

| Clearance to | Cradle | Parent |
|---|---|---|
| Quad35 inner wall (r 17.5 mm) | 0.50 mm | 0.30 mm |
| NECR mouse phantom (r 12.5 mm, centre 4.5 mm above the axis) | 1.71 mm | 0.09 mm |

**Run version.** The mouse cradle in `coil_bed_real/` (`mouse_cradle3mm_cut80*.mac`) starts from this scaled cradle, but its side walls are solid and about 3 mm thick, as I measured on the real cradle with a caliper, and it is made of the same HDPE as the run version of the rat cradle. It ends at z = ±80 mm.
