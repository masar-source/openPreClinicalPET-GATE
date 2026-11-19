#!/usr/bin/env python3
"""
necr_run.py
===========

Runs the NEMA NU 4-2008 count-rate (NECR) simulation: one GATE job per activity.

WHAT IT DOES
  1. Reads the model macro (--main, default NECR_main_std.mac) and activates the chosen coil/cradle setup
     (SETUPS below).
  2. Writes one copy per activity into macros/, changing only the RUN SETTINGS lines at the top:
       /control/alias activity    F-18 activity of the measured frame, Bq
       /control/alias duration    acquisition time, s (default 1 s)
       /control/alias seed        base seed + frame number: a different seed for every activity
       /control/alias output      output/NECR_<tag>_<frame>  (frame 1 = highest activity)
  3. Runs the macros in parallel (GATE 8.2 Docker image by default), one log per job in logs/.
  4. Checks every job: exit code 0, "End of macro" in the log, and the ROOT file exists. The result of
     every job is listed in logs/run_status.txt.

ACTIVITIES
  Default: the measured frames of the coil of the setup, read from column A of "PET-MR NEC curves NEMA
  Masar.xlsx" (only frames with complete measured values), so the simulated and measured frames pair up
  exactly:
    Quad35   sheet "20220915 Quad35 Maus", 145 frames, 117.74 ... 0.013 MBq
    Quad86   sheet "20220906 Quad86 Maus", 132 frames, 58.18 ... 0.013 MBq
  --activities-xlsx FILE   first column of FILE in Bq instead
  --every N                every N-th frame only (frame 1 always included), e.g. a quick curve
  --frames 1 20 40         only these frame numbers
  --mbq 29.3 1.7           free activities in MBq (files output/NECR_<tag>_<A>MBq.root)

SEEDS
  Frame k gets the seed base + k (--seed, default base 20261010), so every activity has its own seed and the
  acquisitions are independent. --mbq A gets base + 10000 + A in kBq, the smoke test base - 1.
  To repeat a run with other seeds, run it in a separate folder with another --seed (the frame seeds of
  bases 1000 apart never overlap).

SETUPS (--setup)
  NECR_main_std.mac holds three coil/cradle setups in '#@setup NAME coil=.. tag=..' ... '#@end' blocks:
    q35     Quad35 coil + mouse cradle, phantom at the measured position   sheet 20220915 Quad35 Maus, tag std35v2
    q86     Quad86 coil + mouse cradle, phantom centred                     sheet 20220906 Quad86 Maus, tag std86v2
    q86rat  Quad86 coil + rat cradle,   phantom centred                     sheet 20220906 Quad86 Maus, tag std86ratv2
  --setup NAME activates that block in the written macros (the other two commented out) and writes
  '/control/execute {coilMacro}' / '{bedMacro}' out as the file paths (so necr_analysis.py finds the coil).
  Without --setup the block that is active in the file is used. The measured sheet follows 'coil=' and the
  default file names 'tag=' (--sheet and --tag still override).
  A finished run (ROOT file) under the same name made with another coil, cradle, phantom position, phantom
  material or ring is never skipped into: use another --tag (or --overwrite). A change INSIDE a coil or
  cradle macro (same file name) is not detected: give such a model a new tag.

TEST VARIANTS (only the written copies change, the model macro stays as it is)
  Every written macro starts with a comment line that names its variant.
  --no-lu176               switch off the intrinsic Lu-176 source
  --b2b                    back-to-back 511 keV gamma pairs instead of F-18 ions (much faster; no
                           positron range). Same volume as the F-18 source (sourceWater, r 1.0 mm,
                           60 mm). The alias activity stays the F-18 activity of the frame (the
                           analysis compares with that frame); the source emits pairs at
                           activity x 0.9686 (F-18 beta+ fraction, alias b2bFraction).
  --policy NAME            MultiplesPolicy of both sorters (prompt and delayed), e.g. takeWinnerOfGoods.
                           Misspelled names are refused (GATE 8.2 would silently use keepIfAllAreGoods).
  --all-pulse-open         allPulseOpenCoincGate true in both sorters (every single opens a window)
  --delayed-all-pulse-open adds a second delayed sorter 'delayAll' (a copy of 'delay' with
                           allPulseOpenCoincGate true) and its ROOT tree. It counts every delayed pair
                           (the singles-rate randoms 2 tau S_a S_b); necr_analysis.py reports it as R_r_all.
                           The prompt and 'delay' sorters stay as they are, so trues, totals, scatter and
                           randoms of the NEMA analysis do not change.
  --pileup NS              pile-up time per block in ns (setPileup; model: 100 ns)
  --resolution FWHM        energy resolution at 511 keV as a fraction, e.g. 0.155 (crystalblurring
                           Min and Max; model: 0.18)
  --save-singles           also write the Singles tree (setRootSinglesFlag 1); large files at high
                           activity, use short durations
  --singles-only           write ONLY the Singles tree: Coincidences and delay are not written (the
                           sorters still run, the singles are the same). Not for necr_analysis.py. The
                           singles rate is about 10x the prompts + delayed rate (15 Mcps at 117.7 MBq),
                           so the files are larger than the usual ones: use short durations (0.2 s).
  --no-deadtime            switch off both deadtime stages (200 ns paralysable, 600 ns nonparalysable).
                           With the same seed, a run with and one without deadtime see the same events,
                           so their ratio is the live fraction of the model.
  --coil 86                only for a model macro without setup blocks that has the coil layer rfCoil1:
                           moves that layer to the Quad86 radius (43.0-44.5 mm) and takes the Quad86
                           sheet. Refused with NECR_main_std.mac: use --setup there.
  --tag NAME               file names NECR_<NAME>_<frame> so variants do not overwrite each other;
                           analyse them separately: necr_analysis.py output/NECR_<NAME>_*.root
  Example (quick test, no Lu-176):
    python3 necr_run.py --b2b --no-lu176 --tag b2bRef --frames 1 9 17 25 33 41 57 --duration 0.2
    python3 necr_run.py --b2b --no-lu176 --policy takeWinnerOfGoods --all-pulse-open --tag b2bWinAll \\
                        --frames 1 9 17 25 33 41 57 --duration 0.2
    python3 necr_run.py --b2b --no-lu176 --pileup 300 --tag b2bPU300 --frames 1 9 17 25 33 41 57 --duration 0.2

USAGE (run it in the folder that contains the model macro, coil_bed_real/ and Material/GateMaterials.db)
  python3 necr_run.py --setup q35 --no-lu176 --smoke          # 1 short job (0.01 s, frame 1) to test the setup
  python3 necr_run.py --setup q35 --no-lu176 --workers 64     # all 145 frames, 1 s each
  python3 necr_run.py --setup q86rat --no-lu176 --workers 64  # all 132 frames, 1 s each
  python3 necr_run.py --every 5 --workers 29                  # 29 frames over the whole curve
  python3 necr_run.py --frames 1 30 45 60 75                  # a few frames
  python3 necr_run.py --dry-run                               # only write the macros and print the commands
  python3 necr_run.py --lowest-first                          # start from the lowest activity (default: highest first)
  python3 necr_run.py --command "Gate {macro}"                # local GATE instead of Docker
  On a cluster with Apptainer:
    --command "apptainer run --bind {project}:/APP /path/to/gate82.sif {macro}"

  Then:  python3 necr_analysis.py --add-measured-bg           # analyses output/NECR_*.root (runs with --no-lu176)

NOTES
  * The duration is written into each run macro, and necr_analysis.py reads it from there.
  * The run macro of an existing ROOT file is never rewritten: it is the record of that run.
  * Progress: every written macro gets /run/printProgress (a line '--> Event k starts.' in the log every
    0.5 % of the run's expected decays; printing only, the simulation is unchanged). On a terminal one
    live line per running job (progress bar, %, ROOT file size so far, time, estimated time left) and a
    summary line are redrawn every second; without a terminal (nohup, output redirected to a file) a
    summary line is printed every 5 minutes. --no-progress switches the display off.
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
NEEDED_MATERIALS = ("Air", "LYSO", "Copper", "Nylon", "Glass", "Plastic", "Polyethylene", "Water")
B2B_FRACTION = 0.9686          # F-18 decays with a positron (beta+ 96.86 %, EC 3.14 %)
F18_HALF_LIFE_S = 6586         # 109.77 min
# Multiples policies GATE 8.2 accepts (GateCoincidenceSorter::SetMultiplesPolicy). GATE does NOT stop
# on a misspelled name, it silently uses keepIfAllAreGoods, so the name is checked here.
POLICIES = ("takeWinnerOfGoods", "takeWinnerIfIsGood", "takeWinnerIfAllAreGoods", "killAll", "takeAllGoods",
            "killAllIfMultipleGoods", "keepIfAnyIsGood", "keepIfOnlyOneGood", "keepIfAllAreGoods", "keepAll")
MEAS_FILE = "PET-MR NEC curves NEMA Masar.xlsx"
MEAS_SHEET = "20220915 Quad35 Maus"
MEAS_SHEETS = {35: "20220915 Quad35 Maus", 86: "20220906 Quad86 Maus"}     # measured mouse curves per coil
COIL_LAYER1 = {35: ("17.50 mm", "19.00 mm"), 86: ("43.00 mm", "44.50 mm")}  # rfCoil1 Rmin, Rmax (--coil)


def set_alias(text, name, value):
    """Replace the value of '/control/alias <name> ...' (exactly one active line expected)."""
    pat = re.compile(r"^(/control/alias[ \t]+" + re.escape(name) + r"[ \t]+)\S.*$", re.M)
    new, n = pat.subn(lambda m: m.group(1) + str(value), text)
    if n != 1:
        sys.exit(f"model macro: expected one '/control/alias {name}' line, found {n}")
    return new


def alias_value(text, name):
    """Value of '/control/alias <name> ...' in a macro text, or None."""
    m = re.search(r"^/control/alias[ \t]+" + re.escape(name) + r"[ \t]+(\S+)", text, re.M)
    return m.group(1) if m else None


SETUP_LINE = re.compile(r"^#@setup[ \t]+(\w+)(.*)$")


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
    macros name their coil and cradle directly (necr_analysis.py reads the coil from them)."""
    def path(m):
        value = alias_value(text, m.group(2))
        if value is None:
            sys.exit(f"{main}: /control/execute {{{m.group(2)}}}, but no active '/control/alias {m.group(2)}' line")
        return m.group(1) + value
    return re.sub(r"^([ \t]*/control/execute[ \t]+)\{(\w+)\}", path, text, flags=re.M)


def model_signature(text):
    """Coil, cradle, phantom position, phantom material and ring of a macro: the executed macros, the setup aliases,
    the module translation and the phantom material. Two runs under the same file name must agree in it. A change
    INSIDE an executed macro (e.g. new coil walls in the same file) is not seen here: give such a model a new tag."""
    execs = tuple(sorted(re.findall(r"^[ \t]*/control/execute[ \t]+(\S+)", text, re.M)))
    aliases = tuple(alias_value(text, k) for k in ("cradleY", "phantomY", "tubeEndY"))
    m = re.search(r"^/gate/module/placement/setTranslation[ \t]+([^#\n]*?)[ \t]*(?:#|$)", text, re.M)
    mat = re.search(r"^/gate/mousePhantom/setMaterial[ \t]+(\S+)", text, re.M)     # phantom material (density)
    return execs, aliases, m.group(1).split() if m else None, mat.group(1) if mat else None


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


def without_lu176(text):
    """Comment out every active line of the intrinsic Lu-176 source."""
    out = []
    for line in text.split("\n"):
        if "Lu176CrystalSource" in line and not line.lstrip().startswith("#"):
            line = "#" + line + "   # disabled by necr_run.py --no-lu176"
        out.append(line)
    return "\n".join(out)


def as_backtoback(text):
    """Turn the active F-18 ion source into back-to-back 511 keV pairs in the same volume.

    The alias activity keeps the F-18 activity; the source emits activity x B2B_FRACTION pairs/s
    through the new alias b2bActivity (set per job). Every expected line must be found exactly once.
    """
    rules = [(r"(setActivity\s+)\{activity\}(\s+becquerel).*", r"\1{b2bActivity}\2\t# F-18 activity x b2bFraction (necr_run.py --b2b)"),
             (r"(setType\s+)gps\b.*", r"\1backtoback"),
             (r"(gps/particle\s+)ion\b.*", r"\1gamma"),
             (r"(gps/monoenergy\s+)0\. eV.*", r"\g<1>511. keV"),
             (r"useDefaultHalfLife.*", f"setForcedHalfLife {F18_HALF_LIFE_S} s\t# F-18, 109.77 min")]
    out, found = [], [0] * len(rules)
    prefix = "/gate/source/F18CylinderSource/"
    for line in text.split("\n"):
        if line.startswith(prefix):
            rest = line[len(prefix):]
            if re.match(r"gps/ion\s", rest):
                line = "#" + line + "   # not used with --b2b"
            else:
                for i, (pat, rep) in enumerate(rules):
                    if re.match(pat, rest):
                        line = prefix + re.sub(pat, rep, rest)
                        found[i] += 1
                        break
        out.append(line)
    if found != [1] * len(rules):
        sys.exit(f"--b2b: the F-18 source block of the model macro is not as expected (matches {found})")
    text = "\n".join(out)
    alias = re.search(r"^/control/alias[ \t]+activity[ \t]+\S+[ \t]*$", text, re.M)
    if not alias:
        sys.exit("--b2b: no '/control/alias activity' line")
    extra = f"\n/control/alias b2bFraction {B2B_FRACTION}\n/control/alias b2bActivity 0"
    return text[:alias.end()] + extra + text[alias.end():]


def without_deadtime(text):
    """Comment out both dead-time stages: the two 'insert deadtime' lines, their settings and the
    'name deadtime2' line (left active, it would rename the next module, the energy thresholder)."""
    pats = (r"/gate/digitizer/Singles/insert\s+deadtime\b", r"/gate/digitizer/Singles/name\s+deadtime2\b",
            r"/gate/digitizer/Singles/deadtime2?/")
    out, n = [], 0
    for line in text.split("\n"):
        if any(re.match(p, line) for p in pats):
            line = "#" + line + "   # disabled by necr_run.py --no-deadtime"
            n += 1
        out.append(line)
    if n != 9:
        sys.exit(f"--no-deadtime: expected the 9 deadtime lines of the model macro, found {n}")
    return "\n".join(out)


def set_command(text, command, value, count=1):
    """Set the value of the active macro line(s) '<command> ...' (exactly `count` lines expected)."""
    pat = re.compile(r"^(" + re.escape(command) + r"[ \t]+).*$", re.M)
    new, n = pat.subn(lambda m: m.group(1) + value + "\t# set by necr_run.py", text)
    if n != count:
        sys.exit(f"model macro: expected {count} active '{command}' line(s), found {n}")
    return new


def set_sorters(text, command, value):
    """Set '<command> <value>' in both coincidence sorters (Coincidences and delay)."""
    pat = re.compile(r"^(/gate/digitizer/(?:Coincidences|delay)/" + command + r"[ \t]+)\S+(.*)$", re.M)
    new, n = pat.subn(lambda m: m.group(1) + value + "\t# set by necr_run.py", text)
    if n != 2:
        sys.exit(f"model macro: expected {command} in both sorters, found {n} lines")
    return new


def expected_decays(text, activity, duration, b2b):
    """Decays (GATE events) a run is expected to simulate: the F-18 source (pairs for --b2b) plus the
    active Lu-176 source, times the duration. Used only for the progress display."""
    lu = 0.0
    m = re.search(r"^/gate/source/Lu176CrystalSource/setActivity\s+([\d.eE+-]+)\s*(\w+)?", text, re.M)
    if m:
        lu = float(m.group(1)) * {"kBq": 1e3, "MBq": 1e6}.get(m.group(2) or "", 1.0)
    return ((activity * B2B_FRACTION if b2b else activity) + lu) * duration


def with_progress(text, n_expected):
    """Insert /run/printProgress before /gate/application/startDAQ: one '--> Event k starts.' line in
    the log every 0.5 % of the expected decays. Returns (text, every), every = None if no startDAQ."""
    every = max(1, int(n_expected / 200))
    new, n = re.subn(r"^(/gate/application/startDAQ)",
                     f"/run/printProgress {every}\t# necr_run.py: progress line every 0.5 % of the expected decays\n\\1",
                     text, count=1, flags=re.M)
    return (new, every) if n == 1 else (text, None)


class Progress:
    """Live progress of the running GATE jobs, read from the '--> Event k starts.' lines that
    /run/printProgress writes into each log: progress = k / expected decays of that run."""
    EVENT = re.compile(rb"--> Event (\d+) starts")

    def __init__(self, jobs_total, decays_total, enabled=True):
        self.enabled = enabled
        self.tty = enabled and sys.stdout.isatty()
        self.lock = threading.Lock()
        self.running = {}                       # name -> dict(log, root, n_exp, mbq, start)
        self.jobs_total, self.decays_total = jobs_total, decays_total
        self.done, self.decays_done = 0, 0.0
        self.t0 = time.time()
        self.drawn = 0
        self.last_plain = time.time()
        self.stop = threading.Event()
        if enabled:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def start(self, name, log, root, n_exp, mbq):
        with self.lock:
            self.running[name] = {"log": log, "root": root, "n_exp": n_exp, "mbq": mbq, "start": time.time()}

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
            lines.append(f"{name[:26]:<26} {info['mbq']:9.4f} MBq [{bar}] {100 * frac:5.1f} %  ROOT {size:7.1f} MiB  "
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


def add_delayed_all(text):
    """A second delayed sorter 'delayAll': a copy of the active /gate/digitizer/delay/ lines with
    allPulseOpenCoincGate true, inserted after them, and its ROOT tree switched on next to the delay tree.
    The prompt and 'delay' sorters are not touched."""
    lines = text.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith("/gate/digitizer/delay/")]
    if not idx:
        sys.exit("model macro: no active /gate/digitizer/delay/ lines found")
    copy = [lines[i].replace("/gate/digitizer/delay/", "/gate/digitizer/delayAll/", 1) for i in idx]
    pat = re.compile(r"^(/gate/digitizer/delayAll/allPulseOpenCoincGate[ \t]+)\S+.*$")
    n = sum(bool(pat.match(ln)) for ln in copy)
    if n != 1:
        sys.exit(f"model macro: expected 1 allPulseOpenCoincGate line in the delay sorter, found {n}")
    copy = [pat.sub(lambda m: m.group(1) + "true\t# every single opens a window", ln) for ln in copy]
    block = ["", "# Second delayed sorter, written by necr_run.py --delayed-all-pulse-open: a copy of 'delay' in which",
             "# every single opens a window, so it counts every delayed pair (singles-rate randoms). It only adds",
             "# the tree 'delayAll'; the NEMA analysis still uses 'delay' for the randoms and the scatter.",
             "/gate/digitizer/name                            delayAll",
             "/gate/digitizer/insert                          coincidenceSorter"] + copy
    lines[idx[-1] + 1:idx[-1] + 1] = block
    text = "\n".join(lines)
    pat = re.compile(r"^(/gate/output/root/setRootdelayFlag[ \t]+.*)$", re.M)
    text, n = pat.subn(lambda m: m.group(1) + "\n/gate/output/root/setRootdelayAllFlag 		1		# tree of the second delayed sorter (necr_run.py)", text)
    if n != 1:
        sys.exit(f"model macro: expected 1 active setRootdelayFlag line, found {n}")
    return text


def activities_from_workbook(path, sheet):
    """Average activity (Bq) of every measured frame with complete values (column A, from row 7).

    A frame counts when its activity, Total, Trues, Randoms and Scatter cells (A, G, H, I, J) are
    numbers; the 126.2 MBq frame of the Quad35 sheet has no randoms and is skipped.
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit("reading the measured workbook needs openpyxl (pip install openpyxl)")
    if not os.path.isfile(path):
        sys.exit(f"{path} not found: give --measured, or --activities-xlsx / --mbq")
    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        sys.exit(f"{path}: no sheet '{sheet}' (sheets: {wb.sheetnames})")
    out = []
    for r in wb[sheet].iter_rows(min_row=7, values_only=True):
        cells = [r[i] if len(r) > i else None for i in (0, 6, 7, 8, 9)]
        if all(isinstance(v, (int, float)) for v in cells) and cells[0] > 0:
            out.append(float(cells[0]) * 1e6)
    if not out:
        sys.exit(f"{path}, sheet {sheet}: no complete measured frames")
    return out


def activities_from_xlsx(path):
    """Activities (Bq) from the first column of the first sheet; text and empty cells are skipped."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit("--activities-xlsx needs openpyxl (pip install openpyxl)")
    if not os.path.isfile(path):
        sys.exit(f"{path} not found")
    ws = load_workbook(path, data_only=True).worksheets[0]
    out = [float(r[0]) for r in ws.iter_rows(values_only=True)
           if r and isinstance(r[0], (int, float)) and r[0] > 0]
    if not out:
        sys.exit(f"{path}: no numeric activities in the first column")
    if max(out) < 1e4:
        print(f"WARNING {path}: the largest value is {max(out):g}; the first column is read as Bq",
              file=sys.stderr)
    return out


def check_materials(path):
    if not os.path.isfile(path):
        sys.exit(f"{path} not found: copy GateMaterials.db into Material/ next to the model macro")
    names = set(re.findall(r"^([A-Za-z0-9_\-]+)\s*:", open(path).read(), re.M))
    missing = [m for m in NEEDED_MATERIALS if m not in names]
    if missing:
        sys.exit(f"{path}: missing materials {missing}")


def main():
    ap = argparse.ArgumentParser(description="Write and run one GATE job per NECR activity.")
    ap.add_argument("--main", default="NECR_main_std.mac", help="the complete model macro (default NECR_main_std.mac)")
    g = ap.add_argument_group("activities (default: the measured frames of the chosen coil)")
    g.add_argument("--measured", default=MEAS_FILE, help="measured workbook (activities in column A)")
    g.add_argument("--sheet", default=None,
                   help="sheet of the measured workbook (default: the sheet of the setup's coil)")
    g.add_argument("--activities-xlsx", default=None, metavar="FILE",
                   help="activities in Bq from the first column of FILE instead of the workbook")
    g.add_argument("--every", type=int, default=1, metavar="N", help="only every N-th frame (frame 1 always)")
    g.add_argument("--frames", type=int, nargs="+", default=None, help="only these frame numbers (1 = highest)")
    g.add_argument("--mbq", type=float, nargs="+", default=None,
                   help="free activities in MBq instead of the frame list (files NECR_<A>MBq)")
    g = ap.add_argument_group("run")
    g.add_argument("--duration", type=float, default=1.0, help="acquisition time per activity, s (default 1)")
    g.add_argument("--seed", type=int, default=20261010,
                   help="base random seed; frame k gets base + k, --mbq A gets base + 10000 + A in kBq")
    g.add_argument("--no-lu176", action="store_true", help="switch off the intrinsic Lu-176 source")
    g.add_argument("--smoke", action="store_true", help="one 0.01 s job at the highest activity (setup test)")
    g = ap.add_argument_group("test variants (only the written copies change)")
    g.add_argument("--b2b", action="store_true",
                   help="back-to-back 511 keV pairs instead of F-18 ions (pairs/s = activity x 0.9686)")
    g.add_argument("--policy", choices=POLICIES, default=None, help="MultiplesPolicy of both sorters")
    m = g.add_mutually_exclusive_group()
    m.add_argument("--all-pulse-open", action="store_true", help="allPulseOpenCoincGate true in both sorters")
    m.add_argument("--delayed-all-pulse-open", action="store_true",
                   help="add a second delayed sorter 'delayAll' with allPulseOpenCoincGate true (extra randoms "
                        "column R_r_all; prompts, delay sorter and NEMA results unchanged)")
    g.add_argument("--pileup", type=float, default=None, metavar="NS", help="pile-up time per block, ns (model: 100)")
    g.add_argument("--resolution", type=float, default=None, metavar="FWHM",
                   help="energy resolution at 511 keV as a fraction, e.g. 0.155 (model: 0.18)")
    g.add_argument("--save-singles", action="store_true", help="also write the Singles tree (large files)")
    g.add_argument("--singles-only", action="store_true",
                   help="write ONLY the Singles tree (no Coincidences, no delay); not for necr_analysis.py")
    g.add_argument("--no-deadtime", action="store_true", help="switch off both dead-time stages")
    g.add_argument("--coil", type=int, choices=(35, 86), default=None,
                   help="only for a model macro without setup blocks that has the coil layer rfCoil1: 35 (Quad35, "
                        "default) or 86 (Quad86; moves rfCoil1). With NECR_main_std.mac use --setup")
    g.add_argument("--setup", default=None, metavar="NAME",
                   help="coil/bed setup of a setup macro (NECR_main_std.mac: q35, q86, q86rat); "
                        "default: the block active in the file")
    g.add_argument("--tag", default="", help="file names NECR_<tag>_<frame>, to keep variants apart "
                                             "(default with --coil 86: Q86; with a setup: its tag=)")
    g = ap.add_argument_group("execution")
    g.add_argument("--workers", type=int, default=4, help="jobs at the same time (<= physical cores)")
    g.add_argument("--command", default=DOCKER,
                   help="command template with {macro} (and optionally {project}); default: GATE 8.2 Docker")
    g.add_argument("--overwrite", action="store_true", help="rerun activities whose ROOT file already exists")
    g.add_argument("--dry-run", action="store_true", help="write the macros, print the commands, run nothing")
    g.add_argument("--no-progress", action="store_true", help="no live progress display")
    g.add_argument("--lowest-first", action="store_true",
                   help="start the jobs from the lowest activity up (default: frame order, highest activity first); "
                        "only the start order changes, not the seeds or file names")
    a = ap.parse_args()

    project = os.path.abspath(".")
    if not os.path.isfile(a.main):
        sys.exit(f"{a.main} not found (run this script in the folder that contains it)")
    check_materials(os.path.join("Material", "GateMaterials.db"))
    template = open(a.main).read()
    setups = setups_of(template)
    setup = None
    if setups:
        if a.coil is not None:
            sys.exit(f"--coil edits the coil layer rfCoil1 of a macro without setups; {a.main} sets the coil per setup: use --setup "
                     f"{'|'.join(setups)}")
        active = [n for n, v in setups.items() if v["active"]]
        setup = a.setup or (active[0] if len(active) == 1 else None)
        if setup is None:
            sys.exit(f"{a.main}: {len(active)} setups are active in the file; choose one with --setup {'|'.join(setups)}")
        if setup not in setups:
            sys.exit(f"--setup {setup}: {a.main} has the setups {', '.join(setups)}")
        meta = setups[setup]["meta"]
        coil = int(meta.get("coil", 35))
        if coil not in MEAS_SHEETS:
            sys.exit(f"{a.main}: setup {setup} has coil={coil}; known: {sorted(MEAS_SHEETS)}")
        a.sheet = a.sheet or MEAS_SHEETS[coil]
        a.tag = a.tag or meta.get("tag", "")
        template = resolve_execute_aliases(activate_setup(template, setup), a.main)
    elif a.setup:
        sys.exit(f"{a.main} has no setups ('#@setup' blocks); --setup works with NECR_main_std.mac")
    else:
        a.coil = a.coil or 35
        a.sheet = a.sheet or MEAS_SHEETS[a.coil]
    check_includes(template, a.main)
    if a.no_lu176:
        template = without_lu176(template)
    variant = []
    if a.b2b:
        template = as_backtoback(template)
        variant.append("back-to-back source")
    if a.policy:
        template = set_sorters(template, "MultiplesPolicy", a.policy)
        variant.append(f"MultiplesPolicy {a.policy}")
    if a.all_pulse_open:
        template = set_sorters(template, "allPulseOpenCoincGate", "true")
        variant.append("allPulseOpenCoincGate true")
    if a.delayed_all_pulse_open:
        template = add_delayed_all(template)
        variant.append("second delayed sorter delayAll (allPulseOpenCoincGate true)")
    if a.pileup is not None:
        if a.pileup <= 0:
            sys.exit("--pileup must be positive (ns)")
        template = set_command(template, "/gate/digitizer/Singles/pileup/setPileup", f"{a.pileup:g} ns")
        variant.append(f"pile-up {a.pileup:g} ns")
    if a.resolution is not None:
        if not 0 < a.resolution < 1:
            sys.exit("--resolution is a fraction, e.g. 0.155 for 15.5 %")
        for cmd in ("setCrystalResolutionMin", "setCrystalResolutionMax"):
            template = set_command(template, "/gate/digitizer/Singles/crystalblurring/" + cmd, f"{a.resolution:g}")
        variant.append(f"energy resolution {100 * a.resolution:g} %")
    if a.no_deadtime:
        template = without_deadtime(template)
        variant.append("dead time OFF")
    if a.save_singles or a.singles_only:
        template = set_command(template, "/gate/output/root/setRootSinglesFlag", "1")
    if a.singles_only:                              # the sorters still run; only their trees are not written
        if a.delayed_all_pulse_open:
            sys.exit("--singles-only writes no coincidence trees: leave out --delayed-all-pulse-open")
        template = set_command(template, "/gate/output/root/setRootCoincidencesFlag", "0")
        template = set_command(template, "/gate/output/root/setRootdelayFlag", "0")
        variant.append("ONLY the Singles tree written (no Coincidences, no delay)")
    elif a.save_singles:
        variant.append("Singles saved")
    if not setups and a.coil != 35:
        rmin, rmax = COIL_LAYER1[a.coil]
        template = set_command(template, "/gate/rfCoil1/geometry/setRmin", rmin)
        template = set_command(template, "/gate/rfCoil1/geometry/setRmax", rmax)
        variant.append(f"coil Quad{a.coil}")
        if not a.tag:
            a.tag = f"Q{a.coil}"
    if a.no_lu176:
        variant.append("Lu-176 off")
    if variant:
        template = f"# necr_run.py test variant: {', '.join(variant)}\n" + template
    if a.tag and not re.fullmatch(r"[A-Za-z0-9]+", a.tag):
        sys.exit("--tag: letters and digits only")
    stem = f"NECR_{a.tag}_" if a.tag else "NECR_"

    # ---- the job list: (name, activity in Bq, duration, seed) --------------------------------
    if a.mbq:
        if len(set(a.mbq)) != len(a.mbq):
            sys.exit("the same activity is listed twice")
        jobs = []
        for mbq in a.mbq:
            if mbq <= 0:
                sys.exit(f"activity must be positive: {mbq}")
            tag = f"{mbq:g}".replace(".", "p")
            jobs.append((f"{stem}{tag}MBq", mbq * 1e6, a.duration, a.seed + 10000 + int(round(mbq * 1e3))))
    else:
        acts = activities_from_xlsx(a.activities_xlsx) if a.activities_xlsx else \
            activities_from_workbook(a.measured, a.sheet)
        frames = list(range(1, len(acts) + 1))
        if a.frames:
            bad = [k for k in a.frames if not 1 <= k <= len(acts)]
            if bad:
                sys.exit(f"frames outside 1..{len(acts)}: {bad}")
            frames = sorted(set(a.frames))
        elif a.every > 1:
            frames = frames[::a.every]
        jobs = [(f"{stem}{k:03d}", acts[k - 1], a.duration, a.seed + k) for k in frames]
    if a.smoke:
        name, act = jobs[0][0], jobs[0][1]
        jobs = [("smoke_" + name, act, 0.01, a.seed - 1)]

    os.makedirs("macros", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    todo = []
    for name, act, duration, seed in jobs:
        macro = os.path.join("macros", name + ".mac")
        root = os.path.join("output", name + ".root")
        if os.path.isfile(root) and not a.overwrite:
            # The run macro is the record of that run (necr_analysis.py reads activity and duration
            # from it), so it is never rewritten while its ROOT file exists. A ROOT file of the same
            # name from a different activity list must not be mixed in silently.
            if os.path.isfile(macro):
                old_text = open(macro, errors="replace").read()
                old = alias_value(old_text, "activity")
                if old is not None and abs(float(old) - act) > 1e-6 * act + 0.5:
                    sys.exit(f"{root} exists with activity {float(old):.0f} Bq, but this list gives {act:.0f} Bq "
                             f"for {name}. Move output/ and macros/ away or use --overwrite.")
                if setups and model_signature(old_text) != model_signature(template):
                    sys.exit(f"{root} exists, but its macro {macro} has another coil, cradle, phantom position, "
                             f"phantom material or ring than setup {setup} of {a.main}. Use another --tag (or --overwrite).")
            print(f"skip {name}: {root} exists (use --overwrite to rerun)")
            continue
        text = template
        for key, value in (("activity", f"{act:.0f}"), ("duration", f"{duration:g}"),
                           ("seed", seed), ("output", f"output/{name}")):
            text = set_alias(text, key, value)
        if a.b2b:
            text = set_alias(text, "b2bActivity", f"{act * B2B_FRACTION:.0f}")
        n_exp = expected_decays(text, act, duration, a.b2b)
        text, _ = with_progress(text, n_exp)
        with open(macro, "w") as f:
            f.write(text)
        cmd = [x.replace("{macro}", macro).replace("{project}", project) for x in shlex.split(a.command)]
        todo.append((name, macro, root, cmd, act, n_exp))
    if a.lowest_first:          # the pool starts jobs in submission order
        todo.sort(key=lambda j: j[4])

    print(f"{len(jobs)} macros in macros/, {len(todo)} to run, {a.workers} at a time, "
          f"{jobs[0][2]:g} s each" + (f"; variant: {', '.join(variant)}" if variant else "")
          + ("" if a.mbq or a.activities_xlsx else f"; activities from sheet '{a.sheet}'")
          + (f"; setup {setup} of {a.main}" if setup else ""))
    if a.dry_run:
        for name, macro, root, cmd, act, n_exp in todo:
            print(f"{name}  {act / 1e6:10.4f} MBq   " + " ".join(shlex.quote(x) for x in cmd))
        return

    progress = Progress(len(todo), sum(j[5] for j in todo), enabled=not a.no_progress)

    def run(job):
        name, macro, root, cmd, act, n_exp = job
        log = os.path.join("logs", name + ".log")
        start = time.time()
        progress.start(name, log, root, n_exp, act / 1e6)
        with open(log, "w") as out:
            try:
                code = subprocess.run(cmd, cwd=project, stdout=out, stderr=subprocess.STDOUT).returncode
            except OSError as exc:
                out.write(str(exc) + "\n")
                code = 127
        text = open(log, errors="replace").read()
        ok = code == 0 and "End of macro" in text and os.path.isfile(root) and os.path.getsize(root) > 0
        problems = [w for w in ("COMMAND NOT FOUND", "Overlap", "G4Exception") if w in text]
        return name, act / 1e6, ok, code, (time.time() - start) / 60, problems

    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(a.workers, len(todo) or 1))) as pool:
        for fut in as_completed([pool.submit(run, j) for j in todo]):
            name, mbq, ok, code, minutes, problems = fut.result()
            results.append((name, mbq, ok, code, minutes, problems))
            size = os.path.getsize(os.path.join("output", name + ".root")) / 2 ** 20 \
                if os.path.isfile(os.path.join("output", name + ".root")) else 0.0
            progress.finish(name, f"{'OK    ' if ok else 'FAILED'} {name} ({mbq:.4f} MBq): exit {code}, {minutes:.1f} min, "
                                  f"ROOT {size:.1f} MiB" + (f", log mentions {problems}" if problems else ""))
    progress.close()
    with open(os.path.join("logs", "run_status.txt"), "w") as f:
        f.write("name\tactivity_MBq\tok\texit_code\tminutes\tlog_warnings\n")
        for row in sorted(results):
            f.write("\t".join(f"{v:.6g}" if isinstance(v, float) else str(v) for v in row) + "\n")
    failed = [r[0] for r in results if not r[2]]
    if failed:
        sys.exit(f"{len(failed)} job(s) failed: {failed}. Read logs/<name>.log")
    print("All jobs finished. Next: python3 necr_analysis.py" if not a.smoke else
          f"Smoke test OK. Check logs/{jobs[0][0]}.log, then run without --smoke.")


if __name__ == "__main__":
    main()
