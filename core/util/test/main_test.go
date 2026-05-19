package util_test

import (
    "testing"
    "os"
    "os/exec"
)

var binary string

func TestMain(m *testing.Main) {
    bin, err := os.CreateTemp("", "binary-*")
    if err != nil {
        panic(err)
    }
    bin.Close()
    binary = bin.Name()

    // Build testdata/main.go into a plugin binary that we can test with
    out, err := exec.Command("go", "build", "-o", binary, "./testdata").CombinedOutput()
    if err != nil {
        panic(string(out))
    }

    // Run test cases
    code := m.Run()

    // Cleanup
    os.Remove(binary)
    os.Exit(code)
}
