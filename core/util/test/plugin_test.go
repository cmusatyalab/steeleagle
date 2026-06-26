package util_test

import (
    "os/exec"
    "time"
	"context"
	"path/filepath"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestPlugin(t *testing.T) {
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateBasePlugin(util.WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestPluginRunhook(t *testing.T) {
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := util.CreateBasePlugin(util.WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
	ln, conn, err := plugin.Start(context.Background())
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
	plugin, err := util.CreateBasePlugin(util.WithPath(path))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
	ln, conn, err := plugin.Start(context.Background())
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
	plugin, err := util.CreateBasePlugin(util.WithPath(path), util.WithAuthCode(util.MissionCode))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
	ln, conn, err := plugin.Start(context.Background())
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
	plugin, err := util.CreateBasePlugin(
        util.WithPath(path),
        util.WithScriptArgs([]string{"--error"}),
        util.WithoutClient(),
        util.WithoutListener(),
    )
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
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

func TestPluginNoCheck(t *testing.T) {
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
    _, err = exec.LookPath("uv")
    if err != nil {
        t.Skip("couldn't find uv, skipping this test")
    }
	plugin, err := util.CreateBasePlugin(
        util.WithExecutable("uv"),
        util.WithExecutableArgs([]string{"run", "--directory", path}),
        util.WithScript(filepath.Base(pyFile)),
        util.WithoutCheck(),
    )
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
	ln, conn, err := plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}
