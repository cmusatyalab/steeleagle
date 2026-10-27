#!/usr/bin/env bash
# Register the git aliases for the scripts in this directory.
#
# Run once per clone (from anywhere inside the repo):
#   tools/git/alias.sh
#
# The aliases are written to the clone's local git config, so they only apply
# to this repository. Rerunning is safe; existing aliases are overwritten.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# alias name -> script path, relative to the repo root (git runs '!' aliases
# from the top of the working tree).
aliases=(
    "release:tools/git/release.sh"
    "update-deps:tools/git/update-deps.sh"
    "workspace:tools/git/workspace.sh"
)

for entry in "${aliases[@]}"; do
    name=${entry%%:*}
    script=${entry#*:}
    [[ -x $script ]] || chmod +x "$script"
    git config --local "alias.$name" "!$script"
    echo "git $name -> $script"
done
