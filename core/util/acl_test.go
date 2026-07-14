package util_test

import (
	"net"
	"os"
	"os/exec"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
)

func TestACLIP(t *testing.T) {
	base, err := net.Listen("tcp", "127.0.0.1:8080")
	if err != nil {
		t.Errorf("couldn't listen on localhost port 8080")
	}
	defer base.Close()

	lis := newSpoofedListener(t, base)
	acl := util.GetACL([]string{"100.64.0.0/10", "10.5.2/10/2"}, []int{}) // add in a bogus ip to make sure it is ignored

	// Test adding bad and good IPs
	err = acl.AddIP("125.100.0.0/24")
	if err != nil {
		t.Errorf("couldn't add correct IP: %v", err)
	}
	err = acl.AddIP("130.100.0.0")
	if err != nil {
		t.Errorf("couldn't add correct IP: %v", err)
	}
	err = acl.AddIP("160.1/2/2")
	if err == nil {
		t.Errorf("added incorrect IP without error")
	}

	aclLn := util.NewCodedListener(lis, util.ServerCode, acl)
	defer aclLn.Close()

	accepted := make(chan net.Conn)
	go func() {
		for {
			conn, err := aclLn.Accept()
			if err != nil {
				return
			}
			accepted <- conn
		}
	}()

	// Rejected case, will be accepted and then closed
	lis.SetFakeIP("101.64.0.1")
	client1, _ := net.Dial("tcp", lis.Addr().String())
	if !isConnClosed(t, client1) {
		t.Errorf("connection 101.64.0.1 should have been rejected, but was accepted")
	}
	client1.Close()

	// Allowed case
	lis.SetFakeIP("100.120.16.5")
	client2, _ := net.Dial("tcp", lis.Addr().String())
	select {
	case conn := <-accepted:
		if isConnClosed(t, conn) {
			t.Errorf("allowed connection rejected incorrectly")
		}
		conn.Close()
	case <-time.After(1 * time.Second):
		t.Errorf("timed out waiting for allowed connection")
	}
	client2.Close()
}

func TestACLPID(t *testing.T) {
	base, err := net.Listen("unix", "/tmp/listener.sock")
	if err != nil {
		t.Errorf("couldn't listen on /tmp/listener.sock")
	}
	defer base.Close()

	acl := util.GetACL([]string{}, []int{})
	err = acl.AddPID(-1)
	if err == nil {
		t.Errorf("added incorrect pid")
	}
	aclLn := util.NewCodedListener(base, util.ServerCode, acl)
	defer aclLn.Close()
	go aclLn.Accept()

	cmd := exec.Command(pidBinary)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err == nil {
		t.Errorf("pid accepted incorrectly")
	}

	cmd = exec.Command(pidBinary)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Start()
	acl.AddPID(cmd.Process.Pid)
	if err != nil {
		t.Errorf("couldn't start command")
	}
	err = cmd.Wait()
	if err != nil {
		t.Errorf("pid rejected incorrectly")
	}
}
