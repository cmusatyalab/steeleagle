package util_test

import (
    "time"
    "os/exec"
	"context"
	"path/filepath"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestContainerPlugin(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin("alpine", 
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginRunhook(t *testing.T) {
	path, err := filepath.Abs(go_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := util.CreateContainerPlugin("alpine",
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginPython(t *testing.T) {
	path, err := filepath.Abs(py_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := util.CreateContainerPlugin("ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginWrongAuthCode(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin("alpine",
        util.WithPath(path),
        util.WithAuthCode(util.MissionCode),
        util.WithRunnerArgs([]string{"--rm"}),
    )
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

func TestContainerPluginArgs(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin("alpine",
        util.WithPath(path),
        util.WithScriptArgs([]string{"--error"}),
        util.WithoutServer(),
        util.WithRunnerArgs([]string{"--rm"}),
    )
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

func TestContainerPluginWrongTag(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin("foobar",
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
    )
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(context.Background())
	if err == nil {
		t.Fatalf("expected an error due to a bogus tag")
	}
}
