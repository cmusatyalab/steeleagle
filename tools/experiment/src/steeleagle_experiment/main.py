"""Auto-experiment runner for SteelEagle.

    python -m steeleagle_experiment.main <experiment_dir>
    python -m steeleagle_experiment.main -r <dir_of_experiment_dirs>

An experiment directory holds an experiment.toml (see example/) and every file
it names: the mission, or the videos and their flow, and each daemon's config.
For each netsim profile, for each video (if any), and for each trial, the runner:

  1. pushes the experiment's files and the video, if any, to every daemon's
     files directory (STEELEAGLE_FILES), and restarts the daemons with the
     profile's configs,
  2. starts the mission (upload, load, start) or sets the video's flow on the
     target vehicle, and starts netsim as soon as the vehicle acknowledges it,
  3. waits for the duration (for a video, the video's length unless a
     duration is set), or for ENTER when the duration is 0,
  4. stops the mission (Hold, then StopMission) and netsim, and
  5. collects the trial into <experiment_dir>/runs/<profile>/:
        trial_<n>/result/<key>/   result files, moved off their hosts
        trial_<n>/catalog/<key>/  catalog files, copied
        trial_<n>/timeline.csv    bandwidth netsim allowed over time
        trial_<n>/netsim.log      netsim's output
        stats_<profile>.csv       totals and bandwidth statistics, a row per trial
        timeline_<profile>.csv    every trial's timeline, with a trial column
     For videos, each video's trials go to <video>/trial_<n>/ instead, and its
     CSVs are stats_<profile>_<video>.csv and timeline_<profile>_<video>.csv,
     where <video> is the video's file name without its extension.

Restarting the daemons means every remote daemon and then the local
orchestrator is reconfigured, which restarts it, and the runner waits for the
vehicle to be listed and running. A daemon's config is found by its name in [daemons]: for
daemon "fermi" and profile "normal", fermi_normal.toml is used if it exists;
otherwise the config of the previous profile carries over, or, for the first
profiles, fermi.toml.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import queue
import re
import shlex
import signal
import struct
import subprocess
import sys
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
NETSIM_PROFILES = ["normal", "limited", "degraded", "intermittent", "denied", "malicious"]
ROUTE_HEADER = "x-route-key"
CHUNK_SIZE = 1 << 20  # same chunk size as `eagle transfer-file`
RPC_TIMEOUT = 60.0
READY_TIMEOUT = 300.0
# Daemon files directory (STEELEAGLE_FILES) relative to the home directory,
# for rsyncing a video to a remote that isn't registered
REMOTE_FILES_DIR = ".local/share/steeleagle/files/"


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
# Experiment config
# --------------------------------------------------------------------------


@dataclass
class Phase:
    kind: str  # "mission" or "video"
    file: Path  # the mission, or the video's flow
    auto: bool
    # seconds to run each trial; 0 waits for ENTER. None (video only, when no
    # duration is set) runs each video for its own length, in video_durations
    duration: float | None
    # the videos, for "video": each runs every trial in turn, and is pushed to
    # every daemon under push_as, if set, or its own name
    videos: list[Path] = field(default_factory=list)
    push_as: str = ""
    video_durations: dict[Path, float] = field(default_factory=dict)

    def duration_for(self, video: Path | None) -> float:
        if self.duration is not None:
            return self.duration
        return self.video_durations[video] if video else 0.0


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
    failpoints: str  # netsim --failpoints value, used only by the malicious profile
    trials: int  # runs of each profile
    daemons: dict[str, DaemonCfg]
    configs: dict[str, dict[str, Path]]  # profile -> daemon key -> config file
    # pushed to every daemon's files directory at the start of each trial
    files: list[PushFile] = field(default_factory=list)
    results: dict[str, str] = field(default_factory=dict)
    catalogs: dict[str, str] = field(default_factory=dict)

    @property
    def orchestrator(self) -> DaemonCfg:
        return next(d for d in self.daemons.values() if d.orchestrator)

    @property
    def remotes(self) -> list[DaemonCfg]:
        return [d for d in self.daemons.values() if not d.orchestrator]


def load_experiment(exp_dir: Path) -> Experiment:
    with open(exp_dir / EXPERIMENT_FILE, "rb") as f:
        raw = tomllib.load(f)
    exp = raw.get("experiment", {})
    name = exp.get("name") or exp_dir.name
    vehicle = exp.get("vehicle", "")
    if not vehicle:
        raise ValueError(f"{exp_dir}: experiment.vehicle is not set")

    if exp.get("flow", {}).get("file"):
        raise ValueError(
            f"{exp_dir}: experiment.flow is now experiment.video; set its video "
            f"(the video file) and flow (the flow file) instead of file"
        )

    def exp_file(kind: str, key: str, value: str) -> Path:
        path = exp_dir / value
        if not path.is_file():
            raise ValueError(f"{exp_dir}: experiment.{kind}.{key} file {path} does not exist")
        return path

    def duration(kind: str, sect: dict) -> float | None:
        if "duration" not in sect:
            return None
        d = sect["duration"]
        if not isinstance(d, (int, float)) or isinstance(d, bool) or d < 0:
            raise ValueError(f"{exp_dir}: experiment.{kind}.duration must be a number >= 0, not {d!r}")
        return float(d)

    phases = []
    sect = exp.get("mission", {})
    if sect.get("file"):
        phases.append(Phase(
            "mission", exp_file("mission", "file", sect["file"]),
            bool(sect.get("auto", False)), duration("mission", sect) or 0.0,
        ))
    sect = exp.get("video", {})
    if sect.get("video") or sect.get("flow"):
        if not (sect.get("video") and sect.get("flow")):
            raise ValueError(f"{exp_dir}: experiment.video needs both video and flow set")
        names = sect["video"]
        if isinstance(names, str):
            names = [names]
        if not isinstance(names, list) or not all(isinstance(n, str) and n for n in names):
            raise ValueError(f"{exp_dir}: experiment.video.video must be a file name or a list of them")
        videos = [exp_file("video", "video", n) for n in names]
        stems = [v.stem for v in videos]
        dups = sorted({x for x in stems if stems.count(x) > 1})
        if dups:
            raise ValueError(
                f"{exp_dir}: experiment.video.video names more than one video called "
                f"{', '.join(dups)} (without the extension); their runs would collide"
            )
        push_as = sect.get("push_as", "")
        if not isinstance(push_as, str) or "/" in push_as:
            raise ValueError(f"{exp_dir}: experiment.video.push_as must be a file name, not {push_as!r}")
        phase = Phase(
            "video", exp_file("video", "flow", sect["flow"]),
            bool(sect.get("auto", False)), duration("video", sect),
            videos=videos, push_as=push_as,
        )
        if phase.duration is None:
            # No duration set: each video runs for its own length
            for v in videos:
                try:
                    phase.video_durations[v] = video_length(v)
                except ValueError as e:
                    raise ValueError(
                        f"{exp_dir}: {e}; set experiment.video.duration instead"
                    ) from None
        phases.append(phase)
    if len(phases) != 1:
        raise ValueError(
            f"{exp_dir}: set exactly one of experiment.mission (file) or "
            f"experiment.video (video and flow)"
        )

    files = parse_files(exp.get("files", []), exp_dir, exp_file)
    phase = phases[0]
    if phase.kind == "video":
        video_names = {phase.push_as} if phase.push_as else {v.name for v in phase.videos}
        clash = sorted(video_names & {f.name for f in files})
        if clash:
            raise ValueError(
                f"{exp_dir}: experiment.files pushes {', '.join(clash)}, which a video "
                f"is also pushed as"
            )

    ns = raw.get("netsim", {})
    profiles = ns.get("profiles", ["*"])
    if "*" in profiles:
        profiles = NETSIM_PROFILES
    for p in profiles:
        if p not in NETSIM_PROFILES:
            raise ValueError(f"{exp_dir}: unknown netsim profile {p!r}")
    if "interface" not in ns or "port" not in ns:
        raise ValueError(f"{exp_dir}: netsim.interface and netsim.port must be set")
    # Optional extra netsim flags, e.g. args = ["--direction", "egress", "--seed", "1"]
    netsim_args = [str(a) for a in ns.get("args", [])]
    failpoints = parse_failpoints(ns.get("failpoints", []), exp_dir)
    trials = ns.get("trials", 1)
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        raise ValueError(f"{exp_dir}: netsim.trials must be an integer >= 1, not {trials!r}")

    daemons = {}
    for key, d in raw.get("daemons", {}).items():
        orch = bool(d.get("orchestrator", False))
        if "config" in d:
            raise ValueError(
                f"{exp_dir}: daemons.{key}.config is no longer supported; name the file "
                f"{key}.toml or {key}_<profile>.toml instead"
            )
        if "pass" in d:
            raise ValueError(
                f"{exp_dir}: daemons.{key}.pass is no longer supported; ssh and rsync now "
                f"prompt for the password (and host key checks) on the terminal"
            )
        daemons[key] = DaemonCfg(key, orch, d.get("prefix", ""))
    if sum(d.orchestrator for d in daemons.values()) != 1:
        raise ValueError(f"{exp_dir}: exactly one daemon must have orchestrator = true")

    configs = resolve_configs(exp_dir, list(daemons), list(profiles))

    e = Experiment(
        exp_dir, name, vehicle, phase, list(profiles), ns["interface"], int(ns["port"]),
        netsim_args, failpoints, trials, daemons, configs, files,
        dict(raw.get("results", {})), dict(raw.get("catalogs", {})),
    )
    for table in (e.results, e.catalogs):
        for key, src in table.items():
            host = src.split("/", 1)[0]
            if host not in daemons:
                raise ValueError(f"{exp_dir}: {key} = {src!r} names unknown daemon {host!r}")
    return e


def parse_files(raw, exp_dir: Path, exp_file) -> list[PushFile]:
    """Parses experiment.files: a list of file names in the experiment
    directory, each optionally a table { file = "...", push_as = "..." } to
    push it under another name."""
    if not isinstance(raw, list):
        raise ValueError(f"{exp_dir}: experiment.files must be a list of file names")
    files = []
    for entry in raw:
        if isinstance(entry, str):
            entry = {"file": entry}
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not entry["file"]:
            raise ValueError(
                f"{exp_dir}: invalid experiment.files entry {entry!r}; want a file name "
                f'or {{ file = "...", push_as = "..." }}'
            )
        unknown = set(entry) - {"file", "push_as"}
        if unknown:
            raise ValueError(f"{exp_dir}: experiment.files entry {entry!r} has unknown keys {sorted(unknown)}")
        path = exp_file("files", "file", entry["file"])
        push_as = entry.get("push_as", "") or path.name
        if not isinstance(push_as, str) or "/" in push_as:
            raise ValueError(f"{exp_dir}: experiment.files push_as must be a file name, not {push_as!r}")
        files.append(PushFile(path, push_as))
    names = [f.name for f in files]
    dups = sorted({n for n in names if names.count(n) > 1})
    if dups:
        raise ValueError(f"{exp_dir}: experiment.files pushes more than one file as {', '.join(dups)}")
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


def resolve_configs(exp_dir: Path, keys: list[str], profiles: list[str]) -> dict[str, dict[str, Path]]:
    """Picks each daemon's config for each profile, in profile order:
    <key>_<profile>.toml if it exists, else the config the previous profile
    used, else <key>.toml."""
    configs: dict[str, dict[str, Path]] = {p: {} for p in profiles}
    for key in keys:
        current: Path | None = None
        for p in profiles:
            specific = exp_dir / f"{key}_{p}.toml"
            if specific.is_file():
                current = specific
            elif current is None:
                base = exp_dir / f"{key}.toml"
                if not base.is_file():
                    raise ValueError(
                        f"{exp_dir}: no config for daemon {key!r} under profile {p!r}; "
                        f"add {specific.name} or {base.name}"
                    )
                current = base
            configs[p][key] = current
    return configs


def parse_failpoints(raw, exp_dir: Path) -> str:
    """Turns netsim.failpoints, a list of [event_time, dead_time] pairs in
    seconds, into netsim's "30:10,90:5" form."""
    if not isinstance(raw, list):
        raise ValueError(f"{exp_dir}: netsim.failpoints must be a list of [event_time, dead_time] pairs")
    pairs = []
    for fp in raw:
        if (
            not isinstance(fp, list) or len(fp) != 2
            or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in fp)
            or fp[0] < 0 or fp[1] <= 0
        ):
            raise ValueError(
                f"{exp_dir}: invalid failpoint {fp!r}; want [event_time >= 0, dead_time > 0] in seconds"
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

    def configure(self, toml_text: str, route: str | None = None) -> None:
        self.daemon.Configure(
            daemon_pb2.ConfigureRequest(config_toml=toml_text),
            metadata=self.route(route), timeout=RPC_TIMEOUT,
        )

    def wait_ready(self, vehicle: str, remotes: list[DaemonCfg], timeout: float = READY_TIMEOUT) -> str:
        """Waits until ListServices answers, every remote is registered and the
        vehicle is running. Returns the vehicle's qualified name."""
        deadline = time.monotonic() + timeout
        last = "daemon not reachable"
        while time.monotonic() < deadline:
            try:
                resp = self.list_services()
            except grpc.RpcError as e:
                last = f"ListServices: {e.code().name} {e.details()}"
                time.sleep(1)
                continue
            missing = [r.key for r in remotes if find_remote(resp, r) is None]
            svc = find_vehicle(resp, vehicle)
            if missing:
                last = f"remote daemon(s) not registered: {', '.join(missing)}"
            elif svc is None:
                last = f"vehicle {vehicle!r} not listed"
            elif not svc.running:
                last = f"vehicle {svc.name!r} not running" + (f" ({svc.error})" if svc.error else "")
            else:
                return svc.name
            time.sleep(1)
        raise TimeoutError(f"daemon not ready after {timeout:.0f}s: {last}")

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


def find_remote(resp: daemon_pb2.ListServicesResponse, d: DaemonCfg):
    for r in resp.remotes:
        if not r.error and r.hostname in (d.key, d.hostname):
            return r
    return None


def configure_daemons(client: Daemon, exp: Experiment, profile: str) -> None:
    """Restarts each remote, then the orchestrator, with its config for the
    profile."""
    configs = exp.configs[profile]
    try:
        listing = client.list_services()
    except grpc.RpcError:
        listing = None
    for d in exp.remotes:
        config = configs[d.key]
        text = config.read_text()
        remote = find_remote(listing, d) if listing else None
        if remote is not None:
            log(f"configuring remote {d.key} ({remote.ip}) through the orchestrator with {config.name}")
            client.configure(text, route=remote.ip)
        elif d.ssh_host:
            log(f"remote {d.key} not registered; configuring it over ssh with {config.name}")
            # ssh prompts (host key, password) on the terminal, not stdin
            cmd = ["ssh", d.ssh_host, "eagle configure /dev/stdin"]
            subprocess.run(cmd, input=text, text=True, check=True)
        else:
            raise RuntimeError(f"remote {d.key} is not registered with the orchestrator and has no prefix to ssh to")
    o = exp.orchestrator
    log(f"configuring orchestrator {o.key} with {configs[o.key].name}")
    client.configure(configs[o.key].read_text())


def push_files(client: Daemon, exp: Experiment, video: Path | None) -> None:
    """Pushes the experiment's files and the video, if any, to every daemon's
    files directory (STEELEAGLE_FILES): the orchestrator's and each remote's,
    through the orchestrator, or with rsync if the remote isn't registered.
    Each file is saved as its push_as, if set; the video as the phase's
    push_as, so the driver's config can name one file for every video."""
    pushes = list(exp.files)
    if video:
        pushes.append(PushFile(video, exp.phase.push_as or video.name))
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
                dest = REMOTE_FILES_DIR.rstrip("/") + "/" + f.name
                cmd = ["rsync", "-a", "--mkpath", str(f.path), f"{d.ssh_host}:{dest}"]
                subprocess.run(cmd, check=True)
            else:
                raise RuntimeError(f"remote {d.key} is not registered with the orchestrator and has no prefix to rsync to")
        log(f"pushing {what} to orchestrator {exp.orchestrator.key}")
        client.transfer_file(f.path, name=f.name)


# --------------------------------------------------------------------------
# File collection
# --------------------------------------------------------------------------


def rsync(exp: Experiment, src: str, dest: Path, move: bool) -> None:
    host, _, rest = src.partition("/")
    d = exp.daemons[host]
    path = "/" + rest
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a"]
    if move:
        cmd.append("--remove-source-files")
    # A directory's contents are collected, not the directory itself.
    # ssh and rsync are not captured, so their prompts (host key, password)
    # and errors reach the user's terminal.
    if d.prefix:
        if not glob.has_magic(path):
            test = ["ssh", d.ssh_host, f"test -d {shlex.quote(path)}"]
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
    def __init__(self, exp: Experiment, profile: str, trial_dir: Path):
        self.timeline = trial_dir / "timeline.csv"
        self.output = trial_dir / "netsim.log"
        cmd = [
            sys.executable, "-u", str(NETSIM),
            "-i", exp.interface, "-p", str(exp.port),
            "--profile", profile, "--log", str(self.timeline),
            *exp.netsim_args,
        ]
        if profile == "malicious" and exp.failpoints:
            cmd += ["--failpoints", exp.failpoints]
        if os.geteuid() != 0 and "--dry-run" not in exp.netsim_args:
            cmd = ["sudo", "-n"] + cmd
        self.needs_sudo = cmd[0] == "sudo"
        self.cmd = cmd
        self.proc: subprocess.Popen | None = None
        self.out = None

    def start(self) -> None:
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


def bandwidth_stats(rows: list[dict[str, str]], end: float) -> dict[str, float]:
    """Time-weighted statistics of the bandwidth netsim allowed: each row's
    rate holds until the next row (or the end of the run)."""
    if not rows:
        return {}
    timeline = [(float(r["t_sec"]), float(r["applied_kbps"])) for r in rows]
    samples = []
    for i, (t, kbps) in enumerate(timeline):
        t_next = timeline[i + 1][0] if i + 1 < len(timeline) else max(end, t)
        if t_next > t:
            samples.append((kbps, t_next - t))
    if not samples:
        samples = [(kbps, 1.0) for _, kbps in timeline]
    total = sum(w for _, w in samples)
    return {
        "bandwidth_mean_kbps": sum(v * w for v, w in samples) / total,
        "bandwidth_median_kbps": weighted_percentile(samples, 0.5),
        "bandwidth_p95_kbps": weighted_percentile(samples, 0.95),
        "bandwidth_min_kbps": min(v for v, _ in samples),
        "bandwidth_max_kbps": max(v for v, _ in samples),
        "time_off_sec": sum(w for v, w in samples if v == 0),
    }


STATS_COLUMNS = [
    "trial", "duration_sec",
    "total_bytes_delivered", "total_bytes_dropped_while_off", "total_bytes_arrived",
    "pkts_dropped_by_queue",
    "bandwidth_mean_kbps", "bandwidth_median_kbps", "bandwidth_p95_kbps",
    "bandwidth_min_kbps", "bandwidth_max_kbps", "time_off_sec",
]
TIMELINE_COLUMNS = ["trial", "t_sec", "drawn_kbps", "applied_kbps", "state"]


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
    timeline_<label>.csv. The label is the profile, followed by the video's
    name for a video run, so each video gets its own CSVs."""
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
        **{k: round(v, 3) for k, v in bandwidth_stats(timeline, end).items()},
    }
    append_csv(run_dir / f"stats_{label}.csv", STATS_COLUMNS, [{k: fmt(v) for k, v in stats.items()}])
    append_csv(run_dir / f"timeline_{label}.csv", TIMELINE_COLUMNS, [{"trial": trial, **r} for r in timeline])
    log(
        f"stats ({label}, trial {trial}): {stats['total_bytes_delivered']} bytes delivered, "
        f"mean {stats.get('bandwidth_mean_kbps', '?')} / median {stats.get('bandwidth_median_kbps', '?')} / "
        f"p95 {stats.get('bandwidth_p95_kbps', '?')} Kbps"
    )


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


def new_run_dir(exp: Experiment, profile: str) -> Path:
    run_dir = exp.dir / "runs" / profile
    if run_dir.exists():
        run_dir = run_dir.with_name(f"{profile}-{datetime.now():%Y%m%d-%H%M%S}")
    run_dir.mkdir(parents=True)
    return run_dir


def cleanup(exp: Experiment, run_dir: Path, trial_dir: Path, netsim: Netsim, label: str, trial: int, wall_sec: float) -> None:
    netsim.stop()
    for key, src in exp.results.items():
        log(f"moving {key} from {src}")
        rsync(exp, src, trial_dir / "result" / key, move=True)
    for key, src in exp.catalogs.items():
        log(f"copying {key} from {src}")
        rsync(exp, src, trial_dir / "catalog" / key, move=False)
    write_stats(run_dir, netsim, label, trial, wall_sec)
    log(f"trial saved to {trial_dir}")


def run_trial(
    client: Daemon, exp: Experiment, vehicle: str, profile: str, run_dir: Path, trial: int,
    video: Path | None = None,
) -> None:
    """Runs one trial. A video's trials go to run_dir/<video>/trial_<n>, and
    its stats to run_dir/stats_<profile>_<video>.csv; a mission's to
    run_dir/trial_<n> and run_dir/stats_<profile>.csv."""
    phase = exp.phase
    label = f"{profile}_{video.stem}" if video else profile
    trial_dir = (run_dir / video.stem if video else run_dir) / f"trial_{trial}"
    trial_dir.mkdir(parents=True)
    netsim = Netsim(exp, profile, trial_dir)
    what = f"profile {profile}, " + (f"video {video.name}, " if video else "") + f"trial {trial}/{exp.trials}"
    desc = f"video {video.name}, flow {phase.file.name}" if video else f"mission {phase.file.name}"
    log(f"=== {exp.name}: {what} ({desc}) ===")

    if phase.kind == "mission":
        log(f"uploading and loading {phase.file.name} on {vehicle}")
        client.upload_mission(phase.file, vehicle)
        client.load_mission(phase.file.name, vehicle)
    flow = phase.file.read_bytes() if phase.kind == "video" else b""
    if not phase.auto:
        input(f"[{label} {trial}/{exp.trials}] Press ENTER to start the {phase.kind}... ")

    wall = 0.0
    try:
        if phase.kind == "mission":
            client.start_mission(vehicle)
        else:
            client.set_dataflow(flow, vehicle)
        netsim.start()
        log(f"{phase.kind} started")
        wall = wait_for(phase.duration_for(video), f"{phase.kind} under {what}")
    finally:
        if phase.kind == "mission":
            for name, call in (("Hold", client.hold), ("StopMission", client.stop_mission)):
                try:
                    call(vehicle)
                    log(f"{name} sent")
                except grpc.RpcError as e:
                    log(f"warning: {name} failed: {e.code().name} {e.details()}")
        cleanup(exp, run_dir, trial_dir, netsim, label, trial, wall)


def run_experiment(client: Daemon, exp_dir: Path) -> None:
    exp = load_experiment(exp_dir)
    # A mission runs once per trial; a video run goes through each video in
    # turn, running every trial on it
    videos: list[Path | None] = list(exp.phase.videos) if exp.phase.kind == "video" else [None]
    log(
        f"### experiment {exp.name} ({exp_dir}): profiles {', '.join(exp.profiles)}, "
        + (f"videos {', '.join(v.name for v in exp.phase.videos)}, " if exp.phase.kind == "video" else "")
        + (f"files {', '.join(f.path.name for f in exp.files)}, " if exp.files else "")
        + f"{exp.trials} trial(s) each"
    )
    for v, d in exp.phase.video_durations.items():
        log(f"video {v.name} is {d:g}s long; each of its trials runs that long")
    for profile in exp.profiles:
        run_dir = new_run_dir(exp, profile)
        for video in videos:
            for trial in range(1, exp.trials + 1):
                # Each trial starts from freshly restarted daemons, so no state
                # (like a running flow) carries over from the previous one
                # Pushed before the daemons restart, so the vehicle's driver
                # finds the files and video when it starts, even if the
                # previous trial's result collection moved them away
                push_files(client, exp, video)
                configure_daemons(client, exp, profile)
                time.sleep(2)  # let the orchestrator go down before polling it
                vehicle = client.wait_ready(exp.vehicle, exp.remotes)
                log(f"daemons ready; targeting {vehicle}")
                run_trial(client, exp, vehicle, profile, run_dir, trial, video)
            if video:
                log(f"video {video.name} under profile {profile} saved to {run_dir / video.stem}")
        log(f"profile {profile} saved to {run_dir}")


def find_experiments(root: Path) -> list[Path]:
    dirs = sorted(p for p in root.iterdir() if (p / EXPERIMENT_FILE).is_file())
    if not dirs:
        raise SystemExit(f"no experiment directories (with {EXPERIMENT_FILE}) in {root}")
    return dirs


def main():
    ap = argparse.ArgumentParser(description="Run SteelEagle experiments.")
    ap.add_argument("path", type=Path, help="experiment directory (or, with -r, a directory of them)")
    ap.add_argument("-r", "--recursive", action="store_true", help="run every experiment directory inside path")
    ap.add_argument("--socket", default=default_socket(), help="daemon control socket (default: %(default)s)")
    args = ap.parse_args()

    root = args.path.resolve()
    if args.recursive:
        exp_dirs = find_experiments(root)
    elif (root / EXPERIMENT_FILE).is_file():
        exp_dirs = [root]
    else:
        raise SystemExit(f"{root} has no {EXPERIMENT_FILE} (use -r for a directory of experiments)")

    # Check every experiment up front, so a typo doesn't stop a batch midway
    exps = []
    for d in exp_dirs:
        try:
            exps.append(load_experiment(d))
        except (ValueError, tomllib.TOMLDecodeError) as e:
            raise SystemExit(f"invalid experiment: {e}")

    # Ask for the sudo password now rather than in the middle of a run
    if os.geteuid() != 0 and any("--dry-run" not in e.netsim_args for e in exps):
        log("netsim needs root; checking sudo")
        sudo_validate()

    client = Daemon(args.socket)
    for d in exp_dirs:
        run_experiment(client, d)
    log(f"done: {len(exp_dirs)} experiment(s)")


if __name__ == "__main__":
    main()
