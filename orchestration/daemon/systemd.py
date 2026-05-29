"""
daemon/systemd.py

Generates and installs a systemd unit file for the orchestrator daemon.

Supports both system-wide services (/etc/systemd/system/, requires root)
and per-user services (~/.config/systemd/user/, no root required but
needs `loginctl enable-linger` to start at boot without a login session).
"""

import grp
import os
import pwd
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Unit file template
# ---------------------------------------------------------------------------

_UNIT_TEMPLATE = """\
[Unit]
Description={description}
Documentation=https://github.com/cmusatyalab/steeleagle
# Wait for the network and Docker before starting.
After=network.target docker.service
Wants=docker.service
# Hard ceiling on restarts within a 30-second window.
StartLimitBurst=5
StartLimitIntervalSec=30s

[Service]
Type=simple
ExecStart={exec_start}
WorkingDirectory={working_directory}
Environment=PYTHONUNBUFFERED=1
{extra_env}
# Restart automatically on non-zero exit; give it 5 s between attempts.
Restart=on-failure
RestartSec=5s

{user_group}
# Write stdout/stderr to the journal; view with:
#   journalctl -u {service_name} -f
StandardOutput=journal
StandardError=journal
SyslogIdentifier={service_name}

[Install]
WantedBy={wanted_by}
"""


# ---------------------------------------------------------------------------
# Data class that captures everything needed to render + install a unit
# ---------------------------------------------------------------------------


@dataclass
class UnitConfig:
    service_name: str  # e.g. "orchestrator"
    description: str
    exec_start: str  # full ExecStart line
    working_directory: str  # directory the daemon runs in
    config_path: str  # path passed via ORCH_CONFIG
    user_service: bool = False  # True → ~/.config/systemd/user/
    run_as_user: str = ""  # system service only; "" = current user
    run_as_group: str = ""  # system service only; "" = current group


def render_unit(cfg: UnitConfig) -> str:
    """Render the unit file content from a UnitConfig."""
    extra_env = f"Environment=ORCH_CONFIG={cfg.config_path}"

    if cfg.user_service:
        user_group = ""
        wanted_by = "default.target"
    else:
        lines = []
        if cfg.run_as_user:
            lines.append(f"User={cfg.run_as_user}")
        if cfg.run_as_group:
            lines.append(f"Group={cfg.run_as_group}")
        user_group = "\n".join(lines)
        wanted_by = "multi-user.target"

    return _UNIT_TEMPLATE.format(
        description=cfg.description,
        exec_start=cfg.exec_start,
        working_directory=cfg.working_directory,
        extra_env=extra_env,
        user_group=user_group,
        service_name=cfg.service_name,
        wanted_by=wanted_by,
    )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def unit_path(service_name: str, user_service: bool) -> Path:
    if user_service:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "systemd" / "user" / f"{service_name}.service"
    return Path("/etc/systemd/system") / f"{service_name}.service"


def current_user() -> tuple[str, str]:
    """Return (username, primary_group_name) for the calling process."""
    pw = pwd.getpwuid(os.getuid())
    gr = grp.getgrgid(pw.pw_gid)
    return pw.pw_name, gr.gr_name


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------


def install(cfg: UnitConfig, enable: bool = True) -> Path:
    """
    Write the unit file and reload systemd.

    Returns the path the file was written to.
    Raises PermissionError if the destination is not writable.
    """
    dest = unit_path(cfg.service_name, cfg.user_service)
    dest.parent.mkdir(parents=True, exist_ok=True)

    content = render_unit(cfg)
    dest.write_text(content)

    _systemctl(["daemon-reload"], user=cfg.user_service)

    if enable:
        _systemctl(["enable", cfg.service_name], user=cfg.user_service)

    return dest


def uninstall(service_name: str, user_service: bool) -> None:
    """Stop, disable, and remove the unit file."""
    _systemctl(["stop", service_name], user=user_service, check=False)
    _systemctl(["disable", service_name], user=user_service, check=False)

    dest = unit_path(service_name, user_service)
    if dest.exists():
        dest.unlink()

    _systemctl(["daemon-reload"], user=user_service)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _systemctl(args: list[str], user: bool = False, check: bool = True) -> None:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)
    subprocess.run(cmd, check=check)
