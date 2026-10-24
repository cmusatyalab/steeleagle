package download

import (
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"testing"
)

// isolateGit keeps git from reading the user's or system's config, so that
// tests behave the same on every machine.
func isolateGit(t *testing.T) {
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
}

// git runs a git command in dir, returning its trimmed output.
func git(t *testing.T, dir string, args ...string) string {
	t.Helper()
	out, err := exec.Command("git", append([]string{"-C", dir}, args...)...).CombinedOutput()
	if err != nil {
		t.Fatalf("git %v: %v\n%s", args, err, out)
	}
	return strings.TrimSpace(string(out))
}

// testRepo is a local git repository served over file://.
type testRepo struct {
	dir, url string
}

// newRepo creates a repository on branch main.
func newRepo(t *testing.T) *testRepo {
	t.Helper()
	isolateGit(t)
	dir := t.TempDir()
	git(t, dir, "init", "-q", "-b", "main")
	return &testRepo{dir, "file://" + filepath.ToSlash(dir)}
}

// commit writes files (path to content) and commits them, returning the
// commit hash.
func (r *testRepo) commit(t *testing.T, files map[string]string) string {
	t.Helper()
	for name, content := range files {
		path := filepath.Join(r.dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}
	git(t, r.dir, "add", "-A")
	git(t, r.dir, "commit", "-q", "-m", "commit")
	return git(t, r.dir, "rev-parse", "HEAD")
}

// tree returns the files under dir as slash separated paths mapped to their
// contents, with symlinks mapped to "-> " and their target.
func tree(t *testing.T, dir string) map[string]string {
	t.Helper()
	files := map[string]string{}
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}
		rel, _ := filepath.Rel(dir, path)
		if info.Mode()&os.ModeSymlink != 0 {
			target, err := os.Readlink(path)
			files[filepath.ToSlash(rel)] = "-> " + target
			return err
		}
		content, err := os.ReadFile(path)
		files[filepath.ToSlash(rel)] = string(content)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	return files
}

// expectTree fails the test unless dir holds exactly want.
func expectTree(t *testing.T, dir string, want map[string]string) {
	t.Helper()
	got := tree(t, dir)
	for name, content := range want {
		if got[name] != content {
			t.Errorf("expected %s to hold %q, got %q", name, content, got[name])
		}
	}
	var extra []string
	for name := range got {
		if _, ok := want[name]; !ok {
			extra = append(extra, name)
		}
	}
	if len(extra) > 0 {
		slices.Sort(extra)
		t.Errorf("expected no %v in %s", extra, dir)
	}
}

// expectEntries fails the test unless dir holds exactly names, so that
// nothing (like a temporary checkout) is left behind.
func expectEntries(t *testing.T, dir string, names ...string) {
	t.Helper()
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, e := range entries {
		got = append(got, e.Name())
	}
	if strings.Join(got, ",") != strings.Join(names, ",") {
		t.Errorf("expected %s to hold %v, got %v", dir, names, got)
	}
}

// layout is a repository with a package in pkg, a nested package in
// pkg/nested, a sibling whose name shares the prefix pkg, and files at the
// root.
var layout = map[string]string{
	"README.md":          "readme",
	"pkg/plugin.toml":    "plugin",
	"pkg/src/main.py":    "main",
	"pkg/nested/a.toml":  "nested",
	"pkg2/plugin.toml":   "other",
	"other/deep/file.go": "other",
}

// TestInstallPackage ensures that only the subdirectory is installed at
// target, without git metadata or the temporary checkout.
func TestInstallPackage(t *testing.T) {
	repo := newRepo(t)
	repo.commit(t, layout)
	dir := t.TempDir()
	target := filepath.Join(dir, "pkg")

	if err := InstallPackage(repo.url+"//pkg@main", target); err != nil {
		t.Fatal(err)
	}
	expectTree(t, target, map[string]string{
		"plugin.toml":   "plugin",
		"src/main.py":   "main",
		"nested/a.toml": "nested",
	})
	expectEntries(t, dir, "pkg")
}

// TestSplitSubdir ensures that the sub directory is split from the url at the
// first double slash after the scheme.
func TestSplitSubdir(t *testing.T) {
	for url, want := range map[string][2]string{
		"https://github.com/org/repo.git":              {"https://github.com/org/repo.git", ""},
		"https://github.com/org/repo.git//pkg":         {"https://github.com/org/repo.git", "pkg"},
		"https://github.com/org/repo.git//pkg/nested/": {"https://github.com/org/repo.git", "pkg/nested/"},
		"https://github.com/org/repo.git//":            {"https://github.com/org/repo.git", ""},
		"file:///tmp/repo//pkg":                        {"file:///tmp/repo", "pkg"},
		"/tmp/repo//pkg//nested":                       {"/tmp/repo", "pkg//nested"},
		"/tmp/repo":                                    {"/tmp/repo", ""},
	} {
		if repo, subdir := splitSubdir(url); repo != want[0] || subdir != want[1] {
			t.Errorf("%s: expected %q, %q, got %q, %q", url, want[0], want[1], repo, subdir)
		}
	}
}

// TestSplitVersion ensures that the version is split from the url at the
// last @ after the host.
func TestSplitVersion(t *testing.T) {
	for url, want := range map[string][2]string{
		"https://github.com/org/repo.git":            {"https://github.com/org/repo.git", ""},
		"https://github.com/org/repo.git@v1":         {"https://github.com/org/repo.git", "v1"},
		"https://github.com/org/repo.git//pkg@main":  {"https://github.com/org/repo.git//pkg", "main"},
		"https://user@github.com/org/repo.git//pkg":  {"https://user@github.com/org/repo.git//pkg", ""},
		"https://user@github.com/org/repo.git@abc12": {"https://user@github.com/org/repo.git", "abc12"},
		"https://user@host":                          {"https://user@host", ""},
		"/tmp/repo//pkg@dev":                         {"/tmp/repo//pkg", "dev"},
		"/tmp/repo@":                                 {"/tmp/repo", ""},
	} {
		if repo, version := splitVersion(url); repo != want[0] || version != want[1] {
			t.Errorf("%s: expected %q, %q, got %q, %q", url, want[0], want[1], repo, version)
		}
	}
}

// TestInstallPackageSubdirs ensures that nested and root subdirectories are
// installed in full.
func TestInstallPackageSubdirs(t *testing.T) {
	repo := newRepo(t)
	repo.commit(t, layout)
	for subdir, want := range map[string]map[string]string{
		"pkg/nested":  {"a.toml": "nested"},
		"pkg/nested/": {"a.toml": "nested"},
		"other/deep":  {"file.go": "other"},
		"":            layout,
	} {
		dir := t.TempDir()
		target := filepath.Join(dir, "pkg")
		if err := InstallPackage(repo.url+"//"+subdir+"@main", target); err != nil {
			t.Errorf("subdir %q: %v", subdir, err)
			continue
		}
		expectTree(t, target, want)
		expectEntries(t, dir, "pkg")
	}
}

// TestInstallPackageVersion ensures that the package is installed at the
// requested branch, tag or commit, or the default branch if none is given.
func TestInstallPackageVersion(t *testing.T) {
	repo := newRepo(t)
	first := repo.commit(t, map[string]string{"pkg/version": "1"})
	git(t, repo.dir, "tag", "v1")
	repo.commit(t, map[string]string{"pkg/version": "2"})
	git(t, repo.dir, "checkout", "-q", "-b", "dev")
	repo.commit(t, map[string]string{"pkg/version": "3"})
	git(t, repo.dir, "checkout", "-q", "main")

	for version, want := range map[string]string{
		"":     "2",
		"main": "2",
		"dev":  "3",
		"v1":   "1",
		first:  "1",
	} {
		target := filepath.Join(t.TempDir(), "pkg")
		url := repo.url + "//pkg"
		if version != "" {
			url += "@" + version
		}
		if err := InstallPackage(url, target); err != nil {
			t.Errorf("version %q: %v", version, err)
			continue
		}
		expectTree(t, target, map[string]string{"version": want})
	}
}

// TestInstallPackageSymlink ensures that symlinks within the package are
// installed as copies of the files they point to, and that symlinks out of the
// package are refused.
func TestInstallPackageSymlink(t *testing.T) {
	repo := newRepo(t)
	link := func(target, name string) {
		t.Helper()
		path := filepath.Join(repo.dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(target, path); err != nil {
			t.Fatal(err)
		}
	}
	link("plugin.toml", "inside/alias")
	link("../plugin.toml", "inside/src/alias")
	link("/etc/passwd", "absolute/escape")
	link("../README.md", "parent/escape")
	repo.commit(t, map[string]string{
		"README.md":            "readme",
		"inside/plugin.toml":   "plugin",
		"absolute/plugin.toml": "plugin",
		"parent/plugin.toml":   "plugin",
	})

	dir := t.TempDir()
	target := filepath.Join(dir, "inside")
	if err := InstallPackage(repo.url+"//inside@main", target); err != nil {
		t.Fatal(err)
	}
	expectTree(t, target, map[string]string{
		"plugin.toml": "plugin",
		"alias":       "plugin",
		"src/alias":   "plugin",
	})
	for _, subdir := range []string{"absolute", "parent"} {
		if err := InstallPackage(repo.url+"//"+subdir+"@main", filepath.Join(dir, subdir)); err == nil {
			t.Errorf("%s: expected a symlink out of the package to be refused", subdir)
		}
	}
	expectEntries(t, dir, "inside")
}

// TestInstallPackageLocal ensures that a repository can be installed from a
// local path as well as a file url.
func TestInstallPackageLocal(t *testing.T) {
	repo := newRepo(t)
	repo.commit(t, layout)
	target := filepath.Join(t.TempDir(), "pkg")
	if err := InstallPackage(repo.dir+"//pkg/nested@main", target); err != nil {
		t.Fatal(err)
	}
	expectTree(t, target, map[string]string{"a.toml": "nested"})
}

// TestInstallPackageProtocol ensures that transports other than https and
// file are refused before they run anything.
func TestInstallPackageProtocol(t *testing.T) {
	isolateGit(t)
	// Allow every protocol in the config, so that only the install's own
	// restriction can refuse them
	t.Setenv("GIT_CONFIG_COUNT", "1")
	t.Setenv("GIT_CONFIG_KEY_0", "protocol.allow")
	t.Setenv("GIT_CONFIG_VALUE_0", "always")
	marker := filepath.Join(t.TempDir(), "ran")
	for _, url := range []string{
		"ext::sh -c touch% " + marker,
		"ssh://127.0.0.1:1/repo",
		"git://127.0.0.1:1/repo",
	} {
		dir := t.TempDir()
		err := InstallPackage(url+"//pkg@main", filepath.Join(dir, "pkg"))
		if err == nil || !strings.Contains(err.Error(), "not allowed") {
			t.Errorf("%s: expected the transport to be refused, got %v", url, err)
		}
		expectEntries(t, dir)
	}
	if _, err := os.Stat(marker); err == nil {
		t.Error("expected the ext transport not to run its command")
	}
}

// TestInstallPackageInvalid ensures that failed installs return an error and
// leave nothing behind.
func TestInstallPackageInvalid(t *testing.T) {
	repo := newRepo(t)
	repo.commit(t, layout)
	missing := "file://" + filepath.ToSlash(filepath.Join(t.TempDir(), "missing"))
	for name, c := range map[string]struct{ url, version, subdir string }{
		"missing repo":    {missing, "main", "pkg"},
		"missing version": {repo.url, "nope", "pkg"},
		"missing subdir":  {repo.url, "main", "nope"},
		"file as subdir":  {repo.url, "main", "README.md"},
		"subdir prefix":   {repo.url, "main", "pk"},
		"parent subdir":   {repo.url, "main", "../pkg"},
	} {
		dir := t.TempDir()
		if err := InstallPackage(c.url+"//"+c.subdir+"@"+c.version, filepath.Join(dir, "pkg")); err == nil {
			t.Errorf("%s: expected an error", name)
		}
		expectEntries(t, dir)
	}
}

// TestInstallPackageTarget ensures that an install never replaces an existing
// target or creates missing parent directories.
func TestInstallPackageTarget(t *testing.T) {
	repo := newRepo(t)
	repo.commit(t, layout)
	dir := t.TempDir()
	target := filepath.Join(dir, "pkg")
	if err := os.WriteFile(filepath.Join(dir, "pkg"), []byte("keep"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := InstallPackage(repo.url+"//pkg@main", target); err == nil {
		t.Error("expected an existing target to be refused")
	}
	if got, err := os.ReadFile(target); err != nil || string(got) != "keep" {
		t.Errorf("expected the existing target to be kept, got %q, %v", got, err)
	}
	expectEntries(t, dir, "pkg")

	if err := InstallPackage(repo.url+"//pkg@main", filepath.Join(dir, "missing", "pkg")); err == nil {
		t.Error("expected a missing parent directory to be refused")
	}
	expectEntries(t, dir, "pkg")
}

// TestInstallPackageNoGit ensures that an install fails without git.
func TestInstallPackageNoGit(t *testing.T) {
	t.Setenv("PATH", t.TempDir())
	dir := t.TempDir()
	if err := InstallPackage("file:///nowhere//pkg@main", filepath.Join(dir, "pkg")); err == nil {
		t.Error("expected an error without git")
	}
	expectEntries(t, dir)
}
