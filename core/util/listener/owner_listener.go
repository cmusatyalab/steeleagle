package listener

import (
	"fmt"
	"net"
	"os"
	"syscall"

	"github.com/rs/zerolog"
)

type ownerListener struct {
	net.Listener
	code AuthCode
	uid  uint32
	log  zerolog.Logger
}

// NewOwnerListener wraps a unix socket listener so that it only accepts
// connections from processes running as the same user as this one, or as
// root, tagging each with code. Other connections are closed. It is for
// sockets that stand in for their owner, such as a control socket for local
// tools, which can't be identified by PID.
func NewOwnerListener(ln net.Listener, code AuthCode, log zerolog.Logger) net.Listener {
	return &ownerListener{Listener: ln, code: code, uid: uint32(os.Getuid()), log: log}
}

// Accept waits for and returns the next connection from the owner, closing
// any from other users.
func (l *ownerListener) Accept() (net.Conn, error) {
	for {
		c, err := l.Listener.Accept()
		if err != nil {
			return nil, err
		}
		uid, err := peerUid(c)
		if err != nil {
			l.log.Error().Err(err).Msg("incoming connection refused, failed to get its user")
			c.Close()
			continue
		}
		if uid != l.uid && uid != 0 {
			l.log.Error().Uint32("uid", uid).Msg("incoming connection refused, not from the socket's owner")
			c.Close()
			continue
		}
		l.log.Debug().Uint32("uid", uid).Str("code", l.code.String()).Msg("new owner connection accepted")
		return &Conn{
			Conn: c,
			Addr: &Addr{Addr: c.RemoteAddr(), Code: l.code},
		}, nil
	}
}

// peerUid returns the user ID of the process at the other end of a unix
// socket connection.
func peerUid(c net.Conn) (uint32, error) {
	uc, ok := c.(*net.UnixConn)
	if !ok {
		return 0, fmt.Errorf("connection is not a unix socket")
	}
	raw, err := uc.SyscallConn()
	if err != nil {
		return 0, err
	}
	var cred *syscall.Ucred
	var credErr error
	if err := raw.Control(func(fd uintptr) {
		cred, credErr = syscall.GetsockoptUcred(int(fd), syscall.SOL_SOCKET, syscall.SO_PEERCRED)
	}); err != nil {
		return 0, err
	}
	if credErr != nil {
		return 0, credErr
	}
	return cred.Uid, nil
}
