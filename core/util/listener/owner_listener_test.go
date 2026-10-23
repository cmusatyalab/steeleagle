package listener

import (
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/rs/zerolog"
)

// listenOwnerSocket returns an owner listener with code on a fresh unix
// socket, and the socket's path.
func listenOwnerSocket(t *testing.T, code AuthCode) (*ownerListener, string) {
	t.Helper()
	// Unix socket paths are limited in length, which t.TempDir can exceed
	dir, err := os.MkdirTemp("", "owner")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	path := filepath.Join(dir, "owner.sock")
	ln, err := net.Listen("unix", path)
	if err != nil {
		t.Fatal(err)
	}
	owner := NewOwnerListener(ln, code, zerolog.Nop()).(*ownerListener)
	t.Cleanup(func() { owner.Close() })
	return owner, path
}

// TestOwnerListenerTagsOwner ensures that a connection from the socket's
// owner is accepted and tagged with the listener's code.
func TestOwnerListenerTagsOwner(t *testing.T) {
	ln, path := listenOwnerSocket(t, PrivilegedCode)
	client, err := net.Dial("unix", path)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()

	c, err := ln.Accept()
	if err != nil {
		t.Fatalf("Accept() = %v", err)
	}
	defer c.Close()
	addr, ok := c.RemoteAddr().(*Addr)
	if !ok || addr.Code != PrivilegedCode {
		t.Errorf("RemoteAddr() = %v, want one with PrivilegedCode", c.RemoteAddr())
	}
}

// TestOwnerListenerRefusesOthers ensures that a connection from another user
// is closed rather than accepted.
func TestOwnerListenerRefusesOthers(t *testing.T) {
	if os.Getuid() == 0 {
		t.Skip("root is always accepted")
	}
	ln, path := listenOwnerSocket(t, PrivilegedCode)
	ln.uid = uint32(os.Getuid()) + 1 // as if the socket were another user's

	accepted := make(chan net.Conn, 1)
	go func() {
		if c, err := ln.Accept(); err == nil {
			accepted <- c
		}
	}()
	client, err := net.Dial("unix", path)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()

	// The refused connection is closed, so reading from it ends
	client.SetReadDeadline(time.Now().Add(5 * time.Second))
	if _, err := client.Read(make([]byte, 1)); err == nil || os.IsTimeout(err) {
		t.Errorf("Read() on a refused connection = %v, want it closed", err)
	}
	select {
	case c := <-accepted:
		c.Close()
		t.Error("connection from another user was accepted")
	default:
	}
}
