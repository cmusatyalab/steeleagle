package swarm

import (
	"net"
	"net/netip"

	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// RegistryServer implements swarmpb.RegistryServiceServer, recording each
// vehicle's socket address in a Registry for the lifetime of its Register
// call.
type RegistryServer struct {
	swarmpb.UnimplementedRegistryServiceServer
	registry *Registry
}

func NewRegistryServer(registry *Registry) *RegistryServer {
	return &RegistryServer{registry: registry}
}

func (s *RegistryServer) Register(
	req *swarmpb.RegisterRequest,
	stream grpc.ServerStreamingServer[swarmpb.RegisterResponse],
) error {
	if req.GetName() == "" {
		return status.Error(codes.InvalidArgument, "name must not be empty")
	}
	if req.GetPort() == 0 || req.GetPort() > 65535 {
		return status.Errorf(codes.InvalidArgument, "port %d out of range", req.GetPort())
	}

	p, ok := peer.FromContext(stream.Context())
	if !ok {
		return status.Error(codes.Internal, "no peer information on connection")
	}
	tcpAddr, ok := p.Addr.(*net.TCPAddr)
	if !ok {
		return status.Errorf(codes.Internal, "unexpected peer address type %T", p.Addr)
	}
	addr := netip.AddrPortFrom(tcpAddr.AddrPort().Addr(), uint16(req.GetPort()))

	unregister := s.registry.Register(req.GetName(), addr)
	defer unregister()

	<-stream.Context().Done()
	return nil
}
