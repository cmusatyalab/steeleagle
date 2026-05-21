package util

import (
	"net"
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

func (c *Conn) RemoteAddr() net.Addr {
	return c.Addr
}

type codedListener struct {
	net.Listener
	code AuthCode
	acl  *ACL
}

func NewCodedListener(ln net.Listener, code AuthCode, acl *ACL) net.Listener {
	return &codedListener{
		Listener: ln,
		code:     code,
		acl:      acl,
	}
}

func (l *codedListener) Accept() (net.Conn, error) {
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
