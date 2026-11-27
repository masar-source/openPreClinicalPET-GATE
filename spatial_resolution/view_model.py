#!/usr/bin/env python3
"""
view_model.py
=============

Look at the model of this test in GATE, with all its volumes: detector, coil, cradle and source or phantom,
exactly as a run builds them.

The same file is in sensitivity/, spatial_resolution/ and necr/. It uses the runner next to it (sens_run.py,
spres_run.py or necr_run.py) to build the macro text of a run (setup, cradle, source position), cuts it after
/gate/run/initialize (so: no source, no digitizer, no output, no acquisition) and adds the viewer commands.
It writes only into vis/ and never touches macros/ or output/.

USAGE (in the test folder, where the model macro, coil_bed_real/ and Material/ are)
  1. write the view macro:    python3 view_model.py [test options] [--view VIEW] [--driver DRIVER]
  2. open it in GATE:         Gate --qt vis/view_<name>.mac

  Test options (the same names as in the runner):
    spatial resolution   --bed mouse|rat  --r MM  --z MM     (source position: radial offset, axial position)
    sensitivity          --setup q86|q35|q86rat  --z MM      (default: the setup active in Sens_main_real.mac)
    NECR                 --setup q35|q86|q86rat               (default: the setup active in NECR_main_std.mac)

  Views (--view; in the open GATE window switch with  /control/execute vis/views/<view>.mac):
    side      cut open along x = 0, seen from -x: z to the right, y up (section through the axis and the source)
    front     cut at the source plane z, seen along the axis: transverse section (ring, coil, cradle, source)
    top       cut at the height of the source, seen from above: coronal section
    oblique   the side cut seen from a little above and in front (3D impression)
    uncut     everything, oblique
  If a cut removes the wrong half (the side kept differs between Geant4 versions), change the sign of the
  normal (the last three numbers of /vis/viewer/addCutawayPlane) in vis/views/<view>.mac.

  --driver OGLSQt      (default) the Qt/OpenGL window of  Gate --qt
  --driver VRML2FILE   no window: GATE writes g4_00.wrl into the folder, to open in a VRML viewer (e.g. on a
                       cluster without a display). Cuts and views do not apply to this file.

  In the GATE window:  /vis/viewer/zoomTo 6   and   /vis/viewer/set/targetPoint 0 10 0 mm   (close-up)
                       /vis/ogl/export vis/<name>.png   (save the current view as an image)
"""
import argparse
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = {"spres_run.py": "spres", "sens_run.py": "sens", "necr_run.py": "necr"}

VIEWS = {   # (cut point, cut normal or None, viewpoint vector, up vector)
    "side": ("0 0 0 mm", "1 0 0", "-1 0 0", "0 1 0"),
    "front": ("0 0 {viewZ} mm", "0 0 1", "0 0 -1", "0 1 0"),
    "top": ("0 {viewY} 0 mm", "0 -1 0", "0 1 0", "1 0 0"),
    "oblique": ("0 0 0 mm", "1 0 0", "-1 0.3 0.4", "0 1 0"),
    "uncut": (None, None, "-1 0.3 0.4", "0 1 0"),
}


def view_commands(view):
    point, normal, vp, up = VIEWS[view]
    lines = ["/vis/viewer/set/autoRefresh false", "/vis/viewer/clearCutawayPlanes"]
    if normal:
        lines.append(f"/vis/viewer/addCutawayPlane {point} {normal}")
    lines += [f"/vis/viewer/set/upVector {up}", f"/vis/viewer/set/viewpointVector {vp}",
              "/vis/viewer/set/targetPoint 0 0 0 mm", "/vis/viewer/zoomTo 2",
              "/vis/viewer/set/autoRefresh true", "/vis/viewer/flush"]
    return lines


def which_test():
    found = [t for f, t in TESTS.items() if os.path.isfile(os.path.join(HERE, f))]
    if len(found) != 1:
        sys.exit(f"view_model.py must sit next to exactly one of {', '.join(TESTS)} (found {len(found)})")
    return found[0]


def choose_setup(R, text, main, setup):
    setups = R.setups_of(text)
    active = [n for n, v in setups.items() if v["active"]]
    setup = setup or (active[0] if len(active) == 1 else None)
    if setup not in setups:
        sys.exit(f"{main}: choose a setup with --setup {'|'.join(setups)}")
    return setup, R.resolve_execute_aliases(R.activate_setup(text, setup), main)


def build(test, a):
    """Macro text of a run, as the runner builds it, the view name and the source position (y, z) in mm."""
    sys.path.insert(0, HERE)
    if test == "spres":
        R = importlib.import_module("spres_run")
        main = a.main or "SpRes_main.mac"
        text = R.use_bed(open(main).read(), a.bed, main)
        for key, value in (("sourceX", 0), ("sourceY", f"{a.r:g}"), ("sourceZ", f"{a.z:g}")):
            text = R.set_alias(text, key, value)
        R.check_includes(text, main)
        return text, R.name_of(a.z, a.r, a.bed), a.r, a.z
    if test == "sens":
        R = importlib.import_module("sens_run")
        main = a.main or "Sens_main_real.mac"
        setup, text = choose_setup(R, open(main).read(), main, a.setup)
        for key, value in (("sourceX", 0), ("sourceY", 0), ("sourceZ", f"{a.z:g}")):
            text = R.set_alias(text, key, value)
        R.check_includes(text, main)
        return text, f"Sens_{setup}_" + R.name_of(a.z)[len("Sens_"):], 0.0, a.z
    R = importlib.import_module("necr_run")
    main = a.main or "NECR_main_std.mac"
    setup, text = choose_setup(R, open(main).read(), main, a.setup)
    R.check_includes(text, main)
    return text, f"NECR_{setup}", 0.0, 0.0


def main():
    test = which_test()
    ap = argparse.ArgumentParser(description="Write a view-only GATE macro of this test's model (vis/view_<name>.mac).")
    ap.add_argument("--main", default=None, help="model macro (default: the runner's default)")
    if test == "spres":
        ap.add_argument("--bed", choices=("mouse", "rat"), default="rat", help="cradle (default rat, as in the paper)")
        ap.add_argument("--r", type=float, default=0.0, help="radial offset of the source, mm (default 0)")
        ap.add_argument("--z", type=float, default=0.0, help="axial position of the source, mm (default 0)")
    elif test == "sens":
        ap.add_argument("--setup", default=None, help="q86 | q35 | q86rat (default: the setup active in the macro)")
        ap.add_argument("--z", type=float, default=0.0, help="axial position of the source, mm (default 0)")
    else:
        ap.add_argument("--setup", default=None, help="q35 | q86 | q86rat (default: the setup active in the macro)")
    ap.add_argument("--view", choices=tuple(VIEWS), default="side", help="first view (default side)")
    ap.add_argument("--driver", choices=("OGLSQt", "VRML2FILE"), default="OGLSQt", help="viewer (default OGLSQt)")
    a = ap.parse_args()
    if os.path.abspath(os.getcwd()) != HERE:
        sys.exit(f"run it in {HERE} (GATE reads the model files relative to that folder)")

    text, name, y, z = build(test, a)
    m = re.search(r"^/gate/run/initialize\b.*$", text, re.M)
    if not m:
        sys.exit("no active /gate/run/initialize line in the model macro")
    geometry = text[:m.end()]

    os.makedirs(os.path.join("vis", "views"), exist_ok=True)
    for view in VIEWS:
        with open(os.path.join("vis", "views", view + ".mac"), "w") as f:
            f.write(f"# view '{view}' (written by view_model.py); run in the GATE window: "
                    f"/control/execute vis/views/{view}.mac\n" + "\n".join(view_commands(view)) + "\n")
    out = os.path.join("vis", f"view_{name}.mac")
    vis = [f"/control/alias viewY {y:g}", f"/control/alias viewZ {z:g}", f"/vis/open {a.driver}",
           "/vis/drawVolume", "/vis/viewer/set/style surface", "/vis/viewer/set/hiddenMarker true",
           "/vis/viewer/set/lineSegmentsPerCircle 100",
           "# frame: everything ends at z = +-80 mm (detectors +-77.5 mm)",
           "/vis/scene/add/extent -100 100 -100 100 -100 100 mm"]
    if a.driver == "OGLSQt":
        vis += view_commands(a.view)
    with open(out, "w") as f:
        f.write("#" * 100 + "\n"
                f"# VIEW ONLY: the model of {name} exactly as the run macro builds it (written by view_model.py from\n"
                f"# {a.main or 'the default model macro'}), cut after /gate/run/initialize: no source, no digitizer, no\n"
                "# output, no acquisition.  Open:  Gate --qt " + out + "\n"
                "# Other views in the GATE window:  /control/execute vis/views/<side|front|top|oblique|uncut>.mac\n"
                + "#" * 100 + "\n\n" + geometry + "\n\n# ---- viewer\n" + "\n".join(vis) + "\n")
    print(f"written {out} (source at y = {y:g} mm, z = {z:g} mm; first view: {a.view})\n"
          f"open it with:  Gate --qt {out}\n"
          f"other views in the GATE window:  /control/execute vis/views/<{'|'.join(VIEWS)}>.mac")


if __name__ == "__main__":
    main()
