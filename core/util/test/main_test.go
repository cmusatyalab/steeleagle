package util_test

import (
	"os"
	"os/exec"
	"testing"
)

const go_pkg string = "./mocks/go_test/"
const go_binary string = "./mocks/go_test/binary"
const py_pkg string = "./mocks/py_test/"

func TestMain(m *testing.M) {
	// Build testdata/main.go into a plugin binary that we can test with
	env := os.Environ()
	env = append(env, "CGO_ENABLED=0", "GOOS=linux")
	cmd := exec.Command("go", "build", "-o", go_binary, "./mocks/go_test/")
	cmd.Env = env
	out, err := cmd.CombinedOutput()
	if err != nil {
		panic(string(out))
	}

	// TODO create package in the normal search path and remove it after

	// Run test cases
	code := m.Run()

	// Cleanup
	os.Remove(go_binary)
	// TODO remove error binary
	os.Exit(code)
}
