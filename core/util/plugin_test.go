package util_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestPlugin(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := CreateBasePlugin(t, util.WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestPluginWithParent(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
		util.WithParentDir(filepath.Join(t.TempDir(), "foo")),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}

	path, err = util.GetVehicleDirByName("foo")
	if err != nil {
		t.Errorf("couldn't get vehicle directory: %v", err)
	}

	os.RemoveAll(path)
}

func TestPluginRunhook(t *testing.T) {
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestPluginPython(t *testing.T) {
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestPluginWrongAuthCode(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
		util.WithAuthCode(util.MissionCode),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.AdminCode)
	if err == nil {
		t.Fatalf("rpc succeeded when it should have failed")
	}
}

func TestPluginArgs(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
		util.WithScriptArgs([]string{"--error"}),
		util.WithoutClient(),
		util.WithoutListener(),
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

func TestPluginNoCheck(t *testing.T) {
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	_, err = exec.LookPath("uv")
	if err != nil {
		t.Skip("couldn't find uv, skipping this test")
	}
	plugin, err := CreateBasePlugin(t,
		util.WithExecutable("uv"),
		util.WithExecutableArgs([]string{"run", "--directory", path}),
		util.WithScript(filepath.Base(pyFile)),
		util.WithoutScriptPathValidation(),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestPluginStartAlreadyRunning(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}
	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
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

	plugin, err := CreateBasePlugin(t,
		util.WithPath(path),
		util.WithScriptArgs([]string{"--erroronce"}),
		util.WithEnvironment("ERROR_ONCE_MARKER", marker),
		util.WithTimeout(0),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(t.Context())
	if err != nil {
		t.Logf("timeed out waiting for plugin socket: %v", err)
	}

	select {
	case <-plugin.Watch():
	case <-time.After(time.Second):
		t.Fatal("expected plugin to error out")
	}
	util.WithTimeout(15)(plugin)
	for i := range 3 {
		ctx, cancel := context.WithCancel(t.Context())
		ln, conn, err := plugin.Start(ctx)
		if err != nil {
			t.Fatalf("encountered error starting plugin again: %v, iter: %d", err, i)
		}
		err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
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
	plugin, err := CreateBasePlugin(t, util.WithoutScriptPathValidation())
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
