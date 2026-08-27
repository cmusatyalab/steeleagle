#!/bin/sh
# Builds the missionservice binary in place. Run by eagled's InstallPlugin
# (cmd/eagled/install_plugin.go) with this directory as the working
# directory -- see run.sh for how the resulting binary gets launched.
set -e

GO_VERSION=1.26.5
TOOLCHAIN_DIR="${HOME:-/tmp}/.local/steeleagle-go-toolchain"

if ! command -v go >/dev/null 2>&1; then
	echo "install.sh: go not found, installing go $GO_VERSION into $TOOLCHAIN_DIR"

	arch=$(uname -m)
	case "$arch" in
		x86_64) goarch=amd64 ;;
		aarch64|arm64) goarch=arm64 ;;
		armv7l|armv6l) goarch=arm ;;
		*)
			echo "install.sh: unsupported architecture $arch, install Go manually" >&2
			exit 1
			;;
	esac
	os=$(uname -s | tr '[:upper:]' '[:lower:]')
	tarball="go${GO_VERSION}.${os}-${goarch}.tar.gz"

	mkdir -p "$TOOLCHAIN_DIR"
	if command -v curl >/dev/null 2>&1; then
		curl -fsSL "https://go.dev/dl/${tarball}" -o "$TOOLCHAIN_DIR/${tarball}"
	elif command -v wget >/dev/null 2>&1; then
		wget -qO "$TOOLCHAIN_DIR/${tarball}" "https://go.dev/dl/${tarball}"
	else
		echo "install.sh: need curl or wget to download Go" >&2
		exit 1
	fi

	rm -rf "$TOOLCHAIN_DIR/go"
	tar -C "$TOOLCHAIN_DIR" -xzf "$TOOLCHAIN_DIR/${tarball}"
	rm -f "$TOOLCHAIN_DIR/${tarball}"

	PATH="$TOOLCHAIN_DIR/go/bin:$PATH"
	export PATH
fi

echo "install.sh: building missionservice with $(go version)"
CGO_ENABLED=0 go build -o missionservice .
