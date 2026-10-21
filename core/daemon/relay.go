package daemon

import (
	"context"
	"net/netip"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// setupRelay creates the router, the relay and the server. The relay hosts
// no services itself; it checks every call against the policy and passes it
// to the router. The daemon's own services are hosted by the server, which is
// only reachable in process, and are service routes of the router.
func (d *Daemon) setupRelay() error {
	d.router = router.NewRouter(nil, nil, router.WithLogger(d.log))
	// Every call is a stream to the router, so only stream interceptors run
	d.relay = grpc.NewServer(
		grpc.ChainStreamInterceptor(d.policy.NewStreamPolicyInterceptor(), callerInterceptor),
		grpc.ForceServerCodec(router.RawCodec{}),
		grpc.UnknownServiceHandler(d.router.Handle),
	)

	d.server = grpc.NewServer()
	daemonpb.RegisterDaemonServiceServer(d.server, d)
	daemonpb.RegisterTransferServiceServer(d.server, d)
	d.serverLn = listener.NewLocalListener(listener.AdminCode)
	conn, err := grpc.NewClient(
		"passthrough:///local",
		grpc.WithContextDialer(d.serverLn.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return err
	}
	d.serverConn = conn
	d.router.AddServiceRoute(daemonpb.DaemonService_ServiceDesc.ServiceName, conn)
	d.router.AddServiceRoute(daemonpb.TransferService_ServiceDesc.ServiceName, conn)
	return nil
}

// callerInterceptor records the address of the caller in the call metadata,
// since the server only sees the router as its peer. Any caller address
// already in the metadata is replaced, so callers can't claim another address.
func callerInterceptor(
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
// recorded by callerInterceptor.
func callerIp(ctx context.Context) (netip.Addr, error) {
	md, _ := metadata.FromIncomingContext(ctx)
	v := md.Get(callerHeader)
	if len(v) == 0 {
		return netip.Addr{}, status.Error(codes.Internal, "no caller address in call")
	}
	ap, err := netip.ParseAddrPort(v[0])
	if err != nil {
		return netip.Addr{}, status.Errorf(codes.InvalidArgument, "caller %s has no IP address", v[0])
	}
	return ap.Addr().Unmap(), nil
}
