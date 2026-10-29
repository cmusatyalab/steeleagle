# Git Scripts

## `release.sh`: tagging Go module and Python package releases

The repo holds several Go modules and a Python package, and each one is
versioned and tagged separately:

| Module | Directory | Tag format |
|---|---|---|
| `github.com/cmusatyalab/steeleagle/v4` | `.` (root) | `v4.1.0` |
| `github.com/cmusatyalab/steeleagle/api/go` | `api/go` | `api/go/v0.4.0` |
| `github.com/cmusatyalab/steeleagle/sdk` | `sdk` | `sdk/v0.2.0` |
| `github.com/cmusatyalab/steeleagle/config` | `config` | `config/v0.1.0` |
| `steeleagle-protocol` (PyPI) | `api/python` | `api/python/v0.4.0` |

Go finds a nested module's versions through tags prefixed with that module's
directory. `release.sh` works out the next version of every module, creates
those tags, and pushes them. It discovers modules from the `go.mod` files
tracked in git, so a new module is included automatically.

### Python packages

A Python package is released the same way when its `pyproject.toml` has a
`[tool.setuptools_scm]` table. `setuptools-scm` then reads the version from
the package's newest tag, so there is no version number in `pyproject.toml`
to bump. Prerelease tags become PEP 440 versions: `api/python/v0.4.0-alpha.1`
builds `0.4.0a1`, and `-beta.N` builds `0.4.0bN`. A build from a commit after
the tag gets a dev version such as `0.4.1.dev3+g1a2b3c4`.

Pushing an `api/python/v*` tag runs
`.github/workflows/publish-steeleagle-protocol.yml`, which builds the package,
checks that its version matches the tag, and uploads it to PyPI. pip installs
prereleases only when asked (`pip install --pre steeleagle-protocol`).

### Binaries

Pushing a root module tag (`v4.1.0`) runs `.github/workflows/release-eagle.yml`,
which builds `eagle` and `eagled` (with liburiel linked statically) for Linux
amd64 and arm64 and attaches them to a GitHub release. Pushing an `sdk/v*` tag
runs `.github/workflows/release-eaglec.yml`, which does the same for `eaglec`.
Alpha and beta tags make prereleases. `tools/install.sh` installs from these
releases.

The script doesn't sync dependencies for Python packages. It doesn't apply
the Go rules on major versions to them either.

### Lockstep groups

Some modules are always released together, on the same version. They are
listed in `lockstep` near the top of `release.sh`:

| Group | Modules |
|---|---|
| `api` | `api/go`, `api/python` |

- **Selection:** `--only api` releases the whole group. Naming one member, such
  as `--only api/go`, releases the others as well.
- **Version:** the group's next version is bumped from the newest release of
  any member. A prerelease series that one member has open is continued by
  all of them. A member that fell behind therefore jumps ahead to match the
  others. For example, with `api/go/v0.3.3` and `api/python/v0.3.0`, the next
  patch release is `v0.3.4` for both.

### Setup (once per clone)

```sh
tools/git/alias.sh       # registers `git release`, `git update-deps` and `git workspace`
git workspace up         # creates go.work over every module in the repo
```

`git workspace down` removes the workspace again, so each module builds
against the published versions in its `go.mod`. The `go.work` file is
gitignored. It makes local builds use the other modules'
working-tree sources. No `go.mod` may contain a `replace` directive, and the
script refuses to run if one does.

### Usage

```sh
git release <patch|minor|major> [alpha|beta|prod] [options]
```

| Option | Effect |
|---|---|
| `--only root,api,api/go,...` | Release only these modules (`root` is the root module, `api` is a [lockstep group](#lockstep-groups)) |
| `--push` | Push the branch and tags, then ask proxy.golang.org to cache the new Go versions |
| `--no-sync` | Don't move modules onto new versions of other repo modules (see below) |
| `--no-update` | Don't run `git update-deps` after releasing (see below) |
| `--remote <name>` | Remote to fetch from and push to (default `origin`) |
| `--no-fetch` | Don't fetch tags from the remote first |
| `-n`, `--dry-run` | Print the plan and change nothing |
| `-y`, `--yes` | Skip the confirmation prompt |

Without `--push` the script tags locally and prints the push and undo
commands. It refuses to run if the working tree has uncommitted changes.
Always start with `-n` to see the plan.

### How versions are chosen

Each module is bumped from its newest release, meaning its newest tag
without an alpha or beta suffix:

- **`patch` / `minor` / `major`** bump the version as usual.
- **Stages:** `alpha` and `beta` produce prereleases (`v4.2.0-alpha.1`). If
  you omit the stage, or pass `prod`, you get a normal release. A new run
  continues the prerelease series already open for the same version:

  ```
  git release minor alpha   # v4.2.0-alpha.1
  git release minor alpha   # v4.2.0-alpha.2
  git release minor beta    # v4.2.0-beta.1
  git release minor         # v4.2.0
  ```

  Going back from beta to alpha is refused.
- **First release:** a module with no tags starts at `v0.0.0` plus the bump
  (`minor` gives `v0.1.0`). A module whose path ends in `/vN` starts at
  `vN.0.0`, whatever bump level you give.
- **Major versions:** Go requires every module at v2 or above to end its path
  in `/vN`. For `major` on the root (currently `/v4`), first change its module
  path and imports to `/v5`. The script refuses until you do, and then the
  release is `v5.0.0`. Taking a nested module from v1 to v2 needs the same
  path change.
- **Tag format:** only tags of the form `vX.Y.Z`, `vX.Y.Z-alpha.N` or
  `vX.Y.Z-beta.N` are recognised. Don't create tags like `v4.0` or `v4.0.0-rc1`
  by hand. Go ignores the first, and the script ignores both.

The plan flags any module with no changes since its last tag.

### Moving modules onto each other's new versions

When a module being released requires another repo module, the script moves
it onto that module's newest version: the one tagged in the same run, or
else its newest existing tag. The new version has to be published before
`go get` can record it with its `go.sum` hashes. So the script releases in
rounds, in dependency order:

```
round 1:  tag api/go/v0.4.0-alpha.1, config/v0.1.0-alpha.1      → push
round 2:  root: go get .../api/go@v0.4.0-alpha.1
          sdk:  go get .../api/go@v0.4.0-alpha.1                → commit "Require api/go@v0.4.0-alpha.1"
          tag v4.0.0-alpha.1, sdk/v0.1.0-alpha.1                → push
```

- **`--push` is required for more than one round**, because later rounds need
  the earlier ones published. Without it, the script stops before changing
  anything.
- **`go get` fetches repo modules straight from GitHub** (via `GOPRIVATE`)
  rather than through the proxy and checksum database, which may not have
  seen a tag pushed seconds earlier.
- **Each round's push is atomic:** the branch and that round's tags land
  together or not at all.
- **`--no-sync` skips all of this.** The plan then lists the modules left on
  older versions.

**If a round fails**, the rounds before it stay published. The script prints
which tags were pushed, which local tags to delete, and the exact command to
finish, for example:

```
release: once fixed, finish with: git release minor alpha --only root,sdk --push
```

The rerun computes the same versions and moves `root` and `sdk` onto the
`api/go` tag that was already pushed.

## `update-deps.sh`: moving modules onto each other's newest versions

```sh
git update-deps        # update every module
git update-deps -n     # show what would change
```

For every Go module in the repo, `git update-deps` finds the other repo
modules it requires, and moves each one onto its newest published version
with `go get`. It counts prereleases, but skips versions that have been
retracted. It never downgrades a requirement, and it leaves a requirement on
a pseudo-version alone.

- **Versions come straight from GitHub** (via `GOPRIVATE`), as with
  `release.sh`, so only tags that have been pushed are used.
- **Changes are left uncommitted**, in each module's `go.mod` and `go.sum`, for
  you to review and commit.

`git release` runs it after a successful release, so modules that weren't
released (for example with `--only`) catch up with the new versions. Pass
`--no-update` to skip it. It doesn't run on a dry run. Without `--push`, the
new tags aren't published yet, so instead of running it, `git release` lists
`git update-deps` among the steps to run after pushing. Run on its own,
`git update-deps` notes any local tag newer than what's been pushed.
