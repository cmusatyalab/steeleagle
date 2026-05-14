package util_test

import (
	"net"
	"testing"
)

type spoofedConn struct {
	net.Conn
	remoteAddr net.Addr
}

func (c *spoofedConn) RemoteAddr() net.Addr {
	return c.remoteAddr
}

type spoofedListener struct {
	net.Listener
	fakeAddr net.Addr
}

func (l *spoofedListener) Accept() (net.Conn, error) {
	conn, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	return &spoofedConn{Conn: conn, remoteAddr: l.fakeAddr}, nil
}

func (l *spoofedListener) SetFakeIP(fakeIP string) {
    l.fakeAddr = &net.TCPAddr{
        IP: net.ParseIP(fakeIP),
        Port: 0,
    }
}

func newSpoofedListener(t *testing.T) net.Listener {
	t.Helper()
	inner, err := net.Listen("tcp", "127.0.0.1:50051")
	if err != nil {
		t.Fatalf("failed to create listener: %v", err)
	}
	return &spoofedListener{
		Listener: inner,
	}
}
