package plugin

import (
	"fmt"
	"os"
	"os/exec"
	"testing"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
)

// TestShimPlugin ensures that a shim plugin can connect to an externally
// started process and complete an RPC handshake with it.
func TestShimPlugin(t *testing.T) {
	acl := listener.GetAcl([]string{}, []int{})
	in := "/tmp/in.sock"
	out := "/tmp/out.sock"
	plugin, err := newTestShimPlugin(t,
		in,
		out,
		WithAcl(acl),
	)
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}

	logger := testLogger{t}
	cmd := exec.CommandContext(t.Context(), goBinary)
	cmd.Stdout = logger
	cmd.Stderr = logger
	cmd.Env = append(os.Environ(),
		fmt.Sprintf("%s=%s", ListenSockEnv, in),
		fmt.Sprintf("%s=%s", ClientSockEnv, out),
	)

	err = cmd.Start()
	if err != nil {
		t.Fatalf("couldn't start command: %v", err)
	}
	defer cmd.Wait()
	acl.AddPid(cmd.Process.Pid)
	ln, conn, err := plugin.Start(t.Context())
	if err != nil {
		t.Fatalf("encountered error spawning plugin: %v", err)
	}

	err = pluginRPCCheck(t, ln, conn, listener.UnknownCode)
	if err != nil {
		t.Errorf("encountered error with plugin RPC handshake: %v", err)
	}

	os.Remove(in)
	os.Remove(out)
}
