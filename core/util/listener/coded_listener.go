package listener

import (
	"net"
	"os"
	"syscall"

	"github.com/rs/zerolog"
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
	acl  *Acl
	log  zerolog.Logger
}

// NewCodedListener wraps ln with AuthCode tagging and optional ACL enforcement.
// Every accepted connection is wrapped in a Conn whose RemoteAddr carries code.
// If acl is non-nil, connections that fail the ACL check are silently closed.
func NewCodedListener(ln net.Listener, code AuthCode, acl *Acl, opts ...ListenerOption) net.Listener {
	l := &codedListener{
		Listener: ln,
		code:     code,
		acl:      acl,
		log:      zerolog.New(os.Stdout).With().Timestamp().Logger(),
	}
	for _, opt := range opts {
		opt(l)
	}
	return l
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
				if !l.acl.AllowsIp(tc.IP) {
					l.log.Error().Str("ip", tc.IP.String()).Msg("incoming connection refused, denied by acl")
					c.Close()
					continue
				}
			}
			if uc, ok := c.(*net.UnixConn); ok {
				raw, err := uc.SyscallConn()
				if err != nil {
					l.log.Error().Err(err).Msg("incoming connection refused, failed to read as unix socket")
					c.Close()
					continue
				}
				var cred *syscall.Ucred
				raw.Control(func(fd uintptr) {
					cred, err = syscall.GetsockoptUcred(int(fd), syscall.SOL_SOCKET, syscall.SO_PEERCRED)
				})
				if err != nil {
					l.log.Error().Err(err).Msg("incoming connection refused, failed to get pid")
					c.Close()
					continue
				} else if !l.acl.AllowsPid(int(cred.Pid)) {
					l.log.Error().Int("pid", int(cred.Pid)).Msg("incoming connection refused, denied by acl")
					c.Close()
					continue
				}
			}
		}
		l.log.Info().Str("code", l.code.String()).Msg("new connection accepted")
		return &Conn{
			Conn: c,
			Addr: &Addr{Addr: c.RemoteAddr(), Code: l.code},
		}, nil
	}
}
