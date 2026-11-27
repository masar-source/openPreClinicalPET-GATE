#!/usr/bin/env python3
"""Write GATE 8.2 viewer macros for the full (uncut) coil and cradle models.

I use this script to look at the full models in full_coil_models/, alone or
inside the PET detector. --show coil, bed or both selects the parts. --view
sagittal, coronal or axial adds a cutaway plane at x = 0, y = 0 or z = 0
(default: uncut). With --pet, the PETscanner volume and its daughters are taken
from the --main macro and drawn as wireframe; the cut coil and cradle of that
macro are left out. The macro is written to vis/ and holds only geometry, one
initialisation and viewer commands (no source, no acquisition). Open it with
Gate --qt; this needs a local GATE with a display. Run the script from one of
the test folders, for example from spatial_resolution/:
    python3 ../full_coil_models/view_full_model.py --setup q86rat --pet
"""

import argparse
import os
from pathlib import Path
import re


MATERIAL_DB = "/gate/geometry/setMaterialDatabase"
# Old name of the model folder (not used; --models defaults to the folder of this script).
ARCHIVE = "Coil-Bed_Real-Simulation"
MODELS = {
    "quad86_rat": ("coil3_bed_gate82", "coil3_bed/coil3_bed_all.mac"),
    "quad35": ("coil35_gate82", "quad35_coil/quad35_coil_all.mac"),
    "mouse": ("mouse_bed_gate82", "mouse_bed/mouse_bed_all.mac"),
}
VIEWS = {
    "uncut": (None, "-1 0.45 0.35", "0 1 0"),
    "sagittal": ("1 0 0", "-1 0.25 0.35", "0 1 0"),
    "coronal": ("0 -1 0", "-0.2 1 0.35", "1 0 0"),
    "axial": ("0 0 1", "-0.3 0.25 -1", "0 1 0"),
}


def split_command(line):
    fields = line.split(maxsplit=1)
    return fields[0], fields[1] if len(fields) > 1 else ""


def read_macro(path, root, aliases, stack=(), skip_cropped=False):
    """Yield the active commands of a macro, following /control/execute and filling in
    {alias} names in file paths. File paths are written relative to the current folder."""
    path = path.resolve()
    if path in stack:
        raise ValueError(f"Recursive macro include: {path}")
    with path.open(encoding="utf-8") as macro:
        for raw in macro:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            command, argument = split_command(line)
            if command == "/control/alias":
                name, value = split_command(argument)
                aliases[name] = value
            elif (command in ("/control/execute", MATERIAL_DB)
                  or command.endswith("/geometry/setPathToSTLFile")):
                target = re.sub(r"\{(\w+)\}", lambda m: aliases.get(m[1], m[0]), argument)
                if "{" in target:
                    raise ValueError(f"{path.name}: unresolved file path {target}")
                dependency = root / target.strip('"')
                if skip_cropped and "coil_bed_real" in dependency.parts:
                    continue
                if command == "/control/execute":
                    yield from read_macro(dependency, root, aliases, (*stack, path), skip_cropped)
                    continue
                relative_path = os.path.relpath(dependency)
                if any(char.isspace() for char in relative_path):
                    raise ValueError(f"Use model paths without spaces: {relative_path}")
                line = f"{command} {relative_path}"
            yield line


def select_volumes(commands, keep_root):
    """Keep the selected world daughters, their descendants and material definitions.
    attachPhantomSD and other attach commands are dropped."""
    kept = set()
    pending = set()
    result = []
    for line in commands:
        command, argument = split_command(line)
        if command in ("/control/alias", MATERIAL_DB):
            result.append(line)
            continue
        if not command.startswith("/gate/"):
            continue
        volume, _, setting = command[len("/gate/"):].partition("/")
        if setting == "daughters/name":
            if volume in kept or (volume == "world" and keep_root(argument)):
                kept.add(argument)
                pending.add(volume)
                result.append(line)
            else:
                pending.discard(volume)
        elif setting == "daughters/insert":
            if volume in pending:
                pending.remove(volume)
                result.append(line)
        elif volume in kept and not setting.startswith("attach"):
            result.append(line)
    return result, kept


def archived_geometry(models, kind, prefixes):
    directory, filename = MODELS[kind]
    root = models / directory
    commands, volumes = select_volumes(
        read_macro(root / filename, root, {}),
        lambda name: name.startswith(prefixes),
    )
    if not volumes:
        raise ValueError(f"No matching volumes found in {root / filename}")
    return commands


def assembly_commands(models, setup, show):
    if setup == "q86rat":
        # The cradle parts are daughters of bedCradle. The rest of the bed (head holder,
        # far end) and the coil parts are world daughters.
        roots = {"coil": ("coil_",), "bed": ("bedCradle", "bed_"),
                 "both": ("coil_", "bedCradle", "bed_")}
        return archived_geometry(models, "quad86_rat", roots[show])

    commands = []
    if show != "bed":
        kind = "quad35" if setup == "q35" else "quad86_rat"
        prefix = "q35_" if setup == "q35" else "coil_"
        commands.extend(archived_geometry(models, kind, (prefix,)))
    if show != "coil":
        bed = archived_geometry(models, "mouse", ("mouseCradle", "mbed_"))
        # Coil3Bed.db already defines the three materials of MouseBed.db, so MouseBed.db is skipped.
        if setup == "q86" and show == "both":
            bed = [line for line in bed if not line.startswith(MATERIAL_DB + " ")]
        commands.extend(bed)
    return commands


def before_initialise(commands, main):
    for line in commands:
        if split_command(line)[0] == "/gate/run/initialize":
            return
        yield line
    raise ValueError(f"{main}: no active /gate/run/initialize")


def scanner_commands(main):
    commands = before_initialise(read_macro(main, Path.cwd(), {}, skip_cropped=True), main)
    result, volumes = select_volumes(commands, lambda name: name == "PETscanner")
    if len(volumes) < 2:
        raise ValueError(f"{main}: expected PETscanner and its detector volumes")
    result.extend(f"/gate/{name}/vis/forceWireframe" for name in sorted(volumes))
    return result


def viewer_commands(view):
    cut, viewpoint, up = VIEWS[view]
    commands = ["/vis/open OGLSQt", "/vis/viewer/set/autoRefresh false", "/vis/drawVolume",
                "/vis/viewer/set/style surface", "/vis/viewer/set/lineSegmentsPerCircle 100",
                "/vis/viewer/clearCutawayPlanes"]
    if cut is not None:
        commands.append(f"/vis/viewer/addCutawayPlane 0 0 0 mm {cut}")
    commands.extend([f"/vis/viewer/set/upVector {up}", f"/vis/viewer/set/viewpointVector {viewpoint}",
                     "/vis/viewer/set/autoRefresh true", "/vis/viewer/flush"])
    return commands


def write_macro(args):
    scanner = scanner_commands(args.main) if args.pet else []
    base_db = [line for line in scanner if line.startswith(MATERIAL_DB + " ")]
    scanner = [line for line in scanner if not line.startswith(MATERIAL_DB + " ")]
    base_db = base_db or [f"{MATERIAL_DB} Material/GateMaterials.db"]
    world = [f"/gate/world/geometry/set{axis}Length 1000 mm" for axis in "XYZ"]
    world.extend(["/gate/world/setMaterial Air", "/gate/world/vis/setVisible 0"])
    assembly = assembly_commands(args.models, args.setup, args.show)
    geometry = base_db + world + scanner + assembly
    paths = {argument for command, argument in map(split_command, geometry)
             if command == MATERIAL_DB or command.endswith("/geometry/setPathToSTLFile")}
    missing = sorted(path for path in paths if not Path(path).is_file())
    if missing:
        raise ValueError("Missing geometry files:\n  " + "\n  ".join(missing))

    scene = "pet" if args.pet else "standalone"
    out = Path("vis") / f"full_{args.setup}_{args.show}_{scene}_{args.view}.mac"
    out.parent.mkdir(exist_ok=True)
    commands = [
        "# Full archived coil/bed geometry for visualisation.",
        "# Run Gate --qt from the project directory.",
        *geometry,
        "/gate/physics/addPhysicsList empenelope",
        "/gate/run/initialize",
        *viewer_commands(args.view),
    ]
    out.write_text("\n".join(commands) + "\n", encoding="utf-8")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", choices=("q86rat", "q86", "q35"), default="q86rat",
                        help="q86rat: Quad86 coil + rat cradle, q86: Quad86 coil + mouse cradle, "
                             "q35: Quad35 coil + mouse cradle (default: q86rat)")
    parser.add_argument("--show", choices=("coil", "bed", "both"), default="both")
    parser.add_argument("--pet", action="store_true", help="also draw the PET detector from the --main macro, as wireframe")
    parser.add_argument("--main", type=Path, default=Path("SpRes_main.mac"), help="macro with the PET detector, used with --pet (default: SpRes_main.mac in the current folder)")
    parser.add_argument("--models", type=Path, default=Path(__file__).resolve().parent, help="folder that holds coil3_bed_gate82/, coil35_gate82/ and mouse_bed_gate82/ "
                             "(default: the folder of this script)")
    parser.add_argument("--view", choices=tuple(VIEWS), default="uncut")
    args = parser.parse_args()
    try:
        out = write_macro(args)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Written {out}\nOpen with: Gate --qt {out}")


if __name__ == "__main__":
    main()
