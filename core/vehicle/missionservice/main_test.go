package main

import (
	"os"
	"os/exec"
	"testing"
)

const mockMissionPkg = "./mocks/mission/"
const mockMissionBinary = "./mocks/mission/binary"

func TestMain(m *testing.M) {
	cmd := exec.Command("go", "build", "-o", mockMissionBinary, mockMissionPkg)
	if out, err := cmd.CombinedOutput(); err != nil {
		panic(string(out))
	}

	code := m.Run()

	os.Remove(mockMissionBinary)
	os.Exit(code)
}
