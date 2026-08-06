package swarm

import (
	"fmt"
	"net/netip"
	"sync"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// connPool caches one gRPC connection per vehicle name, reused across calls.
// A cached connection is redialed only when the vehicle's registered socket
// address changes.
type connPool struct {
	mu    sync.Mutex
	conns map[string]pooledConn
}

type pooledConn struct {
	addr netip.AddrPort   // socket address
	conn *grpc.ClientConn // gRPC client connection
}

func newConnPool() *connPool {
	return &connPool{conns: make(map[string]pooledConn)}
}

func (p *connPool) get(name string, addr netip.AddrPort) (*grpc.ClientConn, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if pc, ok := p.conns[name]; ok {
		if pc.addr == addr {
			return pc.conn, nil
		}
		pc.conn.Close()
		delete(p.conns, name)
	}

	conn, err := grpc.NewClient(addr.String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("dialing %s: %w", addr, err)
	}
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
