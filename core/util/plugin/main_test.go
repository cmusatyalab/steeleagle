package plugin

import (
	"os"
	"os/exec"
	"testing"
)

const goPkg string = "./testdata/go/"
const goBinary string = "./testdata/go/binary"
const pyPkg string = "./testdata/py/"
const pyFile string = "./testdata/py/main.py"
const fileMain string = "./testdata/file/main.py"
const fileRead string = "./testdata/file/read.txt"
const fileWrite string = "./testdata/file/write.txt"

func TestMain(m *testing.M) {
	// Build testdata into plugin binaries that we can test with
	env := os.Environ()
	env = append(env, "CGO_ENABLED=0", "GOOS=linux")
	cmd := exec.Command("go", "build", "-o", goBinary, goPkg)
	cmd.Env = env
	out, err := cmd.CombinedOutput()
	if err != nil {
		panic(string(out))
	}

	// Run test cases
	code := m.Run()

	// Cleanup
	os.Remove(goBinary)

	os.Exit(code)
}
