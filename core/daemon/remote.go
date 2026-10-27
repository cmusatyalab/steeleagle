package daemon

import (
	"context"
	"maps"
	"net"
	"slices"
	"strconv"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// addRemote adds a child daemon at ip, running on os and arch, which
// registered with this daemon as its orchestrator and is dialed at port,
// replacing any earlier registration from the same IP. The child's IP
// and each of its services become header routes to it.
func (d *Daemon) addRemote(
	ip, hostname, os, arch string,
	port int32,
	services []*daemonService,
) (*childInfo, error) {
	conn, err := grpc.NewClient(
		"passthrough:///"+net.JoinHostPort(ip, strconv.Itoa(int(port))),
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return d.network.Dial(ctx, "tcp", addr)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, err
	}
	child := &childInfo{
		ip:       ip,
		hostname: hostname,
		os:       os,
		arch:     arch,
		conn:     conn,
		services: services,
	}
	d.remMu.Lock()
	defer d.remMu.Unlock()
	if old, ok := d.remotes[ip]; ok {
		d.closeRemote(old)
	}
	d.remotes[ip] = child
	d.router.AddHeaderRoute(ip, conn)
	for _, s := range services {
		d.router.AddHeaderRoute(s.name, conn)
	}
	return child, nil
}

// removeRemote removes a child daemon, unless it has already been replaced by
// a newer registration from the same IP.
func (d *Daemon) removeRemote(child *childInfo) {
	d.remMu.Lock()
	defer d.remMu.Unlock()
	if d.remotes[child.ip] != child {
		return
	}
	delete(d.remotes, child.ip)
	d.closeRemote(child)
}

// closeRemotes removes all child daemons.
func (d *Daemon) closeRemotes() {
	d.remMu.Lock()
	defer d.remMu.Unlock()
	for ip, child := range d.remotes {
		delete(d.remotes, ip)
		d.closeRemote(child)
	}
}

// closeRemote removes the routes to a child daemon and closes its connection.
// The caller must hold remMu.
func (d *Daemon) closeRemote(child *childInfo) {
	d.router.RemoveHeaderRoute(child.ip)
	for _, s := range child.services {
		d.router.RemoveHeaderRoute(s.name)
	}
	child.conn.Close()
}

// listRemotes returns the child daemons, in the order of their IPs.
func (d *Daemon) listRemotes() []*childInfo {
	d.remMu.RLock()
	defer d.remMu.RUnlock()
	children := make([]*childInfo, 0, len(d.remotes))
	for _, ip := range slices.Sorted(maps.Keys(d.remotes)) {
		children = append(children, d.remotes[ip])
	}
	return children
}

// remoteFor returns the child daemon hosting the named service, or nil if no
// child does.
func (d *Daemon) remoteFor(name string) *childInfo {
	d.remMu.RLock()
	defer d.remMu.RUnlock()
	for _, child := range d.remotes {
		for _, s := range child.services {
			if s.name == name {
				return child
			}
		}
	}
	return nil
}

// receive reads messages from recv on its own goroutine until it fails or ctx
// is done, so that they can be waited for with a timeout. The error recv
// fails with is sent on the error channel.
func receive[T any](ctx context.Context, recv func() (T, error)) (<-chan T, <-chan error) {
	msgs := make(chan T)
	errs := make(chan error, 1)
	go func() {
		for {
			msg, err := recv()
			if err != nil {
				errs <- err
				return
			}
			select {
			case msgs <- msg:
			case <-ctx.Done():
				return
			}
		}
	}()
	return msgs, errs
}
