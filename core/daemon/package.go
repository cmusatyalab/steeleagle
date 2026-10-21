package daemon

import (
	"bytes"
	"cmp"
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"time"

	"github.com/BurntSushi/toml"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Validation patterns for package urls and tags; urls come from remote callers
// and are passed to git, so anything outside these is rejected
var (
	hostPattern    = regexp.MustCompile(`^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]+)?$`)
	segmentPattern = regexp.MustCompile(`^[A-Za-z0-9_][A-Za-z0-9._-]*$`)
	tagPattern     = regexp.MustCompile(`^[A-Za-z0-9_][A-Za-z0-9._/-]*$`)
)

// packageUrl is a validated package url, split into its host and path
// segments. The path may run past the root of the git repository into a
// subfolder holding the package.
type packageUrl struct {
	host     string   // host, with an optional port
	segments []string // path segments after the host
	url      string   // normalized url, without a scheme
	name     string   // package name, unique per url
}

// packageInfo is the metadata stored with each installed package.
type packageInfo struct {
	Url       string    `toml:"url"`       // normalized package url
	Tag       string    `toml:"tag"`       // requested branch or commit tag, empty for the default branch
	Commit    string    `toml:"commit"`    // checked out commit hash
	Installed time.Time `toml:"installed"` // install time
}

// parsePackageUrl validates and normalizes a package url. The url may omit
// its scheme (e.g. "github.com/org/repo/sub/folder"); only https is used. The
// package name is the host and path with slashes, dots and port colons
// replaced by underscores, so similar packages in different repositories
// don't collide.
func parsePackageUrl(raw string) (*packageUrl, error) {
	u := strings.TrimSpace(raw)
	if scheme, rest, ok := strings.Cut(u, "://"); ok {
		if scheme != "https" && scheme != "http" {
			return nil, status.Errorf(codes.InvalidArgument, "unsupported scheme %q", scheme)
		}
		u = rest
	}
	parts := strings.Split(strings.TrimRight(u, "/"), "/")
	if len(parts) < 2 {
		return nil, status.Errorf(codes.InvalidArgument, "url %q has no repository path", raw)
	}
	host := strings.ToLower(parts[0])
	if !hostPattern.MatchString(host) {
		return nil, status.Errorf(codes.InvalidArgument, "invalid host %q", parts[0])
	}
	// The repository segment may carry a ".git" suffix anywhere in the path
	// (e.g. "org/repo.git/sub"), so strip it from every segment to give the
	// package a single name however its url is written
	segments := parts[1:]
	for i, s := range segments {
		s = strings.TrimSuffix(s, ".git")
		if !segmentPattern.MatchString(s) || s == "." || s == ".." {
			return nil, status.Errorf(codes.InvalidArgument, "invalid path segment %q", segments[i])
		}
		segments[i] = s
	}
	url := host + "/" + strings.Join(segments, "/")
	name := strings.NewReplacer("/", "_", ".", "_", ":", "_").Replace(url)
	return &packageUrl{host: host, segments: segments, url: url, name: name}, nil
}

// resolveRepo finds the root git repository of the url by removing path
// segments from the end until git recognizes a repository. It returns the
// repository url and the remaining segments as the subfolder.
func resolveRepo(ctx context.Context, u *packageUrl) (string, string, error) {
	for n := len(u.segments); n > 0; n-- {
		repo := "https://" + u.host + "/" + strings.Join(u.segments[:n], "/")
		lsCtx, cancel := context.WithTimeout(ctx, gitLsRemoteTimeout)
		_, err := runGit(lsCtx, "ls-remote", "--", repo)
		cancel()
		if err == nil {
			return repo, strings.Join(u.segments[n:], "/"), nil
		}
		if ctx.Err() != nil {
			return "", "", status.FromContextError(ctx.Err()).Err()
		}
	}
	return "", "", status.Errorf(codes.NotFound, "no git repository found for %s", u.url)
}

// runGit runs a git command and returns its trimmed stdout. Prompts are
// disabled and only the https protocol is allowed.
func runGit(ctx context.Context, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0", "GIT_ALLOW_PROTOCOL=https")
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("git: %w: %s", err, strings.TrimSpace(stderr.String()))
	}
	return strings.TrimSpace(stdout.String()), nil
}

// pendingDir returns the path of the pending package directory.
func (d *Daemon) pendingDir() string {
	return filepath.Join(d.PkgDir, PendingDirName)
}

// installPackage sparse checks out the package at url on tag (the default
// branch if empty) into the pending package directory, replacing any pending
// copy of the same package. It takes effect on the next daemon restart.
func (d *Daemon) installPackage(ctx context.Context, url, tag string) error {
	u, err := parsePackageUrl(url)
	if err != nil {
		return err
	}
	if tag != "" && !tagPattern.MatchString(tag) {
		return status.Errorf(codes.InvalidArgument, "invalid tag %q", tag)
	}
	repo, subdir, err := resolveRepo(ctx, u)
	if err != nil {
		return err
	}
	d.log.Info().Str("repo", repo).Str("subdir", subdir).Str("tag", tag).
		Msg("installing package")

	// Check out into a temporary directory on the same filesystem as the
	// pending directory, so that the result can be renamed into place
	tmp, err := os.MkdirTemp(d.PkgDir, tmpPrefix)
	if err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	defer os.RemoveAll(tmp)
	repoDir := filepath.Join(tmp, "repo")
	steps := [][]string{
		{"init", "-q", repoDir},
		{"-C", repoDir, "remote", "add", "origin", repo},
		{"-C", repoDir, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", cmp.Or(tag, "HEAD")},
		{"-C", repoDir, "checkout", "-q", "FETCH_HEAD"},
	}
	if subdir != "" { // a cone of "." would only check out top-level files
		steps = slices.Insert(steps, 2, []string{"-C", repoDir, "sparse-checkout", "set", "--cone", "--", subdir})
	}
	for _, step := range steps {
		if _, err := runGit(ctx, step...); err != nil {
			return status.Error(codes.Internal, err.Error())
		}
	}
	commit, err := runGit(ctx, "-C", repoDir, "rev-parse", "FETCH_HEAD")
	if err != nil {
		return status.Error(codes.Internal, err.Error())
	}

	// Copy the subfolder out through an os.Root, which refuses symlinks that
	// point outside of the checkout
	if err := os.RemoveAll(filepath.Join(repoDir, ".git")); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	root, err := os.OpenRoot(repoDir)
	if err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	defer root.Close()
	src, err := fs.Sub(root.FS(), cmp.Or(subdir, "."))
	if err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	staged := filepath.Join(tmp, "pkg")
	if err := os.CopyFS(staged, src); errors.Is(err, fs.ErrNotExist) {
		return status.Errorf(codes.NotFound, "subfolder %q not found in %s", subdir, repo)
	} else if err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	info := packageInfo{Url: u.url, Tag: tag, Commit: commit, Installed: time.Now().UTC()}
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(info); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	if err := os.WriteFile(filepath.Join(staged, PackageInfoFileName), buf.Bytes(), 0644); err != nil {
		return status.Error(codes.Internal, err.Error())
	}

	// Swap the package into the pending directory
	d.pkgMu.Lock()
	defer d.pkgMu.Unlock()
	dst := filepath.Join(d.pendingDir(), u.name)
	if err := os.RemoveAll(dst); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	if err := os.Rename(staged, dst); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	d.log.Info().Str("package", u.name).Str("commit", commit).Msg("package installed, pending restart")
	return d.markPendingDirty()
}

// removePackage removes the package at url from the pending package
// directory. It takes effect on the next daemon restart.
func (d *Daemon) removePackage(url string) error {
	u, err := parsePackageUrl(url)
	if err != nil {
		return err
	}
	d.pkgMu.Lock()
	defer d.pkgMu.Unlock()
	dst := filepath.Join(d.pendingDir(), u.name)
	if _, err := os.Lstat(dst); errors.Is(err, fs.ErrNotExist) {
		return status.Errorf(codes.NotFound, "%s is not installed", u.url)
	}
	if err := os.RemoveAll(dst); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	d.log.Info().Str("package", u.name).Msg("package removed, pending restart")
	return d.markPendingDirty()
}

// markPendingDirty marks the pending directory as changed, so that it is
// applied on the next restart. The caller must hold pkgMu.
func (d *Daemon) markPendingDirty() error {
	if err := os.WriteFile(filepath.Join(d.pendingDir(), dirtyFileName), nil, 0644); err != nil {
		return status.Error(codes.Internal, err.Error())
	}
	return nil
}

// commitPendingPackages applies a changed pending directory to the package
// directory, so that installs and removals take effect without disrupting
// services running on the old packages. If the pending directory doesn't
// exist yet, it is created as a copy of the package directory. The pending
// directory is never modified here, so an interrupted commit is redone on the
// next call.
func (d *Daemon) commitPendingPackages() error {
	d.pkgMu.Lock()
	defer d.pkgMu.Unlock()

	// Clear out temporary directories left by interrupted operations
	tmps, _ := filepath.Glob(filepath.Join(d.PkgDir, tmpPrefix+"*"))
	for _, tmp := range tmps {
		if err := os.RemoveAll(tmp); err != nil {
			return err
		}
	}

	pending := d.pendingDir()
	if _, err := os.Stat(pending); errors.Is(err, fs.ErrNotExist) {
		d.log.Info().Msg("creating pending package directory")
		tmp, err := os.MkdirTemp(d.PkgDir, tmpPrefix)
		if err != nil {
			return err
		}
		if err := mirror(d.PkgDir, tmp); err != nil {
			return err
		}
		return os.Rename(tmp, pending)
	}
	dirty := filepath.Join(pending, dirtyFileName)
	if _, err := os.Stat(dirty); errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	d.log.Info().Msg("applying pending packages")
	if err := mirror(pending, d.PkgDir); err != nil {
		return err
	}
	return os.Remove(dirty)
}

// mirror replaces the package directories in dst with copies of those in src.
// Hidden entries, like the pending and temporary directories, are left alone.
func mirror(src, dst string) error {
	old, err := os.ReadDir(dst)
	if err != nil {
		return err
	}
	for _, e := range old {
		if !strings.HasPrefix(e.Name(), ".") {
			if err := os.RemoveAll(filepath.Join(dst, e.Name())); err != nil {
				return err
			}
		}
	}
	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}
	for _, e := range entries {
		if e.IsDir() && !strings.HasPrefix(e.Name(), ".") {
			if err := os.CopyFS(filepath.Join(dst, e.Name()), os.DirFS(filepath.Join(src, e.Name()))); err != nil {
				return err
			}
		}
	}
	return nil
}
