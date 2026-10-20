package listener

import (
	"io"
	"os"
	"os/exec"
	"testing"
)

const pidPkg string = "./testdata/pid/"
const pidBinary string = "./testdata/pid/binary"

// testLogger implements the io.Writer interface to pipe process output to the
// testing log method, so it is printed only when a test fails.
type testLogger struct {
	t *testing.T
}

// Write pipes p to the testing log.
func (l testLogger) Write(p []byte) (n int, err error) {
	l.t.Log(string(p))
	return len(p), nil
}

var _ io.Writer = (*testLogger)(nil)

func TestMain(m *testing.M) {
	// Build testdata into binaries that we can test with
	env := os.Environ()
	env = append(env, "CGO_ENABLED=0", "GOOS=linux")
	cmd := exec.Command("go", "build", "-o", pidBinary, pidPkg)
	cmd.Env = env
	out, err := cmd.CombinedOutput()
	if err != nil {
		panic(string(out))
	}

	// Run test cases
	code := m.Run()

	// Cleanup
	os.Remove(pidBinary)

	os.Exit(code)
}
