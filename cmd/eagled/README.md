# eagled

`eagled` runs on a drone's companion computer. It hosts vehicles (driver
plugin + optional mission/extra plugins), installs plugins on request, and
exposes a `DaemonService` gRPC API so it can be configured remotely.

## Why a daemon instead of a config file

We want the GCS to be able to set up a companion computer end to end — install
the driver, define vehicles, point them at the swarm controller and Gabriel —
without anyone SSHing in to hand-edit config. So instead of reading a config
file once at startup, eagled takes almost everything over gRPC (`Configure`,
`InstallPlugin`, etc.) and can be reconfigured live at any point.

That leaves one bootstrapping problem: pushing config over gRPC needs a network
path to eagled, but a freshly imaged companion computer doesn't have one yet.
It hasn't joined the tailnet, because joining the tailnet is itself something
that normally happens in response to a `Configure` call.

`systemd/install.sh` breaks the cycle by seeding `network-config.toml` directly
at install time (a Tailscale auth key + hostname), so eagled joins the tailnet
on its first boot before it's ever been configured. That's the one manual,
on-site step. Everything else, such as driver install, vehicles, and backend
addresses, get pushed by the GCS afterward, over the tailnet.

## Config lifecycle

`Configure` takes a TOML document. Daemon-wide settings (`port-base`,
`hostname`, `backend`, `gabriel`, `aviary`, `plugin-dir`) only take effect on
the first `Configure` call a fresh daemon ever receives. Later calls can't
change them: `ConfigureResponse.daemon_settings_diverged` is true whenever a
later call's daemon-wide settings don't match what's already active, so a
later call that tried to change one doesn't look identical to one that
succeeded, without naming which field. It's false when a later call's
daemon-wide settings already match what's active — that's the common case,
since the intended workflow is to keep re-pushing the same config.toml with
`[[vehicles]]` edited. `[[vehicles]]` is the exception to the freeze and gets
re-applied every call. `Configure` rejects a config with an empty or repeated
`[[vehicles]]` name outright (the whole call fails, not just that vehicle):
both would otherwise reach the same map key in eagled's vehicle bookkeeping
with no way to tell them apart.

Each vehicle in the request gets its own `ok`/`error` result, so one bad
vehicle doesn't sink the whole call or the rest of the vehicles. A vehicle that
fails to start won't show up in `GetStatus` at all. `[[vehicles]]` entries
naming an already-known vehicle replace its config outright, no merge and no
confirmation -- `VehicleResult.reconfigured` is set on that result so it
doesn't look identical to configuring the name for the first time. If that
vehicle is currently running, the running process is left alone rather than
restarted out from under whatever it's doing: the new config is saved and
`VehicleResult.restart_required` is set, and it takes effect the next time
the vehicle is restarted (`RestartVehicles`, or a `StopVehicles` followed by
another `Configure`/eagled restart). That pending-restart state isn't only
visible in that one Configure call's response -- `GetStatus` also reports it
per vehicle via `VehicleStatus.config_stale`, so it's still discoverable
later, from a different `eagle status` call or a different operator
entirely, instead of only being knowable to whoever was watching the
original `Configure` call's output.

Every successful change gets persisted to disk (`applied-config.toml`,
`installed-plugins.toml`, `network-config.toml`), and reloaded on startup.
There is no need to call `Configure` again after a crash or reboot.

`ResetConfig` wipes the persisted config and restarts unconfigured (installed
plugins and the tailscale identity survive). `RestartDaemon` just restarts.

## Vehicles

- `StopVehicles` stops a vehicle but keeps its config around; `RestartVehicles`
  brings it back. `ForgetVehicles` stops it and drops the config for good.
  Stopping something already stopped, or restarting/forgetting something
  unknown, just comes back as a per-vehicle error, not a crash. A name listed
  more than once in the same `StopVehicles`/`RestartVehicles`/`ForgetVehicles`
  call is deduplicated first, so it gets one result, not a real result
  followed by a spurious failure once the first occurrence already changed
  its state.
- Ports are handed out sequentially from `port-base`, in the order vehicles
  were first configured, and never get reused for a different vehicle while
  eagled is running.
- `simulate = true` connects a vehicle to the shared aviary simulator instead
  of a driver plugin (`driver` is ignored). Aviary itself only spawns once, on
  the first `Configure` call that includes a simulated vehicle, and its vehicle
  set is locked in from then on — adding a new simulated vehicle later gets
  rejected, and needs a full eagled restart instead.
- `driver`/`mission`/every entry in `plugins` has to already be installed under
  the right category via `InstallPlugin`. Referencing something that isn't
  installed just fails that one vehicle.

## Plugin install

`InstallPlugin` clones a repo at a given ref/subpath and runs its `install.sh`.
Installing under a name that's already installed just overwrites it. The old
install is backed up first and only removed once `install.sh` succeeds. If it
fails, the backup gets put back so you're never left without a working plugin.

Categories (`driver`, `mission`, `extra`) live in separate directories and have
separate install records, so the same plugin name can be installed under two
categories at once without either one clobbering the other.

Concurrent `InstallPlugin` calls for the same name and category are
serialized (installs for different names/categories still run in parallel):
without that, two overlapping installs could interleave the swap-in and
leave the recorded ref pointing at a different version than what's actually
on disk.

## Deployment (systemd)

`systemd/install.sh` (run as root) builds eagled, or installs a prebuilt binary
specified with `--bin`, creates a dedicated `eagled` system user, installs the
binary and unit file, and enables/restarts the service. Re-running it is the
normal way to upgrade. It rebuilds, reinstalls, and restarts the service to
pick up the new binary.

What it writes:

- `/usr/local/bin/eagled` — the binary
- the `eagled` system user, home `/var/lib/eagled`
- `/etc/systemd/system/eagled.service` — the unit file
- `/etc/eagled/eagled.env` — `TS_AUTHKEY`/`TS_VEHICLE_AUTHKEY`
- `/var/lib/eagled/.local/share/steeleagle/network-config.toml` — the seeded
  hostname (see "Why a daemon instead of a config file" above)

A couple of things worth knowing before you re-run it:

- It overwrites `eagled.env` and the seeded hostname every time, so any manual
  edits to either get clobbered unless you pass the same
  `TS_AUTHKEY`/`TS_VEHICLE_AUTHKEY`/`TS_HOSTNAME` again.
- Run non-interactively (no tty), it requires `TS_AUTHKEY` to already be
  exported — it won't hang waiting on a prompt, it just fails.

`eagled.service` runs as the unprivileged `eagled` user under
`ProtectSystem=strict`, with only `/var/lib/eagled` writable, and
`Restart=always` rather than `on-failure`. `ResetConfig` exits 0 on purpose to
get itself relaunched, so `on-failure` would leave it dead instead.
`ProtectHome` is deliberately left unset: `aviary.dir`/`aviary.command` in a
pushed `config.toml` are arbitrary admin-supplied paths (e.g. a driver
checkout under a developer's home directory), and `Configure` already implies
that trust.

systemd doesn't set `HOME` or `XDG_RUNTIME_DIR` for system services, so the
unit sets them explicitly, and `PATH` ends up fairly bare. If a plugin's
`install.sh`/`run.sh` expects tools like `uv` or `buf` under
`$HOME/.local/bin`, it needs to add that to `PATH` itself since it's not
inheriting anyone's interactive shell environment.

## Networking

`TS_AUTHKEY`/`TS_VEHICLE_AUTHKEY` turn on tailscale. eagled and each vehicle
get their own tsnet identity. No auth key means we use plain TCP only.

By default both eagled's own node and every vehicle's node persist their tsnet
state to disk (under `internal/tailscale.StateDir`), so a restart reconnects
under the same identity instead of registering a new one under the same
hostname. Set `vehicle-tsnet-mem-store = true` in the config to keep vehicle
tsnet state in memory instead (eagled's own node is always persisted). Each
vehicle then gets a fresh identity every restart. `ForgetVehicles` deletes a
forgotten vehicle's persisted tsnet state so a future vehicle reusing that name
doesn't inherit a stale node key.

`hostname` is frozen along with every other daemon-wide setting: it's only ever
established from the daemon's first `Configure` call (or from
`network-config.toml`, seeded before that call ever happens — see "Why a daemon
instead of a config file" above), and no later `Configure` call, not even
`ResetConfig`, changes it. Changing eagled's tailscale identity is a manual,
on-site operation: edit or delete `network-config.toml` on the host and restart
eagled.
