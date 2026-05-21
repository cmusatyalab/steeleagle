package util_test

import (
	"context"
	"fmt"
	"net"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	health_pb "google.golang.org/grpc/health/grpc_health_v1"
)

// This code pairs the ack check in mock_plugin/main.go
func pluginRPCCheck(t *testing.T, ln net.Listener, conn *grpc.ClientConn) error {
	t.Helper()
	// Create notification channel for RPC calls
	done := make(chan struct{})
	notifyInt := func(
		ctx context.Context,
		req interface{},
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (interface{}, error) {
		close(done)
		return handler(ctx, req)
	}
	// Serve the health service
	server := grpc.NewServer(grpc.ChainUnaryInterceptor(notifyInt))
	defer server.GracefulStop()
	health_pb.RegisterHealthServer(server, health.NewServer())
	go server.Serve(ln)

	// Make a check request with a timeout
	client := health_pb.NewHealthClient(conn)
	ctx, _ := context.WithTimeout(context.Background(), time.Second)
	_, err := client.Check(ctx, &health_pb.HealthCheckRequest{}, grpc.WaitForReady(true))
	if err != nil {
		return err
	}

	// Wait to receive a request
	select {
	case <-done:
		return nil
	case <-time.After(time.Second):
		// Timeout
		return fmt.Errorf("expected rpc call, but none arrived")
	}
}
