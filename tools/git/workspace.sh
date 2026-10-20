#!/usr/bin/env bash
# Set up/tear down the Go workspace for this project.
#
# Call whenever local override is needed. Sets each submodule to use the local repository
# source rather than fetching it from Github. Tearing down the workspace sets the modules
# to use the proxy.golang package versions instead.
#
# Set up the alias once per clone:
#   tools/git/alias.sh
#
# Then:
#   git workspace up      # brings the workspace online
#   git workspace down    # tears down the workspace
#   git workspace status  # shows whether the workspace is online

set -euo pipefail

usage() {
    cat <<'EOF'
usage: git workspace <up|down|status>

Brings up or tears down the root module Go workspace which sets module paths to be
local overrides instead of proxy.golang sources.

commands:
  up       create go.work using every Go module in the repo (rebuilds it if present)
  down     remove go.work and go.work.sum
  status   show whether the workspace is online and which modules it uses
EOF
}

die() {
    echo "workspace: $*" >&2
    exit 1
}

if (($# != 1)); then
    usage >&2
    exit 2
fi

cd "$(git rev-parse --show-toplevel)"

# Same discovery as release.sh: every go.mod tracked in git, minus testdata and vendor.
modules() {
    local f d
    while IFS= read -r f; do
        d=$(dirname "$f")
        [[ $d == testdata || $d == */testdata || $d == */testdata/* || $d == testdata/* ]] && continue
        [[ $d == vendor/* || $d == */vendor/* ]] && continue
        [[ $d == . ]] && echo . || echo "./$d"
    done < <(git ls-files -- go.mod '*/go.mod')
}

case $1 in
up)
    command -v go >/dev/null || die "go is not installed"
    mapfile -t dirs < <(modules)
    ((${#dirs[@]})) || die "no Go modules found"
    # go.work is generated and gitignored, so rebuild it from scratch to drop stale entries.
    rm -f go.work
    go work init "${dirs[@]}"
    echo "workspace up: ${dirs[*]}"
    ;;
down)
    if [[ ! -e go.work && ! -e go.work.sum ]]; then
        echo "workspace already down"
        exit 0
    fi
    rm -f go.work go.work.sum
    echo "workspace down: modules resolve from their go.mod requirements"
    ;;
status)
    if [[ -e go.work ]]; then
        echo "workspace up:"
        go work edit -json | awk -F'"' '$2 == "DiskPath" { print "  " $4 }'
    else
        echo "workspace down"
    fi
    ;;
-h | --help)
    usage
    ;;
*)
    usage >&2
    die "unknown command: $1"
    ;;
esac
