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
	acl *Acl
	log zerolog.Logger
}

// NewCodedListener wraps ln with AuthCode tagging and ACL enforcement. Every
// accepted connection is wrapped in a Conn whose RemoteAddr carries the
// AuthCode the ACL grants it; connections the ACL denies are closed. A nil acl
// is an open ACL with no entries, granting every connection ExternalCode.
func NewCodedListener(ln net.Listener, acl *Acl, opts ...ListenerOption) net.Listener {
	if acl == nil {
		acl = NewAcl(nil, nil, true)
	}
	l := &codedListener{
		Listener: ln,
		acl:      acl,
		log:      zerolog.New(os.Stdout).With().Timestamp().Logger(),
	}
	for _, opt := range opts {
		opt(l)
	}
	return l
}

// Accept waits for and returns the next connection, rejecting any that fail the
// ACL check.
func (l *codedListener) Accept() (net.Conn, error) {
	for {
		// Block until we get a Connection
		c, err := l.Listener.Accept()
		if err != nil {
			return nil, err
		}
		// Identify the client by IP or PID and look up its AuthCode
		var allowed bool
		var code AuthCode
		if tc, ok := c.RemoteAddr().(*net.TCPAddr); ok {
			allowed, code = l.acl.AllowsIp(tc.IP)
			if !allowed {
				l.log.Error().Str("ip", tc.IP.String()).Msg("incoming connection refused, denied by acl")
				c.Close()
				continue
			}
		} else if uc, ok := c.(*net.UnixConn); ok {
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
			}
			allowed, code = l.acl.AllowsPid(int(cred.Pid))
			if !allowed {
				l.log.Error().Int("pid", int(cred.Pid)).Msg("incoming connection refused, denied by acl")
				c.Close()
				continue
			}
		} else {
			// The client can't be identified, so treat it as unlisted
			allowed, code = l.acl.AllowsUnlisted()
			if !allowed {
				l.log.Error().Msg("incoming connection refused, acl can't check its address")
				c.Close()
				continue
			}
		}
		l.log.Info().Str("code", code.String()).Msg("new connection accepted")
		return &Conn{
			Conn: c,
			Addr: &Addr{Addr: c.RemoteAddr(), Code: code},
		}, nil
	}
}
