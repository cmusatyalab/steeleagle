#!/usr/bin/env bash
# Install liburiel so the Uriel Go bindings (github.com/cmusatyalab/uriel/go) can link against it.
#
# The Go bindings link liburiel statically and find it through cgo's pkg-config. This script
# installs liburiel.a, <uriel/uriel.h> and uriel.pc under a prefix that pkg-config searches by
# default. After that, `go build` works on any module that depends on the bindings, with no extra
# environment.
#
# It downloads the prebuilt library from the cmusatyalab/uriel GitHub release (Linux x86_64 and
# aarch64). By default it installs the version go.mod requires, so the library always matches the
# bindings.
#
#   tools/uriel/install.sh                        # go.mod's version to /usr/local (uses sudo if needed)
#   tools/uriel/install.sh --prefix ~/.local      # installs there; prints the PKG_CONFIG_PATH to export
#   tools/uriel/install.sh --version v0.2.0       # installs that release instead
#
# Run it again whenever go.mod moves to a new Uriel version: the build stops with an ABI mismatch
# error when the installed library does not match the bindings.

set -euo pipefail

REPO=cmusatyalab/uriel
GO_MOD=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/go.mod
PREFIX=/usr/local
VERSION=

usage() {
    cat <<'EOF'
usage: tools/uriel/install.sh [options]

Downloads and installs liburiel with its header and pkg-config file so that the Uriel Go bindings build.

options:
  --prefix <dir>       install prefix (default: /usr/local)
  --version <version>  Uriel release to install, e.g. v0.2.0 (default: the version go.mod requires)
  -h, --help           show this help
EOF
}

die() {
    echo "install: $*" >&2
    exit 1
}

while (($#)); do
    case $1 in
    --prefix)
        (($# >= 2)) || die "--prefix needs a directory"
        PREFIX=$2
        shift 2
        ;;
    --version)
        (($# >= 2)) || die "--version needs a release version"
        VERSION=$2
        shift 2
        ;;
    -h | --help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        die "unknown option: $1"
        ;;
    esac
done

command -v pkg-config >/dev/null || die "pkg-config is not installed"
command -v curl >/dev/null || die "curl is not installed"
command -v tar >/dev/null || die "tar is not installed"

if [[ -z $VERSION ]]; then
    [[ -f $GO_MOD ]] || die "could not find $GO_MOD; pass --version"
    VERSION=$(sed -n 's|^[[:space:]]*github.com/cmusatyalab/uriel/go \(v[^ ]*\).*|\1|p' "$GO_MOD")
    [[ -n $VERSION ]] || die "$GO_MOD does not require github.com/cmusatyalab/uriel/go; pass --version"
fi
VERSION=v${VERSION#v}
[[ $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
    die "$VERSION is not a release version; prebuilt libraries exist only for tagged releases"

[[ $(uname -s) == Linux ]] || die "prebuilt liburiel is only published for Linux"
case $(uname -m) in
x86_64 | amd64) arch=x86_64 ;;
aarch64 | arm64) arch=aarch64 ;;
*) die "no prebuilt liburiel for $(uname -m)" ;;
esac

name=liburiel-${VERSION#v}-linux-$arch
url=https://github.com/$REPO/releases/download/$VERSION/$name.tar.gz

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "install: downloading $url"
curl -fsSL -o "$work/$name.tar.gz" "$url" || die "could not download $url"
tar -xzf "$work/$name.tar.gz" -C "$work"
stage="$work/$name"
[[ -f $stage/lib/liburiel.a && -f $stage/lib/pkgconfig/uriel.pc && -d $stage/include/uriel ]] ||
    die "$name.tar.gz does not have the expected layout"

sudo=
if ! mkdir -p "$PREFIX" 2>/dev/null || [[ ! -w $PREFIX ]]; then
    command -v sudo >/dev/null || die "$PREFIX is not writable and sudo is not available"
    sudo=sudo
fi

echo "install: installing to $PREFIX"
# Remove a previous install first so stale headers don't linger next to the new ones.
$sudo rm -rf "$PREFIX/include/uriel"
$sudo mkdir -p "$PREFIX/include" "$PREFIX/lib/pkgconfig"
$sudo cp -R "$stage/include/uriel" "$PREFIX/include/"
$sudo cp "$stage/lib/liburiel.a" "$PREFIX/lib/"
$sudo cp "$stage/lib/pkgconfig/uriel.pc" "$PREFIX/lib/pkgconfig/"

pcdir=$(cd "$PREFIX/lib/pkgconfig" && pwd -P)
found=$(PKG_CONFIG_PATH= pkg-config --variable=pcfiledir uriel 2>/dev/null || true)
if [[ -n $found && $(cd "$found" && pwd -P) == "$pcdir" ]]; then
    echo "install: done; Go builds will find liburiel through pkg-config"
else
    echo "install: done, but $pcdir is not on pkg-config's default search path."
    echo "install: add this to your shell profile so Go can find liburiel:"
    echo "  export PKG_CONFIG_PATH=$pcdir\${PKG_CONFIG_PATH:+:\$PKG_CONFIG_PATH}"
fi
