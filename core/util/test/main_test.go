package util_test

import (
	"os"
	"os/exec"
	"testing"
)

const binary string = "./mocks/go_test/binary"

func TestMain(m *testing.M) {
	// Build testdata/main.go into a plugin binary that we can test with
    env := os.Environ()
    env = append(env, "CGO_ENABLED=0", "GOOS=linux")
    cmd := exec.Command("go", "build", "-o", binary, "./mocks/go_test/")
    cmd.Env = env
	out, err := cmd.CombinedOutput()
	if err != nil {
		panic(string(out))
	}

	// Run test cases
	code := m.Run()

	// Cleanup
	os.Remove(binary)
	os.Exit(code)
}
