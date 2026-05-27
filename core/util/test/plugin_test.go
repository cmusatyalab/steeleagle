package util_test

import (
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
	ln, conn, err := plugin.Spawn(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

func TestContainerPlugin(t *testing.T) {
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreateContainerPlugin("alpine", util.WithPath(path))
	ln, conn, err := plugin.Spawn(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

func TestSandboxPlugin(t *testing.T) {
	path, err := filepath.Abs(binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper binary: %v", err)
	}
	plugin := util.CreateSandboxPlugin(util.WithPath(path))
	ln, conn, err := plugin.Spawn(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}
