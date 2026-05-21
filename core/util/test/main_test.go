package util_test

import (
	"os"
	"os/exec"
	"testing"
)

const binary string = "helper-binary"

func TestMain(m *testing.M) {
	// Build testdata/main.go into a plugin binary that we can test with
	out, err := exec.Command("go", "build", "-o", binary, "./mock_plugin").CombinedOutput()
	if err != nil {
		panic(string(out))
	}

	// Run test cases
	code := m.Run()

	// Cleanup
	os.Remove(binary)
	os.Exit(code)
}
