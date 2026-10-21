package daemon

import (
	"context"
	"errors"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// newTestPackageDaemon returns a daemon with only a package directory set,
// after its first commit has created the pending directory.
func newTestPackageDaemon(t *testing.T, packages ...string) *Daemon {
	t.Helper()
	d := &Daemon{PkgDir: t.TempDir(), log: testLogger()}
	for _, name := range packages {
		writeTestPackage(t, d.PkgDir, name, "1")
	}
	if err := d.commitPendingPackages(); err != nil {
		t.Fatalf("commit failed: %v", err)
	}
	return d
}

// writeTestPackage creates a fake package holding one executable file.
func writeTestPackage(t *testing.T, dir, name, content string) {
	t.Helper()
	pkg := filepath.Join(dir, name)
	if err := os.MkdirAll(pkg, 0755); err != nil {
		t.Fatalf("couldn't create package: %v", err)
	}
	if err := os.WriteFile(filepath.Join(pkg, "run.sh"), []byte(content), 0755); err != nil {
		t.Fatalf("couldn't write package file: %v", err)
	}
}

// assertPackages checks that dir holds exactly the named packages.
func assertPackages(t *testing.T, dir string, want ...string) {
	t.Helper()
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("couldn't list %s: %v", dir, err)
	}
	var got []string
	for _, e := range entries {
		if e.IsDir() && e.Name()[0] != '.' {
			got = append(got, e.Name())
		}
	}
	if !slices.Equal(got, want) {
		t.Errorf("expected packages %v in %s, got %v", want, dir, got)
	}
}

// TestParsePackageUrl ensures that package urls are named unambiguously, and
// that urls git could misuse are rejected.
func TestParsePackageUrl(t *testing.T) {
	valid := map[string]string{
		"github.com/cmusatyalab/steeleagle_plugins/drivers/parrot": "github_com_cmusatyalab_steeleagle_plugins_drivers_parrot",
		"https://GitHub.com/org/repo.git":                          "github_com_org_repo",
		"github.com/org/repo.git/sub/pkg":                          "github_com_org_repo_sub_pkg",
		"http://gitlab.com/group/sub/repo/":                        "gitlab_com_group_sub_repo",
		"git.example.com:8443/org/my-repo.v2":                      "git_example_com_8443_org_my-repo_v2",
	}
	for url, name := range valid {
		u, err := parsePackageUrl(url)
		if err != nil {
			t.Errorf("%s: unexpected error: %v", url, err)
		} else if u.name != name {
			t.Errorf("%s: expected name %s, got %s", url, name, u.name)
		}
	}

	invalid := []string{
		"",
		"github.com",
		"ssh://github.com/org/repo",
		"file:///etc/passwd",
		"ext::sh -c touch% /tmp/pwned",
		"git@github.com:org/repo",
		"-uhelp/org/repo",
		"github.com/../repo",
		"github.com/org/./repo",
		"github.com/-org/repo",
		"github.com/org/re po",
		"github.com/org/repo?ref=main",
		"github.com//repo",
		"github.com/org/.git",
	}
	for _, url := range invalid {
		if _, err := parsePackageUrl(url); status.Code(err) != codes.InvalidArgument {
			t.Errorf("%q: expected InvalidArgument, got %v", url, err)
		}
	}
}

// TestCommitPendingPackages ensures that the pending directory is created as a
// copy of the package directory, and that changes to pending are only applied
// to the package directory once pending is marked dirty.
func TestCommitPendingPackages(t *testing.T) {
	d := newTestPackageDaemon(t, "a")
	pending := d.pendingDir()
	assertPackages(t, pending, "a")
	if info, err := os.Stat(filepath.Join(pending, "a", "run.sh")); err != nil || info.Mode().Perm()&0100 == 0 {
		t.Errorf("expected executable file copied into pending, got %v, %v", info, err)
	}

	// Install b and update a; nothing applies until pending is dirty
	writeTestPackage(t, pending, "b", "1")
	writeTestPackage(t, pending, "a", "2")
	if err := d.commitPendingPackages(); err != nil {
		t.Fatalf("commit failed: %v", err)
	}
	assertPackages(t, d.PkgDir, "a")
	d.markPendingDirty()
	if err := d.commitPendingPackages(); err != nil {
		t.Fatalf("commit failed: %v", err)
	}
	assertPackages(t, d.PkgDir, "a", "b")
	assertPackages(t, pending, "a", "b")
	if content, err := os.ReadFile(filepath.Join(d.PkgDir, "a", "run.sh")); err != nil || string(content) != "2" {
		t.Errorf("expected package a updated, got %q, %v", content, err)
	}
	if _, err := os.Stat(filepath.Join(pending, dirtyFileName)); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("expected dirty marker cleared after commit, got %v", err)
	}

	// Leave a stray temporary directory; it is cleaned up on commit
	stray := filepath.Join(d.PkgDir, tmpPrefix+"stray")
	if err := os.MkdirAll(stray, 0755); err != nil {
		t.Fatal(err)
	}
	if err := d.commitPendingPackages(); err != nil {
		t.Fatalf("commit failed: %v", err)
	}
	if _, err := os.Stat(stray); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("expected stray temporary directory removed, got %v", err)
	}
}

// TestRemovePackage ensures that removals only affect pending until the next
// commit, and that removing a package that isn't installed is an error.
func TestRemovePackage(t *testing.T) {
	const url = "github.com/org/repo/pkg"
	name := "github_com_org_repo_pkg"
	d := newTestPackageDaemon(t, name)

	if err := d.removePackage(url); err != nil {
		t.Fatalf("remove failed: %v", err)
	}
	assertPackages(t, d.pendingDir())
	assertPackages(t, d.PkgDir, name)
	if err := d.removePackage(url); status.Code(err) != codes.NotFound {
		t.Errorf("expected NotFound removing twice, got %v", err)
	}
	if err := d.removePackage("ssh://github.com/org/repo"); status.Code(err) != codes.InvalidArgument {
		t.Errorf("expected InvalidArgument, got %v", err)
	}
	if err := d.commitPendingPackages(); err != nil {
		t.Fatalf("commit failed: %v", err)
	}
	assertPackages(t, d.PkgDir)
}

// TestListPackages ensures that pending packages are listed with their
// metadata and the plugin files at their root, and that packages without
// metadata are skipped.
func TestListPackages(t *testing.T) {
	d := newTestPackageDaemon(t, "bare")
	pkg := filepath.Join(d.pendingDir(), "github_com_org_repo")
	writeTestPackage(t, d.pendingDir(), "github_com_org_repo", "1")
	files := map[string]string{
		PackageInfoFileName:         "url = 'github.com/org/repo'\ntag = 'v1'\n",
		"driver.plugin.toml":        "name = 'driver'",
		"engine.plugin.toml":        "name = 'engine'",
		"notes.toml":                "not a plugin",
		"sub/nested.plugin.toml":    "not at the root",
		"dir.plugin.toml/inner.txt": "a directory, not a plugin",
	}
	modified := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
	for name, content := range files {
		path := filepath.Join(pkg, name)
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}

	if err := os.Chtimes(pkg, modified, modified); err != nil {
		t.Fatal(err)
	}

	resp, err := d.ListPackages(context.Background(), &daemonpb.ListPackagesRequest{})
	if err != nil {
		t.Fatalf("list failed: %v", err)
	}
	if len(resp.GetPackages()) != 1 {
		t.Fatalf("expected 1 package, got %v", resp.GetPackages())
	}
	p := resp.GetPackages()[0]
	if p.GetUrl() != "github.com/org/repo" || p.GetTag() != "v1" || !p.GetModified().AsTime().Equal(modified) {
		t.Errorf("unexpected package metadata: %v", p)
	}
	want := map[string]string{"driver": "name = 'driver'", "engine": "name = 'engine'"}
	got := map[string]string{}
	for name, content := range p.GetPlugins() {
		got[name] = string(content)
	}
	if !maps.Equal(got, want) {
		t.Errorf("expected plugins %v, got %v", want, got)
	}
}
