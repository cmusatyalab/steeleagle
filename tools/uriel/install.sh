#!/usr/bin/env bash
# Install liburiel so the Uriel Go bindings (github.com/cmusatyalab/uriel/go) can link against it.
#
# The Go bindings link liburiel statically and find it through cgo's pkg-config. This script
# installs liburiel.a, <uriel/uriel.h> and uriel.pc under a prefix that pkg-config searches by
# default. After that, `go build` works on any module that depends on the bindings, with no extra
# environment.
#
# cmusatyalab/uriel is private, so both ways of getting liburiel need GitHub access:
#   - prebuilt: downloads the release tarball through the GitHub API. Needs a token with read access
#     to the repo, from GH_TOKEN, GITHUB_TOKEN or a logged-in `gh`. Needs no Rust toolchain.
#   - source:   clones the repo over SSH and builds it with cargo-c. Needs an SSH key with access,
#     Rust, libclang and pkg-config.
# By default it uses the prebuilt library when a token is available, and builds from source if not.
#
#   tools/uriel/install.sh                        # latest release to /usr/local (uses sudo if needed)
#   tools/uriel/install.sh --version 0.1.0        # a specific release; match the Go module's version
#   tools/uriel/install.sh --prefix ~/.local      # installs there; prints the PKG_CONFIG_PATH to export
#   tools/uriel/install.sh --source --ref main    # builds an unreleased branch
#
# Run it again whenever the Go module moves to a new version: the build stops with an ABI mismatch
# error when the installed library does not match the bindings.

set -euo pipefail

REPO=cmusatyalab/uriel
GIT_URL=${URIEL_GIT_URL:-git@github.com:$REPO.git}
API=https://api.github.com/repos/$REPO
PREFIX=/usr/local
VERSION=
REF=
METHOD=auto
ARCH=

usage() {
    cat <<'EOF'
usage: tools/uriel/install.sh [options]

Installs liburiel with its header and pkg-config file so that the Uriel Go bindings build.

options:
  --prefix <dir>       install prefix (default: /usr/local)
  --version <version>  release to install, e.g. 0.1.0 (default: the latest release)
  --prebuilt           download the release's prebuilt library (needs a GitHub token)
  --source             build from source (needs SSH access to the repo, Rust and libclang)
  --ref <ref>          branch, tag or commit to build; implies --source (default: v<version>)
  --arch <arch>        x86_64 or aarch64, for a prebuilt cross-compile target (default: this machine)
  -h, --help           show this help

environment:
  GH_TOKEN, GITHUB_TOKEN  token for downloading prebuilt releases (else `gh auth token` is tried)
  URIEL_GIT_URL           URL to clone for --source (default: git@github.com:cmusatyalab/uriel.git)
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
        (($# >= 2)) || die "--version needs a version"
        VERSION=${2#v}
        shift 2
        ;;
    --ref)
        (($# >= 2)) || die "--ref needs a branch, tag or commit"
        REF=$2
        METHOD=source
        shift 2
        ;;
    --arch)
        (($# >= 2)) || die "--arch needs an architecture"
        ARCH=$2
        shift 2
        ;;
    --prebuilt)
        METHOD=prebuilt
        shift
        ;;
    --source)
        METHOD=source
        shift
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

host_arch=$(uname -m)
case $host_arch in
arm64) host_arch=aarch64 ;;
esac
ARCH=${ARCH:-$host_arch}
case $ARCH in
x86_64 | aarch64) ;;
arm64) ARCH=aarch64 ;;
*) die "no prebuilt liburiel for $ARCH; releases have x86_64 and aarch64" ;;
esac

command -v pkg-config >/dev/null || die "pkg-config is not installed"

TOKEN=${GH_TOKEN:-${GITHUB_TOKEN:-}}
if [[ -z $TOKEN ]] && command -v gh >/dev/null; then
    TOKEN=$(gh auth token 2>/dev/null || true)
fi

if [[ $METHOD == auto ]]; then
    if [[ -n $TOKEN ]]; then
        METHOD=prebuilt
    else
        echo "install: no GitHub token found, building from source"
        METHOD=source
    fi
fi
if [[ $METHOD == source && $ARCH != "$host_arch" ]]; then
    die "--source builds for this machine ($host_arch); use --prebuilt for $ARCH"
fi

api() {
    curl -fsSL -H "Authorization: Bearer $TOKEN" -H "X-GitHub-Api-Version: 2022-11-28" "$@"
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
stage="$work/stage"

if [[ $METHOD == prebuilt ]]; then
    [[ -n $TOKEN ]] || die "--prebuilt needs a token in GH_TOKEN or GITHUB_TOKEN, or a logged-in gh"
    command -v curl >/dev/null || die "curl is not installed"
    command -v tar >/dev/null || die "tar is not installed"
    command -v python3 >/dev/null || die "python3 is not installed (it reads the GitHub API's JSON)"

    if [[ -n $VERSION ]]; then
        release_url="$API/releases/tags/v$VERSION"
    else
        release_url="$API/releases/latest"
    fi
    api -H "Accept: application/vnd.github+json" "$release_url" >"$work/release.json" ||
        die "could not read the release from GitHub; check that the token can read $REPO and that the version exists"

    VERSION=$(python3 -I -c 'import json, sys; print(json.load(sys.stdin)["tag_name"].removeprefix("v"))' \
        <"$work/release.json")
    name="liburiel-$VERSION-linux-$ARCH"
    asset_url=$(python3 -I -c '
import json, sys
name = sys.argv[1] + ".tar.gz"
for asset in json.load(sys.stdin)["assets"]:
    if asset["name"] == name:
        print(asset["url"])
' "$name" <"$work/release.json")
    [[ -n $asset_url ]] || die "release v$VERSION has no $name.tar.gz"

    echo "install: downloading $name"
    mkdir "$stage"
    api -H "Accept: application/octet-stream" "$asset_url" |
        tar -xz -C "$stage" --strip-components=1
else
    command -v git >/dev/null || die "git is not installed"
    command -v cargo >/dev/null || die "cargo is not installed (see https://rustup.rs)"

    if [[ -z $REF ]]; then
        if [[ -z $VERSION ]]; then
            # The newest v<version> tag that is not a release candidate.
            VERSION=$(git ls-remote --tags --refs "$GIT_URL" 'v*' | sed -n 's|.*refs/tags/v||p' |
                grep -v -- - | sort -V | tail -n 1) ||
                die "could not list the tags of $GIT_URL; check that your SSH key can read $REPO"
            [[ -n $VERSION ]] || die "$GIT_URL has no releases; pass --ref to build a branch"
        fi
        REF=v$VERSION
    fi

    if ! cargo cinstall --version >/dev/null 2>&1; then
        echo "install: cargo-c not found, installing it"
        cargo install cargo-c --locked
    fi

    echo "install: fetching $REPO@$REF"
    git init -q "$work/src"
    git -C "$work/src" fetch -q --depth 1 "$GIT_URL" "$REF" ||
        die "could not fetch $REF from $GIT_URL; check the ref and that your SSH key can read $REPO"
    git -C "$work/src" checkout -q FETCH_HEAD

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
    # Name the directory uriel.pc is in, as the release tarballs do, so the install is relocatable.
    sed -i 's|^prefix=.*|prefix=${pcfiledir}/../..|' "$stage/lib/pkgconfig/uriel.pc"
fi

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
