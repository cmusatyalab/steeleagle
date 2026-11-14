#!/usr/bin/env bash
# Build the eagle and eagled release binaries into dist/.
#
# It runs inside a manylinux image (see .github/workflows/release-eagle.yml), whose old glibc keeps
# what eagled needs low: eagled links liburiel through cgo, so it links the system glibc
# dynamically, and binaries built against a glibc run only on systems with that glibc or newer.
# GitHub's JavaScript actions can't run in these images, so this script sets up Go and liburiel
# itself. To reproduce a release build locally, from the repository root:
#
#   docker run --rm -v "$PWD:/src" -w /src quay.io/pypa/manylinux2014_x86_64 tools/release/build-eagle.sh

set -euo pipefail

# The newest glibc eagled may need; it matches the manylinux2014 build image. Ubuntu 18.04 ships
# 2.27, so binaries built on newer images don't run there.
MAX_GLIBC=2.17
GO_DOWNLOAD_URL=https://go.dev/dl
GO_ROOT=/usr/local/go
DIST=dist

die() {
    echo "build-eagle: $*" >&2
    exit 1
}

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

case $(uname -m) in
x86_64) arch=amd64 ;;
aarch64) arch=arm64 ;;
*) die "unsupported architecture $(uname -m)" ;;
esac

go_version=$(sed -n 's/^go \([0-9.]*\)$/\1/p' go.mod)
[[ -n $go_version ]] || die "could not find the Go version in go.mod"
echo "build-eagle: installing Go $go_version"
rm -rf "$GO_ROOT"
curl -fsSL "$GO_DOWNLOAD_URL/go$go_version.linux-$arch.tar.gz" | tar -xz -C "$(dirname "$GO_ROOT")"
export PATH=$GO_ROOT/bin:$PATH

# liburiel.a, linked statically into eagled. It goes to /usr/local, which pkg-config doesn't
# search on these images.
tools/uriel/install.sh
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig

# The mounted repository belongs to another user, so git refuses to read it and `go build` can't
# stamp VCS info.
git config --global --add safe.directory "$PWD"

mkdir -p "$DIST"
eagle=$DIST/eagle-linux-$arch
eagled=$DIST/eagled-linux-$arch
CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o "$eagle" ./cmd/eagle
CGO_ENABLED=1 go build -trimpath -ldflags='-s -w' -o "$eagled" ./cmd/eagled

ldd "$eagled"
if ldd "$eagled" | grep -q uriel; then
    die "eagled links liburiel dynamically"
fi

need=$(objdump -T "$eagled" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -n 1)
echo "build-eagle: eagled needs $need"
newest=$(printf '%s\n' "$need" "GLIBC_$MAX_GLIBC" | sort -V | tail -n 1)
[[ $newest == "GLIBC_$MAX_GLIBC" ]] || die "eagled needs $need, newer than glibc $MAX_GLIBC"
