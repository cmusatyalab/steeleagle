# steeleagle-experiment

An automatic experiment runner for SteelEagle. You give it an experiment
directory, and for each network profile it:

- restarts the daemons with that profile's configs,
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

### Running a batch of experiments

`-r` runs every subdirectory that contains an `experiment.toml`, in
alphabetical order:

```bash
uvx --from "git+https://github.com/cmusatyalab/steeleagle@v4_backend_rework#subdirectory=tools/experiment" \
    experiment -r path/to/experiments/
```

Every experiment in the batch is checked before the first one starts. A typo
in the last experiment stops the batch before anything runs, not halfway
through.

### Options

| Option            | Meaning                                                                     |
|-------------------|-----------------------------------------------------------------------------|
| `path`            | An experiment directory, or with `-r`, a directory of experiment directories |
| `-r, --recursive` | Run every experiment directory inside `path`                                |
| `--socket PATH`   | eagled's control socket (default: `$XDG_RUNTIME_DIR/steeleagle/eagled.sock`) |

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
- Remote daemons registered with the orchestrator. If one isn't, the runner
  configures it over ssh instead, which needs `eagle` on that host's `PATH`.

## The experiment directory

Every file the experiment uses lives next to its `experiment.toml`:

```
my_experiment/
├── experiment.toml
├── mission.zip              # or a video and flow.toml: whichever experiment.toml names
├── lambda2.toml             # config for daemon "lambda2"
├── fermi.toml               # config for daemon "fermi"
├── fermi_malicious.toml     # (optional) fermi's config for the malicious profile
└── runs/                    # written by the runner
```

See [`src/steeleagle_experiment/example/experiment.toml`](src/steeleagle_experiment/example/experiment.toml)
for a commented template.

## experiment.toml

### `[experiment]`

| Key       | Meaning                                                                       |
|-----------|-------------------------------------------------------------------------------|
| `name`    | Name shown in the log (defaults to the directory name)                       |
| `vehicle` | Vehicle to target: its name (`drone`) or full name (`100.64.0.2.drone`)  |

Then set **exactly one** of `[experiment.mission]` or `[experiment.video]`. The
other may be left out, or kept with its files set to `""`.

| Key                  | Meaning                                                                                  |
|----------------------|------------------------------------------------------------------------------------------|
| `file` (mission)     | Mission file in the experiment directory                                                 |
| `video` (video)      | Video file, or list of video files, in the experiment directory                          |
| `push_as` (video)    | Name each video is pushed as (optional; defaults to the video's own name)                |
| `flow` (video)       | Flow file in the experiment directory, sent with `SetDataflow` to start each trial       |
| `auto`               | `false`: press ENTER to start each trial. `true`: start right away                       |
| `duration`           | Seconds to run each trial. `0`: run until you press ENTER                                |

With a list of videos, each profile runs every trial on the first video, then
every trial on the next, and so on, and each video gets its own CSVs (see
[Output](#output)).

The current video is pushed at the start of each trial, before the daemons
restart, to `STEELEAGLE_FILES` (`~/.local/share/steeleagle/files`) on the
orchestrator and every remote: through the orchestrator's `TransferFile`, or
with rsync if a remote isn't registered. A driver such as `fake_drone` then
finds it by name. With several videos, set `push_as` (e.g. `"video.mp4"`) so
every video lands under that one name, and set the driver's `video` arg to it;
otherwise each video keeps its own name and the driver's arg must match it.

### `[netsim]`

| Key          | Meaning                                                                                       |
|--------------|-----------------------------------------------------------------------------------------------|
| `profiles`   | Profiles to run, in order. `["*"]` runs all six (see below)                                   |
| `interface`  | Interface netsim shapes, e.g. `tailscale0`                                                    |
| `port`       | Port netsim shapes                                                                            |
| `failpoints` | Outages for the `malicious` profile, as `[event_time, dead_time]` pairs in seconds            |
| `trials`     | (optional) Times to run each profile, default `1`. Every trial runs before the next profile   |
| `args`       | (optional) Extra netsim flags, passed through as is, e.g. `["--direction", "egress", "--seed", "1"]` |

The profiles, in the order `["*"]` runs them:

| Profile        | Bandwidth (Kbps)                         |
|----------------|------------------------------------------|
| `normal`       | 2000 – 3000                              |
| `limited`      | 500 – 1000                               |
| `degraded`     | 50 – 100                                 |
| `intermittent` | 0 – 100, often dropping to 0             |
| `denied`       | always 0                                 |
| `malicious`    | like intermittent, plus `failpoints`     |

Each failpoint `[30, 10]` cuts the port off from 30 s to 40 s after the run
starts, whatever the bandwidth draw says. Failpoints may be given in any order,
and overlapping ones are merged into one outage. Only the `malicious` profile
uses them. With no failpoints, `malicious` behaves like `intermittent` (netsim
prints a warning).

```toml
failpoints = [[30, 10], [90, 5], [150, 20]]
```

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

There is no `config` key. Each daemon's config file is named after the daemon,
and the runner picks one for each profile, in profile order:

1. `<daemon>_<profile>.toml` if it exists, e.g. `fermi_normal.toml`;
2. otherwise the config the previous profile used;
3. otherwise, before any profile-specific file has been found, `<daemon>.toml`.

For example, with `profiles = ["normal", "limited", "degraded", "intermittent"]`:

| Files present                             | normal          | limited              | degraded             | intermittent         |
|-------------------------------------------|-----------------|----------------------|----------------------|----------------------|
| `fermi.toml`                              | `fermi.toml`    | `fermi.toml`         | `fermi.toml`         | `fermi.toml`         |
| `fermi.toml`, `fermi_limited.toml`        | `fermi.toml`    | `fermi_limited.toml` | `fermi_limited.toml` | `fermi_limited.toml` |
| `fermi_normal.toml`, `fermi_degraded.toml`| `fermi_normal.toml` | `fermi_normal.toml` | `fermi_degraded.toml` | `fermi_degraded.toml` |

If a profile has no config to use (no specific file, no earlier one and no
`<daemon>.toml`), the experiment is rejected before it starts. An
`experiment.toml` that still has the old `config` key is rejected too.

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

## What a run does

For each experiment, for each profile in `profiles`, for each video (for a
video experiment), and for each of the `trials`:

1. **Restart the daemons.** If the experiment has a video, it is first pushed
   to every daemon's files directory. Then each remote daemon gets its config
   for the profile, sent through the orchestrator (or over ssh if it isn't
   registered), and then the orchestrator gets its own config. Applying a
   config restarts the daemon.
2. **Wait until ready.** The runner polls `ListServices` until every remote has
   re-registered and the vehicle is listed and running (5-minute timeout).
3. **Prepare.** For a mission: upload and load it on the vehicle.
4. **Wait for you.** If `auto = false`: press ENTER to start the trial.
5. **Start.** `StartMission`, or `SetDataflow` with the video's flow, then start netsim
   as soon as the vehicle answers.
6. **Run** for `duration` seconds, or until you press ENTER if it is `0`.
7. **Stop.** For a mission: `Hold`, then `StopMission`. These are sent even if
   the run is interrupted. netsim is stopped with SIGINT, so it prints its byte
   totals and removes its `tc` rules.
8. **Collect** results and catalogs, and write the statistics.

Because the daemons restart for every trial, nothing (a running flow, a
loaded mission) carries over from one trial or profile to the next.

## Output

Each profile's trials go to `runs/<profile>/` in the experiment directory. If
that folder already exists (from an earlier run), a timestamp is added
(`runs/normal-20261110-031500/`), so nothing is overwritten.

```
runs/normal/
├── trial_1/
│   ├── result/<name>/    files from [results], moved off their hosts
│   ├── catalog/<name>/   files from [catalogs], copied
│   ├── timeline.csv      the bandwidth netsim allowed over time in this trial
│   └── netsim.log        netsim's full output
├── trial_2/ ...
├── stats_normal.csv      summary statistics, one row per trial
└── timeline_normal.csv   every trial's timeline, with a trial column
```

The two profile CSVs are appended to as each trial finishes, so the trials
done so far are kept if a later one fails.

For a video experiment, each video gets its own folder of trials and its own
pair of CSVs, named after the video's file name without its extension:

```
runs/normal/
├── traintrack/
│   ├── trial_1/ ...
│   └── trial_2/ ...
├── parking/
│   └── trial_1/ ...
├── stats_normal_traintrack.csv
├── timeline_normal_traintrack.csv
├── stats_normal_parking.csv
└── timeline_normal_parking.csv
```

### stats_\<profile\>.csv

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

The byte totals come from netsim's own counters. See the netsim README for
exactly what they include.

The bandwidth statistics describe the **allowed** rate, not the measured
throughput. They are weighted by time: each rate counts for as long as it was
in effect, and periods with the port off count as 0.

### timeline_\<profile\>.csv

netsim's trace for each trial, with one row each time it drew a new rate or
crossed a failpoint boundary. `t_sec` restarts at 0 for each trial:

```
trial,t_sec,drawn_kbps,applied_kbps,state
1,0.000,2389,2389,on
1,1.000,0,0,off
1,2.000,48,0,failpoint
2,0.000,2710,2710,on
```

Each `trial_<n>/timeline.csv` holds the same rows for one trial, without the
`trial` column.

- `drawn_kbps` is what the distribution gave.
- `applied_kbps` is what was in effect.
- `state` is `on`, `off` (the draw was 0) or `failpoint`.

## Trying it without the hardware

Add `"--dry-run"` to `netsim.args` to have netsim print its `tc` commands
instead of running them. It then needs no root, and the runner won't ask for
sudo. The byte totals in `stats_<profile>.csv` are empty in this mode, but the timeline
and bandwidth statistics are filled in.

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
