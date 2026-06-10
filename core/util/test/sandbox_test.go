package util_test

import (
    "time"
    "os/exec"
	"context"
	"path/filepath"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestSandboxPlugin(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
        t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateSandboxPlugin(util.WithPath(path))
	defer plugin.Stop()
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestSandboxPluginRunhook(t *testing.T) {
	path, err := filepath.Abs(go_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := util.CreateSandboxPlugin(util.WithPath(path))
	defer plugin.Stop()
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestSandboxPluginPython(t *testing.T) {
	path, err := filepath.Abs(py_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
    _, err = exec.LookPath("uv")
    if err != nil {
        t.Skip("couldn't find uv, skipping this test")
    }
	plugin, err := util.CreateSandboxPlugin(util.WithPath(path),
        util.WithExecutableFiles([]string{"uv"}),
    )
    defer plugin.Stop()
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestSandboxPluginWrongAuthCode(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateSandboxPlugin(util.WithPath(path), util.WithAuthCode(util.MissionCode))
    defer plugin.Stop()
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.AdminCode)
	if err == nil {
		t.Fatalf("rpc succeeded when it should have failed")
	}
}

func TestSandboxPluginArgs(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateSandboxPlugin(util.WithPath(path), util.WithScriptArgs([]string{"--error"}), util.WithoutServer())
    defer plugin.Stop()
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(context.Background())
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
