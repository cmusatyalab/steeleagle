#!/usr/bin/env bash
# Installs eagled as a systemd service: creates a dedicated system user,
# installs the binary and unit file, and enables the service. Builds eagled
# locally with `go build` by default; pass --bin <path> to install an
# already-built binary instead (e.g. cross-compiled elsewhere).
# -e: exit on any failed command. -u: error on unset variables. -o pipefail:
# a pipeline fails if any stage does, not just the last one.
set -euo pipefail

usage() {
	echo "usage: $0 [--bin <path-to-prebuilt-eagled-binary>]" >&2
}

PREBUILT_BIN=""
# Standard flag-parsing loop: dispatch on $1, shift it (and its value, if
# any) off, repeat until no arguments remain.
while [[ $# -gt 0 ]]; do
	case "$1" in
	--bin)
		# ${2:?msg}: use $2, or print msg to stderr and exit if it's unset/empty.
		PREBUILT_BIN="${2:?--bin requires a path}"
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		usage
		exit 1
		;;
	esac
done

# Resolve this script's own directory to an absolute path, so it works
# regardless of where/how it's invoked from (relative path, symlink, etc.).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

SERVICE_USER=eagled
STATE_DIR=/var/lib/eagled
BIN_PATH=/usr/local/bin/eagled
ENV_DIR=/etc/eagled
ENV_FILE="$ENV_DIR/eagled.env"
UNIT_PATH=/etc/systemd/system/eagled.service

if [[ $EUID -ne 0 ]]; then
	echo "install.sh must be run as root" >&2
	exit 1
fi

if [[ -n "$PREBUILT_BIN" ]]; then
	if [[ ! -x "$PREBUILT_BIN" ]]; then
		echo "$PREBUILT_BIN does not exist or is not executable" >&2
		exit 1
	fi
	echo "installing prebuilt eagled from $PREBUILT_BIN..."
	install -m 755 "$PREBUILT_BIN" "$BIN_PATH"
else
	echo "building eagled..."
	( cd "$REPO_ROOT" && go build -o "$BIN_PATH" ./cmd/eagled )
fi

# `id` exits 0 if the user exists, nonzero otherwise; &>/dev/null discards its
# output since only the exit status matters here.
if ! id "$SERVICE_USER" &>/dev/null; then
	echo "creating system user $SERVICE_USER..."
	useradd --system --home-dir "$STATE_DIR" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
	# Get the tailscale auth key before writing the env file: from TS_AUTHKEY
	# in the installer's environment (the non-interactive path, e.g. scripted
	# fleet installs), or prompted for if stdin is a tty. With neither
	# available there's no way to fill it in, so refuse to proceed rather
	# than silently install with no key.
	if [[ -z "${TS_AUTHKEY:-}" ]]; then
		if [[ -t 0 ]]; then
			read -rsp "Tailscale auth key (TS_AUTHKEY, leave blank to fall back to tsnet's interactive login): " TS_AUTHKEY
			echo
		else
			echo "TS_AUTHKEY is not set and stdin is not a tty; export TS_AUTHKEY before running install.sh non-interactively" >&2
			exit 1
		fi
	fi

	# TS_VEHICLE_AUTHKEY is optional: config.go falls back to TS_AUTHKEY for
	# vehicles when it's unset, so there's nothing to require or error on here
	# — just pick it up from the environment, or offer a prompt on a tty.
	if [[ -z "${TS_VEHICLE_AUTHKEY:-}" && -t 0 ]]; then
		read -rsp "Tailscale vehicle auth key (TS_VEHICLE_AUTHKEY, optional, leave blank to reuse TS_AUTHKEY): " TS_VEHICLE_AUTHKEY
		echo
	fi

	install -m 640 -o root -g "$SERVICE_USER" "$SCRIPT_DIR/eagled.env.example" "$ENV_FILE"
	if [[ -n "$TS_AUTHKEY" ]]; then
		echo "TS_AUTHKEY=$TS_AUTHKEY" >>"$ENV_FILE"
	fi
	if [[ -n "${TS_VEHICLE_AUTHKEY:-}" ]]; then
		echo "TS_VEHICLE_AUTHKEY=$TS_VEHICLE_AUTHKEY" >>"$ENV_FILE"
	fi
	echo "wrote default env file to $ENV_FILE"
fi

# Seed a minimal network-config.toml so eagled joins the tailnet on its very
# first start and is reachable there for RPCs, without waiting for an
# `eagle configure` call over LAN. eagled starts its tsnet node from this file
# independently of the rest of Configure (see ensureNetwork in daemon.go), so
# the real config (controller address, vehicles, ...) can then be pushed with
# `eagle configure` over the tailnet itself. This file also survives
# ResetConfig (unlike applied-config.toml), so a reset daemon stays reachable
# on the tailnet for the Configure call that reconfigures it. Guarded by its
# own existence, separately from the env file above, so re-running install.sh
# later doesn't clobber a hostname that's since been changed via Configure.
DATA_DIR="$STATE_DIR/.local/share/steeleagle" # matches eagled.service's HOME=$STATE_DIR with XDG_DATA_HOME unset
NETWORK_CONFIG="$DATA_DIR/network-config.toml"
if [[ ! -f "$NETWORK_CONFIG" ]]; then
	install -d -m 755 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR"
	TS_HOSTNAME="${TS_HOSTNAME:-$(hostname)}"
	cat >"$NETWORK_CONFIG" <<-EOF
		vpn = true

		[tailscale]
		hostname = "$TS_HOSTNAME"
		authkey-env = "TS_AUTHKEY"
	EOF
	if [[ -n "${TS_VEHICLE_AUTHKEY:-}" ]]; then
		echo 'vehicle-authkey-env = "TS_VEHICLE_AUTHKEY"' >>"$NETWORK_CONFIG"
	fi
	chown "$SERVICE_USER:$SERVICE_USER" "$NETWORK_CONFIG"
	chmod 600 "$NETWORK_CONFIG"
	echo "seeded $NETWORK_CONFIG (hostname=$TS_HOSTNAME) so eagled joins the tailnet on start"
fi

install -m 644 "$SCRIPT_DIR/eagled.service" "$UNIT_PATH"

systemctl daemon-reload
systemctl enable eagled.service
# restart (not `enable --now`, which no-ops on an already-running unit) so
# re-running this script after a rebuild actually picks up the new binary
systemctl restart eagled.service

echo "eagled installed and started; check status with: systemctl status eagled"
