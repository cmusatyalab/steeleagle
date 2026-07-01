package util_test

import (
	"net"
	"testing"
	"time"
)

type spoofedConn struct {
	net.Conn
	remoteAddr net.Addr
}

// RemoteAddr returns the spoofed remote address.
func (c *spoofedConn) RemoteAddr() net.Addr {
	return c.remoteAddr
}

type spoofedListener struct {
	net.Listener
	fakeAddr net.Addr
}

// Accept returns the next connection with its remote address replaced by fakeAddr.
func (l *spoofedListener) Accept() (net.Conn, error) {
	conn, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	return &spoofedConn{Conn: conn, remoteAddr: l.fakeAddr}, nil
}

// SetFakeIP sets the IP address that will be reported as the remote address for all accepted connections.
func (l *spoofedListener) SetFakeIP(fakeIP string) {
	l.fakeAddr = &net.TCPAddr{
		IP:   net.ParseIP(fakeIP),
		Port: 0,
	}
}

// newSpoofedListener wraps l in a spoofedListener for use in tests.
func newSpoofedListener(t *testing.T, l net.Listener) *spoofedListener {
	t.Helper()
	return &spoofedListener{
		Listener: l,
	}
}

// isConnClosed reports whether conn has been closed by attempting a read with a short deadline.
func isConnClosed(t *testing.T, conn net.Conn) bool {
	t.Helper()
	if conn == nil {
		return true
	}
	conn.SetReadDeadline(time.Now().Add(200 * time.Millisecond))
	_, err := conn.Read(make([]byte, 1))
	if err == nil {
		return false
	}
	if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
		return false
	}
	return true
}
