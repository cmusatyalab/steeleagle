#!/usr/bin/env bash
# Build and install libgabriel so the gabriel2 Go bindings can link against it.
#
# The Go bindings (github.com/cmusatyalab/gabriel/go) link libgabriel statically and find it
# through cgo's pkg-config. This script fetches the latest gabriel2 source as a tarball, builds
# the static library with cargo-c, and installs libgabriel.a, <gabriel/gabriel.h> and gabriel.pc
# under a prefix that pkg-config searches by default. After that, `go build` works on any module
# that depends on the bindings, with no extra environment.
#
#   tools/install_libgabriel.sh                   # installs to /usr/local (uses sudo if needed)
#   tools/install_libgabriel.sh --prefix ~/.local # installs there; prints the PKG_CONFIG_PATH to export
#
# Run it again whenever the bindings move to a new ABI version: the build stops with an ABI
# mismatch error when the installed library does not match the bindings.

set -euo pipefail

REPO=cmusatyalab/gabriel
REF=gabriel2
PREFIX=/usr/local

usage() {
    cat <<'EOF'
usage: tools/install_libgabriel.sh [options]

Fetches the latest gabriel source, builds libgabriel.a and installs it with its header and
pkg-config file so that the gabriel Go bindings build.

options:
  --prefix <dir>  install prefix (default: /usr/local)
  --ref <branch>  branch of github.com/cmusatyalab/gabriel to build (default: gabriel2)
  -h, --help      show this help
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
    --ref)
        (($# >= 2)) || die "--ref needs a branch"
        REF=$2
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

command -v curl >/dev/null || die "curl is not installed"
command -v tar >/dev/null || die "tar is not installed"
command -v cargo >/dev/null || die "cargo is not installed (see https://rustup.rs)"
command -v pkg-config >/dev/null || die "pkg-config is not installed"

if ! cargo cinstall --version >/dev/null 2>&1; then
    echo "install: cargo-c not found, installing it"
    cargo install cargo-c --locked
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "install: fetching $REPO@$REF"
mkdir "$work/src"
curl -fsSL "https://github.com/$REPO/archive/refs/heads/$REF.tar.gz" |
    tar -xz -C "$work/src" --strip-components=1

# Build and stage as the current user so the Rust toolchain is never run as root; only the copy
# into the prefix may need elevated permissions.
echo "install: building libgabriel"
stage="$work/stage"
cargo cinstall --release -p gabriel \
    --manifest-path "$work/src/Cargo.toml" \
    --target-dir "$work/target" \
    --library-type staticlib \
    --prefix "$PREFIX" --libdir lib \
    --destdir "$stage"

sudo=
if ! mkdir -p "$PREFIX" 2>/dev/null || [[ ! -w $PREFIX ]]; then
    command -v sudo >/dev/null || die "$PREFIX is not writable and sudo is not available"
    sudo=sudo
fi

echo "install: installing to $PREFIX"
# Remove a previous install first so stale headers don't linger next to the new ones.
$sudo rm -rf "$PREFIX/include/gabriel"
$sudo cp -R "$stage$PREFIX/." "$PREFIX/"

pcdir="$PREFIX/lib/pkgconfig"
if PKG_CONFIG_PATH= pkg-config --exists gabriel 2>/dev/null &&
    [[ $(PKG_CONFIG_PATH= pkg-config --variable=prefix gabriel) == "$PREFIX" ]]; then
    echo "install: done; Go builds will find libgabriel through pkg-config"
else
    echo "install: done, but $pcdir is not on pkg-config's default search path."
    echo "install: add this to your shell profile so Go can find libgabriel:"
    echo "  export PKG_CONFIG_PATH=$pcdir\${PKG_CONFIG_PATH:+:\$PKG_CONFIG_PATH}"
fi
