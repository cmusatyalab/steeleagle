# steeleagle-scripts

An automatic experiment runner for SteelEagle. You give it an experiment
directory, and for each network profile it:

- restarts the daemons with that profile's configs,
- starts a mission or a dataflow on a vehicle,
- limits the network with [netsim](src/steeleagle_scripts/netsim/README.md),
- stops everything when the run ends,
- collects the result files, catalog files and bandwidth statistics into the
  experiment directory.

## Running it

### With uvx (no install)

[uv](https://docs.astral.sh/uv/) can run the script straight from the
repository, in a temporary environment:

```bash
uvx --from "git+https://github.com/cmusatyalab/steeleagle@v4_backend_rework#subdirectory=tools/scripts" \
    scripts path/to/my_experiment
```

Change `@v4_backend_rework` to another branch, tag or commit as needed. The
command fetches whatever has been pushed to GitHub at that ref, so push your
changes before running it this way.

From a local checkout (to try out uncommitted changes):

```bash
uvx --from ./tools/scripts scripts path/to/my_experiment
```

### From the project environment

```bash
cd tools/scripts
uv run scripts path/to/my_experiment
```

### Running a batch of experiments

`-r` runs every subdirectory that contains an `experiment.toml`, in
alphabetical order:

```bash
uvx --from "git+https://github.com/cmusatyalab/steeleagle@v4_backend_rework#subdirectory=tools/scripts" \
    scripts -r path/to/experiments/
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
  once at startup, and checks again before each profile, so an expired sudo
  timestamp asks again rather than failing.
- rsync and ssh to the remote daemons use **your** ssh keys and `known_hosts`.

If you do run it as root (for example `sudo "$(which uvx)" ...`), the default
socket is that of the user who ran `sudo` (`SUDO_UID`). In that case rsync and
ssh use root's ssh setup.

## Requirements

- On the machine you run it on:
  - Python 3.12+ (uv installs it if needed).
  - A running eagled, which acts as the orchestrator.
  - `rsync` and `ssh`.
  - `tc` and `ip` (iproute2) and the `ifb` kernel module, for netsim.
- `sshpass`, only if a daemon in `[daemons]` has a `pass` set.
- Remote daemons registered with the orchestrator. If one isn't, the runner
  configures it over ssh instead, which needs `eagle` on that host's `PATH`.

## The experiment directory

Every file the experiment uses lives next to its `experiment.toml`:

```
my_experiment/
├── experiment.toml
├── mission.zip              # or flow.toml: whichever experiment.toml names
├── lambda2.toml             # config for daemon "lambda2"
├── fermi.toml               # config for daemon "fermi"
├── fermi_malicious.toml     # (optional) fermi's config for the malicious profile
└── runs/                    # written by the runner
```

See [`src/steeleagle_scripts/example/experiment.toml`](src/steeleagle_scripts/example/experiment.toml)
for a commented template.

## experiment.toml

### `[experiment]`

| Key       | Meaning                                                                       |
|-----------|-------------------------------------------------------------------------------|
| `name`    | Name shown in the log (defaults to the directory name)                       |
| `vehicle` | Vehicle to target: its name (`drone`) or full name (`100.64.0.2.drone`)  |

Then set **exactly one** of `[experiment.mission]` or `[experiment.flow]`. The
other may be left out, or kept with `file = ""`.

| Key        | Meaning                                                                                  |
|------------|------------------------------------------------------------------------------------------|
| `file`     | Mission or flow file in the experiment directory                                         |
| `auto`     | `false`: press ENTER to start each profile. `true`: start right away                     |
| `duration` | Seconds to run each profile. `0`: run until you press ENTER                              |

### `[netsim]`

| Key          | Meaning                                                                                       |
|--------------|-----------------------------------------------------------------------------------------------|
| `profiles`   | Profiles to run, in order. `["*"]` runs all six (see below)                                   |
| `interface`  | Interface netsim shapes, e.g. `tailscale0`                                                    |
| `port`       | Port netsim shapes                                                                            |
| `failpoints` | Outages for the `malicious` profile, as `[event_time, dead_time]` pairs in seconds            |
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

See the [netsim README](src/steeleagle_scripts/netsim/README.md) for how
bandwidth is drawn and what the other flags do.

### `[daemons]`

One table per daemon, named after the daemon:

```toml
[daemons.lambda2]
orchestrator = true      # exactly one daemon is the orchestrator: the one this runs on
[daemons.fermi]
prefix = "root@fermi:"   # rsync/ssh prefix for this host
pass = ""                # (optional) ssh password; needs sshpass
```

| Key            | Meaning                                                                              |
|----------------|--------------------------------------------------------------------------------------|
| `orchestrator` | `true` for the local daemon the runner talks to. Exactly one must be set            |
| `prefix`       | `user@host:` prefix for rsync and ssh. Empty for the orchestrator (local files)     |
| `pass`         | ssh password, if the host doesn't take your key (needs `sshpass`)                   |

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

Files to collect after each profile, as `name = "<daemon>/<absolute path>"`.
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

For each experiment, and for each profile in `profiles`:

1. **Restart the daemons.** Each remote daemon gets its config for the profile,
   sent through the orchestrator (or over ssh if it isn't registered). Then
   the orchestrator gets its own config. Applying a config restarts the daemon.
2. **Wait until ready.** The runner polls `ListServices` until every remote has
   re-registered and the vehicle is listed and running (5-minute timeout).
3. **Prepare.** For a mission: upload and load it on the vehicle.
4. **Wait for you.** If `auto = false`: press ENTER to start the profile.
5. **Start.** `StartMission`, or `SetDataflow` with the flow, then start netsim
   as soon as the vehicle answers.
6. **Run** for `duration` seconds, or until you press ENTER if it is `0`.
7. **Stop.** For a mission: `Hold`, then `StopMission`. These are sent even if
   the run is interrupted. netsim is stopped with SIGINT, so it prints its byte
   totals and removes its `tc` rules.
8. **Collect** results and catalogs, and write the statistics.

Because the daemons restart for every profile, nothing (a running flow, a
loaded mission) carries over from one profile to the next.

## Output

Each profile's run goes to `runs/<profile>/` in the experiment directory. If
that folder already exists (from an earlier run), a timestamp is added
(`runs/normal-20261110-031500/`), so nothing is overwritten.

```
runs/normal/
├── result/<name>/    files from [results], moved off their hosts
├── catalog/<name>/   files from [catalogs], copied
├── stats.csv         summary statistics
├── timeline.csv      the bandwidth netsim allowed over time
└── netsim.log        netsim's full output
```

### stats.csv

A two-column `statistic,value` table:

| Statistic                       | Meaning                                                                                 |
|---------------------------------|-----------------------------------------------------------------------------------------|
| `profile`                       | The netsim profile                                                                      |
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
| `timeline_file`                 | The timeline file                                                                       |

The byte totals come from netsim's own counters. See the netsim README for
exactly what they include.

The bandwidth statistics describe the **allowed** rate, not the measured
throughput. They are weighted by time: each rate counts for as long as it was
in effect, and periods with the port off count as 0.

### timeline.csv

netsim's trace, with one row each time it drew a new rate or crossed a
failpoint boundary:

```
t_sec,drawn_kbps,applied_kbps,state
0.000,2389,2389,on
1.000,0,0,off
2.000,48,0,failpoint
```

- `drawn_kbps` is what the distribution gave.
- `applied_kbps` is what was in effect.
- `state` is `on`, `off` (the draw was 0) or `failpoint`.

## Trying it without the hardware

Add `"--dry-run"` to `netsim.args` to have netsim print its `tc` commands
instead of running them. It then needs no root, and the runner won't ask for
sudo. The byte totals in `stats.csv` are empty in this mode, but the timeline
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
  sudo python3 src/steeleagle_scripts/netsim/netsim.py -i tailscale0 -p 9001 --cleanup
  ```

  Don't run this if something else on the machine uses a clsact qdisc on that
  interface.
- **`vehicle 'drone' is ambiguous`**: more than one daemon has a vehicle with
  that name. Use its full name (`<ip>.drone`), as shown by
  `eagle list-services`.
