<!--
SPDX-FileCopyrightText: 2026 Carnegie Mellon University - Satyalab

SPDX-License-Identifier: GPL-2.0-only
-->

# SteelEagle Ansible Roles

Provisioning for two kinds of machine:

- **`dev_environment`** — a contributor workstation that can build/run/test
  every steeleagle component.
- **`eagled_vehicle`** — the companion computer onboard a drone that runs
  the `eagled` daemon (`cmd/eagled`).

Both playbooks start with a `bootstrap` pre-play that makes a bare target
controllable by Ansible (installs `python3`/`python3-apt` via the `raw`
module if missing).

Out of scope for now: the `backend/server` Docker Compose/GPU stack itself
(see `setup_wizard.py`), a standalone GCS-host role, and non-Debian targets.
See `docs/superpowers/specs/2026-08-05-ansible-provisioning-roles-design.md`
for the full design rationale.

## Requirements

- Ansible core >= 2.15 on the control host.
- For `eagled_vehicle` with `eagled_install_mode: cross_compile` (the
  default): a Go toolchain on the **control host** (not the vehicle) able to
  build `cmd/eagled` — i.e. the `dev_environment` role, or any Go 1.26+
  install.
- SSH access (or local connection) plus `sudo` on every target for tasks
  that install system packages.

## Usage

Provision a dev workstation (defaults to `localhost`):

```bash
cd ansible
ansible-playbook -i inventory/dev.example.ini playbooks/dev-environment.yml
```

Provision a vehicle fleet:

```bash
cd ansible
cp inventory/vehicles.example.ini inventory/vehicles.ini   # edit hosts/IPs
ansible-playbook -i inventory/vehicles.ini playbooks/eagled-vehicle.yml
```

### Running a subset of tags

Both playbooks support `--tags` to provision only part of a target. One
caveat for `eagled_vehicle`: directory creation lives in the `templates` tag
group, and the binary-provisioning tasks write into directories `templates`
creates. So a partial run like `--tags build` on its own can fail on a host
that has not been provisioned before. **Include `templates` alongside any
`build` / `cross_compile` / `build_on_device` tag:**

```bash
cd ansible
ansible-playbook -i inventory/vehicles.ini playbooks/eagled-vehicle.yml \
  --tags templates,cross_compile
```

## Linting

Run this from inside `ansible/`, not the repo root — `ansible.cfg`'s
`roles_path` is only honored when ansible-lint is invoked from the directory
containing it, so `uvx ansible-lint ansible/` from the repo root fails with
`The role 'bootstrap' was not found`.

```bash
cd ansible
uvx ansible-lint .
```

## Variables

### `dev_environment`

| Variable | Default | Purpose |
| --- | --- | --- |
| `dev_go_version` | `"1.26.5"` | Go toolchain version (matches `go.mod`) |
| `dev_go_install_dir` | `/usr/local/go` | Where the Go toolchain is unpacked |
| `dev_arch_map` | `{x86_64: amd64, aarch64: arm64}` | Maps `ansible_architecture` to Go's `GOARCH` naming |
| `dev_node_version` | `"20"` | Node.js major version (matches CI) |
| `dev_buf_version` | `"1.47.2"` | `buf` CLI version (drives all codegen in `buf.gen.yaml` via remote/local plugins — no standalone `protoc` binary is needed) |
| `dev_apt_packages` | `[ffmpeg, bubblewrap, gnupg, ca-certificates, git, curl]` | Base apt packages |
| `dev_install_docker` | `true` | Install Docker Engine + Compose plugin |
| `dev_install_nvidia_container_toolkit` | `false` | Install the NVIDIA Container Toolkit (requires `dev_install_docker`; does **not** install the NVIDIA driver/CUDA itself) |
| `dev_clone_repo` | `true` | Clone the steeleagle repo if not already present |
| `dev_repo_url` | `https://github.com/cmusatyalab/steeleagle.git` | Repo to clone |
| `dev_repo_version` | `v4.0-beta` | Branch/tag/ref to check out |
| `dev_repo_dest` | `{{ ansible_env.HOME }}/steeleagle` | Clone destination |

### `eagled_vehicle`

| Variable | Default | Purpose |
| --- | --- | --- |
| `eagled_install_mode` | `cross_compile` | `cross_compile` (build on the control host, push the binary) or `build_on_device` (install Go + build on the vehicle) |
| `eagled_use_become` | `true` | Use `become` (sudo) for privileged tasks |
| `eagled_go_version` | `"1.26.5"` | Go toolchain version installed on the vehicle (used by `build_on_device` mode only) |
| `eagled_go_install_dir` | `/usr/local/go` | Where the Go toolchain is installed on the target vehicle (used by `build_on_device` mode) |
| `eagled_go_arch_map` | `{x86_64: amd64, aarch64: arm64}` | Maps `ansible_architecture` to Go's `GOARCH` naming |
| `eagled_repo_url` | `https://github.com/cmusatyalab/steeleagle.git` | Repo to clone (used by `build_on_device` mode) |
| `eagled_repo_version` | `v4.0-beta` | Branch/tag/ref to check out (used by `build_on_device` mode) |
| `eagled_repo_dir` | `{{ playbook_dir }}/../..` | Control-host source dir used by `cross_compile` mode |
| `eagled_local_build_dir` | `{{ playbook_dir }}/../.build` | Temporary directory for build artifacts on control host (used by `cross_compile` mode) |
| `eagled_install_dir` | `/opt/steeleagle` | Where the `eagled` binary and its source (in `build_on_device` mode) live |
| `eagled_config_dir` | `/etc/steeleagle` | Where `config.toml` is written |
| `eagled_service_user` | `eagled` | Dedicated system user the daemon runs as |
| `eagled_systemd_unit_path` | `/etc/systemd/system/eagled.service` | systemd unit destination |
| `eagled_systemd_unit_dirs` | `[/etc/systemd/system, /run/systemd/system, /usr/lib/systemd/system, /lib/systemd/system]` | Directories systemd reads units from; used only to decide whether the unit-reload handler has anything to reload. Not normally overridden |
| `eagled_service_enabled` | `false` | Whether to enable/start the service — left `false` by default because `cmd/eagled/main.go`'s `func main()` is currently a stub |
| `eagled_isolation_mode` | `sandbox` | `sandbox` (Bubblewrap), `container` (Podman), or `process` (no isolation) — mirrors `cmd/eagled/defaults/config.toml`'s `isolation` field |
| `eagled_vpn` | `true` | Enable vehicle VPN integration in `eagled` config |
| `eagled_port_base` | `9000` | Base port for `eagled` services |
| `eagled_log_mcap` | `true` | Enable MCAP logging |
| `eagled_log_filename` | `` (empty) | Log file path (empty = stdout only) |
| `eagled_log_mask` | `4113` | Log filter mask |
| `eagled_log_level` | `info` | Log level (`debug`, `info`, `warn`, `error`) |
| `eagled_errors_failfast` | `true` | Exit on first fatal error |
| `eagled_vehicle_vpn` | `true` | Enable per-vehicle VPN configuration |
| `eagled_backend_engines` | `[]` | List of `{id, isolation, kwargs}` — renders `[[backend.engines]]` blocks in config |
| `eagled_vehicle_devices` | `[]` | List of `{name, id, kwargs}` — renders `[[vehicle.devices]]` blocks; set per-host, e.g. `ansible/inventory/host_vars/harpy.yml` |
