package util

import (
	"net"
    "syscall"
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

// RemoteAddr returns the remote address of the connection, including the embedded AuthCode.
func (c *Conn) RemoteAddr() net.Addr {
	return c.Addr
}

type codedListener struct {
	net.Listener
	code AuthCode
	acl  *ACL
}

// NewCodedListener wraps ln with AuthCode tagging and optional ACL enforcement.
// Every accepted connection is wrapped in a Conn whose RemoteAddr carries code.
// If acl is non-nil, connections that fail the ACL check are silently closed.
func NewCodedListener(ln net.Listener, code AuthCode, acl *ACL) net.Listener {
	return &codedListener{
		Listener: ln,
		code:     code,
		acl:      acl,
	}
}

// Accept waits for and returns the next connection, rejecting any that fail the ACL check.
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
				if !l.acl.AllowsIP(tc.IP) {
					c.Close()
					continue
				}
			}
            if uc, ok := c.(*net.UnixConn); ok {
			    raw, err := uc.SyscallConn()
			    if err != nil {
			    	c.Close()
			    	continue
			    }
			    var cred *syscall.Ucred
			    raw.Control(func(fd uintptr) {
			    	cred, err = syscall.GetsockoptUcred(int(fd), syscall.SOL_SOCKET, syscall.SO_PEERCRED)
			    })
			    if err != nil || !l.acl.AllowsPID(int(cred.Pid)) {
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
