package plugin

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
)

// TestPlugin ensures that a binary plugin can be started and complete an RPC
// handshake.
func TestPlugin(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t, WithPath(path))
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

// TestPluginWithParent ensures that a plugin can be started with a custom
// parent directory for its sockets and files.
func TestPluginWithParent(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
		WithPath(path),
		WithParentDir(filepath.Join(t.TempDir(), "foo")),
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

	path, err = util.GetVehicleRunDirByName("foo")
	if err != nil {
		t.Errorf("couldn't get vehicle directory: %v", err)
	}

	os.RemoveAll(path)
}

// TestPluginPixi ensures that a Go package plugin can be started through its
// pixi start task.
func TestPluginPixi(t *testing.T) {
	requirePixi(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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

// TestPluginPixiArgs ensures that script args are forwarded to the pixi start
// task.
func TestPluginPixiArgs(t *testing.T) {
	requirePixi(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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

	var exitErr *exec.ExitError
	if err := plugin.Wait(); !errors.As(err, &exitErr) {
		t.Fatalf("expected an exit error from the start task, got: %v", err)
	}
}

// TestPluginPixiCustomExec ensures that setting the executable and its args
// replaces `pixi run` while still running the start task.
func TestPluginPixiCustomExec(t *testing.T) {
	requirePixi(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
		WithPath(path),
		WithExecutable("pixi"),
		WithExecutableArgs([]string{"run", "--frozen"}),
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

// TestPluginNoManifest ensures that package plugins without a pixi manifest
// are rejected.
func TestPluginNoManifest(t *testing.T) {
	_, err := newTestBasePlugin(t,
		WithPath(t.TempDir()),
	)
	if err == nil {
		t.Fatal("expected error creating plugin without a pixi manifest")
	}
}

// TestPluginPython ensures that a Python package plugin can be started through
// its pixi start task.
func TestPluginPython(t *testing.T) {
	requirePixi(t)
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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

// TestPluginWrongAuthCode ensures that RPCs from a plugin are rejected when it
// is given a different AuthCode than the one expected.
func TestPluginWrongAuthCode(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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

// TestPluginArgs ensures that script args are forwarded to a binary plugin.
func TestPluginArgs(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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

// TestPluginNoCheck ensures that a plugin can be started with a script that
// isn't on disk when script path validation is disabled.
func TestPluginNoCheck(t *testing.T) {
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	_, err = exec.LookPath("uv")
	if err != nil {
		t.Skip("couldn't find uv, skipping this test")
	}
	plugin, err := newTestBasePlugin(t,
		WithExecutable("uv"),
		WithExecutableArgs([]string{"run", "--directory", path}),
		WithScript(filepath.Base(pyFile)),
		WithoutScriptPathValidation(),
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

// TestPluginStartAlreadyRunning ensures that starting a plugin which is
// already running returns an error.
func TestPluginStartAlreadyRunning(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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
	ln, conn, err = plugin.Start(t.Context())
	if err == nil {
		t.Fatal("expected error starting plugin since it's already running")
	}
}

// TestPluginRestart ensures that plugins can be restarted if they exit
// unexpectedly while running, or if the context provided to them is canceled.
func TestPluginRestart(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	marker := filepath.Join(t.TempDir(), "marker")

	plugin, err := newTestBasePlugin(t,
		WithPath(path),
		WithScriptArgs([]string{"--erroronce"}),
		WithEnvironment("ERROR_ONCE_MARKER", marker),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(t.Context())
	if err == nil {
		t.Fatal("expected first start to fail since the plugin errors once")
	}

	for i := range 3 {
		ctx, cancel := context.WithCancel(t.Context())
		ln, conn, err := plugin.Start(ctx)
		if err != nil {
			t.Fatalf("encountered error starting plugin again: %v, iter: %d", err, i)
		}
		err = pluginRPCCheck(t, ln, conn, listener.UnknownCode)
		if err != nil {
			t.Fatalf("encountered error with plugin RPC handshake: %v, iter: %d", err, i)
		}
		cancel()

		err = <-plugin.Watch()
		if err != context.Canceled {
			t.Fatalf("expected context canceled error, iter: %d", i)
		}
	}
}

// TestPluginStartFailureUnblocksWait ensures that if Start() fails before the
// plugin subprocess is started, it doesn't leave the plugin in a state where a
// later Wait() call blocks forever.
func TestPluginStartFailureUnblocksWait(t *testing.T) {
	plugin, err := newTestBasePlugin(t, WithoutScriptPathValidation())
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}

	// No script path is set up, so Start() should fail before spawning a
	// subprocess
	_, _, err = plugin.Start(t.Context())
	if err == nil {
		t.Fatal("expected Start() to fail due to missing script path")
	}

	done := make(chan error, 1)
	go func() { done <- plugin.Wait() }()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Wait() hung after a failed Start()")
	}
}

// TestPluginConcurrentWaiters makes sure that calling Wait() multiple times,
// especially concurrently, returns the expected error.
func TestPluginConcurrentWaiters(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
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

	const waiters = 8
	results := make([]error, waiters)
	var wg sync.WaitGroup
	for i := range waiters {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			results[i] = plugin.Wait()
		}(i)
	}
	wg.Wait()

	for _, err := range results {
		var exitErr *exec.ExitError
		if !errors.As(err, &exitErr) {
			t.Fatal("expected an exit error")
		} else if exitErr.ExitCode() != 1 {
			t.Fatal("expected exit code 1")
		}
	}
}

// TestPluginStartExitBeforeSocket ensures that Start fails as soon as the
// plugin exits, rather than waiting out the timeout for its socket.
func TestPluginStartExitBeforeSocket(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t,
		WithPath(path),
		WithScriptArgs([]string{"--error"}),
		WithTimeout(15),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	begin := time.Now()
	_, _, err = plugin.Start(t.Context())
	if err == nil {
		t.Fatal("expected Start() to fail since the plugin exits immediately")
	}
	if elapsed := time.Since(begin); elapsed > 5*time.Second {
		t.Fatalf("expected Start() to fail before the timeout, took %v", elapsed)
	}
}

// TestPluginStartFailureKillsProcess ensures that a Start which launches the
// plugin but fails afterwards kills the process and removes it from the ACL.
func TestPluginStartFailureKillsProcess(t *testing.T) {
	// A plugin that never creates its socket
	script := filepath.Join(t.TempDir(), "sleep.sh")
	err := os.WriteFile(script, []byte("#!/bin/sh\nexec sleep 30\n"), 0o755)
	if err != nil {
		t.Fatalf("couldn't write plugin script: %v", err)
	}
	acl := listener.NewAcl(nil, nil, false)
	plugin, err := newTestBasePlugin(t,
		WithPath(script),
		WithAcl(acl),
		WithTimeout(1),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(t.Context())
	if err == nil {
		t.Fatal("expected Start() to fail since the plugin never creates its socket")
	}

	pid := plugin.cmd.Process.Pid
	if plugin.Running() {
		t.Error("expected plugin to not be running after a failed Start()")
	}
	if err := syscall.Kill(pid, 0); !errors.Is(err, syscall.ESRCH) {
		t.Errorf("expected plugin process %d to be killed, got: %v", pid, err)
	}
	if ok, _ := acl.AllowsPid(pid); ok {
		t.Errorf("expected plugin process %d to be removed from the ACL", pid)
	}
}

// TestPluginInstall ensures that a package plugin can be installed, and then
// started from the installed environment.
func TestPluginInstall(t *testing.T) {
	requirePixi(t)
	path := copyPackage(t, pyPkg)
	plugin, err := newTestBasePlugin(t, WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	err = plugin.Install(t.Context())
	if err != nil {
		t.Fatalf("encountered error installing plugin: %v", err)
	}
	if plugin.Running() {
		t.Error("expected plugin to not be running after Install() returns")
	}
	if _, err := os.Stat(filepath.Join(path, ".pixi")); err != nil {
		t.Fatalf("expected pixi environment to be installed: %v", err)
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

// TestPluginInstallFailure ensures that a failed install returns the exit
// error of the install process, and leaves the plugin able to run again.
func TestPluginInstallFailure(t *testing.T) {
	requirePixi(t)
	path := copyPackage(t, pyPkg)
	plugin, err := newTestBasePlugin(t, WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	// pixi.toml takes precedence over pyproject.toml, so pixi will fail to
	// parse the package manifest
	err = os.WriteFile(filepath.Join(path, "pixi.toml"), []byte("[[[invalid"), 0o644)
	if err != nil {
		t.Fatalf("couldn't write invalid manifest: %v", err)
	}
	for i := range 2 {
		err = plugin.Install(t.Context())
		var exitErr *exec.ExitError
		if !errors.As(err, &exitErr) {
			t.Fatalf("expected an exit error from the install, got: %v, iter: %d", err, i)
		}
		if plugin.Running() {
			t.Fatalf("expected plugin to not be running after a failed Install(), iter: %d", i)
		}
	}
}

// TestPluginInstallCanceled ensures that canceling the context stops an
// install.
func TestPluginInstallCanceled(t *testing.T) {
	requirePixi(t)
	plugin, err := newTestBasePlugin(t, WithPath(copyPackage(t, pyPkg)))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ctx, cancel := context.WithCancel(t.Context())
	cancel()
	err = plugin.Install(ctx)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context canceled error, got: %v", err)
	}
	if plugin.Running() {
		t.Error("expected plugin to not be running after a canceled Install()")
	}
}

// TestPluginInstallNotPackage ensures that Install is a no-op for plugins that
// aren't pixi packages, rather than running the plugin.
func TestPluginInstallNotPackage(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestBasePlugin(t, WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	err = plugin.Install(t.Context())
	if err != nil {
		t.Fatalf("expected Install() to be a no-op, got: %v", err)
	}
	if plugin.cmd != nil {
		t.Fatal("expected Install() to not run anything")
	}
}

// TestPluginInstallAlreadyRunning ensures that a plugin can't be installed
// while it is running.
func TestPluginInstallAlreadyRunning(t *testing.T) {
	requirePixi(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestBasePlugin(t, WithPath(path))
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
	err = plugin.Install(t.Context())
	if err == nil {
		t.Fatal("expected error installing plugin since it's already running")
	}
}
