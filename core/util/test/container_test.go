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
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin(
        "alpine", 
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginRunhook(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := util.CreateContainerPlugin(
        "alpine",
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginPython(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := util.CreateContainerPlugin(
        "ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginPythonCustomExec(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := util.CreateContainerPlugin(
        "ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
        util.WithReadOnlyFiles([]string{path+"/pyproject.toml"}),
        util.WithScript(path+"/main.py"),
        util.WithExecutable("uv"),
        util.WithExecutableArgs([]string{"run"}),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginFileBinding(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	plugin, err := util.CreateContainerPlugin(
        "ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
        util.WithoutClient(),
        util.WithFiles([]string{fileWrite}),
        util.WithReadOnlyFiles([]string{fileRead}),
        util.WithExecutable("uv"),
        util.WithExecutableArgs([]string{"run"}),
        util.WithScript(fileMain),
    )
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
	_, _, err = plugin.Start(context.Background())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}
    err = plugin.Wait()
    if err != nil {
        t.Fatalf("plugin exited with error unexpectedly: %v", err)
    }
}

func TestContainerPluginWrongAuthCode(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin(
        "alpine",
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
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := util.CreateContainerPlugin(
        "alpine",
        util.WithPath(path),
        util.WithScriptArgs([]string{"--error"}),
        util.WithoutClient(),
        util.WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginWrongTag(t *testing.T) {
	_, err := exec.LookPath("podman")
	if err != nil {
        t.Skip("podman not found, skipping test")
	}
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	_, err = util.CreateContainerPlugin(
        "foobar",
        util.WithPath(path),
        util.WithRunnerArgs([]string{"--rm"}),
    )
	if err == nil {
		t.Fatalf("no error creating plugin when it was expected")
	}
}
