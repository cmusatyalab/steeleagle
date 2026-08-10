package swarm

import (
	"context"
	"fmt"
	"net"
	"net/netip"
	"sync"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// pooledConn represents a single vehicle gRPC connection.
type pooledConn struct {
	addr netip.AddrPort   // socket address
	conn *grpc.ClientConn // gRPC client connection
}

// connPool caches one gRPC connection per vehicle name, reused across calls.
// A cached connection is redialed only when the vehicle's registered socket
// address changes.
type connPool struct {
	mu     sync.Mutex
	conns  map[string]pooledConn                                             // pooled vehicle client connections, keyed by vehicle name
	dialer func(ctx context.Context, network, addr string) (net.Conn, error) // nil uses the default network stack
	log    zerolog.Logger
}

// newConnPool creates a new connection pool.
func newConnPool(log zerolog.Logger) *connPool {
	return &connPool{conns: make(map[string]pooledConn), log: log}
}

// get returns the cached gRPC client connection for a vehicle, creating a new
// connection if the provided vehicle socket address does not match that of the
// cached connection.
func (p *connPool) get(name string, addr netip.AddrPort) (*grpc.ClientConn, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if pc, ok := p.conns[name]; ok {
		if pc.addr == addr {
			return pc.conn, nil
		}
		p.log.Info().Str("vehicle", name).Str("old_addr", pc.addr.String()).Str("new_addr", addr.String()).
			Msg("vehicle address changed, reconnecting")
		pc.conn.Close()
		delete(p.conns, name)
	}

	dialOpts := []grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}
	if p.dialer != nil {
		dialer := p.dialer
		dialOpts = append(dialOpts, grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return dialer(ctx, "tcp", addr)
		}))
	}

	conn, err := grpc.NewClient(addr.String(), dialOpts...)
	if err != nil {
		p.log.Error().Str("vehicle", name).Str("addr", addr.String()).Err(err).Msg("dialing vehicle failed")
		return nil, fmt.Errorf("dialing %s: %w", addr, err)
	}
	p.log.Debug().Str("vehicle", name).Str("addr", addr.String()).Msg("pooled new connection for vehicle")
	p.conns[name] = pooledConn{addr: addr, conn: conn}
	return conn, nil
}

// close closes every pooled connection.
func (p *connPool) close() {
	p.mu.Lock()
	defer p.mu.Unlock()
	for name, pc := range p.conns {
		pc.conn.Close()
		delete(p.conns, name)
	}
}
