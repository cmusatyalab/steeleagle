#!/usr/bin/env bash
# Tag every Go module and Python package in the repo with its next version in
# one step.
#
# The root module gets plain tags (v4.1.0); nested modules get path-prefixed
# tags (api/go/v0.4.0, sdk/v0.2.0, config/v0.1.0), which is how Go resolves
# versions for modules that live in subdirectories. Modules are discovered from
# the go.mod files tracked in git, so new ones are picked up automatically.
# Python packages that take their version from git through setuptools-scm
# (api/python) are tagged the same way (api/python/v0.4.0), and pushing such a
# tag publishes the package to PyPI.
#
# Modules in a lockstep group (api = api/go + api/python) are always released
# together, on one shared version.
#
# Set up the alias once per clone:
#   tools/git/alias.sh
#
# Then:
#   git release minor              # v4.1.0
#   git release minor alpha        # v4.2.0-alpha.1, then -alpha.2, ...
#   git release minor beta         # v4.2.0-beta.1 (continues an alpha series)
#   git release minor prod         # v4.2.0 (same as omitting the stage)
#
# Afterwards, git update-deps moves every module onto the newest published
# versions of the others, unless --no-update is given.

set -euo pipefail

usage() {
	cat <<'EOF'
usage: git release <patch|minor|major> [alpha|beta|prod] [options]

Bumps every Go module and tag-versioned Python package in the repo and
creates an annotated tag for each one.
Prerelease stages continue an existing series for the same version
(alpha.1 -> alpha.2 -> beta.1 -> prod); going back from beta to alpha is
refused.

options:
  --only <mods>    comma-separated modules or lockstep groups to release:
                   root, api, api/go, api/python, sdk, ...
  --push           push the branch and tags atomically, then warm the Go proxy
  --no-sync        leave require lines on other repo modules as they are
  --no-update      don't run git update-deps after releasing
  --remote <name>  remote to fetch from and push to (default: origin)
  --no-fetch       don't fetch tags from the remote first
  -n, --dry-run    show what would happen without changing anything
  -y, --yes        don't ask for confirmation
  -h, --help       show this help
EOF
}

die() {
	echo "release: $*" >&2
	exit 1
}

level=
stage=prod
only=
remote=origin
push=false
sync=true
update=true
fetch=true
dry_run=false
yes=false

while (($#)); do
	case $1 in
	patch | minor | major)
		[[ -z $level ]] || die "bump level given twice"
		level=$1
		;;
	alpha | beta | prod) stage=$1 ;;
	--only)
		only=${2:?--only needs a module list}
		shift
		;;
	--only=*) only=${1#*=} ;;
	--remote)
		remote=${2:?--remote needs a name}
		shift
		;;
	--remote=*) remote=${1#*=} ;;
	--push) push=true ;;
	--no-sync) sync=false ;;
	--no-update) update=false ;;
	--no-fetch) fetch=false ;;
	-n | --dry-run) dry_run=true ;;
	-y | --yes) yes=true ;;
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

if [[ -z $level ]]; then
	usage >&2
	exit 2
fi

cd "$(git rev-parse --show-toplevel)"

if ! git diff --quiet || ! git diff --cached --quiet; then
	$dry_run || die "working tree has uncommitted changes"
	echo "release: warning: working tree has uncommitted changes" >&2
fi

branch=$(git symbolic-ref -q --short HEAD || true)
if $push && [[ -z $branch ]]; then
	die "--push needs a checked-out branch (HEAD is detached)"
fi

if $fetch; then
	git fetch --quiet --tags "$remote" ||
		echo "release: warning: could not fetch tags from $remote; using local tags" >&2
fi

# --- module discovery ---------------------------------------------------------

dirs=()
while IFS= read -r f; do
	d=$(dirname "$f")
	[[ $d == testdata || $d == */testdata || $d == */testdata/* || $d == testdata/* ]] && continue
	[[ $d == vendor/* || $d == */vendor/* ]] && continue
	dirs+=("$d")
done < <(git ls-files -- go.mod '*/go.mod')
go_dirs=("${dirs[@]}")

# Python packages whose version setuptools-scm reads from these tags. Ones
# without a [tool.setuptools_scm] table keep a hand-written version and are
# left alone.
py_dirs=()
while IFS= read -r f; do
	d=$(dirname "$f")
	[[ $d == testdata || $d == */testdata || $d == */testdata/* || $d == testdata/* ]] && continue
	grep -q '^\[tool\.setuptools_scm\]' "$f" || continue
	py_dirs+=("$d")
	dirs+=("$d")
done < <(git ls-files -- pyproject.toml '*/pyproject.toml')

is_py() { [[ " ${py_dirs[*]} " == *" $1 "* ]]; }

# Consumers ignore replace directives (and go install refuses them), so a
# tagged go.mod must not depend on one; use go.work for local development.
for d in "${go_dirs[@]}"; do
	if grep -Eq '^[[:space:]]*replace([[:space:]]|\()' "$d/go.mod"; then
		die "$d/go.mod has a replace directive; drop it and use go.work instead"
	fi
done

name_of() { [[ $1 == . ]] && echo root || echo "$1"; }
prefix_of() { [[ $1 == . ]] && echo "" || echo "$1/"; }
path_of() { awk '$1 == "module" { print $2; exit }' "$1/go.mod"; }
# The [project] name in a pyproject.toml, e.g. steeleagle-protocol.
py_name_of() { sed -nE '/^\[project\]/,/^\[/ s/^name[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$1/pyproject.toml" | head -1; }

# Version of dep_path that the go.mod in dir requires, if any.
required_of() {
	sed -nE "s#^[[:space:]]*(require[[:space:]]+)?${2//./\\.}[[:space:]]+(v[^[:space:]]+).*#\2#p" "$1/go.mod" | head -1
}

declare -A mod_path
for d in "${go_dirs[@]}"; do
	mod_path[$d]=$(path_of "$d")
	[[ -n ${mod_path[$d]} ]] || die "$d/go.mod has no module line"
done
for d in "${py_dirs[@]}"; do
	mod_path[$d]=$(py_name_of "$d")
	[[ -n ${mod_path[$d]} ]] || die "$d/pyproject.toml has no [project] name"
done

# Modules released in lockstep: selecting one selects them all, and they share
# one version, bumped from the newest release of any of them. The group's name
# also works with --only.
lockstep=(
	"api=api/go,api/python"
)

declare -A group_members group_named
for g in "${lockstep[@]}"; do
	gname=${g%%=*}
	IFS=, read -ra members <<<"${g#*=}"
	for m in "${members[@]}"; do
		[[ -n ${mod_path[$m]:-} ]] || die "lockstep group $gname names $m, which isn't a module"
		group_members[$m]="${members[*]}"
	done
	group_named[$gname]="${members[*]}"
done

# Every module released together with dir, including dir.
members_of() { echo "${group_members[$1]:-$1}"; }

# The repo's import path prefix, e.g. github.com/cmusatyalab/steeleagle.
repo_path=${mod_path[.]:-}
repo_path=${repo_path%/v[0-9]*}

selected=()
if [[ -n $only ]]; then
	declare -A want_dir
	IFS=, read -ra wanted <<<"$only"
	for w in "${wanted[@]}"; do
		w=${w%/}
		[[ $w == . ]] && w=root
		if [[ -n ${group_named[$w]:-} ]]; then
			for m in ${group_named[$w]}; do want_dir[$m]=1; done
			continue
		fi
		found=
		for d in "${dirs[@]}"; do
			[[ $(name_of "$d") == "$w" ]] && found=$d
		done
		if [[ -z $found ]]; then
			have=$(for d in "${dirs[@]}"; do printf '%s ' "$(name_of "$d")"; done)
			die "no module named '$w' (have: ${have% }${group_named[*]:+; groups: ${!group_named[*]}})"
		fi
		for m in $(members_of "$found"); do want_dir[$m]=1; done
	done
	for d in "${dirs[@]}"; do
		[[ -n ${want_dir[$d]:-} ]] && selected+=("$d")
	done
else
	selected=("${dirs[@]}")
fi

# --- version math -------------------------------------------------------------

stage_rank() {
	case $1 in
	alpha) echo 1 ;;
	beta) echo 2 ;;
	*) echo 3 ;;
	esac
}

# Sortable key for MAJOR MINOR PATCH STAGE N.
sort_key() { printf '%06d%06d%06d%d%06d' "$1" "$2" "$3" "$(stage_rank "$4")" "$5"; }

semver_re='^v([0-9]+)\.([0-9]+)\.([0-9]+)(-(alpha|beta)\.([0-9]+))?$'

# sort_key for a version string, or nothing if it isn't one of ours.
version_key() {
	[[ $1 =~ $semver_re ]] || return 0
	sort_key "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" "${BASH_REMATCH[5]:-prod}" "${BASH_REMATCH[6]:-0}"
}

# Diff pathspec for a module: its directory minus any nested modules.
module_pathspec() {
	local dir=$1 o
	echo "$dir"
	for o in "${dirs[@]}"; do
		[[ $o == "$dir" ]] && continue
		if [[ $dir == . || $o == "$dir"/* ]]; then
			echo ":(exclude)$o"
		fi
	done
}

# Sets best (newest tag), best_core, best_stage, best_n, stable (newest
# release as "MAJOR MINOR PATCH"), their sort keys best_key and stable_key, and
# path_major and max_major for the module in dir.
scan_tags() {
	local dir=$1 prefix t v ma mi pa st n k
	prefix=$(prefix_of "$dir")
	best= best_core= best_stage= best_n=0 stable= best_key= stable_key=

	# A /vN suffix pins the major version; without one, only v0 and v1 are
	# valid. Python packages have neither rule.
	path_major= max_major=1
	if is_py "$dir"; then
		max_major=
	elif [[ ${mod_path[$dir]} =~ /v([0-9]+)$ ]]; then
		path_major=${BASH_REMATCH[1]}
	fi

	while IFS= read -r t; do
		v=${t#"$prefix"}
		[[ $v =~ $semver_re ]] || continue
		ma=${BASH_REMATCH[1]} mi=${BASH_REMATCH[2]} pa=${BASH_REMATCH[3]}
		st=${BASH_REMATCH[5]:-prod} n=${BASH_REMATCH[6]:-0}
		if [[ -n $path_major ]]; then
			((10#$ma == 10#$path_major)) || continue
		elif [[ -n $max_major ]]; then
			((10#$ma <= max_major)) || continue
		fi
		k=$(sort_key "$ma" "$mi" "$pa" "$st" "$n")
		if [[ -z $best_key || $k > $best_key ]]; then
			best_key=$k best=$t best_core="$ma $mi $pa" best_stage=$st best_n=$n
		fi
		if [[ $st == prod && (-z $stable_key || $k > $stable_key) ]]; then
			stable_key=$k stable="$ma $mi $pa"
		fi
	done < <(git tag -l "${prefix}v*")
}

# Like scan_tags, but best and stable are the newest across dir's lockstep
# group, so every member moves to the same next version. path_major and
# max_major stay dir's own.
scan_group() {
	local dir=$1 m g_best= g_core= g_stage= g_n=0 g_key= g_stable= g_skey=
	for m in $(members_of "$dir"); do
		[[ $m == "$dir" ]] && continue
		scan_tags "$m"
		if [[ -n $best_key && (-z $g_key || $best_key > $g_key) ]]; then
			g_key=$best_key g_best=$best g_core=$best_core g_stage=$best_stage g_n=$best_n
		fi
		if [[ -n $stable_key && (-z $g_skey || $stable_key > $g_skey) ]]; then
			g_skey=$stable_key g_stable=$stable
		fi
	done
	scan_tags "$dir"
	if [[ -n $g_key && (-z $best_key || $g_key > $best_key) ]]; then
		best=$g_best best_core=$g_core best_stage=$g_stage best_n=$g_n best_key=$g_key
	fi
	if [[ -n $g_skey && (-z $stable_key || $g_skey > $stable_key) ]]; then
		stable=$g_stable stable_key=$g_skey
	fi
}

declare -A cur_tag cur_ver next_ver next_tag note

for dir in "${dirs[@]}"; do
	scan_tags "$dir"
	cur_tag[$dir]=$best
	cur_ver[$dir]=${best#"$(prefix_of "$dir")"}
done

for dir in "${selected[@]}"; do
	scan_group "$dir"
	path=${mod_path[$dir]}

	if [[ -n $stable ]]; then
		read -r ma mi pa <<<"$stable"
		case $level in
		patch) pa=$((pa + 1)) ;;
		minor) mi=$((mi + 1)) pa=0 ;;
		major)
			if [[ -n $path_major ]]; then
				die "$path is already at v$path_major; change its module path to /v$((path_major + 1)) (and its imports) before a major release"
			fi
			ma=$((ma + 1)) mi=0 pa=0
			;;
		esac
	elif [[ -n $path_major ]]; then
		# First release under a /vN path is vN.0.0 whatever the bump level.
		ma=$path_major mi=0 pa=0
	else
		ma=0 mi=0 pa=0
		case $level in
		patch) pa=1 ;;
		minor) mi=1 ;;
		major) ma=1 ;;
		esac
	fi

	if [[ -z $path_major && -n $max_major ]] && ((ma > max_major)); then
		die "v$ma.0.0 of $path needs a /v$ma module path; change it (and its imports) first"
	fi

	core="$ma $mi $pa"
	ver="v$ma.$mi.$pa"
	if [[ -n $best && $best_stage != prod && $best_core == "$core" ]]; then
		# Continue the prerelease series already open for this version.
		have=$(stage_rank "$best_stage")
		want=$(stage_rank "$stage")
		if ((want < have)); then
			die "$(name_of "$dir") already has $best; can't go back to $stage"
		elif ((want == have)); then
			ver+="-$stage.$((best_n + 1))"
		elif [[ $stage != prod ]]; then
			ver+="-$stage.1"
		fi
	elif [[ $stage != prod ]]; then
		ver+="-$stage.1"
	fi

	tag="$(prefix_of "$dir")$ver"
	git rev-parse -q --verify "refs/tags/$tag" >/dev/null && die "tag $tag already exists"

	next_ver[$dir]=$ver
	next_tag[$dir]=$tag
	note[$dir]=
	if [[ -n ${cur_tag[$dir]} ]]; then
		mapfile -t spec < <(module_pathspec "$dir")
		git diff --quiet "${cur_tag[$dir]}" HEAD -- "${spec[@]}" && note[$dir]="no changes since ${cur_tag[$dir]}"
	fi
done

# --- internal require lines ---------------------------------------------------

# A module being released moves onto the newest version of every repo module it
# requires: the one being released alongside it, or else its newest tag.
syncs=() # "dir|dep|version"
warnings=()
for dir in "${go_dirs[@]}"; do
	for dep in "${go_dirs[@]}"; do
		[[ $dep == "$dir" ]] && continue
		required=$(required_of "$dir" "${mod_path[$dep]}")
		[[ -n $required ]] || continue
		target=${next_ver[$dep]:-${cur_ver[$dep]}}
		[[ -n $target ]] || continue
		have=$(version_key "$required")
		want=$(version_key "$target")
		[[ -z $have || $want > $have ]] || continue

		if [[ -n ${next_ver[$dir]:-} ]] && $sync; then
			if [[ -z ${next_ver[$dep]:-} ]] && ! $dry_run &&
				! git ls-remote --exit-code --tags "$remote" "refs/tags/${cur_tag[$dep]}" >/dev/null; then
				die "$(name_of "$dir") would move to ${cur_tag[$dep]}, which isn't on $remote; push it or use --no-sync"
			fi
			syncs+=("$dir|$dep|$target")
		elif [[ -n ${next_ver[$dep]:-} ]]; then
			warnings+=("$(name_of "$dir") stays on ${mod_path[$dep]} $required (releasing $target)")
		fi
	done
done

# Split the release into waves: a module waits for the wave that publishes any
# repo module it is moving onto.
declare -A wave_of
waves=()
remaining=("${selected[@]}")
while ((${#remaining[@]})); do
	this=() rest=()
	for dir in "${remaining[@]}"; do
		ready=true
		for s in "${syncs[@]}"; do
			IFS='|' read -r sd dep _ <<<"$s"
			if [[ $sd == "$dir" && -n ${next_ver[$dep]:-} && -z ${wave_of[$dep]:-} ]]; then
				ready=false
			fi
		done
		if $ready; then this+=("$dir"); else rest+=("$dir"); fi
	done
	((${#this[@]})) || die "repo modules require each other in a cycle: ${rest[*]}"
	for dir in "${this[@]}"; do
		wave_of[$dir]=$((${#waves[@]} + 1))
	done
	waves+=("${this[*]}")
	remaining=("${rest[@]}")
done

# --- plan ---------------------------------------------------------------------

echo
printf '  %-46s %-22s %s\n' MODULE CURRENT NEXT
for dir in "${selected[@]}"; do
	line=$(printf '  %-46s %-22s %s' "${mod_path[$dir]}" "${cur_tag[$dir]:-(none)}" "${next_tag[$dir]}")
	[[ -n ${note[$dir]} ]] && line+="  (${note[$dir]})"
	echo "$line"
done
echo
for i in "${!waves[@]}"; do
	read -ra wave <<<"${waves[i]}"
	((${#waves[@]} > 1)) && echo "  round $((i + 1)):"
	for dir in "${wave[@]}"; do
		for s in "${syncs[@]}"; do
			IFS='|' read -r sd dep ver <<<"$s"
			[[ $sd == "$dir" ]] && echo "    $(name_of "$dir"): go get ${mod_path[$dep]}@$ver"
		done
		echo "    tag ${next_tag[$dir]}"
	done
done
echo
for w in "${warnings[@]}"; do
	echo "  note: $w"
done
((${#warnings[@]})) && echo

if ((${#waves[@]} > 1)) && ! $push; then
	$dry_run || die "this release runs in ${#waves[@]} rounds, so later modules can require the ones published before them; rerun with --push (or --no-sync)"
	echo "note: this release runs in ${#waves[@]} rounds and needs --push"
fi

if $dry_run; then
	echo "dry run: nothing changed"
	exit 0
fi

if ! $yes && [[ -t 0 ]]; then
	action="Create these tags"
	$push && action+=" and push them to $remote"
	read -rp "$action? [y/N] " answer
	[[ $answer == [yY]* ]] || die "aborted"
fi

# --- commit, tag, push --------------------------------------------------------

tags=()
pushed=()
commits=0

# Report what is already done, and how to finish, then exit.
fail() {
	echo "release: $*" >&2
	local left=() unpushed=() dir t
	for dir in "${selected[@]}"; do
		[[ " ${pushed[*]} " == *" ${next_tag[$dir]} "* ]] || left+=("$(name_of "$dir")")
	done
	for t in "${tags[@]}"; do
		[[ " ${pushed[*]} " == *" $t "* ]] || unpushed+=("$t")
	done
	if ((${#unpushed[@]})); then
		echo "release: delete the unpushed tags with: git tag -d ${unpushed[*]}" >&2
	fi
	if ((${#pushed[@]})); then
		echo "release: already pushed: ${pushed[*]}" >&2
		echo "release: once fixed, finish with: git release $level $stage --only $(
			IFS=,
			echo "${left[*]}"
		) --push" >&2
	fi
	exit 1
}

# Our modules are fetched straight from the repo rather than the proxy and
# checksum database, which may not have seen tags pushed moments ago.
go_get() {
	local dir=$1
	shift
	(cd "$dir" && GOWORK=off GOFLAGS=-mod=mod GOPRIVATE="${GOPRIVATE:+$GOPRIVATE,}$repo_path" go get "$@")
}

# Move every module onto the newest published versions of the others, now that
# the release is done.
update_deps() {
	$update || return 0
	echo
	tools/git/update-deps.sh ||
		echo "release: warning: update-deps failed; rerun it with: git update-deps" >&2
}

for i in "${!waves[@]}"; do
	read -ra wave <<<"${waves[i]}"

	changed=()
	moved=()
	for dir in "${wave[@]}"; do
		args=()
		for s in "${syncs[@]}"; do
			IFS='|' read -r sd dep ver <<<"$s"
			[[ $sd == "$dir" ]] || continue
			args+=("${mod_path[$dep]}@$ver")
			moved+=("$(name_of "$dep")@$ver")
		done
		((${#args[@]})) || continue
		echo "$(name_of "$dir"): go get ${args[*]}"
		go_get "$dir" "${args[@]}" || fail "go get failed in $(name_of "$dir")"
		for f in "$dir/go.mod" "$dir/go.sum"; do
			[[ -e $f ]] && changed+=("$f")
		done
	done
	if ((${#changed[@]})) && ! git diff --quiet -- "${changed[@]}"; then
		mapfile -t moved < <(printf '%s\n' "${moved[@]}" | sort -u)
		git add -- "${changed[@]}"
		git commit --quiet -m "Require ${moved[*]}" -- "${changed[@]}" || fail "commit failed"
		commits=$((commits + 1))
		echo "committed $(git rev-parse --short HEAD): Require ${moved[*]}"
	fi

	wave_tags=()
	for dir in "${wave[@]}"; do
		git tag -a "${next_tag[$dir]}" -m "${mod_path[$dir]} ${next_ver[$dir]}" || fail "could not tag ${next_tag[$dir]}"
		echo "tagged ${next_tag[$dir]}"
		wave_tags+=("${next_tag[$dir]}")
		tags+=("${next_tag[$dir]}")
	done

	if $push; then
		git push --atomic "$remote" "$branch" "${wave_tags[@]}" || fail "push failed"
		pushed+=("${wave_tags[@]}")
	fi
done

if ! $push; then
	echo
	echo "to publish:"
	echo "  git push --atomic $remote ${branch:-HEAD} ${tags[*]}"
	# update-deps only sees pushed tags, so it has to wait for the push.
	$update && echo "  git update-deps"
	echo "to undo:"
	echo "  git tag -d ${tags[*]}"
	((commits)) && echo "  git reset --soft HEAD~$commits"
	exit 0
fi

# Ask the Go proxy for each new version so it is cached right away, but only
# when the remote is the repo the module paths point at.
if [[ $(git remote get-url "$remote") == *"${repo_path#*/}"* ]]; then
	for dir in "${selected[@]}"; do
		if is_py "$dir"; then
			echo "${mod_path[$dir]} ${next_ver[$dir]}: GitHub Actions publishes it to PyPI from ${next_tag[$dir]}"
			continue
		fi
		(cd / && GOWORK=off GOPROXY=https://proxy.golang.org go list -m "${mod_path[$dir]}@${next_ver[$dir]}") ||
			echo "release: warning: proxy.golang.org has not picked up ${mod_path[$dir]}@${next_ver[$dir]} yet" >&2
	done
else
	echo "release: $remote doesn't look like ${repo_path#*/}; skipped warming the Go proxy" >&2
fi

update_deps
