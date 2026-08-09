package util_test

import (
	"fmt"
	"os"
	"os/exec"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestShimPlugin(t *testing.T) {
	acl := util.GetACL([]string{}, []int{})
	in := "/tmp/in.sock"
	out := "/tmp/out.sock"
	plugin, err := CreateShimPlugin(t,
		in,
		out,
		util.WithACL(acl),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}

	logger := testLogger{t}
	cmd := exec.CommandContext(t.Context(), goBinary)
	cmd.Stdout = logger
	cmd.Stderr = logger
	cmd.Env = append(os.Environ(),
		fmt.Sprintf("%s=%s", util.ListenSockEnv, in),
		fmt.Sprintf("%s=%s", util.ClientSockEnv, out),
	)

	err = cmd.Start()
	if err != nil {
		t.Fatalf("couldn't start command: %v", err)
	}
	// Wait, not just the context cancellation on return, blocks until the
	// process exits *and* the goroutines Start spun up to copy its
	// stdout/stderr into logger have finished -- without it, one of those
	// goroutines can still call t.Log after this test function has already
	// returned, which panics ("Log in goroutine after Test has completed").
	defer cmd.Wait()
	acl.AddPID(cmd.Process.Pid)
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, util.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}

	os.Remove(in)
	os.Remove(out)
}
