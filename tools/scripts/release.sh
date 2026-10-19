#!/usr/bin/env bash
# Tag every Go module in the repo with its next version in one step.
#
# The root module gets plain tags (v4.1.0); nested modules get path-prefixed
# tags (api/go/v0.4.0, sdk/v0.2.0, config/v0.1.0), which is how Go resolves
# versions for modules that live in subdirectories. Modules are discovered from
# the go.mod files tracked in git, so new ones are picked up automatically.
#
# Set up the alias once per clone:
#   git config alias.release '!tools/scripts/release.sh'
#
# Then:
#   git release minor              # v4.1.0
#   git release minor alpha        # v4.2.0-alpha.1, then -alpha.2, ...
#   git release minor beta         # v4.2.0-beta.1 (continues an alpha series)
#   git release minor prod         # v4.2.0 (same as omitting the stage)

set -euo pipefail

usage() {
	cat <<'EOF'
usage: git release <patch|minor|major> [alpha|beta|prod] [options]

Bumps every Go module in the repo and creates an annotated tag for each one
on HEAD. Prerelease stages continue an existing series for the same version
(alpha.1 -> alpha.2 -> beta.1 -> prod); going back from beta to alpha is
refused.

If a module points at another one through a local replace directive (e.g.
the root go.mod's `replace .../api/go => ./api/go`), its require line is
bumped to the new version and committed before tagging.

options:
  --only <mods>    comma-separated modules to release: root, api/go, sdk, ...
  --push           push the branch and tags atomically, then warm the Go proxy
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

name_of() { [[ $1 == . ]] && echo root || echo "$1"; }
prefix_of() { [[ $1 == . ]] && echo "" || echo "$1/"; }
path_of() { awk '$1 == "module" { print $2; exit }' "$1/go.mod"; }

selected=()
if [[ -n $only ]]; then
	IFS=, read -ra wanted <<<"$only"
	for w in "${wanted[@]}"; do
		w=${w%/}
		[[ $w == . ]] && w=root
		found=
		for d in "${dirs[@]}"; do
			[[ $(name_of "$d") == "$w" ]] && found=$d
		done
		[[ -n $found ]] || die "no Go module named '$w' (have: $(for d in "${dirs[@]}"; do printf '%s ' "$(name_of "$d")"; done))"
		selected+=("$found")
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

declare -A mod_path cur_tag next_ver next_tag note

for dir in "${selected[@]}"; do
	path=$(path_of "$dir")
	[[ -n $path ]] || die "$dir/go.mod has no module line"
	prefix=$(prefix_of "$dir")
	mod_path[$dir]=$path

	# A /vN suffix pins the major version; without one, only v0 and v1 are valid.
	path_major=
	[[ $path =~ /v([0-9]+)$ ]] && path_major=${BASH_REMATCH[1]}

	best_key= best= best_core= best_stage= best_n=0
	stable_key= stable=
	while IFS= read -r t; do
		v=${t#"$prefix"}
		[[ $v =~ $semver_re ]] || continue
		ma=${BASH_REMATCH[1]} mi=${BASH_REMATCH[2]} pa=${BASH_REMATCH[3]}
		st=${BASH_REMATCH[5]:-prod} n=${BASH_REMATCH[6]:-0}
		if [[ -n $path_major ]]; then
			((10#$ma == 10#$path_major)) || continue
		else
			((10#$ma <= 1)) || continue
		fi
		k=$(sort_key "$ma" "$mi" "$pa" "$st" "$n")
		if [[ -z $best_key || $k > $best_key ]]; then
			best_key=$k best=$t best_core="$ma $mi $pa" best_stage=$st best_n=$n
		fi
		if [[ $st == prod && (-z $stable_key || $k > $stable_key) ]]; then
			stable_key=$k stable="$ma $mi $pa"
		fi
	done < <(git tag -l "${prefix}v*")

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

	if [[ -z $path_major ]] && ((ma > 1)); then
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

	tag="$prefix$ver"
	git rev-parse -q --verify "refs/tags/$tag" >/dev/null && die "tag $tag already exists"

	cur_tag[$dir]=${best:-}
	next_ver[$dir]=$ver
	next_tag[$dir]=$tag
	note[$dir]=
	if [[ -n $best ]]; then
		mapfile -t spec < <(module_pathspec "$dir")
		git diff --quiet "$best" HEAD -- "${spec[@]}" && note[$dir]="no changes since $best"
	fi
done

# --- internal require lines ---------------------------------------------------

# Modules that use a local replace for a module being released get their
# require line bumped so the tagged go.mod names the version it was built with.
edits=()   # "dir|dep_path|new_ver"
warnings=()
for dir in "${dirs[@]}"; do
	gomod="$dir/go.mod"
	for dep in "${selected[@]}"; do
		[[ $dep == "$dir" ]] && continue
		dep_path=${mod_path[$dep]}
		re=${dep_path//./\\.}
		required=$(sed -nE "s#^[[:space:]]*(require[[:space:]]+)?$re[[:space:]]+(v[^[:space:]]+).*#\2#p" "$gomod" | head -1)
		[[ -n $required ]] || continue
		if grep -Eq "^[[:space:]]*(replace[[:space:]]+)?$re([[:space:]]+v[^[:space:]]+)?[[:space:]]*=>[[:space:]]*\.\.?/" "$gomod"; then
			# Only ever move a require forward, e.g. not back to a patch of an
			# older line while a newer prerelease is already required.
			have=$(version_key "$required")
			want=$(version_key "${next_ver[$dep]}")
			[[ -n $have && ! $want > $have ]] || edits+=("$dir|$dep_path|${next_ver[$dep]}")
		else
			warnings+=("$(name_of "$dir") requires $dep_path $required from the proxy (releasing ${next_ver[$dep]}); bump it separately if it needs the new version")
		fi
	done
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
for e in "${edits[@]}"; do
	IFS='|' read -r dir dep_path ver <<<"$e"
	gomod=$dir/go.mod
	echo "  ${gomod#./}: require $dep_path $ver"
done
for w in "${warnings[@]}"; do
	echo "  note: $w"
done
((${#edits[@]} + ${#warnings[@]})) && echo

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
for dir in "${selected[@]}"; do
	tags+=("${next_tag[$dir]}")
done

if ((${#edits[@]})); then
	changed=()
	for e in "${edits[@]}"; do
		IFS='|' read -r dir dep_path ver <<<"$e"
		go mod edit -require="$dep_path@$ver" "$dir/go.mod"
		changed+=("$dir/go.mod")
	done
	git add -- "${changed[@]}"
	git commit --quiet -m "Release $(
		IFS=,
		echo "${tags[*]}" | sed 's/,/, /g'
	)" -- "${changed[@]}"
	echo "committed go.mod updates as $(git rev-parse --short HEAD)"
fi

for dir in "${selected[@]}"; do
	git tag -a "${next_tag[$dir]}" -m "${mod_path[$dir]} ${next_ver[$dir]}"
	echo "tagged ${next_tag[$dir]}"
done

if ! $push; then
	echo
	echo "to publish:"
	echo "  git push --atomic $remote ${branch:-HEAD} ${tags[*]}"
	echo "to undo:"
	echo "  git tag -d ${tags[*]}"
	((${#edits[@]})) && echo "  git reset --soft HEAD~1"
	exit 0
fi

git push --atomic "$remote" "$branch" "${tags[@]}"

# Ask the Go proxy for each new version so it is cached right away, but only
# when the remote is the repo the module paths point at.
root_path=$(path_of .)
repo=${root_path%/v[0-9]*}
repo=${repo#*/}
if [[ $(git remote get-url "$remote") == *"$repo"* ]]; then
	for dir in "${selected[@]}"; do
		(cd / && GOWORK=off GOPROXY=https://proxy.golang.org go list -m "${mod_path[$dir]}@${next_ver[$dir]}") ||
			echo "release: warning: proxy.golang.org has not picked up ${mod_path[$dir]}@${next_ver[$dir]} yet" >&2
	done
else
	echo "release: $remote doesn't look like $repo; skipped warming the Go proxy" >&2
fi
