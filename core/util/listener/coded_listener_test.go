package listener

import (
	"context"
	"fmt"
	"net"
	"os"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/peer"
)

// TestAuthCode ensures that the coded listener tags connections with its
// AuthCode, so that gRPC interceptors can read it from the peer address.
func TestAuthCode(t *testing.T) {
	sock, err := net.Listen("unix", "/tmp/listener.sock")
	if err != nil {
		t.Fatalf("failed to listen: %v", err)
	}
	ln := newTestCodedListener(t, sock, MissionCode, GetAcl([]string{}, []int{os.Getpid()}))

	conn, err := grpc.NewClient("unix:///tmp/listener.sock", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatalf("failed to create new client: %v", err)
	}
	defer os.Remove("/tmp/listener.sock")

	// Define a mock auth interceptor
	authInt := func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
		p, ok := peer.FromContext(ctx)
		if !ok {
			return nil, fmt.Errorf("couldn't get peer from context")
		}
		a, ok := p.Addr.(*Addr)
		if !ok {
			return nil, fmt.Errorf("couldn't get auth code from peer")
		}
		if a.Code != MissionCode {
			return nil, fmt.Errorf("cannot call this RPC without code: mission")
		}
		return handler(ctx, req)
	}

	server := grpc.NewServer(grpc.ChainUnaryInterceptor(authInt))
	defer server.GracefulStop()
	healthpb.RegisterHealthServer(server, health.NewServer())
	go server.Serve(ln)

	client := healthpb.NewHealthClient(conn)
	_, err = client.Check(t.Context(), &healthpb.HealthCheckRequest{})
	if err != nil {
		t.Errorf("rpc failed when it was expected to succeed: %v", err)
	}
}
