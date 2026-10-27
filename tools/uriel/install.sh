#!/usr/bin/env bash
# Install liburiel so the Uriel Go bindings (github.com/cmusatyalab/uriel/go) can link against it.
#
# The Go bindings link liburiel statically and find it through cgo's pkg-config. This script
# installs liburiel.a, <uriel/uriel.h> and uriel.pc under a prefix that pkg-config searches by
# default. After that, `go build` works on any module that depends on the bindings, with no extra
# environment.
#
# Uriel lives on the uriel branch of the public cmusatyalab/gabriel repo, which has no prebuilt
# releases of it, so this script builds it from source with cargo-c. It needs git, Rust, libclang
# and pkg-config. By default it builds the gabriel commit that go.mod's replace directive pins, so
# the library always matches the bindings.
#
#   tools/uriel/install.sh                        # the pinned commit to /usr/local (uses sudo if needed)
#   tools/uriel/install.sh --prefix ~/.local      # installs there; prints the PKG_CONFIG_PATH to export
#   tools/uriel/install.sh --ref uriel            # builds the branch's latest commit instead
#
# Run it again whenever go.mod moves to a new gabriel commit: the build stops with an ABI mismatch
# error when the installed library does not match the bindings.

set -euo pipefail

REPO=cmusatyalab/gabriel
GIT_URL=${URIEL_GIT_URL:-https://github.com/$REPO.git}
GO_MOD=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/go.mod
PREFIX=/usr/local
REF=

usage() {
    cat <<'EOF'
usage: tools/uriel/install.sh [options]

Builds and installs liburiel with its header and pkg-config file so that the Uriel Go bindings build.

options:
  --prefix <dir>  install prefix (default: /usr/local)
  --ref <ref>     branch, tag or commit of gabriel to build (default: the commit go.mod pins)
  -h, --help      show this help

environment:
  URIEL_GIT_URL   URL to clone (default: https://github.com/cmusatyalab/gabriel.git)
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
        (($# >= 2)) || die "--ref needs a branch, tag or commit"
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

command -v pkg-config >/dev/null || die "pkg-config is not installed"
command -v git >/dev/null || die "git is not installed"
command -v cargo >/dev/null || die "cargo is not installed (see https://rustup.rs)"

if [[ -z $REF ]]; then
    # The commit hash at the end of the pseudo-version in go.mod's replace directive.
    [[ -f $GO_MOD ]] || die "could not find $GO_MOD; pass --ref"
    REF=$(sed -n 's|.*github.com/cmusatyalab/gabriel/go v[^ ]*-\([0-9a-f]\{12\}\)[[:space:]]*$|\1|p' "$GO_MOD")
    [[ -n $REF ]] || die "$GO_MOD does not pin a gabriel commit; pass --ref"
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
stage="$work/stage"

if ! cargo cinstall --version >/dev/null 2>&1; then
    echo "install: cargo-c not found, installing it"
    cargo install cargo-c --locked
fi

# A blobless clone has every branch's commits, so REF can be a branch, a tag or an abbreviated
# commit hash, while downloading only the files of the commit that is checked out.
echo "install: fetching $REPO@$REF"
git clone -q --filter=blob:none --no-checkout "$GIT_URL" "$work/src" ||
    die "could not clone $GIT_URL"
git -C "$work/src" -c advice.detachedHead=false checkout -q "$REF" ||
    die "$GIT_URL has no branch, tag or commit $REF"

# Build and stage as the current user so the Rust toolchain is never run as root; only the copy
# into the prefix may need elevated permissions. Only the static library, so programs linked
# with it need nothing of Uriel's where they run.
echo "install: building liburiel (needs libclang)"
cargo cinstall --release --locked -p uriel \
    --manifest-path "$work/src/Cargo.toml" \
    --target-dir "$work/target" \
    --library-type staticlib \
    --prefix /usr/local --libdir lib \
    --destdir "$work/build"
mv "$work/build/usr/local" "$stage"
# Name the directory uriel.pc is in, so the install is relocatable.
sed -i 's|^prefix=.*|prefix=${pcfiledir}/../..|' "$stage/lib/pkgconfig/uriel.pc"

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
