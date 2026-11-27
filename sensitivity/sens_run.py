#!/usr/bin/env python3
"""
sens_run.py
===========

Runs the NEMA NU 4-2008 sensitivity simulation (section 5): one GATE job per axial source position.

WHAT IT DOES
  1. Reads the model macro (--main, default Sens_main_real.mac), activates the coil/cradle setup chosen with
     --setup, and checks that the files it loads exist (extra material databases, executed macros such as
     coil_bed_real/*.mac and their STL files).
  2. Writes one copy per position into macros/, changing ONLY the RUN SETTINGS lines at the top:
       /control/alias sourceX / sourceY / sourceZ   source on the axis at axial position z
       /control/alias activity / duration           the setup's activity (or --activity), --duration
       /control/alias seed                          base seed + 100 x (z + 100 mm): one seed per position
       /control/alias output                        output/Sens_z<z>
     and the SETUP block (the chosen setup active, the others commented out, /control/execute {coilMacro} and
     {bedMacro} written out as paths). It also adds /run/printProgress before startDAQ (a line in the log
     every 0.5 % of the expected decays).
  3. Runs the macros in parallel (GATE 8.2 Docker image by default), one log per job in logs/, with a
     live progress display as in necr_run.py: one line per running job (progress bar, %, ROOT file size,
     time, estimated time left) and an overall line (jobs done/running/waiting, % of all decays, time
     left). Without a terminal (e.g. nohup) the overall line is printed every 5 minutes.
  4. Checks every job: exit code 0, "End of macro" in the log, and the ROOT file exists.

MODEL (--main) AND SETUP (--setup)
  Sens_main_real.mac holds the whole model: the real coil and cradle, cut to +-80 mm, the cradle moving
  with the source. It has three setups (--setup):
      q86     Quad86 coil + mouse cradle, 127.075 kBq (Quad86 sheet)
      q35     Quad35 coil + mouse cradle, 131.126 kBq (Quad35 sheet)
      q86rat  Quad86 coil + rat cradle,   127.075 kBq (Quad86 sheet)
  It needs the folder coil_bed_real/ next to it. --main runs another model macro instead; --setup works
  only with a macro that has '#@setup' blocks.
  Give every run its own --tag (folder), so outputs never mix. A tag whose finished positions were run with
  another coil/cradle (or another model) is refused, unless --overwrite.

POSITIONS
  Default: only the centre of the FOV (z = 0), the peak of the profile. --z gives any list;
  --positions-xlsx gives the measured positions: SensPostionsQuad86.xlsx (83 positions, -73.75 ... +75 mm)
  for q86 and q86rat, SensPostionsQuad35.xlsx (78 positions, -57 ... +74.8 mm) for q35; --profile STEP
  gives a regular grid from -74 to +74 mm.

USAGE (run it in the folder that contains the macros, coil_bed_real/ and Material/GateMaterials.db)
  python3 sens_run.py --setup q86 --tag t86 --smoke --no-lu176
                                               # 1 short job (0.5 s) to test the setup first
  python3 sens_run.py --setup q86 --tag t86 --positions-xlsx SensPostionsQuad86.xlsx --workers 64 --no-lu176
                                               # Quad86 coil + mouse cradle, into t86/
  python3 sens_run.py --setup q35 --tag t35 --positions-xlsx SensPostionsQuad35.xlsx --workers 64 --no-lu176
                                               # Quad35 coil + mouse cradle, into t35/
  python3 sens_run.py --setup q86rat --tag t86rat --positions-xlsx SensPostionsQuad86.xlsx --workers 64 \
      --no-lu176                               # Quad86 coil + rat cradle, into t86rat/
  python3 sens_run.py --setup q35 --tag t35 --dry-run   # only write the macros and print the commands

  Without Docker, e.g. on a cluster with Apptainer, add to every call:
      --command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"

  Then:  python3 sens_analysis.py --jobs 64 --dir t86/output --out t86/sens_results --meas-bg-cps 415
         python3 sens_analysis.py --jobs 64 --dir t35/output --out t35/sens_results --coil Quad35 --meas-bg-cps 415
  (add --mask source for runs shorter than 60 s, see sens_analysis.py)

RUN TIME
  In my spatial resolution runs, one 60 s position at about 140 kBq took 2.3-2.9 h on one core. Expect
  about the same here; the wider energy window keeps more singles, which may add a little. Use at most
  one job per physical core.
"""
import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DOCKER = "docker run --rm -v {project}:/APP opengatecollaboration/gate:8.2-docker {macro}"
NEEDED_MATERIALS = ("Air", "LYSO", "Copper", "Nylon", "Glass", "Plastic", "Polyethylene")
AXIAL_LIMIT = 74.0      # mm, last profile position (the axial FOV ends at +-75 mm)


SETUP_LINE = re.compile(r"^#@setup[ \t]+(\S+)(.*)$")


def set_alias(text, name, value):
    """Replace the value of '/control/alias <name> ...' (exactly one active line expected)."""
    pat = re.compile(r"^(/control/alias[ \t]+" + re.escape(name) + r"[ \t]+)\S.*$", re.M)
    new, n = pat.subn(lambda m: m.group(1) + str(value), text)
    if n != 1:
        sys.exit(f"model macro: expected one active '/control/alias {name}' line, found {n}")
    return new


def alias_value(text, name):
    """Value of the active '/control/alias <name> ...' line, or None."""
    m = re.search(r"^/control/alias[ \t]+" + re.escape(name) + r"[ \t]+(\S+)", text, re.M)
    return m.group(1) if m else None


def setups_of(text):
    """The coil/bed setups of a macro: the blocks between '#@setup NAME key=value ...' and '#@end'.
    Returns {name: {"meta": {key: value}, "active": True if the block has an active command line}}."""
    out, cur = {}, None
    for line in text.split("\n"):
        m = SETUP_LINE.match(line)
        if m:
            cur = m.group(1)
            out[cur] = {"meta": dict(kv.split("=", 1) for kv in m.group(2).split() if "=" in kv), "active": False}
        elif line.startswith("#@end"):
            cur = None
        elif cur is not None and line.startswith("/"):
            out[cur]["active"] = True
    return out


def activate_setup(text, name):
    """The macro with the command lines of setup NAME active and those of every other setup commented out."""
    out, cur = [], None
    for line in text.split("\n"):
        m = SETUP_LINE.match(line)
        if m:
            cur = m.group(1)
        elif line.startswith("#@end"):
            cur = None
        elif cur is not None:
            body = line[1:] if line.startswith("#/") else line
            if body.startswith("/"):
                line = body if cur == name else "#" + body
        out.append(line)
    return "\n".join(out)


def resolve_execute_aliases(text, main):
    """Write '/control/execute {alias}' out as the path of the active alias (e.g. {coilMacro}), so the job
    macros name their coil and cradle directly and check_includes can check the files."""
    def path(m):
        value = alias_value(text, m.group(2))
        if value is None:
            sys.exit(f"{main}: /control/execute {{{m.group(2)}}}, but no active '/control/alias {m.group(2)}' line")
        return m.group(1) + value
    return re.sub(r"^([ \t]*/control/execute[ \t]+)\{(\w+)\}", path, text, flags=re.M)


def setup_signature(text):
    """What coil and cradle a macro uses: (active setup, coil macro, bed macro, cradleY, executed macros).
    For a macro without setups the setup is None."""
    active = [n for n, v in setups_of(text).items() if v["active"]]
    coil = alias_value(text, "coilMacro")
    bed = alias_value(text, "bedMacro")
    m = re.findall(r"^[ \t]*/control/execute[ \t]+(\S+)", text, re.M)
    return (active[0] if len(active) == 1 else None, coil or "", bed or "", alias_value(text, "cradleY"),
            tuple(sorted(m)))


def check_includes(text, main):
    """Files the model loads besides Material/GateMaterials.db: extra material databases, executed macros
    (e.g. coil_bed_real/*.mac) and the STL files those macros read. A missing one stops here, not in every job."""
    missing = []
    for path in re.findall(r"^[ \t]*/(?:gate/geometry/setMaterialDatabase|control/execute)[ \t]+(\S+)", text, re.M):
        if "{" in path:                                 # path built from an alias: not checked
            continue
        if not os.path.isfile(path):
            missing.append(path)
        elif path.endswith(".mac"):
            missing += [p for p in re.findall(r"^[ \t]*/gate/\S+/geometry/setPathToSTLFile[ \t]+(\S+)",
                                              open(path).read(), re.M) if not os.path.isfile(p)]
    if missing:
        sys.exit(f"{main} loads files that are missing here (copy coil_bed_real/ next to it?): {missing}")


def expected_decays(text, activity, duration):
    """Decays (GATE events) a run is expected to simulate: the Na-22 source plus the active Lu-176
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
                     f"/run/printProgress {every}\t# sens_run.py: progress line every 0.5 % of the expected decays\n\\1",
                     text, count=1, flags=re.M)
    return (new, every) if n == 1 else (text, None)


class Progress:
    """Live progress of the running GATE jobs (as necr_run.py), read from the '--> Event k starts.'
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


def without_lu176(text):
    """Comment out every active line of the intrinsic Lu-176 source."""
    out = []
    for line in text.split("\n"):
        if "Lu176CrystalSource" in line and not line.lstrip().startswith("#"):
            line = "#" + line + "   # disabled by sens_run.py --no-lu176"
        out.append(line)
    return "\n".join(out)


def name_of(z):
    zs = f"{z:g}".replace("-", "m").replace(".", "p")
    return f"Sens_z{zs}"


def profile_positions(step):
    """0, +-step, +-2 step, ... up to +-74 mm, sorted."""
    n = int(AXIAL_LIMIT // step)
    zs = [k * step for k in range(-n, n + 1)]
    return sorted(set(round(z, 3) for z in zs))


def positions_from_xlsx(path):
    """Axial positions (mm) from the first column of the first sheet; text cells are skipped."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit("--positions-xlsx needs openpyxl (pip install openpyxl)")
    if not os.path.isfile(path):
        sys.exit(f"{path} not found")
    ws = load_workbook(path, data_only=True).worksheets[0]
    zs = [round(float(r[0]), 3) for r in ws.iter_rows(values_only=True)
          if r and isinstance(r[0], (int, float))]
    if not zs:
        sys.exit(f"{path}: no numeric positions in the first column")
    return zs


def check_materials(path):
    if not os.path.isfile(path):
        sys.exit(f"{path} not found: copy GateMaterials.db into Material/ next to the model macro")
    names = set(re.findall(r"^([A-Za-z0-9_\-]+)\s*:", open(path).read(), re.M))
    missing = [m for m in NEEDED_MATERIALS if m not in names]
    if missing:
        sys.exit(f"{path}: missing materials {missing}")


def main():
    ap = argparse.ArgumentParser(description="Write and run one GATE job per sensitivity position.")
    ap.add_argument("--main", default="Sens_main_real.mac", help="the complete model macro (default: "
                    "Sens_main_real.mac)")
    ap.add_argument("--setup", default=None, metavar="NAME",
                    help="coil/bed setup in --main: q86 (Quad86 coil + mouse cradle), q35 (Quad35 coil + mouse "
                         "cradle) or q86rat (Quad86 coil + rat cradle); default: the setup active in the macro")
    ap.add_argument("--z", type=float, nargs="+", default=[0.0], help="axial source positions, mm (default 0)")
    ap.add_argument("--positions-xlsx", default=None, metavar="FILE",
                    help="measured positions from the first column of FILE, e.g. SensPostionsQuad86.xlsx "
                         "(replaces --z and --profile)")
    ap.add_argument("--profile", type=float, default=None, metavar="STEP",
                    help="whole axial profile from -74 to +74 mm in steps of STEP mm (replaces --z)")
    ap.add_argument("--activity", type=float, default=None,
                    help="Na-22 activity, Bq (default: the activity alias of --main, e.g. 127075 Quad86, 131126 Quad35)")
    ap.add_argument("--duration", type=float, default=60.0, help="acquisition time per position, s")
    ap.add_argument("--seed", type=int, default=20261009,
                    help="base random seed; each position gets base + 100 x (z + 100), so separate calls "
                         "never reuse a seed for another position")
    ap.add_argument("--no-lu176", action="store_true", help="switch off the intrinsic Lu-176 source")
    ap.add_argument("--smoke", action="store_true", help="one 0.5 s job at z = 0 (setup test)")
    ap.add_argument("--workers", type=int, default=4, help="jobs at the same time (<= physical cores)")
    ap.add_argument("--command", default=DOCKER,
                    help="command template with {macro} (and optionally {project}); default: GATE 8.2 Docker")
    ap.add_argument("--overwrite", action="store_true", help="rerun positions whose ROOT file already exists")
    ap.add_argument("--dry-run", action="store_true", help="write the macros, print the commands, run nothing")
    ap.add_argument("--tag", default=None, metavar="NAME",
                    help="write macros/, output/ and logs/ into the folder NAME/ (one folder per run, e.g. q86, "
                         "q35); analyse with sens_analysis.py --dir NAME/output --out NAME/sens_results")
    ap.add_argument("--no-progress", action="store_true", help="no live progress display")
    a = ap.parse_args()

    project = os.path.abspath(".")
    if not os.path.isfile(a.main):
        sys.exit(f"{a.main} not found (run this script in the folder that contains it)")
    if a.tag and not re.fullmatch(r"[A-Za-z0-9_.-]+", a.tag):
        sys.exit("--tag: use letters, digits, '_', '.' or '-' only")
    # GATE must get exactly the macro path: with a stray character after {macro} (e.g. a '~' typed after the
    # closing quote) it gets a file that does not exist and waits at its interactive 'PreInit>' prompt
    tokens = shlex.split(a.command)
    glued = [t for t in tokens if re.search(r"\{macro\}\S", t)]
    if not any("{macro}" in t for t in tokens) or glued:
        sys.exit(f"--command must pass {{macro}} as a separate word; got {tokens}. Check for a stray character "
                 "after {macro} or the closing quote.")
    check_materials(os.path.join("Material", "GateMaterials.db"))
    template = open(a.main).read()
    setups = setups_of(template)
    setup = None
    if setups:
        active = [n for n, v in setups.items() if v["active"]]
        setup = a.setup or (active[0] if len(active) == 1 else None)
        if setup is None:
            sys.exit(f"{a.main}: {len(active)} setups are active in the file; choose one with --setup {'|'.join(setups)}")
        if setup not in setups:
            sys.exit(f"--setup {setup}: {a.main} has the setups {', '.join(setups)}")
        template = resolve_execute_aliases(activate_setup(template, setup), a.main)
        want_pos = setups[setup]["meta"].get("positions")
        if a.positions_xlsx and want_pos and os.path.basename(a.positions_xlsx) != want_pos:
            print(f"WARNING: setup {setup} was measured at the positions of {want_pos}, not {a.positions_xlsx}")
    elif a.setup:
        sys.exit(f"{a.main} has no setups ('#@setup' blocks); --setup works with Sens_main_real.mac")
    check_includes(template, a.main)
    if a.no_lu176:
        template = without_lu176(template)
    activity = a.activity
    if activity is None:
        value = alias_value(template, "activity")
        if value is None:
            sys.exit(f"{a.main}: no '/control/alias activity' line; give --activity")
        activity = float(value)
    mac_dir, out_dir, log_dir = (os.path.join(a.tag, d) if a.tag else d for d in ("macros", "output", "logs"))

    if a.smoke:
        jobs = [(0.0, "smoke_z0", 0.5)]
    else:
        if a.positions_xlsx:
            zs = positions_from_xlsx(a.positions_xlsx)
        elif a.profile:
            zs = profile_positions(a.profile)
        else:
            zs = a.z
        if len(set(zs)) != len(zs):
            sys.exit("the same position is listed twice")
        bad = [z for z in zs if abs(z) > 75.0]
        if bad:
            sys.exit(f"positions outside the axial FOV (+-75 mm): {bad}")
        jobs = [(z, name_of(z), a.duration) for z in zs]
    # a tag holds one model: refuse to add positions to (or skip into) runs made with another coil/cradle
    want = setup_signature(template)
    clash = [name for z, name, duration in jobs
             if os.path.isfile(os.path.join(mac_dir, name + ".mac"))
             and os.path.isfile(os.path.join(out_dir, name + ".root"))
             and setup_signature(open(os.path.join(mac_dir, name + ".mac"), errors="replace").read()) != want]
    if clash and not a.overwrite:
        sys.exit(f"{mac_dir}/ holds finished runs made with another coil/bed or model ({len(clash)} positions, "
                 f"e.g. {clash[0]}). Use a new --tag, or --overwrite to replace them.")
    for d in (mac_dir, out_dir, log_dir):
        os.makedirs(d, exist_ok=True)

    todo = []
    for z, name, duration in jobs:
        text = template
        # the smoke job gets its own seed, so a later production run at z = 0 does not repeat its events
        seed = a.seed - 1 if a.smoke else a.seed + int(round(100 * (z + 100.0)))
        for key, value in (("sourceX", 0), ("sourceY", 0), ("sourceZ", f"{z:g}"),
                           ("activity", f"{activity:.0f}"), ("duration", f"{duration:g}"),
                           ("seed", seed), ("output", f"{out_dir}/{name}")):
            text = set_alias(text, key, value)
        n_exp = expected_decays(text, activity, duration)
        text, _ = with_progress(text, n_exp)
        macro = os.path.join(mac_dir, name + ".mac")
        root = os.path.join(out_dir, name + ".root")
        if os.path.exists(root) and not a.overwrite and not a.dry_run:
            # A finished position is skipped, and its macro (the record sens_analysis.py reads) is left as it
            # was. A ROOT file whose log has no "End of macro" is from an aborted job: run that position again.
            log = os.path.join(log_dir, name + ".log")
            if os.path.isfile(log) and "End of macro" in open(log, errors="replace").read():
                print(f"skip {name}: {root} exists (use --overwrite to rerun)")
                continue
            print(f"rerun {name}: {root} exists, but its log does not end the run (aborted job)")
        with open(macro, "w") as f:
            f.write(text)
        cmd = [x.replace("{macro}", macro).replace("{project}", project) for x in shlex.split(a.command)]
        todo.append((name, macro, root, cmd, z, n_exp))

    print(f"{a.main}" + (f" [setup {setup}]" if setup else "") + f": {len(jobs)} macros in {mac_dir}/, "
          f"{len(todo)} to run, {a.workers} at a time, "
          f"{activity:.0f} Bq" + (", Lu-176 OFF" if a.no_lu176 else ""))
    if a.dry_run:
        for name, macro, root, cmd, z, n_exp in todo:
            print(" ".join(shlex.quote(x) for x in cmd))
        return

    if todo and shutil.which(todo[0][3][0]) is None:
        sys.exit(f"'{todo[0][3][0]}' not found on this computer. Without Docker, pass e.g. --command "
                 "\"apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}\"")

    progress = Progress(len(todo), sum(j[5] for j in todo), enabled=not a.no_progress)

    def run(job):
        name, macro, root, cmd, z, n_exp = job
        log = os.path.join(log_dir, name + ".log")
        start = time.time()
        progress.start(name, log, root, n_exp, f"z {z:+7.2f} mm")
        with open(log, "w") as out:
            try:
                # stdin closed: a GATE that ends up at its interactive prompt gets end-of-input instead of the terminal
                code = subprocess.run(cmd, cwd=project, stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=subprocess.STDOUT).returncode
            except OSError as exc:
                out.write(str(exc) + "\n")
                code = 127
        text = open(log, errors="replace").read()
        ok = code == 0 and "End of macro" in text and os.path.isfile(root) and os.path.getsize(root) > 0
        problems = [w for w in ("COMMAND NOT FOUND", "Overlap", "G4Exception") if w in text]
        return name, ok, code, (time.time() - start) / 60, problems

    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(a.workers, len(todo) or 1))) as pool:
        for fut in as_completed([pool.submit(run, j) for j in todo]):
            name, ok, code, minutes, problems = fut.result()
            results.append((name, ok, code, minutes, problems))
            size = os.path.getsize(os.path.join(out_dir, name + ".root")) / 2 ** 20 \
                if os.path.isfile(os.path.join(out_dir, name + ".root")) else 0.0
            progress.finish(name, f"{'OK    ' if ok else 'FAILED'} {name}: exit {code}, {minutes:.1f} min, "
                                  f"ROOT {size:.1f} MiB" + (f", log mentions {problems}" if problems else ""))
    progress.close()
    with open(os.path.join(log_dir, "run_status.txt"), "w") as f:
        f.write("position\tok\texit_code\tminutes\tlog_warnings\n")
        for row in sorted(results):
            f.write("\t".join(str(v) for v in row) + "\n")
    failed = [r[0] for r in results if not r[1]]
    if failed:
        sys.exit(f"{len(failed)} job(s) failed: {failed}. Read {log_dir}/<name>.log")
    sheet = setups[setup]["meta"].get("sheet") if setup else None
    after = ("python3 sens_analysis.py --mask source --jobs 64" + (f" --dir {out_dir} --out {a.tag}/sens_results" if a.tag else "")
             + (f" --coil {sheet}" if sheet and sheet != "Quad86" else "") + " --meas-bg-cps 415")
    print(f"All jobs finished. Next: {after}" if not a.smoke else
          f"Smoke test OK. Check {log_dir}/smoke_z0.log (overlap check: 'OK!' for every volume), then run without --smoke.")


if __name__ == "__main__":
    main()
