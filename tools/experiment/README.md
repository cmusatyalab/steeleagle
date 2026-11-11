# steeleagle-experiment

An automatic experiment runner for SteelEagle. You give it an experiment
directory, whose `experiment.toml` holds a list of experiments. For each
experiment, and for each of its network profiles, it:

- restarts the daemons with that profile's configs,
- pushes any extra files the experiment needs to the daemons,
- starts a mission, or pushes a video to the daemons and starts a dataflow, on a vehicle,
- limits the network with [netsim](src/steeleagle_experiment/netsim/README.md),
- stops everything when the run ends,
- collects the result files, catalog files and bandwidth statistics into the
  experiment directory.

## Running it

### With uvx (no install)

[uv](https://docs.astral.sh/uv/) can run the script straight from the
repository, in a temporary environment:

```bash
uvx --from "git+https://github.com/cmusatyalab/steeleagle@v4_backend_rework#subdirectory=tools/experiment" \
    experiment path/to/my_experiment
```

Change `@v4_backend_rework` to another branch, tag or commit as needed. The
command fetches whatever has been pushed to GitHub at that ref, so push your
changes before running it this way.

From a local checkout (to try out uncommitted changes):

```bash
uvx --from ./tools/experiment experiment path/to/my_experiment
```

### From the project environment

```bash
cd tools/experiment
uv run experiment path/to/my_experiment
```

### Picking and listing experiments

By default every experiment in the directory's `experiment.toml` runs, in the
order they appear. `-e` runs only the named experiment, and can be repeated:

```bash
uv run experiment path/to/my_experiment -e onboard_track -e parking
```

`-l` lists the experiments and exits, without running anything or checking
the files they name:

```
$ uv run experiment path/to/my_experiment -l
path/to/my_experiment:
  NAME           KIND     RUNS                             VEHICLE  PROFILES          TRIALS
  onboard_track  video    traintrack.mp4 (flow flow.toml)  drone    all               3
  parking        video    parking.mp4 (flow flow.toml)     drone    normal,malicious  1
  survey         mission  survey.zip                       drone    all               3
```

### Running a batch of experiment directories

`-r` runs every experiment in every subdirectory that contains an
`experiment.toml`, in alphabetical order of directory:

```bash
uvx --from "git+https://github.com/cmusatyalab/steeleagle@v4_backend_rework#subdirectory=tools/experiment" \
    experiment -r path/to/experiments/
```

Every experiment in the batch is checked before the first one starts.
`-l` works with `-r` too, listing each directory's experiments; `-e` doesn't. A typo
in the last experiment stops the batch before anything runs, not halfway
through.

### Options

| Option            | Meaning                                                                     |
|-------------------|-----------------------------------------------------------------------------|
| `path`            | An experiment directory, or with `-r`, a directory of experiment directories |
| `-r, --recursive` | Run every experiment directory inside `path`                                |
| `-e, --experiment NAME` | Run only the experiment named `NAME` (repeat for several). Not with `-r` |
| `-l, --list`      | List the experiments in `path` (with `-r`, in each directory) and exit      |
| `--update-packages` | Reinstall every package the daemons' configs use, once per daemon per run, to get a branch's latest code (see below) |
| `--socket PATH`   | eagled's control socket (default: `$XDG_RUNTIME_DIR/steeleagle/eagled.sock`) |

Before configuring a daemon, the runner installs any package its config uses
that the daemon doesn't have, through the orchestrator. A package that is
already installed is left alone, even if its branch has moved on since; with
`--update-packages`, each one is reinstalled the first time a daemon is
configured in the run, so it picks up the branch's latest code. Updated
plugins rebuild their environments when the daemon restarts, which makes the
first trial slower.

## sudo: run it as yourself, not as root

netsim changes kernel network settings, so it needs root. Run the runner as
your own user anyway:

- eagled is a systemd **user** service. Its control socket is
  `/run/user/<your uid>/steeleagle/eagled.sock`.
- The runner runs only netsim through `sudo`. It asks for your sudo password
  once at startup, and checks again before each trial, so an expired sudo
  timestamp asks again rather than failing.
- rsync and ssh to the remote daemons use **your** ssh keys and `known_hosts`.
  They run attached to your terminal, so if a host asks for a password or to
  confirm its host key, answer the prompt there.

If you do run it as root (for example `sudo "$(which uvx)" ...`), the default
socket is that of the user who ran `sudo` (`SUDO_UID`). In that case rsync and
ssh use root's ssh setup.

## Requirements

- On the machine you run it on:
  - Python 3.12+ (uv installs it if needed).
  - A running eagled, which acts as the orchestrator.
  - `rsync` and `ssh`.
  - `tc` and `ip` (iproute2) and the `ifb` kernel module, for netsim.
- Remote daemons locked to the orchestrator. They are configured through it,
  so the runner waits (up to 5 minutes) for each one to register before
  configuring it.

## The experiment directory

Every file the experiment uses lives next to its `experiment.toml`:

```
my_experiment/
├── experiment.toml
├── traintrack.mp4, flow.toml        # the videos, flows and missions the experiments name
├── labels.json                      # (optional) any files listed in an experiment's files
├── lambda2.toml                     # config for daemon "lambda2", for every experiment
├── fermi.toml                       # config for daemon "fermi", for every experiment
├── fermi_onboard_track.toml         # (optional) fermi's config for experiment onboard_track
├── fermi_onboard_track_malicious.toml  # (optional) ...and for its malicious profile
└── runs/                            # written by the runner
```

See [`src/steeleagle_experiment/example/experiment.toml`](src/steeleagle_experiment/example/experiment.toml)
for a commented template.

## experiment.toml

`experiment.toml` holds a list of experiments, each an `[[experiments]]`
table with its own `[experiments.mission]` or `[experiments.video]` and
`[experiments.netsim]` sections. They run in the order they appear. The
`[daemons]`, `[results]` and `[catalogs]` tables are shared by all of them.

```toml
[[experiments]]
name = "traintrack"
vehicle = "drone"
[experiments.video]
video = "traintrack.mp4"
push_as = "video.mp4"
flow = "flow.toml"
[experiments.netsim]
interface = "tailscale0"
port = 9001
trials = 3

[[experiments]]
name = "parking"
vehicle = "drone"
[experiments.video]
video = "parking.mp4"
push_as = "video.mp4"
flow = "flow.toml"
[experiments.netsim]
profiles = ["normal", "malicious"]
interface = "tailscale0"
port = 9001
failpoints = [[5, 5], [60, 20]]

[daemons.lambda2]
orchestrator = true
```

Each section header must start with `experiments.` (plural). After an
`[[experiments]]` header, `[experiment.video]` would make a separate table, so
the runner rejects it.

### `[[experiments]]`

| Key       | Meaning                                                                       |
|-----------|-------------------------------------------------------------------------------|
| `name`    | Unique name. Used by `-e`, in the daemon config file names, and for the `runs/` folder |
| `vehicle` | Vehicle to target: its name (`drone`) or full name (`100.64.0.2.drone`)  |
| `files`   | (optional) Files in the experiment directory to push to every daemon at the start of each trial (see below) |

Then set **exactly one** of `[experiments.mission]` or `[experiments.video]`.
The other may be left out, or kept with its files set to `""`.

| Key                  | Meaning                                                                                  |
|----------------------|------------------------------------------------------------------------------------------|
| `file` (mission)     | Mission file in the experiment directory                                                 |
| `no_upload` (mission)| `true`: don't upload the mission; it's assumed to already be on the vehicle under its own name, and is just loaded |
| `video` (video)      | A single video file in the experiment directory. For several videos, add an experiment for each |
| `push_as` (video)    | Name the video is pushed as (optional; defaults to the video's own name)                 |
| `no_upload` (video)  | `true`: don't push the video; it's assumed to already be on every daemon (see below)     |
| `flow` (video)       | Flow file in the experiment directory, sent with `SetDataflow` to start each trial       |
| `auto`               | `false`: press ENTER to start each trial. `true`: start right away                       |
| `duration`           | Seconds to run each trial. `0`: run until you press ENTER. For a mission, defaults to `0`; for a video, defaults to the video's length (see below) |

The video is pushed at the start of each trial, before the daemons restart, to
`STEELEAGLE_FILES` (`~/.local/share/steeleagle/files`) on the orchestrator and
every remote: through the orchestrator's `TransferFile`, or with rsync if a
remote isn't registered. A driver such as `fake_drone` then finds it by name.
Across several video experiments, set `push_as` (e.g. `"video.mp4"`) in each so
every video lands under that one name, and set the driver's `video` arg to it;
otherwise each video keeps its own name and the driver's arg must match it.

With `no_upload = true`, the video is not pushed at all: it is assumed to
already be in `STEELEAGLE_FILES` on the orchestrator and every remote, under
its own name. The `video` name then only labels the experiment, so the file
need not be in the experiment directory; but if it isn't, its length can't be
found, so `duration` must be set. `push_as` can't be combined with it. The
experiment's `files` are still pushed.

If a video experiment leaves `duration` out, each trial runs for the length of
its video. The length comes from `ffprobe` if it is installed, or else from the
header of an MP4/MOV file; if neither works, the experiment is rejected before
it starts and you need to set `duration`. Setting `duration` (including `0`)
overrides the video's length.

A flow can name its engines by their bare service names (`rescale`,
`verifier`), as in the daemon configs. uriel only finds an engine by the name
its daemon serves it under, `<daemon ip>.<name>` (e.g.
`100.101.84.40.rescale`), so before each trial the runner qualifies each bare
name, and the edges with it, from the orchestrator's `ListServices`:

- a `local` engine is the one of that name on the vehicle's daemon;
- a `remote` engine is the only one of that name on any other daemon.

A bare name with no such engine, or (remote) more than one, stops the trial
before it starts, naming the engines it found. Names that are already
qualified are sent as they are. The runner logs what it mapped each name to.

#### `files`

Any other files a trial needs (a model, a label map, a driver's input) can be
listed in an experiment's `files`. They are pushed exactly like a video: at the start of every
trial, before the daemons restart, to `STEELEAGLE_FILES` on the orchestrator
and every remote. This works with both missions and videos.

```toml
[[experiments]]
name = "onboard_track"
vehicle = "drone"
files = [
    "labels.json",                                     # pushed as labels.json
    { file = "model_v2.pt", push_as = "model.pt" },    # pushed as model.pt
]
```

Each file must be in the experiment directory. Two files can't be pushed under
the same name, nor under the name the video is pushed as.

### `[experiments.netsim]`

Each experiment has its own netsim settings.

| Key          | Meaning                                                                                       |
|--------------|-----------------------------------------------------------------------------------------------|
| `profiles`   | Profiles to run, in order. `["*"]` runs all nine (see below)                                  |
| `interface`  | Interface netsim shapes, e.g. `tailscale0`                                                    |
| `port`       | Port netsim shapes                                                                            |
| `failpoints` | Outages for the `malicious` profile, as `[event_time, dead_time]` pairs in seconds            |
| `trials`     | (optional) Times to run each profile, default `1`. Every trial runs before the next profile   |
| `args`       | (optional) Extra netsim flags, passed through as is, e.g. `["--direction", "egress", "--seed", "1"]` |
| `iperf_port` | (optional) `ambient` only: port iperf3 measures the link on, default `5201`                    |
| `iperf_duration` | (optional) `ambient` only: seconds iperf3 measures the link for, default `30`              |

The profiles, in the order `["*"]` runs them:

| Profile        | Bandwidth (Kbps)                         |
|----------------|------------------------------------------|
| `normal`       | 2000 – 3000                              |
| `limited`      | 500 – 1000                               |
| `degraded`     | 50 – 100                                 |
| `intermittent` | 0 – 100, often dropping to 0             |
| `denied`       | always 0                                 |
| `malicious`    | like intermittent, plus `failpoints`     |
| `delay`        | unshaped, plus 0 – 300 ms of variable latency |
| `none`         | unshaped: netsim isn't run               |
| `ambient`      | like `none`, but measured with iperf3 first |

`delay` leaves the bandwidth alone. Every second it picks a new one-way delay
uniformly between 0 and 300 ms and applies it to the port's traffic with a
netem qdisc. Change the range with netsim's `--min-delay-ms` and
`--max-delay-ms` in `args`. When the delay drops, packets sent under the new
delay can overtake ones still held under the old one, so TCP sees some
reordering.

`none` runs the experiment on the network as it is, without netsim. Its
trials have no timeline, and their stats CSV has only the trial and duration
filled in.

`ambient` also runs the experiment on the network as it is. Before each trial,
once the daemons are up, the runner:

1. stops the vehicle (`StopService`), so it isn't sending anything,
2. starts a one-off `iperf3` server on the vehicle's host over ssh, and runs
   the client here against it for `iperf_duration` seconds on `iperf_port`,
   in the direction netsim would shape (by default the vehicle's host sends,
   with `-R`; with `--direction egress` in `args`, this host sends),
3. restarts the vehicle (`RestartService`, even if iperf3 failed) and waits for
   it to be running again,

and then runs the trial without netsim. The per-second throughput iperf3
measured is the trial's bandwidth timeline (state `ambient`), and its full
report is saved as `trial_<n>/iperf3.json`. This needs `iperf3` installed on
both hosts, the vehicle running on a remote daemon (not the orchestrator),
and that daemon in `[daemons]` with a `prefix` to ssh to. A stopped service
stays stopped across daemon restarts, so if the runner is killed hard while
measuring, restart the vehicle with `eagle restart-service <vehicle>`.

Each failpoint `[30, 10]` cuts the port off from 30 s to 40 s after the run
starts, whatever the bandwidth draw says. Failpoints may be given in any order,
and overlapping ones are merged into one outage. Only the `malicious` profile
uses them. With no failpoints, `malicious` behaves like `intermittent` (netsim
prints a warning).

```toml
failpoints = [[30, 10], [90, 5], [150, 20]]
```

Since each experiment has its own `failpoints`, each video gets its own
outages by being its own experiment.

See the [netsim README](src/steeleagle_experiment/netsim/README.md) for how
bandwidth is drawn and what the other flags do.

### `[daemons]`

One table per daemon, named after the daemon:

```toml
[daemons.lambda2]
orchestrator = true      # exactly one daemon is the orchestrator: the one this runs on
[daemons.fermi]
prefix = "root@fermi:"   # rsync/ssh prefix for this host
```

| Key            | Meaning                                                                              |
|----------------|--------------------------------------------------------------------------------------|
| `orchestrator` | `true` for the local daemon the runner talks to. Exactly one must be set            |
| `prefix`       | `user@host:` prefix for rsync and ssh. Empty for the orchestrator (local files)     |

Remote daemons are matched to the orchestrator's registered remotes by
hostname: either the table name (`fermi`) or the host in `prefix`.

#### Daemon configs

There is no `config` key. Each daemon's config file is named after the daemon
and the experiment, and the runner picks one for each of the experiment's
profiles, in profile order:

1. `<daemon>_<experiment>_<profile>.toml` if it exists, e.g.
   `fermi_onboard_track_normal.toml`;
2. otherwise the config the previous profile used;
3. otherwise, before any profile-specific file has been found,
   `<daemon>_<experiment>.toml`, e.g. `fermi_onboard_track.toml`;
4. otherwise `<daemon>.toml`, shared by every experiment.

For example, for experiment `track` with
`profiles = ["normal", "limited", "degraded", "intermittent"]`:

| Files present                                         | normal               | limited                    | degraded                    | intermittent                |
|-------------------------------------------------------|----------------------|----------------------------|-----------------------------|-----------------------------|
| `fermi.toml`                                          | `fermi.toml`         | `fermi.toml`               | `fermi.toml`                | `fermi.toml`                |
| `fermi.toml`, `fermi_track.toml`                      | `fermi_track.toml`   | `fermi_track.toml`         | `fermi_track.toml`          | `fermi_track.toml`          |
| `fermi.toml`, `fermi_track_limited.toml`              | `fermi.toml`         | `fermi_track_limited.toml` | `fermi_track_limited.toml`  | `fermi_track_limited.toml`  |
| `fermi_track_normal.toml`, `fermi_track_degraded.toml`| `fermi_track_normal.toml` | `fermi_track_normal.toml` | `fermi_track_degraded.toml` | `fermi_track_degraded.toml` |

If a profile has no config to use (no specific file, no earlier one, and
neither `<daemon>_<experiment>.toml` nor `<daemon>.toml`), the experiment is
rejected before it starts. An `experiment.toml` that still has the old
`config` key is rejected too.

### `[results]` and `[catalogs]`

Files to collect after each trial, as `name = "<daemon>/<absolute path>"`.
The first part of the path names the daemon whose host holds the files. The
rest is an absolute path on that host, without its leading `/`:

```toml
[results]   # moved: the sources are deleted (rsync --remove-source-files)
frames_seen = "fermi/home/me/.local/share/steeleagle/files/seen"
frames_sent = "lambda2/home/me/.local/share/steeleagle/files/sent"
[catalogs]  # copied: the sources are kept
mcap = "lambda2/home/me/.local/share/steeleagle/files/mcap*"   # globs work
```

A directory's contents are collected into `result/<name>/` (or
`catalog/<name>/`). The runner doesn't put the directory itself inside. Moving
leaves the emptied source directories in place. A source that matches nothing
gives a warning, not an error.

A catalog can instead be left on its host, to be transferred later, with
`defer_pull`:

```toml
[catalogs]
dets_onboard = { path = "heisenberg/root/.local/share/steeleagle/files/detection_log/*", defer_pull = true }
```

It isn't copied; the files the trial added are moved, on their host, into
`<experiment>_<profile>_<trial>_<catalog>/` in the files directory
(`~/.local/share/steeleagle/files`), keeping their names, e.g.
`case_study_2_cop_delay_2_dets_onboard/10002.jpg`. They are moved out of the
engine's own directory because an engine may empty that whenever it starts
(detection_log does with `refresh`), and the daemons restart twice in every
trial. Before each trial (before the daemons restart) the runner lists what
the path holds, so only files written during the trial are moved. If the
trial's directory already exists, e.g. from an earlier run, a new one with
the time added (`...-20261111-134131`) is used. A file whose name is taken in
the directory is left where it is, with a warning. `defer_pull` is only for
catalogs: a result is
removed from its host once it is pulled, so it can't be left there.

## What a run does

For each experiment, in order, for each profile in its `profiles`, and for
each of its `trials`:

1. **Restart the daemons.** The experiment's `files`, and its video if it has
   one (unless `no_upload` is set), are first pushed to every daemon's files
   directory. Then each remote daemon gets its config for the experiment and
   profile, sent through the orchestrator once the remote has registered, and
   then the orchestrator gets its own config. Applying a config restarts the
   daemon. Before its config is replaced, each daemon's own config is saved
   (see step 10).
2. **Wait until ready.** The runner polls `ListServices` until every remote has
   re-registered and the vehicle is listed and running (5-minute timeout).
3. **Measure** (`ambient` only). Stop the vehicle, measure the link with
   iperf3, and restart the vehicle (see [`[experiments.netsim]`](#experimentsnetsim)).
4. **Prepare.** For a mission: upload it (unless `no_upload` is set) and load
   it on the vehicle.
5. **Wait for you.** If `auto = false`: press ENTER to start the trial.
6. **Start.** `StartMission`, or `SetDataflow` with the video's flow (its bare
   engine names qualified; see [`[[experiments]]`](#experiments)), then start netsim
   as soon as the vehicle answers (except under `none` and `ambient`).
7. **Run** for `duration` seconds (for a video with no `duration`, the video's
   length), or until you press ENTER if it is `0`.
8. **Stop.** For a mission: `Hold`, then `StopMission`. These are sent even if
   the run is interrupted. Then every service of the experiment's daemons is
   stopped (`StopService`, the vehicles first), so nothing is still writing to
   the files collected next, and netsim is stopped with SIGINT, so it prints
   its byte totals and removes its `tc` rules.
9. **Collect** results and catalogs, and write the statistics. A
   `defer_pull` catalog is moved aside on its host instead (see
   [`[results]` and `[catalogs]`](#results-and-catalogs)).
10. **Restore the daemons.** The services stopped in step 8 are restarted
    first: a service stopped with `StopService` stays marked stopped across
    reconfigures, so one the daemon's own config doesn't have would otherwise
    start stopped under a later config that has it. With no flow set, they
    don't do anything. Then each daemon is configured with its own config
    again: the remotes through the orchestrator, then the orchestrator. That
    restarts them, which also ends the trial's flow, so no engine (e.g. a
    detection log) keeps working for it afterwards. This happens however the
    trial ends: its duration is up, you press ENTER, Ctrl-C, an error, or the
    runner is killed (SIGTERM, or SIGHUP when its ssh session drops).

Because the daemons restart for every trial, nothing (a running flow, a
loaded mission) carries over from one trial, profile or experiment to the next.

Each daemon's own config is saved in
`~/.local/state/steeleagle-experiment/original-configs/<daemon>.toml` from
just before it is configured until it is restored. If a run dies before it
can restore one (e.g. `kill -9`), the file stays, and the next run restores
that config, rather than the experiment config it finds on the daemon, so it
can also be restored by running the runner again.

## Output

Each profile's trials go to `runs/<experiment>/<profile>/` in the experiment
directory. If that folder already exists (from an earlier run), a timestamp is
added (`runs/onboard_track/normal-20261110-031500/`), so nothing is
overwritten.

```
runs/onboard_track/normal/
├── trial_1/
│   ├── result/<name>/    files from [results], moved off their hosts
│   ├── catalog/<name>/   files from [catalogs], copied
│   ├── timeline.csv      the bandwidth netsim allowed over time in this trial
│   └── netsim.log        netsim's full output
├── trial_2/ ...
├── stats_normal_onboard_track.csv      summary statistics, one row per trial
└── timeline_normal_onboard_track.csv   every trial's timeline, with a trial column
```

The two CSVs are named `stats_<profile>_<experiment>.csv` and
`timeline_<profile>_<experiment>.csv`, so they stay distinct when gathered
together. They are appended to as each trial finishes, so the trials done so
far are kept if a later one fails.

### stats_\<profile\>_\<experiment\>.csv

One row per trial, with these columns:

| Column                          | Meaning                                                                                 |
|---------------------------------|-----------------------------------------------------------------------------------------|
| `trial`                         | The trial number, from 1                                                                |
| `duration_sec`                  | How long netsim ran                                                                     |
| `total_bytes_delivered`         | Bytes that got through netsim on the shaped port (IP layer, link headers removed)       |
| `total_bytes_dropped_while_off` | Bytes discarded while the port was off (rate 0 or a failpoint)                          |
| `total_bytes_arrived`           | Delivered + dropped while off (not counting packets dropped by the shaper queue)        |
| `pkts_dropped_by_queue`         | Packets that overflowed the shaper queue (tc doesn't record their size)                 |
| `bandwidth_mean_kbps`           | Mean bandwidth allowed                                                                  |
| `bandwidth_median_kbps`         | Median bandwidth allowed                                                                |
| `bandwidth_p95_kbps`            | 95th percentile of bandwidth allowed                                                    |
| `bandwidth_min_kbps`, `bandwidth_max_kbps` | Range of bandwidth allowed                                                   |
| `time_off_sec`                  | Time the port was fully off                                                             |
| `delay_mean_ms`, `delay_median_ms`, `delay_p95_ms`, `delay_min_ms`, `delay_max_ms` | Latency netsim added (`delay` only) |

The byte totals come from netsim's own counters. See the netsim README for
exactly what they include.

The bandwidth statistics describe the **allowed** rate, not the measured
throughput. They are weighted by time: each rate counts for as long as it was
in effect, and periods with the port off count as 0. Under `delay` the
bandwidth isn't limited, so they're empty and the delay columns are filled in
instead. Under `ambient`, they describe the throughput iperf3 measured before
the trial, and the byte totals are empty since netsim doesn't run.

### timeline_\<profile\>_\<experiment\>.csv

netsim's trace for each trial, with one row each time it drew a new rate or
crossed a failpoint boundary. `t_sec` restarts at 0 for each trial:

```
trial,t_sec,drawn_kbps,applied_kbps,state,delay_ms
1,0.000,2389,2389,on,
1,1.000,0,0,off,
1,2.000,48,0,failpoint,
2,0.000,2710,2710,on,
```

Each `trial_<n>/timeline.csv` holds the same rows for one trial, without the
`trial` column.

- `drawn_kbps` is what the distribution gave.
- `applied_kbps` is what was in effect.
- `state` is `on`, `off` (the draw was 0), `failpoint`, `delay` or `ambient`.
- `delay_ms` is the latency added, under `delay` (whose kbps columns are empty).
- Under `ambient`, the rows are iperf3's one-second intervals, and both kbps
  columns hold the measured throughput.

## Trying it without the hardware

Add `"--dry-run"` to an experiment's `netsim.args` to have netsim print its `tc` commands
instead of running them. It then needs no root, and the runner won't ask for
sudo. The byte totals in the stats CSV are empty in this mode, but the timeline
and bandwidth statistics are filled in. `none` and `ambient` don't use netsim,
so `--dry-run` doesn't affect them: `ambient` still stops the vehicle and runs
iperf3.

## Troubleshooting

- **`daemon not ready after 300s: ...`**: the message says what was missing.
  - *remote not registered*: the remote didn't reconnect to the orchestrator.
  - *vehicle not listed*: `vehicle` names nothing the orchestrator lists.
  - *not running*: the vehicle is listed but stopped, and its error is shown.

  Check with `eagle list-services`.
- **Network still limited after a crash**: if the runner is killed hard
  (`kill -9`, power loss), netsim's `tc` rules stay in place. The next run
  removes them by itself before it starts. To remove them right away:

  ```bash
  sudo python3 src/steeleagle_experiment/netsim/netsim.py -i tailscale0 -p 9001 --cleanup
  ```

  Don't run this if something else on the machine uses a clsact qdisc on that
  interface.
- **`vehicle 'drone' is ambiguous`**: more than one daemon has a vehicle with
  that name. Use its full name (`<ip>.drone`), as shown by
  `eagle list-services`.
