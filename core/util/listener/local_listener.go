package listener

import (
	"context"
	"net"

	"google.golang.org/grpc/test/bufconn"
)

// localBufferSize is the size of the in-memory buffer for each local connection.
const localBufferSize = 1024 * 1024

// LocalListener is an in-memory listener that is only reachable from within
// this process, through Dial. It has no socket file or descriptor that another
// process could connect to, so it needs no Acl; every accepted connection is
// tagged with the listener's AuthCode.
type LocalListener struct {
	*bufconn.Listener
	code AuthCode
}

// NewLocalListener creates a LocalListener whose connections carry code.
func NewLocalListener(code AuthCode) *LocalListener {
	return &LocalListener{
		Listener: bufconn.Listen(localBufferSize),
		code:     code,
	}
}

// Accept waits for and returns the next connection, tagged with the
// listener's AuthCode.
func (l *LocalListener) Accept() (net.Conn, error) {
	c, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	return &Conn{
		Conn: c,
		Addr: &Addr{Addr: c.RemoteAddr(), Code: l.code},
	}, nil
}

// Dial opens a connection to the listener. Its signature matches
// grpc.WithContextDialer, so a gRPC client can connect with
// grpc.NewClient("passthrough:///local", grpc.WithContextDialer(l.Dial), ...).
func (l *LocalListener) Dial(ctx context.Context, _ string) (net.Conn, error) {
	return l.Listener.DialContext(ctx)
}
