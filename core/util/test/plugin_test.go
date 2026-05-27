package util_test

import (
    "os/exec"
	"context"
	"path/filepath"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestProcessPlugin(t *testing.T) {
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreatePlugin(util.WithPath(path))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

func TestContainerPlugin(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreateContainerPlugin("alpine", util.WithPath(path))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

func TestSandboxPlugin(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
        t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreateSandboxPlugin(util.WithPath(path))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

func TestContainerPluginWrongTag(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreateContainerPlugin("foobar", util.WithPath(path))
	_, _, err = plugin.Start(context.Background())
	if err == nil {
		t.Fatalf("expected an error due to a bogus tag")
	}
}

func TestPluginWrongAuthCode(t *testing.T) {
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreatePlugin(util.WithPath(path), util.WithAuthCode(util.MissionCode))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.AdminCode)
	if err == nil {
		t.Errorf("rpc succeeded when it should have failed")
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

