package plugin

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
)

// The image used to run package plugins, which must include pixi
const pixiImage string = "ghcr.io/prefix-dev/pixi:latest"

func TestContainerPlugin(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		"alpine",
		WithPath(path),
		WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginPixi(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		pixiImage,
		WithPath(path),
		WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginPython(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		pixiImage,
		WithPath(path),
		WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginPythonCustomExec(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		"ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
		WithReadOnlyFiles([]string{path + "/pyproject.toml"}),
		WithScript(path+"/main.py"),
		WithExecutable("uv"),
		WithExecutableArgs([]string{"run"}),
		WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginFileBinding(t *testing.T) {
	requireContainer(t)
	plugin, err := newTestContainerPlugin(t,
		"ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
		WithoutClient(),
		WithFiles([]string{fileWrite}),
		WithReadOnlyFiles([]string{fileRead}),
		WithExecutable("uv"),
		WithExecutableArgs([]string{"run"}),
		WithScript(fileMain),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	_, _, err = plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}
	err = plugin.Wait()
	if err != nil {
		t.Fatalf("plugin exited with error unexpectedly: %v", err)
	}
}

func TestContainerPluginWrongAuthCode(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		"alpine",
		WithPath(path),
		WithAuthCode(listener.MissionCode),
		WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginArgs(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		"alpine",
		WithPath(path),
		WithScriptArgs([]string{"--error"}),
		WithoutClient(),
		WithRunnerArgs([]string{"--rm"}),
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

func TestContainerPluginWrongTag(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	_, err = newTestContainerPlugin(t,
		"foobar",
		WithPath(path),
		WithRunnerArgs([]string{"--rm"}),
	)
	if err == nil {
		t.Fatalf("no error creating plugin when it was expected")
	}
}
