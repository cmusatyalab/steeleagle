package util_test

import (
	"os"
	"os/exec"
	"testing"
)

const goPkg string = "./mocks/go/"
const goBinary string = "./mocks/go/binary"
const pidPkg string = "./mocks/pid/"
const pidBinary string = "./mocks/pid/binary"
const pyPkg string = "./mocks/py/"
const pyFile string = "./mocks/py/main.py"
const fileMain string = "./mocks/file/main.py"
const fileRead string = "./mocks/file/read.txt"
const fileWrite string = "./mocks/file/write.txt"

func TestMain(m *testing.M) {
	// Build mocks into plugin binaries that we can test with
	env := os.Environ()
	env = append(env, "CGO_ENABLED=0", "GOOS=linux")
	cmd := exec.Command("go", "build", "-o", goBinary, goPkg)
	cmd.Env = env
	out, err := cmd.CombinedOutput()
	if err != nil {
		panic(string(out))
	}
	cmd = exec.Command("go", "build", "-o", pidBinary, pidPkg)
	cmd.Env = env
	out, err = cmd.CombinedOutput()
	if err != nil {
		panic(string(out))
	}

	// Run test cases
	code := m.Run()

	// Cleanup
	os.Remove(goBinary)
	os.Remove(pidBinary)
	
    os.Exit(code)
}
