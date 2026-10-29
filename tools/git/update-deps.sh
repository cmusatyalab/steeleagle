#!/usr/bin/env bash
# Move every Go module in the repo onto the newest published version of each
# other repo module it requires.
#
# Versions are looked up straight from the repo (via GOPRIVATE) rather than the
# proxy, which may not have seen tags pushed moments ago. Only tags that have
# been pushed can be used. The changes to go.mod and go.sum are left in the
# working tree to review and commit.
#
# Set up the alias once per clone:
#   tools/git/alias.sh
#
# Then:
#   git update-deps        # update every module
#   git update-deps -n     # show what would change

set -euo pipefail

usage() {
	cat <<'EOF'
usage: git update-deps [options]

Moves each Go module in the repo onto the newest published version of every
other repo module it requires. Requirements are never downgraded, and the
changes are left uncommitted.

options:
  -n, --dry-run    show what would change without changing anything
  -h, --help       show this help
EOF
}

die() {
	echo "update-deps: $*" >&2
	exit 1
}

dry_run=false

while (($#)); do
	case $1 in
	-n | --dry-run) dry_run=true ;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		usage >&2
		die "unknown argument: $1"
		;;
	esac
	shift
done

command -v go >/dev/null || die "go is not installed"

cd "$(git rev-parse --show-toplevel)"

# --- module discovery ---------------------------------------------------------

# Same discovery as release.sh: every go.mod tracked in git, minus testdata and vendor.
dirs=()
while IFS= read -r f; do
	d=$(dirname "$f")
	[[ $d == testdata || $d == */testdata || $d == */testdata/* || $d == testdata/* ]] && continue
	[[ $d == vendor/* || $d == */vendor/* ]] && continue
	dirs+=("$d")
done < <(git ls-files -- go.mod '*/go.mod')

name_of() { [[ $1 == . ]] && echo root || echo "$1"; }
path_of() { awk '$1 == "module" { print $2; exit }' "$1/go.mod"; }

# Version of dep_path that the go.mod in dir requires, if any.
required_of() {
	sed -nE "s#^[[:space:]]*(require[[:space:]]+)?${2//./\\.}[[:space:]]+(v[^[:space:]]+).*#\2#p" "$1/go.mod" | head -1
}

declare -A mod_path
for d in "${dirs[@]}"; do
	mod_path[$d]=$(path_of "$d")
	[[ -n ${mod_path[$d]} ]] || die "$d/go.mod has no module line"
done

# The repo's import path prefix, e.g. github.com/cmusatyalab/steeleagle.
repo_path=${mod_path[.]:-}
repo_path=${repo_path%/v[0-9]*}

# --- version math -------------------------------------------------------------

stage_rank() {
	case $1 in
	alpha) echo 1 ;;
	beta) echo 2 ;;
	*) echo 3 ;;
	esac
}

semver_re='^v([0-9]+)\.([0-9]+)\.([0-9]+)(-(alpha|beta)\.([0-9]+))?$'

# Sortable key for a version string, or nothing if it isn't one of ours.
version_key() {
	[[ $1 =~ $semver_re ]] || return 0
	printf '%06d%06d%06d%d%06d' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" \
		"$(stage_rank "${BASH_REMATCH[5]:-prod}")" "${BASH_REMATCH[6]:-0}"
}

# Run go for the module in dir, resolving repo modules straight from the repo.
go_in() {
	local dir=$1
	shift
	(cd "$dir" && GOWORK=off GOFLAGS=-mod=mod GOPRIVATE="${GOPRIVATE:+$GOPRIVATE,}$repo_path" go "$@")
}

# Sets target to the newest published version of the repo module in dep, or
# nothing if it has none, looking each module up once. go list leaves out
# retracted versions, and only lists those of the module's major version.
declare -A newest
newest_of() {
	local dep=$1 out v k best= best_key=
	if [[ -z ${newest[$dep]+set} ]]; then
		out=$(go_in "$dep" list -m -versions "${mod_path[$dep]}") ||
			die "couldn't list the versions of ${mod_path[$dep]}"
		for v in ${out#* }; do
			k=$(version_key "$v")
			[[ -n $k ]] || continue
			if [[ -z $best_key || $k > $best_key ]]; then
				best_key=$k best=$v
			fi
		done
		newest[$dep]=$best
		note_unpushed "$dep" "$best_key"
	fi
	target=${newest[$dep]}
}

# Warns when dep has a local tag newer than anything published, since go can
# only fetch versions that have been pushed.
note_unpushed() {
	local dep=$1 published_key=$2 prefix= major t v k best= best_key=
	[[ $dep == . ]] || prefix=$dep/
	# go only lists versions of the module path's major version.
	[[ ${mod_path[$dep]} =~ /v([0-9]+)$ ]] && major=${BASH_REMATCH[1]} || major='[01]'
	while IFS= read -r t; do
		v=${t#"$prefix"}
		[[ $v =~ ^v$major\. ]] || continue
		k=$(version_key "$v")
		[[ -n $k ]] || continue
		if [[ -z $best_key || $k > $best_key ]]; then
			best_key=$k best=$t
		fi
	done < <(git tag --list "${prefix}v*")
	if [[ -n $best_key && $best_key > $published_key ]]; then
		echo "update-deps: note: tag $best hasn't been pushed, so ${mod_path[$dep]} isn't moved onto it; push it and rerun" >&2
	fi
}

# --- update -------------------------------------------------------------------

updated=0
for dir in "${dirs[@]}"; do
	args=()
	for dep in "${dirs[@]}"; do
		[[ $dep == "$dir" ]] && continue
		required=$(required_of "$dir" "${mod_path[$dep]}")
		[[ -n $required ]] || continue
		newest_of "$dep"
		[[ -n $target ]] || continue
		have=$(version_key "$required")
		if [[ -z $have ]]; then
			echo "update-deps: note: $(name_of "$dir") requires ${mod_path[$dep]} $required, which isn't a release; leaving it" >&2
			continue
		fi
		[[ $(version_key "$target") > $have ]] || continue
		echo "$(name_of "$dir"): ${mod_path[$dep]} $required -> $target"
		args+=("${mod_path[$dep]}@$target")
	done
	((${#args[@]})) || continue
	updated=$((updated + 1))
	$dry_run && continue
	go_in "$dir" get "${args[@]}" || die "go get failed in $(name_of "$dir")"
done

if ((updated == 0)); then
	echo "update-deps: every module is on the newest versions"
elif $dry_run; then
	echo "dry run: nothing changed"
else
	echo "update-deps: updated $updated module(s); review and commit the go.mod and go.sum changes"
fi
