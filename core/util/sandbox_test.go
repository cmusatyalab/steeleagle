package util_test

import (
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
)

func TestSandboxPlugin(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	plugin, err := util.CreateSandboxPlugin(
		util.WithPath(path),
		util.WithLogger(logger),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestSandboxPluginRunhook(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(goPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_pkg: %v", err)
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	plugin, err := util.CreateSandboxPlugin(
		util.WithPath(path),
		util.WithLogger(logger),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestSandboxPluginPython(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(pyPkg)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper py_pkg: %v", err)
	}
	_, err = exec.LookPath("uv")
	if err != nil {
		t.Skip("couldn't find uv, skipping this test")
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	plugin, err := util.CreateSandboxPlugin(
		util.WithPath(path),
		util.WithRunnerArgs([]string{"--share-net"}),
		util.WithExecutableFiles([]string{"uv"}),
		util.WithLogger(logger),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}
}

func TestSandboxPluginFileBinding(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	_, err = exec.LookPath("uv")
	if err != nil {
		t.Skip("couldn't find uv, skipping this test")
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	plugin, err := util.CreateSandboxPlugin(
		util.WithoutClient(),
		util.WithRunnerArgs([]string{"--share-net"}),
		util.WithFiles([]string{fileWrite}),
		util.WithReadOnlyFiles([]string{fileRead}),
		util.WithExecutableFiles([]string{"uv"}),
		util.WithExecutable("uv"),
		util.WithExecutableArgs([]string{"run"}),
		util.WithScript(fileMain),
		util.WithLogger(logger),
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

func TestSandboxPluginWrongAuthCode(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	plugin, err := util.CreateSandboxPlugin(
		util.WithPath(path),
		util.WithAuthCode(util.MissionCode),
		util.WithLogger(logger),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.AdminCode)
	if err == nil {
		t.Fatalf("rpc succeeded when it should have failed")
	}
}

func TestSandboxPluginArgs(t *testing.T) {
	_, err := exec.LookPath("bwrap")
	if err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
	path, err := filepath.Abs(goBinary)
	if err != nil {
		t.Fatalf("couldn't stat mock_plugin helper go_binary: %v", err)
	}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: testLogger{t}})
	plugin, err := util.CreateSandboxPlugin(
		util.WithPath(path),
		util.WithScriptArgs([]string{"--error"}),
		util.WithoutClient(),
		util.WithoutListener(),
		util.WithLogger(logger),
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
