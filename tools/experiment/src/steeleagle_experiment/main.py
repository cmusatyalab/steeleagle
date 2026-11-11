"""Auto-experiment runner for SteelEagle.

    python -m steeleagle_experiment.main <dir>              run every experiment in dir
    python -m steeleagle_experiment.main <dir> -e <name>    run only that experiment (repeatable)
    python -m steeleagle_experiment.main <dir> -l           list the experiments in dir
    python -m steeleagle_experiment.main -r <dir_of_dirs>   run every experiment directory inside

An experiment directory holds an experiment.toml (see example/) and every file
it names. The toml holds a list of experiments ([[experiments]]), each either a
mission or a single video with its flow, run under its own netsim profiles; the
daemons, results and catalogs are shared by all of them. For each experiment,
for each of its netsim profiles, and for each trial, the runner:

  1. pushes the experiment's files and its video, if any, to every daemon's
     files directory (STEELEAGLE_FILES), and restarts the daemons with the
     experiment's configs for the profile,
  2. for the ambient profile only: stops the vehicle, measures the link from
     its host with iperf3 (the trial's bandwidth timeline), and restarts it,
  3. starts the mission (upload, load, start) or sets the video's flow on the
     target vehicle, and starts netsim as soon as the vehicle acknowledges it
     (not for none or ambient, which run unattenuated),
  4. waits for the duration (for a video, the video's length unless a
     duration is set), or for ENTER when the duration is 0,
  5. stops the mission (Hold, then StopMission) and netsim, and
  6. collects the trial into <dir>/runs/<experiment>/<profile>/:
        trial_<n>/result/<key>/              result files, moved off their hosts
        trial_<n>/catalog/<key>/             catalog files, copied
        trial_<n>/timeline.csv               bandwidth netsim allowed over time
        trial_<n>/netsim.log                 netsim's output
        stats_<profile>_<experiment>.csv     totals and bandwidth statistics, a row per trial
        timeline_<profile>_<experiment>.csv  every trial's timeline, with a trial column

Restarting the daemons means every remote daemon and then the local
orchestrator is reconfigured, which restarts it, and the runner waits for the
vehicle to be listed and running. A daemon's config is found by its name in
[daemons] and the experiment's name: for daemon "fermi", experiment "track"
and profile "normal", fermi_track_normal.toml is used if it exists; otherwise
the config of the previous profile carries over, or, for the first profiles,
fermi_track.toml, or else fermi.toml.
"""

from __future__ import annotations

import argparse
import atexit
import csv
import glob
import json
import os
import queue
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import grpc
from steeleagle_protocol.v1.services.daemon import (
    daemon_pb2,
    daemon_pb2_grpc,
    transfer_pb2,
    transfer_pb2_grpc,
)
from steeleagle_protocol.v1.services.driver import control_pb2, control_pb2_grpc
from steeleagle_protocol.v1.services.mission import mission_pb2, mission_pb2_grpc
from steeleagle_protocol.v1.services.vehicle import (
    data_pb2,
    data_pb2_grpc,
    upload_pb2,
    upload_pb2_grpc,
)

EXPERIMENT_FILE = "experiment.toml"
NETSIM = Path(__file__).resolve().parent / "netsim" / "netsim.py"
# Profiles that aren't netsim's, and run the trial without it: none just
# runs it unattenuated, and ambient first measures the link with iperf3
NONE = "none"
AMBIENT = "ambient"
NO_NETSIM = {NONE, AMBIENT}
NETSIM_PROFILES = [
    "normal", "limited", "degraded", "intermittent", "denied", "malicious", "outage", "delay",
    NONE, AMBIENT,
]
IPERF_PORT = 5201
IPERF_DURATION = 30.0
ROUTE_HEADER = "x-route-key"
CHUNK_SIZE = 1 << 20  # same chunk size as `eagle transfer-file`
RPC_TIMEOUT = 60.0
READY_TIMEOUT = 300.0
# Where each daemon's own config is saved before an experiment config replaces
# it, until it is restored after the trial. A run that dies before restoring
# leaves it here, and the next run restores that config rather than saving the
# experiment config it finds on the daemon.
ORIGINALS_DIR = Path.home() / ".local" / "state" / "steeleagle-experiment" / "original-configs"
# The services the runner stopped at the end of a trial, which stay stopped
# across the restore (StopService lasts across reconfigures), so it restarts
# them after it. Kept until then, so a run that dies in between leaves them
# for the next run's restore.
STOPPED_FILE = ORIGINALS_DIR / "stopped-services.json"
# A package install downloads the package, which can be slow
INSTALL_TIMEOUT = 600.0
# How long a daemon may report that it failed to start its services before
# the wait for it gives up, in case the report is from before its restart
START_FAILURE_GRACE = 15.0
# How often a wait says what it is still waiting for
PROGRESS_INTERVAL = 15.0
# Daemon files directory (STEELEAGLE_FILES) relative to the home directory,
# for rsyncing a video to a remote that isn't registered
REMOTE_FILES_DIR = ".local/share/steeleagle/files/"
# Where install.sh puts eagle and its tools, which isn't on the PATH of the
# non-interactive shell ssh runs a command in
REMOTE_PATH = 'PATH="$HOME/.local/bin:$PATH"'


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def default_socket() -> str:
    """The daemon control socket, as `eagle` finds it (XDG runtime dir).
    eagled is a user service, so under sudo it is the invoking user's socket."""
    sudo_uid = os.environ.get("SUDO_UID")
    if os.getuid() == 0 and sudo_uid:
        runtime = f"/run/user/{sudo_uid}"
    else:
        runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime, "steeleagle", "eagled.sock")


# --------------------------------------------------------------------------
# ssh
# --------------------------------------------------------------------------

# Every ssh the runner starts, directly or through rsync, shares one master
# connection per host (OpenSSH connection multiplexing), so a host's password
# is asked for once, when open_ssh connects to it, rather than on every call.
_ssh_dir: str | None = None
_ssh_hosts: set[str] = set()


def ssh_opts() -> list[str]:
    global _ssh_dir
    if _ssh_dir is None:
        # Short, as the sockets' paths must fit in about 100 characters
        _ssh_dir = tempfile.mkdtemp(prefix="se-ssh-", dir="/tmp")
        atexit.register(close_ssh)
    return [
        "-o", "ControlMaster=auto",
        "-o", f"ControlPath={_ssh_dir}/%C",
        "-o", "ControlPersist=yes",
    ]


def ssh(host: str, command: str) -> list[str]:
    """An ssh command line that runs command on host."""
    _ssh_hosts.add(host)
    return ["ssh", *ssh_opts(), host, command]


def rsync_cmd(host: str) -> list[str]:
    """An rsync command line whose ssh to host shares its master connection."""
    _ssh_hosts.add(host)
    return ["rsync", "-e", shlex.join(["ssh", *ssh_opts()])]


def open_ssh(hosts: list[str]) -> None:
    """Connects to each host up front, asking for its password (or host key
    check) on the terminal now, rather than in the middle of a run. The
    connection stays open in the background for later calls to share."""
    for host in hosts:
        _ssh_hosts.add(host)
        log(f"connecting to {host} over ssh")
        # -f: go to the background once logged in; -N: run no command
        # ControlMaster=auto makes this the master, as none is open yet
        r = subprocess.run(["ssh", *ssh_opts(), "-f", "-N", host])
        if r.returncode:
            log(f"warning: couldn't connect to {host} over ssh (exit {r.returncode}); later calls will retry")


def close_ssh() -> None:
    """Closes the master connections, and removes their sockets."""
    if _ssh_dir is None:
        return
    for host in sorted(_ssh_hosts):
        subprocess.run(
            ["ssh", *ssh_opts(), "-O", "exit", host],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    shutil.rmtree(_ssh_dir, ignore_errors=True)


# --------------------------------------------------------------------------
# Experiment config
# --------------------------------------------------------------------------


@dataclass
class Phase:
    kind: str  # "mission" or "video"
    file: Path  # the mission, or the video's flow
    auto: bool
    # seconds to run each trial; 0 waits for ENTER. For a video with no
    # duration set, the video's own length (duration_from_video)
    duration: float
    # the video, for "video": pushed to every daemon as push_as, if set, or
    # under its own name
    video: Path | None = None
    push_as: str = ""
    # no_upload: the mission or video is not pushed, and is assumed to already
    # be on every daemon under its own name
    no_upload: bool = False
    duration_from_video: bool = False


@dataclass
class PushFile:
    path: Path  # in the experiment directory
    name: str  # name it is saved as in each daemon's files directory


@dataclass
class DaemonCfg:
    key: str
    orchestrator: bool
    prefix: str

    @property
    def ssh_host(self) -> str:
        return self.prefix.rstrip(":")

    @property
    def hostname(self) -> str:
        return self.ssh_host.rsplit("@", 1)[-1] or self.key


@dataclass
class Experiment:
    dir: Path
    name: str
    vehicle: str
    phase: Phase
    profiles: list[str]
    interface: str
    port: int
    netsim_args: list[str]
    failpoints: str  # netsim --failpoints value, used only by the malicious and outage profiles
    trials: int  # runs of each profile
    iperf_port: int  # ambient: port iperf3 measures the link on
    iperf_duration: float  # ambient: seconds iperf3 measures the link for
    daemons: dict[str, DaemonCfg]
    configs: dict[str, dict[str, Path]]  # profile -> daemon key -> config file
    # pushed to every daemon's files directory at the start of each trial
    files: list[PushFile] = field(default_factory=list)
    results: dict[str, str] = field(default_factory=dict)
    catalogs: dict[str, str] = field(default_factory=dict)
    # catalogs moved aside on their host after each trial, into a directory of
    # their own in its files directory, to be transferred later, rather than copied
    defer_pull: set[str] = field(default_factory=set)

    @property
    def orchestrator(self) -> DaemonCfg:
        return next(d for d in self.daemons.values() if d.orchestrator)

    @property
    def remotes(self) -> list[DaemonCfg]:
        return [d for d in self.daemons.values() if not d.orchestrator]


def read_toml(exp_dir: Path) -> dict:
    path = exp_dir / EXPERIMENT_FILE
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{path}: {e}") from None


def experiment_tables(exp_dir: Path, raw: dict, names: list[str] | None = None) -> list[dict]:
    """The [[experiments]] tables, in order, each checked for a unique name;
    all of them, or, if names are given, only those."""
    if "experiment" in raw:
        raise ValueError(
            f"{exp_dir}: [experiment] is now a list of [[experiments]] tables, one per "
            f"experiment, with sections [experiments.mission], [experiments.video] and "
            f"[experiments.netsim] (after a [[experiments]] header, [experiment.<x>] makes "
            f"a separate table)"
        )
    if "netsim" in raw:
        raise ValueError(f"{exp_dir}: [netsim] is now set per experiment, as [experiments.netsim]")
    tables = raw.get("experiments")
    if not isinstance(tables, list) or not tables or not all(isinstance(t, dict) for t in tables):
        raise ValueError(f"{exp_dir}: no experiments; add one or more [[experiments]] tables")
    known = []
    for i, t in enumerate(tables, 1):
        name = t.get("name")
        if not isinstance(name, str) or not name or "/" in name:
            raise ValueError(
                f"{exp_dir}: experiment #{i} needs a name (usable in a file name), not {name!r}"
            )
        known.append(name)
    dups = sorted({n for n in known if known.count(n) > 1})
    if dups:
        raise ValueError(f"{exp_dir}: more than one experiment is named {', '.join(dups)}")
    if names:
        unknown = [n for n in names if n not in known]
        if unknown:
            raise ValueError(
                f"{exp_dir}: no experiment named {', '.join(unknown)}; "
                f"its experiments are {', '.join(known)}"
            )
        tables = [t for t in tables if t["name"] in names]
    return tables


def load_experiments(exp_dir: Path, names: list[str] | None = None) -> list[Experiment]:
    """Loads and checks the experiments in exp_dir's experiment.toml: all of
    them, in order, or, if names are given, only those."""
    raw = read_toml(exp_dir)
    tables = experiment_tables(exp_dir, raw, names)

    daemons = {}
    for key, d in raw.get("daemons", {}).items():
        orch = bool(d.get("orchestrator", False))
        if "config" in d:
            raise ValueError(
                f"{exp_dir}: daemons.{key}.config is no longer supported; name the file "
                f"{key}.toml, {key}_<experiment>.toml or {key}_<experiment>_<profile>.toml instead"
            )
        if "pass" in d:
            raise ValueError(
                f"{exp_dir}: daemons.{key}.pass is no longer supported; ssh and rsync now "
                f"prompt for the password (and host key checks) on the terminal"
            )
        daemons[key] = DaemonCfg(key, orch, d.get("prefix", ""))
    if sum(d.orchestrator for d in daemons.values()) != 1:
        raise ValueError(f"{exp_dir}: exactly one daemon must have orchestrator = true")

    results: dict[str, str] = {}
    for key, value in raw.get("results", {}).items():
        if isinstance(value, dict) and "defer_pull" in value:
            raise ValueError(
                f"{exp_dir}: results.{key}: defer_pull goes under [catalogs], not [results], "
                f"since results are removed from their host once they are pulled"
            )
        if not isinstance(value, str):
            raise ValueError(f"{exp_dir}: results.{key} must be a path")
        results[key] = value
    catalogs: dict[str, str] = {}
    defer_pull: set[str] = set()
    for key, value in raw.get("catalogs", {}).items():
        if isinstance(value, dict):
            unknown = set(value) - {"path", "defer_pull"}
            if unknown or not isinstance(value.get("path"), str):
                raise ValueError(
                    f"{exp_dir}: catalogs.{key} must be a path, or a table "
                    f"{{ path = \"<daemon>/<path>\", defer_pull = true }}"
                    + (f" (unknown keys {', '.join(sorted(unknown))})" if unknown else "")
                )
            if not isinstance(value.get("defer_pull", False), bool):
                raise ValueError(f"{exp_dir}: catalogs.{key}.defer_pull must be true or false")
            catalogs[key] = value["path"]
            if value.get("defer_pull", False):
                defer_pull.add(key)
        elif isinstance(value, str):
            catalogs[key] = value
        else:
            raise ValueError(f"{exp_dir}: catalogs.{key} must be a path or a table")
    for table in (results, catalogs):
        for key, src in table.items():
            host = src.split("/", 1)[0]
            if host not in daemons:
                raise ValueError(f"{exp_dir}: {key} = {src!r} names unknown daemon {host!r}")

    return [parse_experiment(exp_dir, t, daemons, results, catalogs, defer_pull) for t in tables]


def parse_experiment(
    exp_dir: Path, exp: dict, daemons: dict[str, DaemonCfg],
    results: dict[str, str], catalogs: dict[str, str], defer_pull: set[str],
) -> Experiment:
    """Parses one [[experiments]] table."""
    name = exp["name"]
    where = f"{exp_dir}: experiment {name}"
    vehicle = exp.get("vehicle", "")
    if not vehicle:
        raise ValueError(f"{where}: vehicle is not set")

    def exp_file(key: str, value: str) -> Path:
        path = exp_dir / value
        if not path.is_file():
            raise ValueError(f"{where}: {key} file {path} does not exist")
        return path

    def flag(sect: dict, key: str) -> bool:
        v = sect.get(key.rsplit(".", 1)[-1], False)
        if not isinstance(v, bool):
            raise ValueError(f"{where}: {key} must be true or false, not {v!r}")
        return v

    def duration(kind: str, sect: dict) -> float | None:
        if "duration" not in sect:
            return None
        d = sect["duration"]
        if not isinstance(d, (int, float)) or isinstance(d, bool) or d < 0:
            raise ValueError(f"{where}: {kind}.duration must be a number >= 0, not {d!r}")
        return float(d)

    def file_name(key: str, value) -> str:
        if not isinstance(value, str) or not value or "/" in value:
            raise ValueError(f"{where}: {key} must be a file name, not {value!r}")
        return value

    phases = []
    sect = exp.get("mission", {})
    if sect.get("file"):
        no_upload = flag(sect, "mission.no_upload")
        if no_upload:
            # Not pushed, so it need not exist here; only its name is used
            mission = exp_dir / file_name("mission.file (with no_upload)", sect["file"])
        else:
            mission = exp_file("mission.file", sect["file"])
        phases.append(Phase(
            "mission", mission, flag(sect, "mission.auto"),
            duration("mission", sect) or 0.0, no_upload=no_upload,
        ))
    sect = exp.get("video", {})
    if sect.get("video") or sect.get("flow"):
        if not (sect.get("video") and sect.get("flow")):
            raise ValueError(f"{where}: video needs both video and flow set")
        if isinstance(sect["video"], list):
            raise ValueError(
                f"{where}: video.video is now a single video; for several videos, "
                f"add an experiment for each"
            )
        no_upload = flag(sect, "video.no_upload")
        if no_upload:
            # Not pushed, so it need not exist here; only its name is used
            video = exp_dir / file_name("video.video (with no_upload)", sect["video"])
        else:
            video = exp_file("video.video", sect["video"])
        push_as = sect.get("push_as", "")
        if push_as:
            file_name("video.push_as", push_as)
        if no_upload and push_as:
            raise ValueError(f"{where}: video.push_as does nothing with no_upload; leave it out")
        d = duration("video", sect)
        from_video = d is None
        if from_video:
            # No duration set: the video runs for its own length
            if no_upload and not video.is_file():
                raise ValueError(
                    f"{where}: with no_upload, video {video.name} is not in the experiment "
                    f"directory to find its length; set video.duration"
                )
            try:
                d = video_length(video)
            except ValueError as e:
                raise ValueError(f"{where}: {e}; set video.duration instead") from None
        phases.append(Phase(
            "video", exp_file("video.flow", sect["flow"]), flag(sect, "video.auto"), d,
            video=video, push_as=push_as, no_upload=no_upload, duration_from_video=from_video,
        ))
    if len(phases) != 1:
        raise ValueError(f"{where}: set exactly one of mission (file) or video (video and flow)")
    phase = phases[0]

    files = parse_files(exp.get("files", []), where, exp_file)
    if phase.video and not phase.no_upload:
        pushed = phase.push_as or phase.video.name
        if pushed in {f.name for f in files}:
            raise ValueError(f"{where}: files pushes {pushed}, which the video is also pushed as")

    ns = exp.get("netsim", {})
    profiles = ns.get("profiles", ["*"])
    if "*" in profiles:
        profiles = NETSIM_PROFILES
    for p in profiles:
        if p not in NETSIM_PROFILES:
            raise ValueError(f"{where}: unknown netsim profile {p!r}")
    if "interface" not in ns or "port" not in ns:
        raise ValueError(f"{where}: netsim.interface and netsim.port must be set")
    # Optional extra netsim flags, e.g. args = ["--direction", "egress", "--seed", "1"]
    netsim_args = [str(a) for a in ns.get("args", [])]
    if "failpoint_map" in ns:
        raise ValueError(
            f"{where}: netsim.failpoint_map is no longer supported; each experiment has "
            f"one video, so set netsim.failpoints"
        )
    failpoints = parse_failpoints(ns.get("failpoints", []), where)
    trials = ns.get("trials", 1)
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        raise ValueError(f"{where}: netsim.trials must be an integer >= 1, not {trials!r}")
    iperf_port = ns.get("iperf_port", IPERF_PORT)
    if not isinstance(iperf_port, int) or isinstance(iperf_port, bool) or not 1 <= iperf_port <= 65535:
        raise ValueError(f"{where}: netsim.iperf_port must be a port number, not {iperf_port!r}")
    iperf_duration = ns.get("iperf_duration", IPERF_DURATION)
    if not isinstance(iperf_duration, (int, float)) or isinstance(iperf_duration, bool) or iperf_duration < 1:
        raise ValueError(f"{where}: netsim.iperf_duration must be a number >= 1, not {iperf_duration!r}")

    configs = resolve_configs(exp_dir, name, list(daemons), list(profiles))

    return Experiment(
        exp_dir, name, vehicle, phase, list(profiles), ns["interface"], int(ns["port"]),
        netsim_args, failpoints, trials, iperf_port, float(iperf_duration),
        daemons, configs, files, results, catalogs, defer_pull,
    )


def parse_files(raw, where: str, exp_file) -> list[PushFile]:
    """Parses an experiment's files: a list of file names in the experiment
    directory, each optionally a table { file = "...", push_as = "..." } to
    push it under another name."""
    if not isinstance(raw, list):
        raise ValueError(f"{where}: files must be a list of file names")
    files = []
    for entry in raw:
        if isinstance(entry, str):
            entry = {"file": entry}
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not entry["file"]:
            raise ValueError(
                f"{where}: invalid files entry {entry!r}; want a file name "
                f'or {{ file = "...", push_as = "..." }}'
            )
        unknown = set(entry) - {"file", "push_as"}
        if unknown:
            raise ValueError(f"{where}: files entry {entry!r} has unknown keys {sorted(unknown)}")
        path = exp_file("files", entry["file"])
        push_as = entry.get("push_as", "") or path.name
        if not isinstance(push_as, str) or "/" in push_as:
            raise ValueError(f"{where}: files push_as must be a file name, not {push_as!r}")
        files.append(PushFile(path, push_as))
    names = [f.name for f in files]
    dups = sorted({n for n in names if names.count(n) > 1})
    if dups:
        raise ValueError(f"{where}: files pushes more than one file as {', '.join(dups)}")
    return files


def video_length(path: Path) -> float:
    """A video's length in seconds, from ffprobe if it is installed, or else
    from the header of an MP4/MOV file."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            d = float(json.loads(r.stdout)["format"]["duration"])
            if d > 0:
                return d
    except (FileNotFoundError, subprocess.TimeoutExpired, KeyError, ValueError):
        pass
    d = mp4_length(path)
    if d is None or d <= 0:
        raise ValueError(
            f"can't find the length of video {path.name} (install ffprobe, or use an MP4/MOV file)"
        )
    return d


def mp4_length(path: Path) -> float | None:
    """Reads the length from an MP4/MOV file's moov/mvhd box, or None."""

    def boxes(f, end: int):
        """Yields (type, payload offset, payload size) of the boxes up to end."""
        pos = f.tell()
        while pos + 8 <= end:
            f.seek(pos)
            size, kind = struct.unpack(">I4s", f.read(8))
            header = 8
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0]
                header = 16
            elif size == 0:
                size = end - pos
            if size < header:
                return
            yield kind, pos + header, size - header
            pos += size

    try:
        with open(path, "rb") as f:
            end = f.seek(0, os.SEEK_END)
            f.seek(0)
            for kind, off, size in boxes(f, end):
                if kind != b"moov":
                    continue
                f.seek(off)
                for kind2, off2, size2 in boxes(f, off + size):
                    if kind2 != b"mvhd" or size2 < 20:
                        continue
                    f.seek(off2)
                    version = f.read(4)[0]
                    if version == 1:
                        f.seek(16, os.SEEK_CUR)
                        timescale, duration = struct.unpack(">IQ", f.read(12))
                    else:
                        f.seek(8, os.SEEK_CUR)
                        timescale, duration = struct.unpack(">II", f.read(8))
                    return duration / timescale if timescale else None
    except (OSError, struct.error, IndexError):
        pass
    return None


def resolve_configs(
    exp_dir: Path, exp_name: str, keys: list[str], profiles: list[str],
) -> dict[str, dict[str, Path]]:
    """Picks each daemon's config for each profile, in profile order:
    <key>_<experiment>_<profile>.toml if it exists, else the config the
    previous profile used, else <key>_<experiment>.toml, else <key>.toml."""
    configs: dict[str, dict[str, Path]] = {p: {} for p in profiles}
    for key in keys:
        current: Path | None = None
        for p in profiles:
            specific = exp_dir / f"{key}_{exp_name}_{p}.toml"
            if specific.is_file():
                current = specific
            elif current is None:
                bases = [exp_dir / f"{key}_{exp_name}.toml", exp_dir / f"{key}.toml"]
                current = next((b for b in bases if b.is_file()), None)
                if current is None:
                    raise ValueError(
                        f"{exp_dir}: experiment {exp_name}: no config for daemon {key!r} under "
                        f"profile {p!r}; add {specific.name}, {bases[0].name} or {bases[1].name}"
                    )
            configs[p][key] = current
    return configs


def parse_failpoints(raw, where: str, key: str = "netsim.failpoints") -> str:
    """Turns netsim.failpoints, a list of [event_time, dead_time] pairs in
    seconds, into netsim's "30:10,90:5" form."""
    if not isinstance(raw, list):
        raise ValueError(f"{where}: {key} must be a list of [event_time, dead_time] pairs")
    pairs = []
    for fp in raw:
        if (
            not isinstance(fp, list) or len(fp) != 2
            or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in fp)
            or fp[0] < 0 or fp[1] <= 0
        ):
            raise ValueError(
                f"{where}: invalid failpoint {fp!r} in {key}; want [event_time >= 0, dead_time > 0] in seconds"
            )
        pairs.append(f"{fp[0]:g}:{fp[1]:g}")
    return ",".join(pairs)

# --------------------------------------------------------------------------
# Daemon client
# --------------------------------------------------------------------------


class Daemon:
    """A client of the local daemon's control socket, like `eagle`. Calls with a
    route key are proxied by the daemon to that vehicle or remote daemon."""

    def __init__(self, socket: str):
        self.socket = socket
        self.channel = grpc.insecure_channel("unix://" + socket)
        self.daemon = daemon_pb2_grpc.DaemonServiceStub(self.channel)
        self.transfer = transfer_pb2_grpc.TransferServiceStub(self.channel)
        self.loader = upload_pb2_grpc.LoaderServiceStub(self.channel)
        self.mission = mission_pb2_grpc.MissionServiceStub(self.channel)
        self.data = data_pb2_grpc.DataServiceStub(self.channel)
        self.control = control_pb2_grpc.ControlServiceStub(self.channel)

    @staticmethod
    def route(key: str | None):
        return ((ROUTE_HEADER, key),) if key else None

    def list_services(self, timeout: float = 10.0) -> daemon_pb2.ListServicesResponse:
        return self.daemon.ListServices(daemon_pb2.ListServicesRequest(), timeout=timeout)

    def get_configuration(self, route: str | None = None) -> str:
        resp = self.daemon.GetConfiguration(
            daemon_pb2.GetConfigurationRequest(), metadata=self.route(route), timeout=RPC_TIMEOUT,
        )
        return resp.config_toml.decode()

    def configure(self, toml_text: str, route: str | None = None) -> None:
        self.daemon.Configure(
            daemon_pb2.ConfigureRequest(config_toml=toml_text),
            metadata=self.route(route), timeout=RPC_TIMEOUT,
        )

    def wait_ready(self, vehicle: str, remotes: list[DaemonCfg], timeout: float = READY_TIMEOUT) -> str:
        """Waits until ListServices answers, every remote is registered and the
        vehicle is running. Returns the vehicle's qualified name. Says what it
        is waiting for every PROGRESS_INTERVAL seconds, and gives up early if
        a daemon keeps reporting that it failed to start its services."""
        start = time.monotonic()
        deadline = start + timeout
        next_progress = start + PROGRESS_INTERVAL
        failing_since: float | None = None
        last = "daemon not reachable"
        while time.monotonic() < deadline:
            failed = None
            try:
                resp = self.list_services()
            except grpc.RpcError as e:
                last = f"ListServices: {e.code().name} {e.details()}"
                if is_start_failure(e.details()):
                    failed = f"orchestrator: {e.details()}"
                resp = None
            if resp is not None:
                missing = []
                for r in remotes:
                    listed = find_remote(resp, r, include_failed=True)
                    if listed is None:
                        missing.append(r.key)
                    elif listed.error:
                        missing.append(f"{r.key} ({listed.error})")
                        if is_start_failure(listed.error):
                            failed = f"remote {r.key}: {listed.error}"
                svc = find_vehicle(resp, vehicle)
                if missing:
                    last = f"remote daemon(s) not available: {', '.join(missing)}"
                elif svc is None:
                    last = f"vehicle {vehicle!r} not listed"
                elif not svc.running:
                    last = f"vehicle {svc.name!r} not running" + (f" ({svc.error})" if svc.error else "")
                else:
                    return svc.name
            now = time.monotonic()
            if failed is None:
                failing_since = None
            elif failing_since is None:
                failing_since = now
            elif now - failing_since >= START_FAILURE_GRACE:
                raise RuntimeError(f"daemon failed to start: {failed}")
            if now >= next_progress:
                log(f"still waiting for the daemons ({now - start:.0f}s): {last}")
                next_progress = now + PROGRESS_INTERVAL
            time.sleep(1)
        raise TimeoutError(f"daemon not ready after {timeout:.0f}s: {last}")

    def list_packages(self, route: str | None = None) -> set[str]:
        """The uris of the packages installed on the daemon, or, with a route,
        that remote daemon, including those pending its next restart."""
        resp = self.daemon.ListPackages(
            daemon_pb2.ListPackagesRequest(), metadata=self.route(route), timeout=RPC_TIMEOUT,
        )
        return {p.uri for p in resp.packages}

    def install_package(self, uri: str, route: str | None = None) -> None:
        """Installs a package, which takes effect on the daemon's next restart."""
        self.daemon.InstallPackage(
            daemon_pb2.InstallPackageRequest(uri=uri), metadata=self.route(route), timeout=INSTALL_TIMEOUT,
        )

    def _send_chunks(
        self, call, request_type, path: Path, route: str | None, what: str, timeout: float,
        filename: str = "",
    ) -> None:
        """Streams a file in chunks to an upload-style RPC, which acks each
        chunk before the next is sent. The file is sent as filename, if
        given, or its own name."""
        data = path.read_bytes()
        chunks = [data[i : i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)] or [b""]
        total = len(chunks)
        acks: queue.Queue[int] = queue.Queue()

        def requests():
            for n, chunk in enumerate(chunks, start=1):
                yield request_type(filename=filename or path.name, chunk=chunk, number=n, total=total)
                if acks.get(timeout=RPC_TIMEOUT) != n:
                    return

        received = 0
        for resp in call(requests(), metadata=self.route(route), timeout=timeout):
            received = resp.received
            acks.put(received)
        if received != total:
            raise RuntimeError(f"{what} ended after {received} of {total} chunks were acknowledged")

    def upload_mission(self, path: Path, route: str) -> None:
        self._send_chunks(
            self.loader.UploadMission, upload_pb2.UploadMissionRequest,
            path, route, "mission upload", RPC_TIMEOUT,
        )

    def transfer_file(self, path: Path, route: str | None = None, name: str = "") -> None:
        """Saves a file to the daemon's files directory, or, with a route,
        to that remote daemon's, as name if given. A video can be large, so
        the deadline is for the whole transfer, not a chunk."""
        self._send_chunks(
            self.transfer.TransferFile, transfer_pb2.TransferFileRequest,
            path, route, "file transfer", None, filename=name,
        )

    def load_mission(self, name: str, route: str) -> None:
        self.loader.LoadMission(upload_pb2.LoadMissionRequest(name=name), metadata=self.route(route), timeout=RPC_TIMEOUT)

    def start_mission(self, route: str) -> None:
        self.mission.StartMission(mission_pb2.StartMissionRequest(), metadata=self.route(route), timeout=RPC_TIMEOUT)

    def stop_mission(self, route: str) -> None:
        self.mission.StopMission(mission_pb2.StopMissionRequest(), metadata=self.route(route), timeout=RPC_TIMEOUT)

    def stop_service(self, name: str) -> None:
        """Stops a service, by its qualified name; the orchestrator passes it
        on to the remote daemon that runs it. It stays stopped, even across
        daemon restarts, until restart_service."""
        self.daemon.StopService(daemon_pb2.StopServiceRequest(service_name=name), timeout=RPC_TIMEOUT)

    def restart_service(self, name: str) -> None:
        self.daemon.RestartService(daemon_pb2.RestartServiceRequest(service_names=name), timeout=RPC_TIMEOUT)

    def hold(self, route: str) -> None:
        self.control.Hold(control_pb2.HoldRequest(), metadata=self.route(route), timeout=RPC_TIMEOUT)

    def set_dataflow(self, toml_bytes: bytes, route: str) -> None:
        self.data.SetDataflow(data_pb2.SetDataflowRequest(toml=toml_bytes), metadata=self.route(route), timeout=RPC_TIMEOUT)


def find_vehicle(resp: daemon_pb2.ListServicesResponse, vehicle: str):
    """Finds a vehicle by its qualified name ("{ip}.{name}") or plain name."""
    vehicles = [s for s in resp.services if s.category == daemon_pb2.SERVICE_CATEGORY_VEHICLE]
    for s in vehicles:
        if s.name == vehicle:
            return s
    matches = [s for s in vehicles if s.name.endswith("." + vehicle)]
    if len(matches) > 1:
        raise ValueError(f"vehicle {vehicle!r} is ambiguous: {', '.join(s.name for s in matches)}")
    return matches[0] if matches else None


def find_remote(resp: daemon_pb2.ListServicesResponse, d: DaemonCfg, include_failed: bool = False):
    """The registered remote d, matched by its hostname. A remote whose
    services can't be listed (it failed to start them, say) is left out,
    unless include_failed; it can still be configured."""
    for r in resp.remotes:
        if (include_failed or not r.error) and r.hostname in (d.key, d.hostname):
            return r
    return None


def is_start_failure(error: str) -> bool:
    """Whether a daemon's error says it failed to start its services, which
    lasts until it is reconfigured."""
    return "failed to start services" in error


def config_packages(config: Path) -> list[str]:
    """The package uris a daemon config's services (and simulator) use."""
    with open(config, "rb") as f:
        raw = tomllib.load(f)
    uris = [s.get("plugin", {}).get("package", "") for s in raw.get("services", [])]
    uris.append(raw.get("simulator", {}).get("package", ""))
    return sorted({u for u in uris if u})


# --update-packages: reinstall every package a daemon's configs use, once per
# run, so one installed from a branch gets that branch's latest code
UPDATE_PACKAGES = False
# (daemon key, package uri) installed or updated in this run
_installed: set[tuple[str, str]] = set()


def install_packages(client: Daemon, key: str, config: Path, route: str | None = None) -> None:
    """Installs the packages config uses that daemon key doesn't have yet,
    or, with UPDATE_PACKAGES, every one it uses, the first time in this run.
    They take effect on the restart that configuring it causes."""
    needed = [u for u in config_packages(config) if (key, u) not in _installed]
    if not needed:
        return
    have = client.list_packages(route)
    for uri in needed:
        if uri in have and not UPDATE_PACKAGES:
            continue
        log(f"{'updating' if uri in have else 'installing'} {uri} on {key}")
        try:
            client.install_package(uri, route)
        except grpc.RpcError as e:
            raise RuntimeError(f"couldn't install {uri} on {key}: {e.details()}") from None
        _installed.add((key, uri))


def config_services(config: Path) -> set[str]:
    """The names of the services a daemon config runs."""
    with open(config, "rb") as f:
        raw = tomllib.load(f)
    return {s["name"] for s in raw.get("services", []) if s.get("name")}


def start_stopped_services(client: Daemon, exp: Experiment, profile: str, timeout: float = READY_TIMEOUT) -> None:
    """Restarts the services of the experiment's daemon configs that are
    stopped by request (with StopService, e.g. `eagle stop-service`), which
    they stay across restarts and reconfigures, and waits for them to run.
    Other daemons registered with the orchestrator are left alone."""
    resp = client.list_services()
    remote_ips = {r.ip for r in resp.remotes if r.ip}
    # The qualifier of each of the experiment's daemons' services
    owners: dict[str, str] = {}
    for d in exp.remotes:
        listed = find_remote(resp, d, include_failed=True)
        if listed is not None:
            owners[listed.ip] = d.key
    wanted: list[str] = []
    for svc in resp.services:
        if not svc.stopped:
            continue
        ip = next((i for i in remote_ips if svc.name.startswith(i + ".")), None)
        if ip is None:
            key, base = exp.orchestrator.key, svc.name.split(".")[-1]
        elif ip in owners:
            key, base = owners[ip], svc.name[len(ip) + 1:]
        else:
            continue  # a daemon this experiment doesn't use
        if base in config_services(exp.configs[profile][key]):
            wanted.append(svc.name)
    if not wanted:
        return
    for name in wanted:
        log(f"starting {name}, which was stopped by request")
        client.restart_service(name)
    deadline = time.monotonic() + timeout
    next_progress = time.monotonic() + PROGRESS_INTERVAL
    while True:
        try:
            listed = {s.name: s for s in client.list_services().services}
        except grpc.RpcError:
            listed = {}
        waiting = [n for n in wanted if not (n in listed and listed[n].running)]
        if not waiting:
            return
        if time.monotonic() > deadline:
            errors = "; ".join(f"{n}: {listed[n].error or 'not running'}" if n in listed else f"{n}: not listed" for n in waiting)
            raise TimeoutError(f"service(s) not running after {timeout:.0f}s: {errors}")
        if time.monotonic() >= next_progress:
            log(f"still waiting for {', '.join(waiting)} to run")
            next_progress = time.monotonic() + PROGRESS_INTERVAL
        time.sleep(1)


def wait_registered(client: Daemon, d: DaemonCfg, timeout: float = READY_TIMEOUT):
    """Waits for remote d to be registered with the orchestrator, and returns
    its listing."""
    deadline = time.monotonic() + timeout
    logged = False
    last = "not listed"
    while True:
        try:
            remote, last = find_remote(client.list_services(), d, include_failed=True), "not listed"
        except grpc.RpcError as e:
            remote, last = None, f"ListServices: {e.code().name} {e.details()}"
        if remote is not None:
            return remote
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"remote {d.key} didn't register with the orchestrator within {timeout:.0f}s "
                f"({last}); it can only be configured through the orchestrator it is locked to"
            )
        if not logged:
            if last.startswith("ListServices"):
                log(f"waiting for remote {d.key}: can't reach the orchestrator's daemon at {client.socket} ({last})")
            else:
                log(f"waiting for remote {d.key} to register with the orchestrator")
            logged = True
        time.sleep(1)


def configure_daemons(client: Daemon, exp: Experiment, profile: str) -> None:
    """Restarts each remote, then the orchestrator, with its config for the
    profile, first installing any packages the config needs that the daemon
    doesn't have, and saving the daemon's own config for restore_configs. A
    remote is locked to the orchestrator, so it is configured through it, once
    it has registered."""
    configs = exp.configs[profile]
    for d in exp.remotes:
        config = configs[d.key]
        remote = wait_registered(client, d)
        save_original(client, d.key, route=remote.ip)
        install_packages(client, d.key, config, route=remote.ip)
        log(f"configuring remote {d.key} ({remote.ip}) through the orchestrator with {config.name}")
        client.configure(config.read_text(), route=remote.ip)
    o = exp.orchestrator
    save_original(client, o.key)
    install_packages(client, o.key, configs[o.key])
    log(f"configuring orchestrator {o.key} with {configs[o.key].name}")
    client.configure(configs[o.key].read_text())


def original_path(key: str) -> Path:
    return ORIGINALS_DIR / f"{key}.toml"


def save_original(client: Daemon, key: str, route: str | None = None) -> None:
    """Saves daemon key's config, before an experiment config replaces it,
    unless a run that didn't restore it already saved it."""
    path = original_path(key)
    if path.exists():
        log(f"{key}'s own config is still saved from a run that didn't restore it ({path}); keeping it")
        return
    text = client.get_configuration(route)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.replace(path)
    log(f"saved {key}'s own config to {path}")


def restore_configs(client: Daemon, exp: Experiment) -> None:
    """Configures each daemon whose own config was saved with it again, the
    remotes first, through the orchestrator, then the orchestrator, and waits
    for them to come back. That also ends the trial's flow or mission, so no
    engine keeps working (or logging) for it. A config that can't be restored
    stays saved, for the next run to restore.

    The services stop_services stopped are restarted first, while the
    experiment configs (which have them all) still run: being stopped by
    request lasts across reconfigures, so one the restored config doesn't
    have would stay marked stopped on the daemon, and start stopped under a
    later config that has it. They have no flow, so they don't do anything
    before the restore restarts them again."""
    restart_stopped_by_runner(client)
    remotes = [d for d in exp.remotes if original_path(d.key).exists()]
    o = exp.orchestrator
    if not remotes and not original_path(o.key).exists():
        restart_stopped_by_runner(client)
        return
    restored: list[DaemonCfg] = []
    for d in remotes:
        path = original_path(d.key)
        try:
            remote = wait_registered(client, d, timeout=60)
            log(f"restoring remote {d.key}'s own config through the orchestrator")
            client.configure(path.read_text(), route=remote.ip)
            path.unlink()
            restored.append(d)
        except (grpc.RpcError, TimeoutError, OSError) as e:
            details = f"{e.code().name} {e.details()}" if isinstance(e, grpc.RpcError) else str(e)
            log(f"warning: couldn't restore {d.key}'s own config ({details}); it is still saved in {path}")
    path = original_path(o.key)
    if path.exists():
        try:
            log(f"restoring orchestrator {o.key}'s own config")
            client.configure(path.read_text())
            path.unlink()
            restored.append(o)
        except (grpc.RpcError, OSError) as e:
            details = f"{e.code().name} {e.details()}" if isinstance(e, grpc.RpcError) else str(e)
            log(f"warning: couldn't restore {o.key}'s own config ({details}); it is still saved in {path}")
    if restored:
        time.sleep(2)  # let a restarting daemon go down before polling it
        try:
            for d in exp.remotes:
                wait_registered(client, d)
            log("daemons are back on their own configs")
        except TimeoutError as e:
            log(f"warning: {e}")
    restart_stopped_by_runner(client)


def experiment_services(resp: daemon_pb2.ListServicesResponse, exp: Experiment) -> list:
    """The services of the experiment's daemons (the orchestrator and its
    remotes) in a ListServices response; other remotes' are left out."""
    remote_ips = {r.ip for r in resp.remotes if r.ip}
    ours = {listed.ip for d in exp.remotes if (listed := find_remote(resp, d, include_failed=True)) is not None}
    services = []
    for svc in resp.services:
        ip = next((i for i in remote_ips if svc.name.startswith(i + ".")), None)
        if ip is None or ip in ours:
            services.append(svc)
    return services


def stop_services(client: Daemon, exp: Experiment) -> None:
    """Stops every running service of the experiment's daemons, the vehicles
    first, so that nothing writes to the files that are collected next. They
    are recorded in STOPPED_FILE first, for restart_stopped_by_runner."""
    services = [s for s in experiment_services(client.list_services(), exp) if not s.stopped]
    order = {daemon_pb2.SERVICE_CATEGORY_VEHICLE: 0, daemon_pb2.SERVICE_CATEGORY_ENGINE: 1}
    services.sort(key=lambda s: order.get(s.category, 2))
    if not services:
        return
    names = [s.name for s in services]
    recorded = json.loads(STOPPED_FILE.read_text()) if STOPPED_FILE.exists() else []
    STOPPED_FILE.parent.mkdir(parents=True, exist_ok=True)
    STOPPED_FILE.write_text(json.dumps(sorted(set(recorded) | set(names))))
    log(f"stopping {len(names)} service(s) before collecting: {', '.join(names)}")
    for name in names:
        try:
            client.stop_service(name)
        except grpc.RpcError as e:
            log(f"warning: couldn't stop {name}: {e.code().name} {e.details()}")


def restart_stopped_by_runner(client: Daemon) -> None:
    """Restarts the services stop_services stopped that are still stopped,
    which clears their stopped by request mark. A service that isn't listed
    (its daemon's config doesn't have it) is skipped."""
    if not STOPPED_FILE.exists():
        return
    try:
        names = json.loads(STOPPED_FILE.read_text())
        listed = {s.name: s for s in client.list_services().services}
        todo = [n for n in names if n in listed and listed[n].stopped]
        for name in todo:
            client.restart_service(name)
        if todo:
            log(f"restarted {len(todo)} service(s) the runner had stopped, so none stays marked stopped: {', '.join(todo)}")
        STOPPED_FILE.unlink()
    except grpc.RpcError as e:
        log(
            f"warning: couldn't restart the services the runner stopped ({e.code().name} {e.details()}); "
            f"they are listed in {STOPPED_FILE}, for the next run to restart"
        )


def push_files(client: Daemon, exp: Experiment) -> None:
    """Pushes the experiment's files and its video, if any, to every daemon's
    files directory (STEELEAGLE_FILES): the orchestrator's and each remote's,
    through the orchestrator, or with rsync if the remote isn't registered.
    Each file is saved as its push_as, if set; the video as the phase's
    push_as, so the driver's config can name one file for every video. With
    no_upload, the video is not pushed: it is assumed to already be there."""
    phase = exp.phase
    pushes = list(exp.files)
    if phase.video and not phase.no_upload:
        pushes.append(PushFile(phase.video, phase.push_as or phase.video.name))
    if not pushes:
        return
    try:
        listing = client.list_services()
    except grpc.RpcError:
        listing = None
    for f in pushes:
        what = f.path.name + (f" as {f.name}" if f.name != f.path.name else "")
        for d in exp.remotes:
            remote = find_remote(listing, d) if listing else None
            if remote is not None:
                log(f"pushing {what} to remote {d.key} ({remote.ip}) through the orchestrator")
                client.transfer_file(f.path, route=remote.ip, name=f.name)
            elif d.ssh_host:
                log(f"remote {d.key} not registered; pushing {what} to it with rsync")
                files_dir = REMOTE_FILES_DIR.rstrip("/")
                dest = files_dir + "/" + f.name
                # The remote makes the files directory before its rsync starts
                # (rsync's --mkpath needs 3.2.3+ on both ends)
                cmd = [
                    *rsync_cmd(d.ssh_host), "-a",
                    f"--rsync-path=mkdir -p {shlex.quote(files_dir)} && rsync",
                    str(f.path), f"{d.ssh_host}:{dest}",
                ]
                subprocess.run(cmd, check=True)
            else:
                raise RuntimeError(f"remote {d.key} is not registered with the orchestrator and has no prefix to rsync to")
        log(f"pushing {what} to orchestrator {exp.orchestrator.key}")
        client.transfer_file(f.path, name=f.name)


# --------------------------------------------------------------------------
# File collection
# --------------------------------------------------------------------------


def source_files(exp: Experiment, src: str) -> tuple[DaemonCfg, list[str]]:
    """The daemon whose host holds result or catalog src, and the paths of the files
    (or directories) it names there: those its glob matches, or a
    directory's entries, as they are collected."""
    host, _, rest = src.partition("/")
    d = exp.daemons[host]
    path = "/" + rest
    if not d.prefix:
        if glob.has_magic(path):
            return d, sorted(glob.glob(path))
        if os.path.isdir(path):
            return d, sorted(os.path.join(path, n) for n in os.listdir(path) if not n.startswith("."))
        return d, [path] if os.path.exists(path) else []
    if glob.has_magic(path):
        expand = f"set -- {path}"  # the remote shell expands the glob
    else:
        q = shlex.quote(path)
        expand = f"if [ -d {q} ]; then set -- {q}/*; else set -- {q}; fi"
    script = f'{expand}; for f in "$@"; do [ -e "$f" ] && printf "%s\\0" "$f"; done; true'
    r = subprocess.run(ssh(d.ssh_host, script), capture_output=True, check=True)
    return d, sorted(p for p in r.stdout.decode().split("\0") if p)


def deferred_files(exp: Experiment) -> dict[str, set[str]]:
    """The files each defer_pull catalog names now, before a trial, so that only
    the ones the trial adds are renamed after it."""
    return {key: set(source_files(exp, exp.catalogs[key])[1]) for key in sorted(exp.defer_pull)}


def defer_pull(exp: Experiment, key: str, before: set[str], profile: str, trial: int) -> None:
    """Moves the files catalog key gained during the trial into
    <experiment>_<profile>_<trial>_<key>/ in the files directory
    (STEELEAGLE_FILES) of the host that holds them, to be transferred later.
    They are moved out of the engine's own directory, since an engine may
    empty that when it starts (detection_log does, with refresh), which it
    does on every daemon restart. If the directory exists already (from an
    earlier run), a new one with the time added is used. A file whose name is
    taken in it is left where it is, with a warning."""
    d, paths = source_files(exp, exp.catalogs[key])
    moves = [p for p in paths if p not in before]
    if not moves:
        log(f"warning: {key} has no new files on {d.key} to move")
        return
    name = f"{exp.name}_{profile}_{trial}_{key}"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if d.prefix:
        files_dir = '"$HOME"/' + shlex.quote(REMOTE_FILES_DIR.rstrip("/"))
        script = (
            f"set -e\nd={files_dir}/{shlex.quote(name)}\n"
            f'if [ -e "$d" ]; then d="$d-{stamp}"; fi\n'
            'mkdir -p "$d"\necho "$d"\nset +e\n'
        ) + "".join(
            f'b=$(basename -- {shlex.quote(p)}); '
            f'if [ -e "$d/$b" ]; then echo "taken $d/$b"; else mv -- {shlex.quote(p)} "$d/$b"; fi\n'
            for p in moves
        )
        # Sent on stdin, since a long list of files can be over the command
        # line's limit
        r = subprocess.run(ssh(d.ssh_host, "sh -s"), input=script.encode(), capture_output=True)
        out = r.stdout.decode().splitlines()
        if r.returncode != 0 or not out:
            raise RuntimeError(f"moving {key} on {d.key} failed: {r.stderr.decode().strip()}")
        dest, taken = out[0], [line[len("taken "):] for line in out[1:] if line.startswith("taken ")]
    else:
        target = Path.home() / REMOTE_FILES_DIR / name
        if target.exists():
            target = target.with_name(f"{name}-{stamp}")
        target.mkdir(parents=True)
        dest, taken = str(target), []
        for p in moves:
            new = target / os.path.basename(p)
            if new.exists():
                taken.append(str(new))
            else:
                shutil.move(p, new)
    log(f"deferred {key}: moved {len(moves) - len(taken)} file(s) on {d.key} to {dest}, to be transferred later")
    if taken:
        log(f"warning: {len(taken)} file(s) of {key} weren't moved, since their name is taken in {dest} (e.g. {taken[0]})")


def rsync(exp: Experiment, src: str, dest: Path, move: bool) -> None:
    host, _, rest = src.partition("/")
    d = exp.daemons[host]
    path = "/" + rest
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [*rsync_cmd(d.ssh_host), "-a"] if d.prefix else ["rsync", "-a"]
    if move:
        cmd.append("--remove-source-files")
    # A directory's contents are collected, not the directory itself.
    # ssh and rsync are not captured, so their prompts (host key, password)
    # and errors reach the user's terminal.
    if d.prefix:
        if not glob.has_magic(path):
            test = ssh(d.ssh_host, f"test -d {shlex.quote(path)}")
            if subprocess.run(test).returncode == 0:
                path = path.rstrip("/") + "/"
        sources = [d.prefix + path]  # the remote shell expands globs
    else:
        sources = sorted(glob.glob(path))
        if not sources:
            log(f"warning: nothing matches {path}")
            return
        if len(sources) == 1 and not glob.has_magic(path) and os.path.isdir(sources[0]):
            sources = [sources[0].rstrip("/") + "/"]
    r = subprocess.run(cmd + sources + [str(dest) + "/"])
    if r.returncode:
        log(f"warning: rsync of {src} exited {r.returncode}")


# --------------------------------------------------------------------------
# netsim
# --------------------------------------------------------------------------


def sudo_validate() -> None:
    """Caches sudo credentials for netsim, asking for a password if needed."""
    if subprocess.run(["sudo", "-v"]).returncode:
        raise SystemExit("netsim needs root: sudo failed")


class Netsim:
    """netsim, run for one trial. Under the none and ambient profiles it
    isn't run at all: the trial runs unattenuated. Under none, it has no
    timeline; under ambient, its timeline is the iperf3 measurement, ending
    at timeline_end."""

    def __init__(self, exp: Experiment, profile: str, trial_dir: Path):
        self.timeline = trial_dir / "timeline.csv"
        self.output = trial_dir / "netsim.log"
        self.enabled = profile not in NO_NETSIM
        self.profile = profile
        self.timeline_end: float | None = None
        cmd = [
            sys.executable, "-u", str(NETSIM),
            "-i", exp.interface, "-p", str(exp.port),
            "--profile", profile, "--log", str(self.timeline),
            *exp.netsim_args,
        ]
        if profile in ("malicious", "outage") and exp.failpoints:
            cmd += ["--failpoints", exp.failpoints]
        if os.geteuid() != 0 and "--dry-run" not in exp.netsim_args:
            cmd = ["sudo", "-n"] + cmd
        self.needs_sudo = self.enabled and cmd[0] == "sudo"
        self.cmd = cmd
        self.proc: subprocess.Popen | None = None
        self.out = None

    def start(self) -> None:
        if not self.enabled:
            log(f"{self.profile} profile: running without netsim")
            return
        if self.needs_sudo:
            sudo_validate()  # refresh the cached credentials the -n above relies on
        self.out = open(self.output, "w")
        self.proc = subprocess.Popen(self.cmd, stdout=self.out, stderr=subprocess.STDOUT)
        log(f"netsim started (pid {self.proc.pid})")

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            # SIGINT makes netsim print its totals and tear down its tc state
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)
        else:
            log(f"warning: netsim exited early with code {self.proc.returncode}; see {self.output}")
        self.out.close()
        self.proc = None
        log("netsim stopped")


def parse_netsim_summary(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    patterns = {
        "elapsed_sec": r"totals over ([\d.]+) s",
        "delivered_bytes": r"delivered through shaper\s*:.*?\((\d+) bytes",
        "dropped_off_bytes": r"dropped while port off\s*:.*?\((\d+) bytes",
        "dropped_queue_pkts": r"dropped by shaper queue\s*:\s*(\d+) pkts",
        "total_arrived_bytes": r"total arrived on port\s*:.*?\((\d+) bytes",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            out[key] = float(m.group(1))
    return out


def read_timeline(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def weighted_percentile(samples: list[tuple[float, float]], q: float) -> float:
    """Percentile of (value, weight) samples, i.e. of the time-weighted rate."""
    samples = sorted(samples)
    total = sum(w for _, w in samples)
    acc = 0.0
    for v, w in samples:
        acc += w
        if acc >= q * total:
            return v
    return samples[-1][0]


def timed_samples(rows: list[dict[str, str]], column: str, end: float) -> list[tuple[float, float]]:
    """(value, seconds) samples of a timeline column: each row's value holds
    until the next row (or the end of the run). Rows that leave the column
    empty are skipped."""
    timeline = [(float(r["t_sec"]), float(r[column])) for r in rows if r.get(column)]
    samples = []
    for i, (t, v) in enumerate(timeline):
        t_next = timeline[i + 1][0] if i + 1 < len(timeline) else max(end, t)
        if t_next > t:
            samples.append((v, t_next - t))
    return samples or [(v, 1.0) for _, v in timeline]


def summarize(samples: list[tuple[float, float]], prefix: str, unit: str) -> dict[str, float]:
    if not samples:
        return {}
    total = sum(w for _, w in samples)
    return {
        f"{prefix}_mean_{unit}": sum(v * w for v, w in samples) / total,
        f"{prefix}_median_{unit}": weighted_percentile(samples, 0.5),
        f"{prefix}_p95_{unit}": weighted_percentile(samples, 0.95),
        f"{prefix}_min_{unit}": min(v for v, _ in samples),
        f"{prefix}_max_{unit}": max(v for v, _ in samples),
    }


def bandwidth_stats(rows: list[dict[str, str]], end: float) -> dict[str, float]:
    """Time-weighted statistics of the bandwidth allowed (by netsim, or, for
    ambient, measured by iperf3) and of the delay netsim added."""
    bw = timed_samples(rows, "applied_kbps", end)
    stats = summarize(bw, "bandwidth", "kbps")
    if bw:
        stats["time_off_sec"] = sum(w for v, w in bw if v == 0)
    stats.update(summarize(timed_samples(rows, "delay_ms", end), "delay", "ms"))
    return stats


STATS_COLUMNS = [
    "trial", "duration_sec",
    "total_bytes_delivered", "total_bytes_dropped_while_off", "total_bytes_arrived",
    "pkts_dropped_by_queue",
    "bandwidth_mean_kbps", "bandwidth_median_kbps", "bandwidth_p95_kbps",
    "bandwidth_min_kbps", "bandwidth_max_kbps", "time_off_sec",
    "delay_mean_ms", "delay_median_ms", "delay_p95_ms", "delay_min_ms", "delay_max_ms",
]
TIMELINE_COLUMNS = ["trial", "t_sec", "drawn_kbps", "applied_kbps", "state", "delay_ms"]


def append_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    """Appends rows to a CSV, writing the header first if the file is new, so
    the trials finished so far are saved even if a later one fails."""
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def fmt(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def write_stats(run_dir: Path, netsim: Netsim, label: str, trial: int, wall_sec: float) -> None:
    """Adds the trial's row to stats_<label>.csv and its timeline to
    timeline_<label>.csv, where the label is <profile>_<experiment>."""
    summary = parse_netsim_summary(netsim.output.read_text() if netsim.output.is_file() else "")
    end = summary.get("elapsed_sec", wall_sec)
    timeline = read_timeline(netsim.timeline)
    stats = {
        "trial": trial,
        "duration_sec": round(end, 3),
        "total_bytes_delivered": summary.get("delivered_bytes", ""),
        "total_bytes_dropped_while_off": summary.get("dropped_off_bytes", ""),
        "total_bytes_arrived": summary.get("total_arrived_bytes", ""),
        "pkts_dropped_by_queue": summary.get("dropped_queue_pkts", ""),
        **{
            k: round(v, 3)
            for k, v in bandwidth_stats(
                timeline, netsim.timeline_end if netsim.timeline_end is not None else end,
            ).items()
        },
    }
    append_csv(run_dir / f"stats_{label}.csv", STATS_COLUMNS, [{k: fmt(v) for k, v in stats.items()}])
    append_csv(run_dir / f"timeline_{label}.csv", TIMELINE_COLUMNS, [{"trial": trial, **r} for r in timeline])
    if "delay_mean_ms" in stats:
        summary_text = (
            f"delay mean {stats['delay_mean_ms']} / median {stats['delay_median_ms']} / "
            f"p95 {stats['delay_p95_ms']} ms"
        )
    elif not netsim.enabled and netsim.timeline_end is None:
        summary_text = "unattenuated"
    else:
        summary_text = (
            f"mean {stats.get('bandwidth_mean_kbps', '?')} / median {stats.get('bandwidth_median_kbps', '?')} / "
            f"p95 {stats.get('bandwidth_p95_kbps', '?')} Kbps"
        )
    log(f"stats ({label}, trial {trial}): {stats['total_bytes_delivered']} bytes delivered, {summary_text}")


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


def wait_for(duration: float, what: str) -> float:
    """Waits for duration seconds, or for ENTER if it is 0. Returns seconds
    waited."""
    t0 = time.monotonic()
    if duration > 0:
        log(f"running {what} for {duration:g}s")
        time.sleep(duration)
    else:
        input(f"Running {what}. Press ENTER to stop... ")
    return time.monotonic() - t0


def toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)  # a JSON string is a valid TOML basic string
    raise ValueError(f"can't write {v!r} into a flow")


def flow_toml(flow: dict) -> bytes:
    """A flow (its arrays of tables of scalars) as TOML."""
    lines = []
    for key, tables in flow.items():
        if not isinstance(tables, list) or not all(isinstance(t, dict) for t in tables):
            raise ValueError(f"flow key {key!r} isn't an array of tables")
        for t in tables:
            lines.append(f"[[{key}]]")
            lines += [f"{k} = {toml_value(v)}" for k, v in t.items()]
            lines.append("")
    return "\n".join(lines).encode()


def qualify_flow(client: Daemon, flow_bytes: bytes, vehicle: str) -> bytes:
    """The flow with each bare engine name replaced by the qualified name of
    the engine service that runs it, as uriel needs: for a local engine, the
    one on the vehicle's daemon (<vehicle's ip>.<name>), and for a remote
    engine, the only one of that name on another daemon. Edges are renamed to
    match. A name that is already a service's is kept, as is any name with a
    dot in it; a bare name that matches no engine, or more than one, is an
    error."""
    flow = tomllib.loads(flow_bytes.decode())
    engines = [
        s.name for s in client.list_services().services
        if s.category == daemon_pb2.SERVICE_CATEGORY_ENGINE
    ]
    vehicle_ip = vehicle.rsplit(".", 1)[0]
    names: dict[str, str] = {}
    for e in flow.get("engines", []):
        name, location = e.get("name", ""), e.get("location", "local")
        if name in engines or "." in name:
            continue
        if location == "local":
            matches = [n for n in engines if n == f"{vehicle_ip}.{name}"]
            where = f"on the vehicle's daemon ({vehicle_ip})"
        else:
            matches = [n for n in engines if n.endswith("." + name) and not n.startswith(vehicle_ip + ".")]
            where = "on a daemon other than the vehicle's"
        if len(matches) != 1:
            found = ", ".join(n for n in engines if n.endswith("." + name)) or "none"
            raise RuntimeError(
                f"{location} engine {name!r} of the flow: "
                + ("no engine service of that name runs " if not matches else f"{len(matches)} engine services of that name run ")
                + f"{where} (engines named {name!r}: {found})"
            )
        names[name] = matches[0]
    if not names:
        return flow_bytes
    for e in flow.get("engines", []):
        e["name"] = names.get(e["name"], e["name"])
    for edge in flow.get("edges", []):
        for end in ("from", "to"):
            if end in edge:
                edge[end] = names.get(edge[end], edge[end])
    log("flow engines: " + ", ".join(f"{k} -> {v}" for k, v in names.items()))
    return flow_toml(flow)


def new_run_dir(exp: Experiment, profile: str) -> Path:
    run_dir = exp.dir / "runs" / exp.name / profile
    if run_dir.exists():
        run_dir = run_dir.with_name(f"{profile}-{datetime.now():%Y%m%d-%H%M%S}")
    run_dir.mkdir(parents=True)
    return run_dir


def cleanup(
    exp: Experiment, run_dir: Path, trial_dir: Path, netsim: Netsim, label: str, profile: str, trial: int,
    wall_sec: float, deferred_before: dict[str, set[str]], started: bool = True,
) -> None:
    netsim.stop()
    for key, src in exp.results.items():
        log(f"moving {key} from {src}")
        rsync(exp, src, trial_dir / "result" / key, move=True)
    for key, src in exp.catalogs.items():
        if key in exp.defer_pull:
            defer_pull(exp, key, deferred_before.get(key, set()), profile, trial)
            continue
        log(f"copying {key} from {src}")
        rsync(exp, src, trial_dir / "catalog" / key, move=False)
    if started:
        write_stats(run_dir, netsim, label, trial, wall_sec)
    else:
        log("the trial didn't start, so no stats are written for it")
    log(f"trial saved to {trial_dir}")


def describe(phase: Phase) -> str:
    if phase.video:
        return f"video {phase.video.name}, flow {phase.file.name}"
    return f"mission {phase.file.name}"


def netsim_direction(exp: Experiment) -> str:
    """The direction netsim shapes, from its --direction arg, if given."""
    args = exp.netsim_args
    for i, a in enumerate(args):
        if a == "--direction" and i + 1 < len(args):
            return args[i + 1]
        if a.startswith("--direction="):
            return a.split("=", 1)[1]
    return "ingress"


def measure_ambient(client: Daemon, exp: Experiment, vehicle: str, trial_dir: Path) -> float:
    """For the ambient profile: stops the vehicle, so it sends nothing, and
    measures the link between its host and this one with iperf3, in the
    direction netsim would shape (by default, from the vehicle's host to
    here). The vehicle is restarted afterwards, even if the measurement
    fails. The per-second throughput is written to trial_dir/timeline.csv, as
    netsim would write its timeline, and iperf3's report to iperf3.json.
    Returns the end of the measurement, in seconds."""
    listing = client.list_services()
    remote = next(
        (r for r in listing.remotes if not r.error and r.ip and vehicle.startswith(r.ip + ".")), None,
    )
    if remote is None:
        raise RuntimeError(
            f"ambient: vehicle {vehicle} doesn't run on a registered remote daemon, "
            f"so there is no link to measure"
        )
    host = next(
        (d for d in exp.remotes if (r := find_remote(listing, d)) is not None and r.ip == remote.ip), None,
    )
    if host is None or not host.ssh_host:
        raise RuntimeError(
            f"ambient: the daemon at {remote.ip} ({remote.hostname}), which runs {vehicle}, "
            f"needs a [daemons] entry with a prefix, to start iperf3 on it over ssh"
        )

    log(f"ambient: stopping {vehicle}")
    client.stop_service(vehicle)
    try:
        report = run_iperf(exp, host, remote.ip, trial_dir)
    finally:
        log(f"ambient: restarting {vehicle}")
        client.restart_service(vehicle)

    rows, end = [], 0.0
    for interval in report.get("intervals", []):
        sums = interval.get("sum", {})
        if "start" not in sums:
            continue
        kbps = round(sums.get("bits_per_second", 0.0) / 1000, 1)
        rows.append({
            "t_sec": f"{sums['start']:.3f}", "drawn_kbps": kbps, "applied_kbps": kbps,
            "state": AMBIENT, "delay_ms": "",
        })
        end = max(end, float(sums.get("end", sums["start"])))
    if not rows:
        raise RuntimeError(f"ambient: iperf3 reported no intervals; see {trial_dir / 'iperf3.json'}")
    with open(trial_dir / "timeline.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TIMELINE_COLUMNS[1:])
        w.writeheader()
        w.writerows(rows)
    mean = sum(float(r["applied_kbps"]) for r in rows) / len(rows)
    log(f"ambient: measured {mean:.1f} Kbps on average over {end:g}s")
    return end


def run_iperf(exp: Experiment, host: DaemonCfg, ip: str, trial_dir: Path) -> dict:
    """Starts a one-off iperf3 server on host over ssh, and runs the client
    here against it at ip. Returns the client's JSON report, also saved to
    trial_dir/iperf3.json."""
    port = exp.iperf_port
    # -R makes the server (the vehicle's host) send, as for ingress shaping
    reverse = ["-R"] if netsim_direction(exp) == "ingress" else []
    client_cmd = [
        "iperf3", "-c", ip, "-p", str(port), "-t", f"{exp.iperf_duration:g}", "-i", "1", "-J", *reverse,
    ]
    log(
        f"ambient: measuring {'from' if reverse else 'to'} {host.key} ({ip}) with iperf3 "
        f"on port {port} for {exp.iperf_duration:g}s"
    )
    with open(trial_dir / "iperf3_server.log", "w") as server_log:
        # -1: the server exits after one test
        server = subprocess.Popen(
            ssh(host.ssh_host, f"{REMOTE_PATH} iperf3 -s -1 -p {port}"),
            stdout=server_log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                time.sleep(1)  # let the server start listening
                try:
                    r = subprocess.run(
                        client_cmd, capture_output=True, text=True, timeout=exp.iperf_duration + 60,
                    )
                except FileNotFoundError:
                    raise RuntimeError("ambient: iperf3 is not installed here") from None
                try:
                    report = json.loads(r.stdout)
                except ValueError:
                    report = {"error": (r.stderr or r.stdout).strip()}
                if r.returncode == 0 and "error" not in report:
                    break
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(
                        f"ambient: iperf3 failed: {report.get('error')}"
                        + (
                            f" (the server on {host.key} exited {server.returncode}; "
                            f"see {trial_dir / 'iperf3_server.log'})"
                            if server.poll() is not None else ""
                        )
                    )
        finally:
            if server.poll() is None:
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.terminate()
                    server.wait(timeout=10)
    (trial_dir / "iperf3.json").write_text(json.dumps(report, indent=2))
    return report


def run_trial(
    client: Daemon, exp: Experiment, vehicle: str, profile: str, run_dir: Path, trial: int,
    deferred_before: dict[str, set[str]],
) -> None:
    """Runs one trial into run_dir/trial_<n>, adding its stats to
    run_dir/stats_<profile>_<experiment>.csv. deferred_before is what each
    defer_pull result held before the trial (deferred_files)."""
    phase = exp.phase
    label = f"{profile}_{exp.name}"
    trial_dir = run_dir / f"trial_{trial}"
    trial_dir.mkdir(parents=True)
    netsim = Netsim(exp, profile, trial_dir)
    what = f"profile {profile}, trial {trial}/{exp.trials}"
    log(f"=== {exp.name}: {what} ({describe(phase)}) ===")

    if profile == AMBIENT:
        netsim.timeline_end = measure_ambient(client, exp, vehicle, trial_dir)
        vehicle = client.wait_ready(exp.vehicle, exp.remotes)
        log(f"vehicle restarted; targeting {vehicle}")

    if phase.kind == "mission":
        if phase.no_upload:
            log(f"loading {phase.file.name} on {vehicle} (not uploaded)")
        else:
            log(f"uploading and loading {phase.file.name} on {vehicle}")
            client.upload_mission(phase.file, vehicle)
        client.load_mission(phase.file.name, vehicle)
    flow = qualify_flow(client, phase.file.read_bytes(), vehicle) if phase.kind == "video" else b""
    if not phase.auto:
        input(f"[{exp.name} {profile} {trial}/{exp.trials}] Press ENTER to start the {phase.kind}... ")

    wall = 0.0
    started = False
    try:
        if phase.kind == "mission":
            client.start_mission(vehicle)
        else:
            client.set_dataflow(flow, vehicle)
        started = True
        netsim.start()
        log(f"{phase.kind} started")
        wall = wait_for(phase.duration, f"{phase.kind} under {what}")
    finally:
        if phase.kind == "mission":
            for name, call in (("Hold", client.hold), ("StopMission", client.stop_mission)):
                try:
                    call(vehicle)
                    log(f"{name} sent")
                except grpc.RpcError as e:
                    log(f"warning: {name} failed: {e.code().name} {e.details()}")
        # Nothing may write to the files while they are collected
        try:
            stop_services(client, exp)
        except grpc.RpcError as e:
            log(f"warning: couldn't stop the services: {e.code().name} {e.details()}")
        cleanup(exp, run_dir, trial_dir, netsim, label, profile, trial, wall, deferred_before, started)


def run_experiment(client: Daemon, exp: Experiment) -> None:
    phase = exp.phase
    log(
        f"### experiment {exp.name} ({exp.dir}): {describe(phase)}"
        + (" (not uploaded)" if phase.no_upload else "")
        + f", profiles {', '.join(exp.profiles)}, "
        + (f"files {', '.join(f.path.name for f in exp.files)}, " if exp.files else "")
        + f"{exp.trials} trial(s) each"
    )
    if phase.duration_from_video:
        log(f"video {phase.video.name} is {phase.duration:g}s long; each trial runs that long")
    for profile in exp.profiles:
        run_dir = new_run_dir(exp, profile)
        for trial in range(1, exp.trials + 1):
            # Each trial starts from freshly restarted daemons, so no state
            # (like a running flow) carries over from the previous one.
            # Pushed before the daemons restart, so the vehicle's driver
            # finds the files and video when it starts, even if the previous
            # trial's result collection moved them away
            # However the trial ends (its duration is up, ENTER, Ctrl-C or
            # an error), each daemon gets its own config back
            try:
                # Taken before the daemons restart, since an engine may
                # write its files as soon as it starts
                deferred_before = deferred_files(exp)
                push_files(client, exp)
                configure_daemons(client, exp, profile)
                time.sleep(2)  # let the orchestrator go down before polling it
                vehicle = client.wait_ready(exp.vehicle, exp.remotes)
                start_stopped_services(client, exp, profile)
                log(f"daemons ready; targeting {vehicle}")
                run_trial(client, exp, vehicle, profile, run_dir, trial, deferred_before)
            finally:
                restore_configs(client, exp)
        log(f"profile {profile} saved to {run_dir}")
    log(f"experiment {exp.name} saved to {exp.dir / 'runs' / exp.name}")


def find_experiment_dirs(root: Path) -> list[Path]:
    dirs = sorted(p for p in root.iterdir() if (p / EXPERIMENT_FILE).is_file())
    if not dirs:
        raise SystemExit(f"no experiment directories (with {EXPERIMENT_FILE}) in {root}")
    return dirs


def list_experiments(exp_dir: Path, names: list[str] | None = None) -> None:
    """Prints the experiments in exp_dir's experiment.toml. Only the toml is
    read: the files it names are not checked."""
    tables = experiment_tables(exp_dir, read_toml(exp_dir), names)
    rows = [("NAME", "KIND", "RUNS", "VEHICLE", "PROFILES", "TRIALS")]
    for t in tables:
        mission, video, ns = (t.get(k) if isinstance(t.get(k), dict) else {} for k in ("mission", "video", "netsim"))
        if mission.get("file"):
            kind, runs = "mission", str(mission["file"])
        elif video.get("video") or video.get("flow"):
            kind, runs = "video", f"{video.get('video') or '?'} (flow {video.get('flow') or '?'})"
        else:
            kind, runs = "?", "(no mission or video set)"
        profiles = ns.get("profiles", ["*"])
        profiles = "all" if "*" in profiles else ",".join(map(str, profiles))
        rows.append((t["name"], kind, runs, str(t.get("vehicle", "")), profiles, str(ns.get("trials", 1))))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    print(f"{exp_dir}:")
    for r in rows:
        print("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())


def main():
    ap = argparse.ArgumentParser(description="Run SteelEagle experiments.")
    ap.add_argument("path", type=Path, help="experiment directory (or, with -r, a directory of them)")
    ap.add_argument("-r", "--recursive", action="store_true", help="run every experiment directory inside path")
    ap.add_argument(
        "-e", "--experiment", action="append", dest="experiments", metavar="NAME",
        help="run only the experiment with this name in path's experiment.toml (repeat for several)",
    )
    ap.add_argument(
        "-l", "--list", action="store_true",
        help="list the experiments in path's experiment.toml (with -r, in each directory) and exit",
    )
    ap.add_argument(
        "--update-packages", action="store_true",
        help="reinstall every package the daemons' configs use, once per daemon per run, "
        "to get a branch's latest code (missing packages are always installed)",
    )
    ap.add_argument("--socket", default=default_socket(), help="daemon control socket (default: %(default)s)")
    args = ap.parse_args()
    global UPDATE_PACKAGES
    UPDATE_PACKAGES = args.update_packages
    if args.recursive and args.experiments:
        ap.error("-e picks experiments in one directory's experiment.toml; it can't be used with -r")

    root = args.path.resolve()
    if args.recursive:
        exp_dirs = find_experiment_dirs(root)
    elif (root / EXPERIMENT_FILE).is_file():
        exp_dirs = [root]
    else:
        raise SystemExit(f"{root} has no {EXPERIMENT_FILE} (use -r for a directory of experiments)")

    try:
        if args.list:
            for i, d in enumerate(exp_dirs):
                if i:
                    print()
                list_experiments(d, args.experiments)
            return
        # Check every experiment up front, so a typo doesn't stop a batch midway
        exps = [e for d in exp_dirs for e in load_experiments(d, args.experiments)]
    except ValueError as e:
        raise SystemExit(f"invalid experiment: {e}")

    # Ask for the sudo password now rather than in the middle of a run
    if os.geteuid() != 0 and any(
        "--dry-run" not in e.netsim_args and any(p not in NO_NETSIM for p in e.profiles) for e in exps
    ):
        log("netsim needs root; checking sudo")
        sudo_validate()

    # Ask for each remote's ssh password now too, once
    open_ssh(sorted({d.ssh_host for e in exps for d in e.remotes if d.ssh_host}))

    # A kill or a dropped ssh session exits through the finally blocks too, so
    # netsim is stopped and the daemons get their own configs back
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda signum, _: sys.exit(128 + signum))
    if not Path(args.socket).exists():
        found = sorted(glob.glob("/run/user/*/steeleagle/eagled.sock"))
        raise SystemExit(
            f"no daemon control socket at {args.socket}: the runner talks to the orchestrator's "
            f"eagled through the socket of the user it runs as (the invoking user's, under sudo). "
            + (f"Daemon sockets on this host: {', '.join(found)}; run as that user, or pass --socket."
               if found else "No eagled socket was found on this host; is eagled running here?")
        )
    client = Daemon(args.socket)
    for e in exps:
        run_experiment(client, e)
    log(f"done: {len(exps)} experiment(s)")


if __name__ == "__main__":
    main()
