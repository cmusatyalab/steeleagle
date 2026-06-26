package util_test

import (
    "fmt"
    "os"
    "os/exec"
	"context"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestShimPlugin(t *testing.T) {
    acl := util.GetACL([]string{}, []int{})
    in := "/tmp/in.sock"
    out := "/tmp/out.sock"
	plugin, err := util.CreateShimPlugin(in, out, util.WithACL(acl))
	if err != nil {
		t.Fatalf("encountered error creating plugin: %v", err)
	}
    defer plugin.Stop()
    
    cmd := exec.CommandContext(context.Background(), goBinary)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(),
		fmt.Sprintf("%s=%s", util.ListenSockEnv, in),
		fmt.Sprintf("%s=%s", util.ClientSockEnv, out),
	)

    err = cmd.Start()
    if err != nil {
        t.Fatalf("couldn't start command: %v", err)
    }
    acl.AddPID(cmd.Process.Pid)
	ln, conn, err := plugin.Start(context.Background())
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
