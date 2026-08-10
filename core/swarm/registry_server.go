package swarm

import (
	"net"
	"net/netip"
	"os"

	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"github.com/rs/zerolog"
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
	log      zerolog.Logger
}

func NewRegistryServer(registry *Registry) *RegistryServer {
	return &RegistryServer{
		registry: registry,
		log:      zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
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
	if req.GetDaemonName() == "" {
		return status.Error(codes.InvalidArgument, "daemon name must not be empty")
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
	s.log.Info().
		Str("vehicle", req.GetName()).
		Str("daemon", req.GetDaemonName()).
		Str("addr", addr.String()).
		Msg("vehicle registered")
	defer func() {
		unregister()
		s.log.Info().Str("vehicle", req.GetName()).Msg("vehicle unregistered")
	}()

	if err := stream.Send(swarmpb.RegisterResponse_builder{}.Build()); err != nil {
		return err
	}

	<-stream.Context().Done()
	return nil
}
