package util_test

import (
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
	plugin := util.CreateContainerPlugin("alpine", util.WithPath(path))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
    plugin.Stop()
}

func TestContainerPluginRunhook(t *testing.T) {
	path, err := filepath.Abs(go_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
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
	plugin.Stop()
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
	plugin := util.CreateContainerPlugin("foobar", util.WithPath(path))
	_, _, err = plugin.Start(context.Background())
	if err == nil {
		t.Fatalf("expected an error due to a bogus tag")
	}
}
