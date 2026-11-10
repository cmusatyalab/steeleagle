"""Auto-experiment runner for SteelEagle.

    python -m steeleagle_experiment.main <experiment_dir>
    python -m steeleagle_experiment.main -r <dir_of_experiment_dirs>

An experiment directory holds an experiment.toml (see example/) and every file
it names: the mission or flow, and each daemon's config. For each netsim
profile, and for each of its trials, the runner:

  1. restarts the daemons with the profile's configs,
  2. starts the mission (upload, load, start) or sets the flow on the target
     vehicle, and starts netsim as soon as the vehicle acknowledges it,
  3. waits for the duration, or for ENTER when the duration is 0,
  4. stops the mission (Hold, then StopMission) and netsim, and
  5. collects the trial into <experiment_dir>/runs/<profile>/:
        trial_<n>/result/<key>/   result files, moved off their hosts
        trial_<n>/catalog/<key>/  catalog files, copied
        trial_<n>/timeline.csv    bandwidth netsim allowed over time
        trial_<n>/netsim.log      netsim's output
        stats_<profile>.csv       totals and bandwidth statistics, a row per trial
        timeline_<profile>.csv    every trial's timeline, with a trial column

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
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import grpc
from steeleagle_protocol.v1.services.daemon import daemon_pb2, daemon_pb2_grpc
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
    kind: str  # "mission" or "flow"
    file: Path
    auto: bool
    duration: float


@dataclass
class DaemonCfg:
    key: str
    orchestrator: bool
    prefix: str
    password: str

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

    phases = []
    for kind in ("mission", "flow"):
        sect = exp.get(kind, {})
        if sect.get("file"):
            path = exp_dir / sect["file"]
            if not path.is_file():
                raise ValueError(f"{exp_dir}: {kind} file {path} does not exist")
            phases.append(
                Phase(kind, path, bool(sect.get("auto", False)), float(sect.get("duration", 0)))
            )
    if len(phases) != 1:
        raise ValueError(f"{exp_dir}: set exactly one of experiment.mission.file or experiment.flow.file")

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
        daemons[key] = DaemonCfg(key, orch, d.get("prefix", ""), d.get("pass", ""))
    if sum(d.orchestrator for d in daemons.values()) != 1:
        raise ValueError(f"{exp_dir}: exactly one daemon must have orchestrator = true")

    configs = resolve_configs(exp_dir, list(daemons), list(profiles))

    e = Experiment(
        exp_dir, name, vehicle, phases[0], list(profiles), ns["interface"], int(ns["port"]),
        netsim_args, failpoints, trials, daemons, configs,
        dict(raw.get("results", {})), dict(raw.get("catalogs", {})),
    )
    for table in (e.results, e.catalogs):
        for key, src in table.items():
            host = src.split("/", 1)[0]
            if host not in daemons:
                raise ValueError(f"{exp_dir}: {key} = {src!r} names unknown daemon {host!r}")
    return e


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

    def upload_mission(self, path: Path, route: str) -> None:
        data = path.read_bytes()
        chunks = [data[i : i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)] or [b""]
        total = len(chunks)

        # The vehicle acks each chunk before the next is sent
        acks: queue.Queue[int] = queue.Queue()

        def requests():
            for n, chunk in enumerate(chunks, start=1):
                yield upload_pb2.UploadMissionRequest(
                    filename=path.name, chunk=chunk, number=n, total=total
                )
                if acks.get(timeout=RPC_TIMEOUT) != n:
                    return

        received = 0
        for resp in self.loader.UploadMission(requests(), metadata=self.route(route), timeout=RPC_TIMEOUT):
            received = resp.received
            acks.put(received)
        if received != total:
            raise RuntimeError(f"mission upload ended after {received} of {total} chunks were acknowledged")

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
            cmd = ssh_cmd(d) + [d.ssh_host, "eagle configure /dev/stdin"]
            subprocess.run(cmd, input=text, text=True, check=True)
        else:
            raise RuntimeError(f"remote {d.key} is not registered with the orchestrator and has no prefix to ssh to")
    o = exp.orchestrator
    log(f"configuring orchestrator {o.key} with {configs[o.key].name}")
    client.configure(configs[o.key].read_text())


# --------------------------------------------------------------------------
# File collection
# --------------------------------------------------------------------------


def ssh_cmd(d: DaemonCfg) -> list[str]:
    if not d.password:
        return ["ssh"]
    if not shutil.which("sshpass"):
        raise RuntimeError(f"daemon {d.key} has a password set, which needs sshpass installed")
    return ["sshpass", "-p", d.password, "ssh"]


def rsync(exp: Experiment, src: str, dest: Path, move: bool) -> None:
    host, _, rest = src.partition("/")
    d = exp.daemons[host]
    path = "/" + rest
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a"]
    if move:
        cmd.append("--remove-source-files")
    # A directory's contents are collected, not the directory itself
    if d.prefix:
        if d.password:
            cmd = ssh_cmd(d)[:-1] + cmd  # sshpass -p <pass> rsync ...
        if not glob.has_magic(path):
            test = ssh_cmd(d) + [d.ssh_host, f"test -d {shlex.quote(path)}"]
            if subprocess.run(test, capture_output=True).returncode == 0:
                path = path.rstrip("/") + "/"
        sources = [d.prefix + path]  # the remote shell expands globs
    else:
        sources = sorted(glob.glob(path))
        if not sources:
            log(f"warning: nothing matches {path}")
            return
        if len(sources) == 1 and not glob.has_magic(path) and os.path.isdir(sources[0]):
            sources = [sources[0].rstrip("/") + "/"]
    r = subprocess.run(cmd + sources + [str(dest) + "/"], capture_output=True, text=True)
    if r.returncode:
        log(f"warning: rsync of {src} exited {r.returncode}: {r.stderr.strip()}")


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


def write_stats(run_dir: Path, netsim: Netsim, profile: str, trial: int, wall_sec: float) -> None:
    """Adds the trial's row to stats_<profile>.csv and its timeline to
    timeline_<profile>.csv."""
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
    append_csv(run_dir / f"stats_{profile}.csv", STATS_COLUMNS, [{k: fmt(v) for k, v in stats.items()}])
    append_csv(run_dir / f"timeline_{profile}.csv", TIMELINE_COLUMNS, [{"trial": trial, **r} for r in timeline])
    log(
        f"stats (trial {trial}): {stats['total_bytes_delivered']} bytes delivered, "
        f"mean {stats.get('bandwidth_mean_kbps', '?')} / median {stats.get('bandwidth_median_kbps', '?')} / "
        f"p95 {stats.get('bandwidth_p95_kbps', '?')} Kbps"
    )


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


def wait_for(phase: Phase, what: str) -> float:
    """Waits for the phase's duration, or for ENTER. Returns seconds waited."""
    t0 = time.monotonic()
    if phase.duration > 0:
        log(f"running {what} for {phase.duration:g}s")
        time.sleep(phase.duration)
    else:
        input(f"Running {what}. Press ENTER to stop... ")
    return time.monotonic() - t0


def new_run_dir(exp: Experiment, profile: str) -> Path:
    run_dir = exp.dir / "runs" / profile
    if run_dir.exists():
        run_dir = run_dir.with_name(f"{profile}-{datetime.now():%Y%m%d-%H%M%S}")
    run_dir.mkdir(parents=True)
    return run_dir


def cleanup(exp: Experiment, run_dir: Path, trial_dir: Path, netsim: Netsim, profile: str, trial: int, wall_sec: float) -> None:
    netsim.stop()
    for key, src in exp.results.items():
        log(f"moving {key} from {src}")
        rsync(exp, src, trial_dir / "result" / key, move=True)
    for key, src in exp.catalogs.items():
        log(f"copying {key} from {src}")
        rsync(exp, src, trial_dir / "catalog" / key, move=False)
    write_stats(run_dir, netsim, profile, trial, wall_sec)
    log(f"trial saved to {trial_dir}")


def run_trial(client: Daemon, exp: Experiment, vehicle: str, profile: str, run_dir: Path, trial: int) -> None:
    phase = exp.phase
    trial_dir = run_dir / f"trial_{trial}"
    trial_dir.mkdir()
    netsim = Netsim(exp, profile, trial_dir)
    what = f"profile {profile}, trial {trial}/{exp.trials}"
    log(f"=== {exp.name}: {what} ({phase.kind} {phase.file.name}) ===")

    if phase.kind == "mission":
        log(f"uploading and loading {phase.file.name} on {vehicle}")
        client.upload_mission(phase.file, vehicle)
        client.load_mission(phase.file.name, vehicle)
    flow = phase.file.read_bytes() if phase.kind == "flow" else b""
    if not phase.auto:
        input(f"[{profile} {trial}/{exp.trials}] Press ENTER to start the {phase.kind}... ")

    wall = 0.0
    try:
        if phase.kind == "mission":
            client.start_mission(vehicle)
        else:
            client.set_dataflow(flow, vehicle)
        netsim.start()
        log(f"{phase.kind} started")
        wall = wait_for(phase, f"{phase.kind} under {what}")
    finally:
        if phase.kind == "mission":
            for name, call in (("Hold", client.hold), ("StopMission", client.stop_mission)):
                try:
                    call(vehicle)
                    log(f"{name} sent")
                except grpc.RpcError as e:
                    log(f"warning: {name} failed: {e.code().name} {e.details()}")
        cleanup(exp, run_dir, trial_dir, netsim, profile, trial, wall)


def run_experiment(client: Daemon, exp_dir: Path) -> None:
    exp = load_experiment(exp_dir)
    log(
        f"### experiment {exp.name} ({exp_dir}): profiles {', '.join(exp.profiles)}, "
        f"{exp.trials} trial(s) each"
    )
    for profile in exp.profiles:
        run_dir = new_run_dir(exp, profile)
        for trial in range(1, exp.trials + 1):
            # Each trial starts from freshly restarted daemons, so no state
            # (like a running flow) carries over from the previous one
            configure_daemons(client, exp, profile)
            time.sleep(2)  # let the orchestrator go down before polling it
            vehicle = client.wait_ready(exp.vehicle, exp.remotes)
            log(f"daemons ready; targeting {vehicle}")
            run_trial(client, exp, vehicle, profile, run_dir, trial)
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
