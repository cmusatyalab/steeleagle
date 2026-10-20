package plugin

import (
	"io"
	"os/exec"
	"testing"

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

// newTestBasePlugin wraps CreateBasePlugin, and pipes both logs and
// process output to a testLogger.
func newTestBasePlugin(t *testing.T, options ...PluginOption) (*BasePlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return CreateBasePlugin(options...)
}

// newTestContainerPlugin wraps CreateContainerPlugin, and pipes both logs and
// process output to a testLogger.
func newTestContainerPlugin(t *testing.T, imageRef string, options ...PluginOption) (*ContainerPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return CreateContainerPlugin(imageRef, options...)
}

// newTestSandboxPlugin wraps CreateSandboxPlugin, and pipes both logs and
// process output to a testLogger.
func newTestSandboxPlugin(t *testing.T, options ...PluginOption) (*SandboxPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return CreateSandboxPlugin(options...)
}

// newTestShimPlugin wraps CreateShimPlugin, and pipes both logs and
// process output to a testLogger.
func newTestShimPlugin(t *testing.T, client string, listener string, options ...PluginOption) (*ShimPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return CreateShimPlugin(client, listener, options...)
}

// requirePixi skips the test if pixi is not installed.
func requirePixi(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("pixi"); err != nil {
		t.Skip("pixi not found, skipping test")
	}
}

// requireSandbox skips the test if bubblewrap is not installed.
func requireSandbox(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("bwrap"); err != nil {
		t.Skip("bubblewrap (bwrap) not found, skipping test")
	}
}

// requireContainer skips the test if podman is not installed.
func requireContainer(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("podman"); err != nil {
		t.Skip("podman not found, skipping test")
	}
}
