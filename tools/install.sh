#!/bin/sh
# Install SteelEagle from its GitHub releases, without cloning the repo.
#
#   curl -fsSL https://raw.githubusercontent.com/cmusatyalab/steeleagle/main/tools/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/cmusatyalab/steeleagle/main/tools/install.sh | sh -s -- --sdk
#
# It downloads eagle and eagled for this machine's architecture into
# ~/.local/bin and installs Pixi, which eagled starts plugins with. With
# --sdk, it also downloads eaglec, and installs Go into ~/.local/go if there
# is no go on the PATH. `eagle init` then installs the eagled service.
#
# The newest stable release is installed. If there is none yet, or with
# --pre, the newest release is installed even if it is an alpha or beta.

set -eu

REPO=cmusatyalab/steeleagle
BIN=$HOME/.local/bin
SDK=
PRE=

usage() {
    cat <<'EOF'
usage: install.sh [options]

Installs eagle, eagled and Pixi.

options:
  --sdk        also install eaglec, and Go if it isn't installed
  --pre        install the newest release even if it is an alpha or beta
  -h, --help   show this help
EOF
}

say() {
    echo "install: $*"
}

die() {
    echo "install: $*" >&2
    exit 1
}

while [ $# -gt 0 ]; do
    case $1 in
    --sdk) SDK=1 ;;
    --pre) PRE=1 ;;
    -h | --help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        die "unknown option: $1"
        ;;
    esac
    shift
done

for cmd in curl sha256sum tar uname; do
    command -v "$cmd" >/dev/null || die "$cmd is not installed"
done

[ "$(uname -s)" = Linux ] || die "SteelEagle is only published for Linux"
case $(uname -m) in
x86_64 | amd64) ARCH=amd64 ;;
aarch64 | arm64) ARCH=arm64 ;;
*) die "no SteelEagle release for $(uname -m)" ;;
esac

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# The tags of the repo's releases, newest first
curl -fsSL "https://api.github.com/repos/$REPO/releases?per_page=100" -o "$work/releases.json" ||
    die "could not list the releases of $REPO"
sed -n 's/^ *"tag_name": *"\([^"]*\)".*/\1/p' "$work/releases.json" >"$work/tags"

# latest_tag prints the newest release tag matching the extended regex $1,
# which is stable unless there is no stable release or --pre was given.
latest_tag() {
    tag=
    [ -z "$PRE" ] && tag=$(grep -E "$1" "$work/tags" | grep -v -e - | head -n 1)
    [ -z "$tag" ] && tag=$(grep -E "$1" "$work/tags" | head -n 1)
    echo "$tag"
}

# download fetches each of the binaries $2... of release $1 into $BIN, after
# checking them against the release's SHA256SUMS.
download() {
    tag=$1
    shift
    # A tag such as sdk/v0.2.0 has a slash, which must be escaped in the URL
    base=https://github.com/$REPO/releases/download/$(echo "$tag" | sed 's|/|%2F|g')
    dir=$work/$(echo "$tag" | tr / -)
    mkdir -p "$dir"
    curl -fsSL -o "$dir/SHA256SUMS" "$base/SHA256SUMS" || die "could not download the checksums of $tag"
    for name in "$@"; do
        asset=$name-linux-$ARCH
        say "downloading $asset from $tag"
        curl -fsSL -o "$dir/$asset" "$base/$asset" || die "could not download $asset from $tag"
        (cd "$dir" && grep " $asset\$" SHA256SUMS | sha256sum -c --quiet -) ||
            die "$asset from $tag does not match its checksum"
        chmod 755 "$dir/$asset"
        # Rename over the old binary, so that a running one isn't written to
        mv -f "$dir/$asset" "$BIN/.$name.new"
        mv -f "$BIN/.$name.new" "$BIN/$name"
    done
}

mkdir -p "$BIN"

# Releases before v4 have no eagle binaries
tag=$(latest_tag '^v([4-9]|[1-9][0-9]+)\.')
[ -n "$tag" ] || die "$REPO has no eagle release"
download "$tag" eagle eagled

if [ -n "$SDK" ]; then
    tag=$(latest_tag '^sdk/v[0-9]')
    [ -n "$tag" ] || die "$REPO has no SDK release"
    download "$tag" eaglec
fi

# eagled starts plugins with pixi, and its service looks in ~/.pixi/bin
if command -v pixi >/dev/null || [ -x "$HOME/.pixi/bin/pixi" ]; then
    say "pixi is already installed"
else
    say "installing pixi"
    curl -fsSL https://pixi.sh/install.sh | sh || die "could not install pixi"
fi

# eaglec builds missions with go
if [ -n "$SDK" ]; then
    if command -v go >/dev/null; then
        say "go is already installed"
    else
        version=$(curl -fsSL 'https://go.dev/VERSION?m=text' | head -n 1) ||
            die "could not find the latest Go version"
        say "installing $version to $HOME/.local/go"
        curl -fsSL -o "$work/go.tar.gz" "https://go.dev/dl/$version.linux-$ARCH.tar.gz" ||
            die "could not download $version"
        rm -rf "$HOME/.local/go"
        tar -xzf "$work/go.tar.gz" -C "$HOME/.local"
        ln -sf "$HOME/.local/go/bin/go" "$HOME/.local/go/bin/gofmt" "$BIN/"
    fi
fi

case :$PATH: in
*:"$BIN":*) ;;
*) say "add $BIN to your PATH: export PATH=\"$BIN:\$PATH\"" ;;
esac
say "done; run eagle init to get started!"
