package plugin

import (
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
)

// TestSandboxPlugin ensures that a binary plugin can be started in a sandbox
// and complete an RPC handshake.
func TestSandboxPlugin(t *testing.T) {
	requireSandbox(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestSandboxPlugin(t,
		WithPath(path),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, listener.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

// TestSandboxPluginPixi ensures that a Go package plugin can be started in a
// sandbox through its pixi start task.
func TestSandboxPluginPixi(t *testing.T) {
	requireSandbox(t)
	requirePixi(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestSandboxPlugin(t,
		WithPath(path),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, listener.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

// TestSandboxPluginPython ensures that a Python package plugin can be started
// in a sandbox through its pixi start task.
func TestSandboxPluginPython(t *testing.T) {
	requireSandbox(t)
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	requirePixi(t)
	plugin, err := newTestSandboxPlugin(t,
		WithPath(path),
		WithRunnerArgs([]string{"--share-net"}),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, listener.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

// TestSandboxPluginFileBinding ensures that writable, read-only and
// executable files are bound into the sandbox.
func TestSandboxPluginFileBinding(t *testing.T) {
	requireSandbox(t)
	_, err := exec.LookPath("uv")
	if err != nil {
		t.Skip("couldn't find uv, skipping this test")
	}
	plugin, err := newTestSandboxPlugin(t,
		WithoutClient(),
		WithRunnerArgs([]string{"--share-net"}),
		WithFiles([]string{fileWrite}),
		WithReadOnlyFiles([]string{fileRead}),
		WithExecutableFiles([]string{"uv"}),
		WithExecutable("uv"),
		WithExecutableArgs([]string{"run"}),
		WithScript(fileMain),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}
	err = plugin.Wait()
	if err != nil {
		t.Fatalf("plugin exited with error unexpectedly: %v", err)
	}
}

// TestSandboxPluginWrongAuthCode ensures that RPCs from a sandboxed plugin are
// rejected when it is given a different AuthCode than the one expected.
func TestSandboxPluginWrongAuthCode(t *testing.T) {
	requireSandbox(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestSandboxPlugin(t,
		WithPath(path),
		WithAuthCode(listener.UserCode),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, listener.AdminCode)
	if err == nil {
		t.Fatalf("rpc succeeded when it should have failed")
	}
}

// TestSandboxPluginArgs ensures that script args are forwarded to a sandboxed
// plugin.
func TestSandboxPluginArgs(t *testing.T) {
	requireSandbox(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestSandboxPlugin(t,
		WithPath(path),
		WithScriptArgs([]string{"--error"}),
		WithoutClient(),
		WithoutListener(),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	select {
	case _ = <-plugin.Watch():
		return // expect an error
	case <-time.After(5 * time.Second):
		t.Fatalf("didn't get error from plugin when it was expected")
	}
}

// TestSandboxPluginInstall ensures that a package plugin can be installed in a
// sandbox, which has network access only while installing, and then started
// from the installed environment.
func TestSandboxPluginInstall(t *testing.T) {
	requireSandbox(t)
	requirePixi(t)
	path := copyPackage(t, pyPkg)
	plugin, err := newTestSandboxPlugin(t, WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	err = plugin.Install(t.Context())
	if err != nil {
		t.Fatalf("encountered error installing plugin: %v", err)
	}
	if _, err := os.Stat(filepath.Join(path, ".pixi")); err != nil {
		t.Fatalf("expected pixi environment to be installed: %v", err)
	}

	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}
	if slices.Contains(plugin.final, "--share-net") {
		t.Errorf("expected started plugin to not share the network: %v", plugin.final)
	}
	err = pluginRPCCheck(t, ln, conn, listener.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}
