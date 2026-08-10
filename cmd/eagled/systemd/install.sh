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
	install -m 640 -o root -g "$SERVICE_USER" "$SCRIPT_DIR/eagled.env.example" "$ENV_FILE"
	echo "wrote default env file to $ENV_FILE (edit TS_AUTHKEY there if needed)"
fi

install -m 644 "$SCRIPT_DIR/eagled.service" "$UNIT_PATH"

systemctl daemon-reload
systemctl enable eagled.service
# restart (not `enable --now`, which no-ops on an already-running unit) so
# re-running this script after a rebuild actually picks up the new binary
systemctl restart eagled.service

echo "eagled installed and started; check status with: systemctl status eagled"
