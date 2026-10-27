package daemon

import (
	"context"
	"maps"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// newRepo creates a local git repository with files (path to content)
// committed, isolated from the user's git config.
func newRepo(t *testing.T, files map[string]string) string {
	t.Helper()
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not installed")
	}
	t.Setenv("GIT_CONFIG_GLOBAL", os.DevNull)
	t.Setenv("GIT_CONFIG_NOSYSTEM", "1")
	t.Setenv("GIT_AUTHOR_NAME", "test")
	t.Setenv("GIT_AUTHOR_EMAIL", "test@example.com")
	t.Setenv("GIT_COMMITTER_NAME", "test")
	t.Setenv("GIT_COMMITTER_EMAIL", "test@example.com")
	dir := t.TempDir()
	git(t, dir, "init", "-q", "-b", "main")
	commit(t, dir, files)
	return dir
}

// commit writes files (path to content) to a repository and commits them.
func commit(t *testing.T, dir string, files map[string]string) {
	t.Helper()
	for name, content := range files {
		path := filepath.Join(dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}
	git(t, dir, "add", "-A")
	git(t, dir, "commit", "-q", "-m", "commit")
}

func git(t *testing.T, dir string, args ...string) {
	t.Helper()
	out, err := exec.Command("git", append([]string{"-C", dir}, args...)...).CombinedOutput()
	if err != nil {
		t.Fatalf("git %v: %v\n%s", args, err, out)
	}
}

// listedPackages lists the packages of a daemon by uri.
func listedPackages(t *testing.T, d *Daemon) map[string]*daemonpb.Package {
	t.Helper()
	resp, err := d.ListPackages(context.Background(), &daemonpb.ListPackagesRequest{})
	if err != nil {
		t.Fatal(err)
	}
	out := map[string]*daemonpb.Package{}
	for _, p := range resp.GetPackages() {
		out[p.GetUri()] = p
	}
	return out
}

func install(d *Daemon, uri string) error {
	_, err := d.InstallPackage(context.Background(), daemonpb.InstallPackageRequest_builder{Uri: uri}.Build())
	return err
}

func remove(d *Daemon, uri string) error {
	_, err := d.RemovePackage(context.Background(), daemonpb.RemovePackageRequest_builder{Uri: uri}.Build())
	return err
}

// TestPackages checks that packages are installed into and removed from the
// pending directory, where they are listed, and only take effect once a new
// daemon commits them.
func TestPackages(t *testing.T) {
	const plugin = "[plugin]\nname = \"X\"\ntype = \"extra\"\n"
	repo := newRepo(t, map[string]string{
		"pkgs/a/x.plugin.toml": plugin,
		"pkgs/a/pixi.toml":     "",
		"pkgs/b/README":        "no plugins here",
	})
	uri := repo + "//pkgs/a"
	d := newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))

	if err := install(d, ""); status.Code(err) != codes.InvalidArgument {
		t.Errorf("InstallPackage() without a uri = %v, want InvalidArgument", err)
	}
	if err := install(d, uri); err != nil {
		t.Fatal(err)
	}
	packages := listedPackages(t, d)
	p, ok := packages[uri]
	if !ok {
		t.Fatalf("packages = %v, want %s", packages, uri)
	}
	if got := p.GetPlugins(); len(got) != 1 || string(got["x"]) != plugin {
		t.Errorf("plugins = %v, want x", got)
	}
	if !p.HasModified() {
		t.Error("package has no modified time")
	}
	if _, ok := packages[testPkg]; !ok {
		t.Errorf("packages = %v, want the test package too", packages)
	}
	// Installs take effect only once committed by a new daemon
	if _, err := util.GetPackageDirByName(getPackageDir(uri)); err == nil {
		t.Error("package is installed before it was committed")
	}

	// Reinstalling replaces the package
	commit(t, repo, map[string]string{"pkgs/a/y.plugin.toml": plugin})
	if err := install(d, uri); err != nil {
		t.Fatal(err)
	}
	if got := listedPackages(t, d)[uri].GetPlugins(); len(got) != 2 {
		t.Errorf("plugins after reinstalling = %v, want x and y", got)
	}

	// A package without plugins, or that can't be fetched, isn't installed
	for _, bad := range []string{repo + "//pkgs/b", repo + "//pkgs/missing", repo + "@nope", filepath.Join(t.TempDir(), "nothing")} {
		if err := install(d, bad); status.Code(err) != codes.Internal {
			t.Errorf("InstallPackage(%q) = %v, want Internal", bad, err)
		}
		if _, ok := listedPackages(t, d)[bad]; ok {
			t.Errorf("failed install of %q is listed", bad)
		}
	}
	pending, _ := util.GetPendingDir()
	parent, _ := os.ReadDir(filepath.Dir(pending))
	for _, e := range parent {
		if strings.HasPrefix(e.Name(), ".install-") {
			t.Errorf("install staging directory %s left behind", e.Name())
		}
	}
	entries, _ := os.ReadDir(pending)
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".") {
			t.Errorf("staging directory %s left in the pending directory", e.Name())
		}
	}

	// A directory without a uri file isn't listed as a package
	installed, _ := util.GetPackageDir()
	if err := os.Mkdir(filepath.Join(installed, "stray"), 0755); err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(filepath.Join(installed, "stray"))
	if _, ok := listedPackages(t, d)["stray"]; ok {
		t.Error("directory without a uri is listed")
	}

	// A new daemon commits the package, leaving nothing pending
	newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))
	dir, err := util.GetPackageDirByName(getPackageDir(uri))
	if err != nil {
		t.Fatalf("committed package not found: %v", err)
	}
	if b, err := os.ReadFile(filepath.Join(dir, PackageUrlFileName)); err != nil || string(b) != uri {
		t.Errorf("committed package uri = %q, %v, want %q", b, err, uri)
	}
	if got := readPluginNames(t, dir); len(got) != 2 {
		t.Errorf("committed plugins = %v, want x and y", got)
	}
	expectNothingPending(t)

	if err := remove(d, uri); err != nil {
		t.Fatal(err)
	}
	if _, ok := listedPackages(t, d)[uri]; ok {
		t.Error("removed package is still listed")
	}
	if err := remove(d, uri); status.Code(err) != codes.NotFound {
		t.Errorf("RemovePackage() of a removed package = %v, want NotFound", err)
	}
	// Removals take effect once committed too
	if _, err := util.GetPackageDirByName(getPackageDir(uri)); err != nil {
		t.Error("package removed before the removal was committed")
	}
	newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))
	if _, err := util.GetPackageDirByName(getPackageDir(uri)); err == nil {
		t.Error("removed package is still installed after committing")
	}
	expectNothingPending(t)
	if err := remove(d, uri); status.Code(err) != codes.NotFound {
		t.Errorf("RemovePackage() of an uninstalled package = %v, want NotFound", err)
	}
}

// TestPendingChanges checks that an install and a removal of the same package
// before the next start cancel out as they should.
func TestPendingChanges(t *testing.T) {
	const plugin = "[plugin]\nname = \"X\"\ntype = \"extra\"\n"
	repo := newRepo(t, map[string]string{"x.plugin.toml": plugin})
	d := newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))

	// Installed, then removed before it was committed: nothing changes
	if err := install(d, repo); err != nil {
		t.Fatal(err)
	}
	if err := remove(d, repo); err != nil {
		t.Fatalf("RemovePackage() of a pending install = %v, want nil", err)
	}
	if _, ok := listedPackages(t, d)[repo]; ok {
		t.Error("removed pending install is listed")
	}
	expectNothingPending(t)

	// Installed and committed, removed, then installed again: it stays
	if err := install(d, repo); err != nil {
		t.Fatal(err)
	}
	newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))
	if err := remove(d, repo); err != nil {
		t.Fatal(err)
	}
	if err := install(d, repo); err != nil {
		t.Fatal(err)
	}
	if _, ok := listedPackages(t, d)[repo]; !ok {
		t.Error("reinstalled package isn't listed")
	}
	pending, _ := util.GetPendingDir()
	if _, err := os.Stat(filepath.Join(pending, PendingRemovePrefix+getPackageDir(repo))); err == nil {
		t.Error("reinstalling left the removal pending")
	}
	newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))
	if _, err := util.GetPackageDirByName(getPackageDir(repo)); err != nil {
		t.Errorf("reinstalled package isn't installed: %v", err)
	}
	expectNothingPending(t)
	if err := remove(d, repo); err != nil {
		t.Fatal(err)
	}
	newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))
}

// TestCommitPackages checks that committing replaces installed packages with
// pending installs, deletes those marked for removal, ignores removals of
// packages that aren't installed, and leaves the rest alone.
func TestCommitPackages(t *testing.T) {
	newIdleDaemon(t, orchAddr, testConfig(t, "solo", ""))
	pending, _ := util.GetPendingDir()
	installed, _ := util.GetPackageDir()
	write := func(path, content string) {
		t.Helper()
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}
	// An unchanged package keeps its environment
	kept := filepath.Join(installed, getPackageDir(testPkg), ".pixi", "kept")
	write(kept, "")
	write(filepath.Join(installed, "replaced", "old"), "")
	write(filepath.Join(installed, "replaced", ".pixi", "env"), "")
	write(filepath.Join(pending, "replaced", "new"), "")
	write(filepath.Join(installed, "removed", "file"), "")
	write(filepath.Join(pending, PendingRemovePrefix+"removed"), "")
	write(filepath.Join(pending, PendingRemovePrefix+"absent"), "")
	write(filepath.Join(pending, "added", "file"), "")

	if err := commitPackages(); err != nil {
		t.Fatal(err)
	}
	expectNothingPending(t)
	if _, err := os.Stat(kept); err != nil {
		t.Error("unchanged package lost its environment")
	}
	if got := readNames(t, filepath.Join(installed, "replaced")); !slices.Equal(got, []string{"new"}) {
		t.Errorf("replaced package = %v, want only the new version", got)
	}
	if _, err := os.Stat(filepath.Join(installed, "removed")); err == nil {
		t.Error("removed package is still installed")
	}
	if _, err := os.Stat(filepath.Join(installed, "added", "file")); err != nil {
		t.Error("added package isn't installed")
	}
	for _, name := range []string{"replaced", "added"} {
		os.RemoveAll(filepath.Join(installed, name))
	}
}

// expectNothingPending fails the test unless the pending directory is empty.
func expectNothingPending(t *testing.T) {
	t.Helper()
	pending, _ := util.GetPendingDir()
	if got := readNames(t, pending); len(got) != 0 {
		t.Errorf("pending = %v, want it empty", got)
	}
}

// readNames returns the names in a directory.
func readNames(t *testing.T, dir string) []string {
	t.Helper()
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	for _, e := range entries {
		names = append(names, e.Name())
	}
	return names
}

// readPluginNames returns the names of the plugins in a package.
func readPluginNames(t *testing.T, dir string) []string {
	t.Helper()
	plugins, err := readPlugins(dir)
	if err != nil {
		t.Fatal(err)
	}
	return slices.Sorted(maps.Keys(plugins))
}
