package plugin

import (
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
)

// The image used to run package plugins, which must include pixi
const pixiImage string = "ghcr.io/prefix-dev/pixi:latest"

// TestContainerPlugin ensures that a binary plugin can be started in a
// container and complete an RPC handshake.
func TestContainerPlugin(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		"alpine",
		WithPath(path),
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

// TestContainerPluginPixi ensures that a Go package plugin can be started in a
// container through its pixi start task.
func TestContainerPluginPixi(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		pixiImage,
		WithPath(path),
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

// TestContainerPluginPython ensures that a Python package plugin can be
// started in a container through its pixi start task.
func TestContainerPluginPython(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		pixiImage,
		WithPath(path),
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

// TestContainerPluginPythonCustomExec ensures that setting the executable and
// its args replaces `pixi run` for a containerized Python plugin.
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

// TestContainerPluginFileBinding ensures that writable and read-only files are
// bound into the container.
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

// TestContainerPluginWrongAuthCode ensures that RPCs from a containerized
// plugin are rejected when it is given a different AuthCode than the one
// expected.
func TestContainerPluginWrongAuthCode(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	plugin, err := newTestContainerPlugin(t,
		"alpine",
		WithPath(path),
		WithAuthCode(listener.UserCode),
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

// TestContainerPluginArgs ensures that script args are forwarded to a
// containerized plugin.
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

// TestContainerPluginWrongTag ensures that creating a container plugin with an
// image that doesn't exist returns an error.
func TestContainerPluginWrongTag(t *testing.T) {
	requireContainer(t)
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	_, err = newTestContainerPlugin(t,
		"foobar",
		WithPath(path),
	)
	if err == nil {
		t.Fatalf("no error creating plugin when it was expected")
	}
}

// TestContainerEnvArgs ensures that variables are forwarded by name only, once
// each, and without the socket variables.
func TestContainerEnvArgs(t *testing.T) {
	envVars := []string{
		"STEELEAGLE_PLUGIN",
		"STEELEAGLE_PLUGIN_ARGS",
		"STEELEAGLE_PLUGIN", // duplicate
		ClientSockEnv,
		ListenSockEnv,
		"",
	}
	got := containerEnvArgs(envVars)
	want := []string{
		"-e", "STEELEAGLE_PLUGIN",
		"-e", "STEELEAGLE_PLUGIN_ARGS",
	}
	if !slices.Equal(got, want) {
		t.Fatalf("got env args %q, want %q", got, want)
	}
}

// TestContainerPluginEnvironment ensures that variables added with
// WithEnvironment reach a containerized plugin verbatim, while the parent's
// environment isn't forwarded.
func TestContainerPluginEnvironment(t *testing.T) {
	requireContainer(t)
	// The parent's environment is captured when the plugin is created
	t.Setenv("STEELEAGLE_TEST_PARENT", "parent")
	multiline := "line one\nline two"
	args := `{"message": "h\u00fcllo", "quote": "it's \"fine\"", "literal": "$HOME"}`

	// The script writes what it sees into files bound in from the host
	dir := t.TempDir()
	script := filepath.Join(dir, "env.sh")
	err := os.WriteFile(script, []byte(`#!/bin/sh
printf '%s' "$STEELEAGLE_PLUGIN_ARGS" > args.txt
printf '%s' "$STEELEAGLE_TEST_MULTILINE" > multiline.txt
printf '%s' "${STEELEAGLE_TEST_PARENT-unset}" > parent.txt
printf '%s' "$HOME" > home.txt
`), 0o755)
	if err != nil {
		t.Fatalf("couldn't write env script: %v", err)
	}
	outputs := map[string]string{}
	for _, name := range []string{"args.txt", "multiline.txt", "parent.txt", "home.txt"} {
		outputs[name] = filepath.Join(dir, name)
		if err := os.WriteFile(outputs[name], nil, 0o644); err != nil {
			t.Fatalf("couldn't create output file: %v", err)
		}
	}

	plugin, err := newTestContainerPlugin(t,
		"alpine",
		WithoutClient(),
		WithPath(script),
		WithFiles([]string{
			outputs["args.txt"], outputs["multiline.txt"],
			outputs["parent.txt"], outputs["home.txt"],
		}),
		WithEnvironment("STEELEAGLE_PLUGIN_ARGS", args),
		WithEnvironment("STEELEAGLE_TEST_MULTILINE", multiline),
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

	for name, want := range map[string]string{
		"args.txt":      args,
		"multiline.txt": multiline,
		"parent.txt":    "unset",
		"home.txt":      "/root", // alpine's HOME, not the host's
	} {
		got, err := os.ReadFile(outputs[name])
		if err != nil {
			t.Fatalf("couldn't read %s: %v", name, err)
		}
		if string(got) != want {
			t.Errorf("%s: got %q, want %q", name, got, want)
		}
	}
}
