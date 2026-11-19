#!/usr/bin/env python3
"""
spres_run.py
============

Runs the NEMA NU 4-2008 spatial-resolution simulation: one GATE job per point-source position.

MODEL AND SETUP
  SpRes_main.mac loads the Quad86 coil and the cradles from coil_bed_real/.
  --bed mouse (default) or --bed rat selects the cradle. --setup q86 (mouse cradle) and
  --setup q86rat (rat cradle) do the same, with the setup names of the other tests.
  The cradle heights are 7.045 mm for the mouse and 19.740 mm for the rat cradle. A model macro
  with #@setup blocks can define more setups, each with a known cradle macro or bed=mouse /
  bed=rat on its setup line. The runner checks that every file the macro loads is there.

RUN SETTINGS AND OUTPUT
  The source moves radially along +y and axially to the chosen plane; the cradle follows the
  axial position only. The activity comes from the model macro unless --activity is given.
  The measurement used 140 kBq and 60 s per position.
  --isotope Ga68 switches on the #GA68 source block instead of Na-22. --no-field switches off
  the 9.4 T field. The ROOT file names contain the cradle, the position and a Ga68 or NoB tag.
  Each job uses --seed plus its index in the list of positions; the smoke test uses --seed minus
  one. Keep the same order of positions to get the same seeds again.

  --tag PATH puts macros/, output/ and logs/ under a relative folder such as q86_na22/1/.
  Use a separate tag for each configuration or repetition. Completed positions are skipped,
  also in a dry run; --overwrite runs them again. Incomplete positions are run again. Before it
  adds results to a folder, the runner checks that the saved macros there have the same settings.
  The GATE jobs run in parallel, with the same progress display and logs as sens_run.py.
  A job is complete when GATE exits without error, the log reaches "End of macro" and a new,
  nonempty ROOT file is written.

DEFAULT POSITIONS (Kuntner et al. 2025, Table 3, Quad86)
  radial offset 0, 5, 10, 15, 20, 25, 30, 35 mm  x  axial position 0 and 37.5 mm  = 16 jobs.

USAGE (run it in the folder that contains SpRes_main.mac, coil_bed_real/ and Material/GateMaterials.db)
  python3 spres_run.py --smoke                 # 1 short job (0.5 s) to test the setup first (mouse cradle)
  python3 spres_run.py --workers 16            # all 16 positions with the mouse cradle, 16 jobs at a time
  python3 spres_run.py --bed rat --smoke       # the same with the rat cradle
  python3 spres_run.py --bed rat --workers 16
  python3 spres_run.py --setup q86 --tag q86_na22/1 --dry-run
  python3 spres_run.py --setup q86 --tag q86_na22/1 --workers 16
  python3 spres_run.py --radii 0 10 35 --planes centre      # a subset
  python3 spres_run.py --duration 300          # longer runs = less noise in the widths
  python3 spres_run.py --no-lu176              # without the intrinsic Lu-176 source (faster)
  python3 spres_run.py --command "Gate {macro}"             # local GATE instead of Docker
  python3 spres_run.py --command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"
  python3 spres_run.py --isotope Ga68 --smoke
  python3 spres_run.py --isotope Ga68 --no-field --tag ga68_nob --workers 16

  Then:  python3 spres_analysis.py             # analyses output/SpRes_mouse_*.root
         python3 spres_analysis.py --bed rat   # analyses output/SpRes_rat_*.root
         python3 spres_analysis.py output/SpResGa68_mouse_*.root --compare-with results_mouse \
             --compare-label "Na-22 simulation"                # Ga-68 compared with Na-22

RUN TIME
  With the 9.4 T field and 0.05 mm positron steps in the source, GATE simulated about 2,400
  decays per second of CPU time on my workstation. 140 kBq x 60 s = 8.4 million Na-22 decays,
  plus 9.1 million Lu-176 decays with Lu-176 on: roughly 1-2 h per position on one core.
  Use at most one job per physical core (lscpu: "Core(s) per socket" x "Socket(s)").
"""
import argparse
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_RADII = [0, 5, 10, 15, 20, 25, 30, 35]           # mm
PLANES = {"centre": 0.0, "quarter": 37.5}                 # mm: axial centre, 1/4 of the 150 mm FOV
DOCKER = "docker run --rm -v {project}:/APP opengatecollaboration/gate:8.2-docker {macro}"
NEEDED_MATERIALS = ("Air", "LYSO", "Copper", "Nylon", "Plastic")      # coil and cradle: coil_bed_real/Coil3Bed.db
# --bed: the cradle macro executed in the CRADLE section of SpRes_main.mac and its height cradleY (mm), the height
# at which the 10 mm cube centred on the axis rests on the cradle floor (as in the sensitivity model)
BEDS = {"mouse": ("coil_bed_real/mouse_cradle3mm_cut80_sens.mac", "7.045"),
        "rat": ("coil_bed_real/rat_cradle_hdpe_cut80_sens.mac", "19.740")}
LEGACY_SETUPS = {"q86": "mouse", "q86rat": "rat"}
SETUP_LINE = re.compile(r"^#@setup[ \t]+(\S+)(.*)$")
INCLUDE_LINE = re.compile(
    r"^[ \t]*/(control/execute|gate/\S+/(?:setMaterialDatabase|setPathToSTLFile))[ \t]+(\S+)", re.M
)
LOG_START = "[spres_run.py] seed="
LOG_COMPLETE = "[spres_run.py] completed successfully"


def set_alias(text, name, value):
    """Replace the value of '/control/alias <name> ...' (exactly one active line expected)."""
    pat = re.compile(r"^(/control/alias[ \t]+" + re.escape(name) + r"[ \t]+)\S.*$", re.M)
    new, n = pat.subn(lambda m: m.group(1) + str(value), text)
    if n != 1:
        sys.exit(f"model macro: expected one active '/control/alias {name}' line, found {n}")
    return new


def alias_value(text, name):
    """Return the value of an active macro alias."""
    match = re.search(r"^/control/alias[ \t]+" + re.escape(name) + r"[ \t]+(\S+)", text, re.M)
    return match.group(1) if match else None


def setups_of(text):
    """Read setup metadata and identify the active blocks."""
    setups, current = {}, None
    for line in text.splitlines():
        match = SETUP_LINE.match(line)
        if match:
            current = match.group(1)
            meta = dict(word.split("=", 1) for word in match.group(2).split() if "=" in word)
            setups[current] = {"meta": meta, "active": False}
        elif line.startswith("#@end"):
            current = None
        elif current is not None and line.startswith("/"):
            setups[current]["active"] = True
    return setups


def activate_setup(text, name):
    """Activate the requested setup and comment out the other setup commands."""
    lines, current = [], None
    for line in text.split("\n"):
        match = SETUP_LINE.match(line)
        if match:
            current = match.group(1)
        elif line.startswith("#@end"):
            current = None
        elif current is not None:
            body = line[1:] if line.startswith("#/") else line
            if body.startswith("/"):
                line = body if current == name else "#" + body
        lines.append(line)
    return "\n".join(lines)


def resolve_execute_aliases(text, main):
    """Write active execute aliases as file paths, as in the sensitivity runner."""
    def path(match):
        name = match.group(2)
        value = alias_value(text, name)
        if value is None:
            sys.exit(f"{main}: /control/execute {{{name}}} has no active alias definition")
        return match.group(1) + value

    return re.sub(r"^([ \t]*/control/execute[ \t]+)\{(\w+)\}", path, text, flags=re.M)


def without_lu176(text):
    """Comment out every active line of the intrinsic Lu-176 source."""
    out = []
    for line in text.split("\n"):
        if "Lu176CrystalSource" in line and not line.lstrip().startswith("#"):
            line = "#" + line + "   # disabled by spres_run.py --no-lu176"
        out.append(line)
    return "\n".join(out)


def use_bed(text, bed, main):
    """Execute the cradle macro of --bed (one active cradle /control/execute line expected) and set cradleY."""
    macros = tuple(m for m, _ in BEDS.values())
    out, n = [], 0
    for line in text.split("\n"):
        if line.startswith("/control/execute") and line.split()[1:2] and line.split()[1] in macros:
            line = "/control/execute " + BEDS[bed][0]
            n += 1
        out.append(line)
    if n != 1:
        sys.exit(f"{main}: expected one active '/control/execute <cradle macro>' line "
                 f"({' or '.join(macros)}), found {n}")
    return set_alias("\n".join(out), "cradleY", BEDS[bed][1])


def select_model(text, main, setup, requested_bed):
    """Select the macro setup and determine the cradle name for the outputs."""
    setups = setups_of(text)
    if not setups:
        if setup is not None and setup not in LEGACY_SETUPS:
            sys.exit(f"{main}: --setup {setup} requires a matching #@setup block. "
                     f"This model supports --setup {' or '.join(LEGACY_SETUPS)}.")
        bed = LEGACY_SETUPS.get(setup, requested_bed or "mouse")
        if requested_bed is not None and requested_bed != bed:
            sys.exit(f"--setup {setup} uses the {bed} cradle. Choose matching --setup and --bed values.")
        return use_bed(resolve_execute_aliases(text, main), bed, main), bed, setup

    if setup is None:
        active = [name for name, block in setups.items() if block["active"]]
        if len(active) != 1:
            sys.exit(f"{main}: {len(active)} setups are active. Choose one with --setup {'|'.join(setups)}.")
        setup = active[0]
    if setup not in setups:
        sys.exit(f"{main}: choose --setup from {', '.join(setups)}")
    text = resolve_execute_aliases(activate_setup(text, setup), main)
    paths = {os.path.basename(path) for command, path in INCLUDE_LINE.findall(text)
             if command == "control/execute"}
    known_beds = [bed for bed, (path, _) in BEDS.items() if os.path.basename(path) in paths]
    bed = setups[setup]["meta"].get("bed")
    if bed is None and len(known_beds) == 1:
        bed = known_beds[0]
    if bed not in BEDS or (known_beds and known_beds != [bed]):
        sys.exit(f"{main}: setup {setup} must identify one mouse or rat cradle. "
                 "Use the matching cradle macro or specify bed=mouse or bed=rat in the setup metadata.")
    if requested_bed is not None and requested_bed != bed:
        sys.exit(f"--setup {setup} uses the {bed} cradle. Choose matching --setup and --bed values.")
    return text, bed, setup


def use_ga68(text, main):
    """Swap the Na-22 point source for the commented Ga-68 block (lines starting with '#GA68 ')."""
    out, n_off, n_on = [], 0, 0
    for line in text.split("\n"):
        if "Na22PointSource" in line and not line.lstrip().startswith("#"):
            line = "#" + line + "   # disabled by spres_run.py --isotope Ga68"
            n_off += 1
        elif line.startswith("#GA68 "):
            line = line[len("#GA68 "):]
            n_on += 1
        out.append(line)
    if n_off == 0 or n_on == 0:
        sys.exit(f"{main}: --isotope Ga68 needs active Na22PointSource lines ({n_off} found) "
                 f"and '#GA68 ' lines ({n_on} found)")
    return "\n".join(out)


def without_field(text, main):
    """Comment out the magnetic field (every active /gate/geometry/setMagField line)."""
    out, n = [], 0
    for line in text.split("\n"):
        if line.lstrip().startswith("/gate/geometry/setMagField"):
            line = "#" + line + "   # disabled by spres_run.py --no-field"
            n += 1
        out.append(line)
    if n == 0:
        sys.exit(f"{main}: --no-field found no active /gate/geometry/setMagField line")
    return "\n".join(out)


def run_tag(isotope="Na22", field=True):
    """Name tag of a run: '' (Na-22, 9.4 T), 'Ga68', 'NoB', 'Ga68NoB'."""
    return ("" if isotope == "Na22" else isotope) + ("" if field else "NoB")


def name_of(z, r, bed, isotope="Na22", field=True):
    zs = f"{z:g}".replace(".", "p")
    return f"SpRes{run_tag(isotope, field)}_{bed}_z{zs}_r{r:g}"


def expected_decays(text, activity, duration):
    """Decays (GATE events) a run is expected to simulate: the point source plus the active Lu-176
    source, times the duration. Used only for the progress display."""
    lu = 0.0
    m = re.search(r"^/gate/source/Lu176CrystalSource/setActivity\s+([\d.eE+-]+)\s*(\w+)?", text, re.M)
    if m:
        lu = float(m.group(1)) * {"kBq": 1e3, "MBq": 1e6}.get(m.group(2) or "", 1.0)
    return (activity + lu) * duration


def with_progress(text, n_expected):
    """Insert /run/printProgress before /gate/application/startDAQ: one '--> Event k starts.' line in
    the log every 0.5 % of the expected decays. Returns (text, every), every = None if no startDAQ."""
    every = max(1, int(n_expected / 200))
    new, n = re.subn(r"^(/gate/application/startDAQ)",
                     f"/run/printProgress {every}\t# spres_run.py: progress line every 0.5 % of the expected decays\n\\1",
                     text, count=1, flags=re.M)
    return (new, every) if n == 1 else (text, None)


class Progress:
    """Live progress of the running GATE jobs (as necr_run.py and sens_run.py), read from the '--> Event k starts.'
    lines that /run/printProgress writes into each log: progress = k / expected decays of that run."""
    EVENT = re.compile(rb"--> Event (\d+) starts")

    def __init__(self, jobs_total, decays_total, enabled=True):
        self.enabled = enabled
        self.tty = enabled and sys.stdout.isatty()
        self.lock = threading.Lock()
        self.running = {}                       # name -> dict(log, root, n_exp, label, start)
        self.jobs_total, self.decays_total = jobs_total, decays_total
        self.done, self.decays_done = 0, 0.0
        self.t0 = time.time()
        self.drawn = 0
        self.last_plain = time.time()
        self.stop = threading.Event()
        if enabled:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def start(self, name, log, root, n_exp, label):
        with self.lock:
            self.running[name] = {"log": log, "root": root, "n_exp": n_exp, "label": label, "start": time.time()}

    def finish(self, name, line):
        with self.lock:
            info = self.running.pop(name, None)
            if info:
                self.decays_done += info["n_exp"]
            self.done += 1
            self._clear()
            print(line, flush=True)
            if self.tty:
                self._draw()

    def close(self):
        self.stop.set()
        if self.enabled:
            self.thread.join()
        with self.lock:
            self._clear()

    @staticmethod
    def _time(sec):
        if sec is None:
            return "--:--"
        sec = int(sec)
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"

    def _events(self, log):
        try:
            with open(log, "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 8192))
                hits = self.EVENT.findall(f.read())
            return int(hits[-1]) if hits else 0
        except OSError:
            return 0

    def _lines(self):
        cols, rows = shutil.get_terminal_size((120, 40))
        width = max(10, min(40, cols - 86))
        now, lines, decays_now = time.time(), [], self.decays_done
        jobs = sorted(self.running.items(), key=lambda kv: kv[1]["start"])
        for name, info in jobs:
            k = self._events(info["log"])
            decays_now += min(k, info["n_exp"])
            frac = min(k / info["n_exp"], 0.999) if info["n_exp"] > 0 else 0.0
            el = now - info["start"]
            eta = el * (1 - frac) / frac if frac > 0.005 else None
            size = os.path.getsize(info["root"]) / 2 ** 20 if os.path.isfile(info["root"]) else 0.0
            n = int(frac * width)
            bar = "=" * n + (">" if n < width else "") + " " * max(0, width - n - 1)
            lines.append(f"{name[:22]:<22} {info['label']} [{bar}] {100 * frac:5.1f} %  ROOT {size:7.1f} MiB  "
                         f"{self._time(el)}  left {self._time(eta)}")
        room = max(1, rows - 3)
        if len(lines) > room:
            lines = lines[:room - 1] + [f"... and {len(lines) - room + 1} more running"]
        f = decays_now / self.decays_total if self.decays_total else 0.0
        el = now - self.t0
        eta = el * (1 - f) / f if f > 0.001 else None
        waiting = self.jobs_total - self.done - len(self.running)
        summary = (f"jobs: {self.done} done, {len(self.running)} running, {waiting} waiting | overall "
                   f"{100 * f:5.1f} % of the decays | elapsed {self._time(el)} | left about {self._time(eta)}")
        return lines, summary

    def _clear(self):
        if self.tty and self.drawn:
            sys.stdout.write(f"\x1b[{self.drawn}F\x1b[J")
            sys.stdout.flush()
            self.drawn = 0

    def _draw(self):
        lines, summary = self._lines()
        block = lines + [summary]
        sys.stdout.write("\n".join(block) + "\n")
        sys.stdout.flush()
        self.drawn = len(block)

    def _loop(self):
        while not self.stop.wait(1.0):
            with self.lock:
                if self.tty:
                    self._clear()
                    self._draw()
                elif time.time() - self.last_plain >= 300:
                    print(self._lines()[1], flush=True)
                    self.last_plain = time.time()


def check_materials(path):
    if not os.path.isfile(path):
        sys.exit(f"{path} not found: copy your GateMaterials.db into Material/ next to SpRes_main.mac")
    names = set(re.findall(r"^([A-Za-z0-9_\-]+)\s*:", open(path).read(), re.M))
    missing = [m for m in NEEDED_MATERIALS if m not in names]
    if missing:
        sys.exit(f"{path}: missing materials {missing}")


def check_includes(text, main):
    """Check the files referenced by the main macro and its included macros."""
    pending = [(main, text)]
    checked = {os.path.realpath(main)}
    missing = []
    while pending:
        parent, contents = pending.pop()
        for command, path in INCLUDE_LINE.findall(contents):
            if "{" in path:  # GATE resolves aliases defined at runtime.
                continue
            if not os.path.isfile(path):
                missing.append(f"{parent} -> {path}")
            elif command == "control/execute" and os.path.realpath(path) not in checked:
                checked.add(os.path.realpath(path))
                with open(path) as f:
                    pending.append((path, f.read()))
    if missing:
        sys.exit("Missing model dependencies:\n  " + "\n  ".join(dict.fromkeys(missing)))


def configuration_signature(text):
    """Compare active settings after removing per-position aliases and progress commands."""
    per_position = {"sourceX", "sourceY", "sourceZ", "seed", "output"}
    signature = []
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if not words or words[0] == "/run/printProgress":
            continue
        if words[0] == "/control/alias" and len(words) > 1 and words[1] in per_position:
            continue
        signature.append(tuple(words))
    return signature


def root_stamp(path):
    """Return an identity for a nonempty ROOT file that can detect a fresh write."""
    try:
        info = os.stat(path)
    except FileNotFoundError:
        return None
    if os.path.isfile(path) and info.st_size > 0:
        return (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return None


def job_completed(root, log):
    """True if the job is complete: a nonempty ROOT file and a log that reaches "End of macro". A log
    written by this runner (it starts with LOG_START) must also end with LOG_COMPLETE."""
    if root_stamp(root) is None or not os.path.isfile(log):
        return False
    with open(log, errors="replace") as f:
        text = f.read()
    return "End of macro" in text and (not text.startswith(LOG_START) or text.rstrip().endswith(LOG_COMPLETE))


def main():
    ap = argparse.ArgumentParser(description="Write and run one GATE job per spatial-resolution position.")
    ap.add_argument("--main", default="SpRes_main.mac", help="the complete model macro")
    ap.add_argument("--setup", metavar="NAME",
                    help="coil/cradle setup in --main. With SpRes_main.mac, q86 selects mouse and q86rat selects rat")
    ap.add_argument("--bed", choices=sorted(BEDS),
                    help="mouse or rat cradle. Default: the cradle of the selected setup, or mouse with SpRes_main.mac")
    ap.add_argument("--radii", type=float, nargs="+", default=DEFAULT_RADII, help="radial offsets, mm")
    ap.add_argument("--planes", nargs="+", choices=sorted(PLANES), default=["centre", "quarter"])
    ap.add_argument("--activity", type=float,
                    help="point-source activity in Bq. Defaults to the activity alias in --main")
    ap.add_argument("--duration", type=float, default=60.0, help="acquisition time per position, s")
    ap.add_argument("--seed", type=int, default=20261008,
                    help="base seed. Each position adds its index in the list; the smoke test subtracts one")
    ap.add_argument("--no-lu176", action="store_true", help="switch off the intrinsic Lu-176 source")
    ap.add_argument("--isotope", choices=["Na22", "Ga68"], default="Na22",
                    help="point-source nuclide (default Na22, as NEMA and Kuntner et al. 2025; Ga68 uses the "
                         "commented Ga-68 block of the macro, outputs SpResGa68_*)")
    ap.add_argument("--no-field", action="store_true",
                    help="switch off the 9.4 T magnetic field (comments out setMagField); the output "
                         "names get 'NoB', e.g. SpResGa68NoB_mouse_z0_r10")
    ap.add_argument("--smoke", action="store_true", help="one 0.5 s job at r = 10 mm, z = 0 (setup test)")
    ap.add_argument("--workers", type=int, default=4, help="jobs at the same time (<= physical cores)")
    ap.add_argument("--command", default=DOCKER,
                    help="command template with {macro} (and optionally {project}); default: GATE 8.2 Docker")
    ap.add_argument("--overwrite", action="store_true", help="rerun positions whose ROOT file already exists")
    ap.add_argument("--dry-run", action="store_true", help="write pending macros and print the commands")
    ap.add_argument("--tag", metavar="PATH",
                    help="relative output folder for macros/, output/ and logs/, such as q86_na22/1")
    ap.add_argument("--no-progress", action="store_true", help="no live progress display")
    a = ap.parse_args()

    project = os.path.abspath(".")
    if not os.path.isfile(a.main):
        sys.exit(f"{a.main} not found (run this script in the folder that contains it)")
    if a.tag is not None:
        folders = a.tag.split("/")
        if any(folder in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", folder) for folder in folders):
            sys.exit("--tag must be a relative folder path such as q86_na22/1. "
                     "Use letters, digits, '_', '.' or '-' in each folder name.")
    try:
        tokens = shlex.split(a.command)
    except ValueError as exc:
        sys.exit(f"Invalid --command quoting: {exc}")
    if (tokens.count("{macro}") != 1 or tokens[0] == "{macro}"
            or any("{macro}" in token and token != "{macro}" for token in tokens)):
        sys.exit("--command must pass {macro} once as a separate argument. Check for a stray character after it.")
    check_materials(os.path.join("Material", "GateMaterials.db"))
    with open(a.main) as f:
        template, bed, setup = select_model(f.read(), a.main, a.setup, a.bed)
    if a.no_lu176:
        template = without_lu176(template)
    if a.isotope == "Ga68":
        template = use_ga68(template, a.main)
    if a.no_field:
        template = without_field(template, a.main)
    check_includes(template, a.main)
    variant = run_tag(a.isotope, not a.no_field)
    activity = a.activity
    if activity is None:
        value = alias_value(template, "activity")
        try:
            activity = float(value)
        except (TypeError, ValueError):
            sys.exit(f"{a.main}: expected a numeric activity alias. Supply --activity in Bq.")
    if not math.isfinite(activity) or activity < 0:
        sys.exit("Activity must be a finite, nonnegative value in Bq.")
    activity = float(f"{activity:.0f}")
    duration = 0.5 if a.smoke else a.duration
    if not math.isfinite(duration) or duration <= 0:
        sys.exit("Acquisition duration must be a finite, positive number of seconds.")
    template = set_alias(set_alias(template, "activity", f"{activity:.0f}"), "duration", f"{duration:g}")
    mac_dir, out_dir, log_dir = (os.path.join(a.tag, d) if a.tag else d for d in ("macros", "output", "logs"))

    if a.smoke:
        name = "smoke" + (f"_{variant}" if variant else "") + f"_{bed}_z0_r10"
        jobs = [(0.0, 10.0, name)]
    else:
        if any(not math.isfinite(r) for r in a.radii):
            sys.exit("--radii must contain finite radial offsets in mm.")
        jobs = [(PLANES[p], r, name_of(PLANES[p], r, bed, a.isotope, not a.no_field))
                for p in a.planes for r in a.radii]
    names = {name for _, _, name in jobs}
    if len(names) != len(jobs):
        sys.exit("Two requested positions have the same output name. Check --planes and --radii.")

    # Check all completed positions in this analysis group before adding or replacing any macros.
    prefix = f"SpRes{variant}_{bed}_"
    finished = set()
    if os.path.isdir(out_dir):
        wanted = configuration_signature(template)
        for entry in sorted(os.listdir(out_dir)):
            name, ext = os.path.splitext(entry)
            if ext != ".root" or (name not in names and (a.smoke or not name.startswith(prefix))):
                continue
            root, log = os.path.join(out_dir, entry), os.path.join(log_dir, name + ".log")
            if not job_completed(root, log):
                continue
            finished.add(name)
            macro = os.path.join(mac_dir, name + ".mac")
            if os.path.isfile(macro):
                with open(macro, errors="replace") as f:
                    matches = configuration_signature(f.read()) == wanted
                if not matches and not (a.overwrite and not a.dry_run and name in names):
                    sys.exit(f"{root} was produced with different macro settings. Use a new --tag, "
                             "or include all conflicting positions in a run with --overwrite.")

    todo = []
    for i, (z, r, name) in enumerate(jobs):
        macro, root = os.path.join(mac_dir, name + ".mac"), os.path.join(out_dir, name + ".root")
        if name in finished and (not a.overwrite or a.dry_run):
            print(f"skip {name}: completed result in {root} (use --overwrite to rerun)")
            continue
        if os.path.exists(root) and name not in finished:
            print(f"rerun {name}: {root} has no completed job record")
        seed = a.seed - 1 if a.smoke else a.seed + i
        text = template
        for key, value in (("sourceX", 0), ("sourceY", f"{r:g}"), ("sourceZ", f"{z:g}"),
                           ("seed", seed), ("output", f"{out_dir}/{name}")):
            text = set_alias(text, key, value)
        n_exp = expected_decays(text, activity, duration)
        text, _ = with_progress(text, n_exp)
        cmd = [x.replace("{macro}", macro).replace("{project}", project) for x in tokens]
        todo.append((name, macro, root, cmd, z, r, n_exp, seed, text))

    if todo and not a.dry_run and shutil.which(todo[0][3][0]) is None:
        sys.exit(f"'{todo[0][3][0]}' not found on this computer. With Apptainer, pass e.g. --command "
                 "\"apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}\"")
    for directory in (mac_dir, out_dir, log_dir):
        os.makedirs(directory, exist_ok=True)
    if a.dry_run:
        for name, macro, root, cmd, z, r, n_exp, seed, text in todo:
            with open(macro, "w") as f:
                f.write(text)
            print(" ".join(shlex.quote(x) for x in cmd))
        print(f"Wrote {len(todo)} pending macros in {mac_dir}/.")
        return

    print(f"{a.main}" + (f" [setup {setup}]" if setup else "") + f": {len(todo)} of {len(jobs)} positions to run, "
          f"{a.workers} at a time, {activity:.0f} Bq, {bed} cradle, {a.isotope}"
          + (", Lu-176 OFF" if a.no_lu176 else "") + (", magnetic field OFF" if a.no_field else ", 9.4 T"))

    progress = Progress(len(todo), sum(j[6] for j in todo), enabled=bool(todo) and not a.no_progress)

    def run(job):
        name, macro, root, cmd, z, r, n_exp, seed, macro_text = job
        log = os.path.join(log_dir, name + ".log")
        previous_root = root_stamp(root)
        start = time.time()
        progress.start(name, log, root, n_exp, f"z {z:4.1f} r {r:4.1f}")
        with open(log, "w") as out:
            out.write(f"{LOG_START}{seed}\n")
            out.flush()
            try:
                with open(macro, "w") as f:
                    f.write(macro_text)
                # stdin closed: a GATE that ends up at its interactive prompt gets end-of-input instead of the terminal
                code = subprocess.run(cmd, cwd=project, stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=subprocess.STDOUT).returncode
            except OSError as exc:
                out.write(str(exc) + "\n")
                code = 127
        with open(log, errors="replace") as f:
            text = f.read()
        current_root = root_stamp(root)
        fresh_root = current_root is not None and current_root != previous_root
        ok = code == 0 and "End of macro" in text and fresh_root
        problems = [w for w in ("COMMAND NOT FOUND", "Overlap", "G4Exception") if w in text]
        if not fresh_root:
            problems.append("No new nonempty ROOT file")
        with open(log, "a") as f:
            f.write(f"\n[spres_run.py] exit code {code}\n")
            if ok:
                f.write(LOG_COMPLETE + "\n")
        return name, ok, code, (time.time() - start) / 60, problems

    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(a.workers, len(todo) or 1))) as pool:
        for fut in as_completed([pool.submit(run, j) for j in todo]):
            name, ok, code, minutes, problems = fut.result()
            results.append((name, ok, code, minutes, problems))
            root = root_stamp(os.path.join(out_dir, name + ".root"))
            size = root[1] / 2 ** 20 if root else 0.0
            progress.finish(name, f"{'OK    ' if ok else 'FAILED'} {name}: exit {code}, {minutes:.1f} min, "
                                  f"ROOT {size:.1f} MiB" + (f", log mentions {problems}" if problems else ""))
    progress.close()
    if results:
        with open(os.path.join(log_dir, "run_status.txt"), "w") as f:
            f.write("position\tok\texit_code\tminutes\tlog_warnings\n")
            for row in sorted(results):
                f.write("\t".join(str(v) for v in row) + "\n")
    failed = [r[0] for r in results if not r[1]]
    if failed:
        sys.exit(f"{len(failed)} job(s) failed: {failed}. Read {log_dir}/<name>.log")
    if a.smoke:
        print(f"Smoke test OK. Check {log_dir}/{jobs[0][2]}.log, then run without --smoke.")
    else:
        result_name = f"spres_results_{variant.lower()}_{bed}" if variant else f"spres_results_{bed}"
        result_path = os.path.join(a.tag, result_name) if a.tag else result_name
        print(f"All jobs finished. Next: python3 spres_analysis.py {out_dir}/{prefix}*.root "
              f"--bed {bed} --out {result_path}")


if __name__ == "__main__":
    main()
