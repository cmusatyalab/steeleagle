package util

import (
	"fmt"
	"net"
	"sync"
)

// Embedded Address that holds the AuthCode
type Addr struct {
	net.Addr
	Code AuthCode
}

type Conn struct {
	net.Conn
	Addr *Addr
}

func (c *Conn) RemoteAddr() net.Addr { return c.Addr }

type listener struct {
	net.Listener
	code AuthCode
	// Connection for single-Connection socket pair listeners, if applicable
	socket net.Conn
	// ACL for checking incoming IP Addresses, if applicable
	acl *ACL
	// Synchronization members
	once sync.Once
	done chan struct{}
}

func NewListener(ln net.Listener, code AuthCode, acl *ACL) net.Listener {
	return &listener{
		Listener: ln,
		code:     code,
		acl:      acl,
	}
}

func NewSocketPairListener(sock net.Conn, code AuthCode) net.Listener {
	return &listener{
		socket: sock,
		code:   code,
		// Event signaling channel
		done: make(chan struct{}),
	}
}

func (l *listener) Accept() (net.Conn, error) {
	if l.socket != nil {
		return l.acceptSocketPair()
	} else {
		return l.acceptBase()
	}
}

func (l *listener) acceptBase() (net.Conn, error) {
	for {
		// Block until we get a Connection
		c, err := l.Listener.Accept()
		if err != nil {
			return nil, err
		}
		// If our access control list is set, check the incoming IP
		if l.acl != nil {
			if tc, ok := c.RemoteAddr().(*net.TCPAddr); ok {
				if !l.acl.Allows(tc.IP) {
					c.Close()
					continue
				}
			}
		}
		return &Conn{
			Conn: c,
			Addr: &Addr{Addr: c.RemoteAddr(), Code: l.code},
		}, nil
	}
}

func (l *listener) acceptSocketPair() (net.Conn, error) {
	var c net.Conn
	// Return the Connection exactly once to not spawn spurious handlers
	l.once.Do(func() { c = l.socket })
	if c != nil {
		return &Conn{
			Conn: c,
			Addr: &Addr{Addr: c.RemoteAddr(), Code: l.code},
		}, nil
	}
	// Wait until the socket closes, then exit
	<-l.done
	return nil, fmt.Errorf("listener closed")
}

func (l *listener) Close() error {
	if l.socket != nil {
		close(l.done)
		return l.socket.Close()
	}
	return l.Listener.Close()
}

func (l *listener) Addr() net.Addr {
	if l.socket != nil {
		return l.socket.LocalAddr()
	}
	return l.Listener.Addr()
}
