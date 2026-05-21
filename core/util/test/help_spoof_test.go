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
		IP:   net.ParseIP(fakeIP),
		Port: 0,
	}
}

func newSpoofedListener(t *testing.T, l net.Listener) *spoofedListener {
	t.Helper()
	return &spoofedListener{
		Listener: l,
	}
}

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
