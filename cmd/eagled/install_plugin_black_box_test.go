package main_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// gitFixtureRepo creates a throwaway local git repo under t.TempDir() with an
// install.sh/run.sh pair at subpath. Returns the repo's filesystem path,
// usable directly as InstallPluginRequest.repo.
func gitFixtureRepo(t *testing.T, subpath string) string {
	t.Helper()
	repo := t.TempDir()
	dir := filepath.Join(repo, subpath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("creating fixture subpath: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "install.sh"), []byte("#!/bin/sh\necho installed > installed.marker\n"), 0755); err != nil {
		t.Fatalf("writing install.sh: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "run.sh"), []byte("#!/bin/sh\nexec ./binary\n"), 0755); err != nil {
		t.Fatalf("writing run.sh: %v", err)
	}

	run := func(args ...string) {
		t.Helper()
		cmd := exec.Command("git", args...)
		cmd.Dir = repo
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v\n%s", args, err, out)
		}
	}
	run("init", "-q")
	run("config", "user.email", "test@example.com")
	run("config", "user.name", "Test")
	run("config", "commit.gpgsign", "false")
	run("add", "-A")
	run("commit", "-q", "-m", "fixture plugin", "--no-gpg-sign")

	return repo
}

// gitHead returns repo's current commit hash, to install a pinned ref exactly
// like a real InstallPluginRequest would.
func gitHead(t *testing.T, repo string) string {
	t.Helper()
	out, err := exec.Command("git", "-C", repo, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatalf("git rev-parse HEAD: %v", err)
	}
	return string(out[:len(out)-1]) // trim trailing newline
}

// TestInstallPlugin exercises InstallPlugin/GetInstalledPlugins end to end
// through eagled's real DaemonService, against a local scratch git repo.
func TestInstallPlugin(t *testing.T) {
	inst := startEagled(t, "")
	ctx := t.Context()

	// InstallPlugin requires a configured daemon (it needs plugin-dir)
	cfgResp, err := inst.Client.Configure(ctx, eagledpb.ConfigureRequest_builder{
		ConfigToml: `
port-base = 0
plugin-dir = "` + inst.PluginDir + `"

[backend.swarm-controller]
address = "127.0.0.1:1"
`,
	}.Build())
	if err != nil || len(cfgResp.GetVehicles()) != 0 {
		t.Fatalf("Configure: resp=%v err=%v", cfgResp, err)
	}

	const pluginName, subpath = "mydriver", "subdir"
	repo := gitFixtureRepo(t, subpath)
	ref := gitHead(t, repo)

	installResp, err := inst.Client.InstallPlugin(ctx, eagledpb.InstallPluginRequest_builder{
		Name:     pluginName,
		Repo:     repo,
		Ref:      ref,
		Subpath:  subpath,
		Category: eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER,
	}.Build())
	if err != nil {
		t.Fatalf("InstallPlugin: %v", err)
	}
	if !installResp.GetOk() {
		t.Fatalf("InstallPlugin failed: %s", installResp.GetError())
	}

	// The installed plugin should be on disk under
	// util.GetInstalledPluginDir("driver"), i.e.
	// data-dir/steeleagle/plugins/driver/<name> — not plugin-dir.
	installedDir := filepath.Join(inst.DataDir, "steeleagle", "plugins", "driver", pluginName)
	for _, f := range []string{"install.sh", "run.sh", "installed.marker"} {
		if _, err := os.Stat(filepath.Join(installedDir, f)); err != nil {
			t.Errorf("expected %s to exist in installed plugin: %v", f, err)
		}
	}

	// GetInstalledPlugins should report it, with the exact ref and category
	// installed.
	listResp, err := inst.Client.GetInstalledPlugins(ctx, eagledpb.GetInstalledPluginsRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetInstalledPlugins: %v", err)
	}
	found := false
	for _, p := range listResp.GetPlugins() {
		if p.GetName() == pluginName {
			found = true
			if p.GetRef() != ref {
				t.Errorf("installed ref = %q, want %q", p.GetRef(), ref)
			}
			if p.GetCategory() != eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER {
				t.Errorf("installed category = %v, want %v", p.GetCategory(), eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER)
			}
		}
	}
	if !found {
		t.Fatalf("expected %s in GetInstalledPlugins, got %v", pluginName, listResp.GetPlugins())
	}

	// A plugin whose install.sh fails should leave the existing install
	// untouched and report the failure.
	badRepo := gitFixtureRepo(t, subpath)
	badDir := filepath.Join(badRepo, subpath)
	if err := os.WriteFile(filepath.Join(badDir, "install.sh"), []byte("#!/bin/sh\nexit 1\n"), 0755); err != nil {
		t.Fatalf("writing failing install.sh: %v", err)
	}
	cmd := exec.Command("git", "-C", badRepo, "commit", "-q", "-a", "-m", "break install.sh", "--no-gpg-sign")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("git commit: %v\n%s", err, out)
	}
	badRef := gitHead(t, badRepo)

	failResp, err := inst.Client.InstallPlugin(ctx, eagledpb.InstallPluginRequest_builder{
		Name:     pluginName,
		Repo:     badRepo,
		Ref:      badRef,
		Subpath:  subpath,
		Category: eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER,
	}.Build())
	if err != nil {
		t.Fatalf("InstallPlugin (expected failure): %v", err)
	}
	if failResp.GetOk() {
		t.Fatal("expected InstallPlugin to fail for a nonzero install.sh")
	}

	// The original install should be untouched.
	listResp2, err := inst.Client.GetInstalledPlugins(ctx, eagledpb.GetInstalledPluginsRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetInstalledPlugins (after failed install): %v", err)
	}
	for _, p := range listResp2.GetPlugins() {
		if p.GetName() == pluginName && p.GetRef() != ref {
			t.Errorf("expected recorded ref to stay %q after failed install, got %q", ref, p.GetRef())
		}
	}
}
