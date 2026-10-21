package listener

import (
	"context"
	"fmt"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/peer"
)

// TestLocalListener ensures that the local listener tags in-process gRPC
// connections with its AuthCode, so that interceptors can read it from the
// peer address.
func TestLocalListener(t *testing.T) {
	ln := NewLocalListener(AdminCode)
	defer ln.Close()

	conn, err := grpc.NewClient(
		"passthrough:///local",
		grpc.WithContextDialer(ln.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("failed to create new client: %v", err)
	}
	defer conn.Close()

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
		if a.Code != AdminCode {
			return nil, fmt.Errorf("cannot call this RPC without code: admin")
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
