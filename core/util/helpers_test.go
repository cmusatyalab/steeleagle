package util_test

import (
	"io"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
)

// testLogger implements the io.Writer interface to allow zerolog to write logs
// to the testing log method. By using testLogger, zerolog logs are printed to
// the console only when a test fails.
type testLogger struct {
	t *testing.T
}

func (l testLogger) Write(p []byte) (n int, err error) {
	l.t.Log(string(p))
	return len(p), nil
}

var _ io.Writer = (*testLogger)(nil)

// CreateBasePlugin masks the normal util.CreateBasePlugin, and pipes both logs and
// process output to a testLogger.
func CreateBasePlugin(t *testing.T, options ...util.PluginOption) (*util.BasePlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, util.WithProcessOutputStream(out), util.WithLogger(logger))
	return util.CreateBasePlugin(options...)
}

// CreateContainerPlugin masks the normal util.CreateContainerPlugin, and pipes both logs and
// process output to a testLogger.
func CreateContainerPlugin(t *testing.T, imageRef string, options ...util.PluginOption) (*util.ContainerPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, util.WithProcessOutputStream(out), util.WithLogger(logger))
	return util.CreateContainerPlugin(imageRef, options...)
}

// CreateSandboxPlugin masks the normal util.CreateSandboxPlugin, and pipes both logs and
// process output to a testLogger.
func CreateSandboxPlugin(t *testing.T, options ...util.PluginOption) (*util.SandboxPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, util.WithProcessOutputStream(out), util.WithLogger(logger))
	return util.CreateSandboxPlugin(options...)
}

// CreateShimPlugin masks the normal util.CreateShimPlugin, and pipes both logs and
// process output to a testLogger.
func CreateShimPlugin(t *testing.T, client string, listener string, options ...util.PluginOption) (*util.ShimPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, util.WithProcessOutputStream(out), util.WithLogger(logger))
	return util.CreateShimPlugin(client, listener, options...)
}
