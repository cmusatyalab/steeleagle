package plugin

import (
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/rs/zerolog"
)

// testLogger implements the io.Writer interface to allow zerolog to write logs
// to the testing log method. By using testLogger, zerolog logs are printed to
// the console only when a test fails.
type testLogger struct {
	t *testing.T
}

// Write pipes p to the testing log.
func (l testLogger) Write(p []byte) (n int, err error) {
	l.t.Log(string(p))
	return len(p), nil
}

var _ io.Writer = (*testLogger)(nil)

// newTestBasePlugin wraps NewBasePlugin, and pipes both logs and
// process output to a testLogger.
func newTestBasePlugin(t *testing.T, options ...PluginOption) (*BasePlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return NewBasePlugin(options...)
}

// newTestContainerPlugin wraps NewContainerPlugin, and pipes both logs and
// process output to a testLogger.
func newTestContainerPlugin(t *testing.T, imageRef string, options ...PluginOption) (*ContainerPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return NewContainerPlugin(imageRef, options...)
}

// newTestSandboxPlugin wraps NewSandboxPlugin, and pipes both logs and
// process output to a testLogger.
func newTestSandboxPlugin(t *testing.T, options ...PluginOption) (*SandboxPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return NewSandboxPlugin(options...)
}

// newTestShimPlugin wraps NewShimPlugin, and pipes both logs and
// process output to a testLogger.
func newTestShimPlugin(t *testing.T, client string, listener string, options ...PluginOption) (*ShimPlugin, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out})
	options = append(options, WithProcessOutputStream(out), WithLogger(logger))
	return NewShimPlugin(client, listener, options...)
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

// copyPackage copies the package plugin at src into a temporary directory,
// leaving out its installed environments so that it must be installed before
// it can be started.
func copyPackage(t *testing.T, src string) string {
	t.Helper()
	dst := filepath.Join(t.TempDir(), filepath.Base(filepath.Clean(src)))
	err := filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() && (d.Name() == ".pixi" || d.Name() == ".venv") {
			return filepath.SkipDir
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, data, info.Mode().Perm())
	})
	if err != nil {
		t.Fatalf("couldn't copy package %s: %v", src, err)
	}
	return dst
}
