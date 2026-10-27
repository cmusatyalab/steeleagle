package daemon

import (
	"context"
	"net"
	"net/netip"
	"strings"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// orchestratorHost returns the orchestrator from the daemon config without
// its port, if it has one. The host may be a name or an IP address, including
// a bracketed ("[fd7a::1]:9000") or bare ("fd7a::1") IPv6 address.
func (d *Daemon) orchestratorHost() string {
	host := d.Config.Daemon.Orchestrator
	if h, _, err := net.SplitHostPort(host); err == nil {
		return h
	}
	return strings.TrimSuffix(strings.TrimPrefix(host, "["), "]")
}

// setLocalAddr sets the local address of the daemon on the current network.
// Over a VPN, this is the virtual address, otherwise the daemon probes a
// pre-configured endpoint to find its address, using 127.0.0.1 as a fallback.
func (d *Daemon) setLocalAddr() {
	remote := DefaultRouteProbe
	if d.Config.Daemon.Orchestrator != "" {
		if addrs, err := d.network.Resolve(d.ctx, d.orchestratorHost()); err == nil {
			remote = addrs[0]
		}
	}
	addr, err := d.network.LocalAddr(d.ctx, remote)
	if err != nil {
		d.log.Warn().Err(err).Msg("could not find daemon address, using loopback")
		d.netAddr = netip.AddrFrom4([4]byte{127, 0, 0, 1})
	} else {
		d.netAddr = addr
	}
}

// qualify returns name qualified with the daemon's address, as "{daemon
// IP}.{name}", so that it is unique across the network. An empty name, or
// any name before the daemon has an address, is returned as it is.
func (d *Daemon) qualify(name string) string {
	if name == "" || !d.netAddr.IsValid() {
		return name
	}
	return d.netAddr.String() + "." + name
}

// newCallerInterceptor returns a gRPC interceptor thatrecords the address of
// the caller in the call metadata, since the server only sees the router as
// its peer. Any caller address already in the metadata is replaced, so callers
// can't claim another address.
func newCallerInterceptor() grpc.StreamServerInterceptor {
	return func(
		srv any,
		ss grpc.ServerStream,
		info *grpc.StreamServerInfo,
		handler grpc.StreamHandler,
	) error {
		ctx := ss.Context()
		md, _ := metadata.FromIncomingContext(ctx)
		md = md.Copy()
		md.Delete(callerHeader)
		if p, ok := peer.FromContext(ctx); ok {
			addr := p.Addr
			if coded, ok := addr.(*listener.Addr); ok {
				addr = coded.Addr
			}
			md.Set(callerHeader, addr.String())
		}
		return handler(srv, &callerStream{ServerStream: ss, ctx: metadata.NewIncomingContext(ctx, md)})
	}
}

// callerStream is a server stream with the caller address in its metadata.
type callerStream struct {
	grpc.ServerStream
	ctx context.Context
}

// Context returns the stream context with the caller address in its metadata.
func (s *callerStream) Context() context.Context {
	return s.ctx
}

// callerIp returns the IP address of the caller of a daemon service, as
// recorded by the caller interceptor.
func callerIp(ctx context.Context) (string, error) {
	md, _ := metadata.FromIncomingContext(ctx)
	v := md.Get(callerHeader)
	if len(v) == 0 {
		return "", status.Error(codes.Internal, "no caller address in call")
	}
	ap, err := netip.ParseAddrPort(v[0])
	if err != nil {
		return "", status.Errorf(codes.InvalidArgument, "caller %s has no IP address", v[0])
	}
	return ap.Addr().Unmap().String(), nil
}
