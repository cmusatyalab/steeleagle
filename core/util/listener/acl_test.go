package listener

import (
	"net"
	"os"
	"os/exec"
	"testing"
	"time"
)

// TestAclIp ensures that invalid CIDRs are rejected, and that the coded
// listener only keeps connections from IPs inside the ACL's allowed ranges.
func TestAclIp(t *testing.T) {
	base, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("couldn't listen on localhost: %v", err)
	}
	defer base.Close()

	lis := newSpoofedListener(t, base)
	// Add in a bogus ip to make sure it is ignored
	acl := NewAcl(map[string]AuthCode{"100.64.0.0/10": ServerCode, "10.5.2/10/2": ServerCode}, nil, false)

	// Test adding bad and good IPs
	err = acl.AddIp("125.100.0.0/24", ServerCode)
	if err != nil {
		t.Errorf("couldn't add correct IP: %v", err)
	}
	err = acl.AddIp("130.100.0.0", ServerCode)
	if err != nil {
		t.Errorf("couldn't add correct IP: %v", err)
	}
	err = acl.AddIp("160.1/2/2", ServerCode)
	if err == nil {
		t.Errorf("added incorrect IP without error")
	}

	aclLn := newTestCodedListener(t, lis, acl)
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
		if code := conn.RemoteAddr().(*Addr).Code; code != ServerCode {
			t.Errorf("expected code %s, got %s", ServerCode, code)
		}
		conn.Close()
	case <-time.After(1 * time.Second):
		t.Errorf("timed out waiting for allowed connection")
	}
	client2.Close()
}

// TestAclPid ensures that invalid PIDs are rejected, and that the coded
// listener only accepts unix socket clients descended from an allowed PID.
func TestAclPid(t *testing.T) {
	const sockPath = "/tmp/listener.sock"
	os.Remove(sockPath)
	base, err := net.Listen("unix", sockPath)
	if err != nil {
		t.Fatalf("couldn't listen on %s: %v", sockPath, err)
	}
	defer base.Close()

	acl := NewAcl(nil, nil, false)
	err = acl.AddPid(-1, ServerCode)
	if err == nil {
		t.Errorf("added incorrect pid")
	}
	aclLn := newTestCodedListener(t, base, acl)
	defer aclLn.Close()
	go aclLn.Accept()

	logger := testLogger{t}
	cmd := exec.Command(pidBinary)
	cmd.Stdout = logger
	cmd.Stderr = logger
	err = cmd.Run()
	if err == nil {
		t.Errorf("pid accepted incorrectly")
	}

	cmd = exec.Command(pidBinary)
	cmd.Stdout = logger
	cmd.Stderr = logger
	err = cmd.Start()
	acl.AddPid(cmd.Process.Pid, ServerCode)
	if err != nil {
		t.Errorf("couldn't start command")
	}
	err = cmd.Wait()
	if err != nil {
		t.Errorf("pid rejected incorrectly")
	}
}

// TestAclCodes ensures that the ACL grants each IP and PID the AuthCode of its
// entry, picking the most specific CIDR and the nearest ancestor PID.
func TestAclCodes(t *testing.T) {
	acl := NewAcl(
		map[string]AuthCode{"100.64.0.0/10": ExternalCode, "100.100.0.0/16": MissionCode, "100.100.1.1": AdminCode},
		map[int]AuthCode{os.Getppid(): ServerCode, os.Getpid(): AdminCode},
		false,
	)

	ips := []struct {
		ip   string
		code AuthCode
	}{
		{"100.64.0.1", ExternalCode},
		{"100.100.5.5", MissionCode},
		{"100.100.1.1", AdminCode},
	}
	for _, tt := range ips {
		allowed, code := acl.AllowsIp(net.ParseIP(tt.ip))
		if !allowed || code != tt.code {
			t.Errorf("%s: expected (true, %s), got (%v, %s)", tt.ip, tt.code, allowed, code)
		}
	}

	// This process is on the ACL and is nearer than its parent
	if allowed, code := acl.AllowsPid(os.Getpid()); !allowed || code != AdminCode {
		t.Errorf("expected own pid to get (true, %s), got (%v, %s)", AdminCode, allowed, code)
	}
	if allowed, code := acl.AllowsPid(os.Getppid()); !allowed || code != ServerCode {
		t.Errorf("expected parent pid to get (true, %s), got (%v, %s)", ServerCode, allowed, code)
	}
}

// TestAclOpenClosed ensures that clients not on the ACL are denied by a
// closed ACL and granted ExternalCode by an open one.
func TestAclOpenClosed(t *testing.T) {
	cidrs := map[string]AuthCode{"100.64.0.0/10": AdminCode}
	closed := NewAcl(cidrs, nil, false)
	open := NewAcl(cidrs, nil, true)
	unlisted := net.ParseIP("10.0.0.1")

	if allowed, _ := closed.AllowsIp(unlisted); allowed {
		t.Errorf("closed acl allowed unlisted ip")
	}
	if allowed, _ := closed.AllowsPid(os.Getpid()); allowed {
		t.Errorf("closed acl allowed unlisted pid")
	}
	if allowed, _ := closed.AllowsUnlisted(); allowed {
		t.Errorf("closed acl allowed unidentified client")
	}
	if allowed, code := open.AllowsIp(unlisted); !allowed || code != ExternalCode {
		t.Errorf("open acl expected (true, %s) for unlisted ip, got (%v, %s)", ExternalCode, allowed, code)
	}
	if allowed, code := open.AllowsPid(os.Getpid()); !allowed || code != ExternalCode {
		t.Errorf("open acl expected (true, %s) for unlisted pid, got (%v, %s)", ExternalCode, allowed, code)
	}
	if allowed, code := open.AllowsUnlisted(); !allowed || code != ExternalCode {
		t.Errorf("open acl expected (true, %s) for unidentified client, got (%v, %s)", ExternalCode, allowed, code)
	}
	// Listed entries keep their own code on an open ACL
	if allowed, code := open.AllowsIp(net.ParseIP("100.64.0.1")); !allowed || code != AdminCode {
		t.Errorf("open acl expected (true, %s) for listed ip, got (%v, %s)", AdminCode, allowed, code)
	}
}
