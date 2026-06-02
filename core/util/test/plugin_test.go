package util_test

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestPlugin(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
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

func TestPluginRunhook(t *testing.T) {
	path, err := filepath.Abs(go_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
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

func TestPluginPython(t *testing.T) {
	path, err := filepath.Abs(py_pkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
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

func TestPluginWrongAuthCode(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin := util.CreatePlugin(util.WithPath(path), util.WithAuthCode(util.MissionCode))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.AdminCode)
	if err == nil {
		t.Fatalf("rpc succeeded when it should have failed")
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}

func TestPluginArgs(t *testing.T) {
	path, err := filepath.Abs(go_binary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin := util.CreatePlugin(util.WithPath(path), util.WithScriptArgs([]string{"--error"}))
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err == nil {
		t.Fatalf("rpc succeeded when it should have failed")
	}
	err = plugin.Stop()
	if err != nil {
		t.Errorf("encountered error while stopping plugin: %v", err)
	}
}
