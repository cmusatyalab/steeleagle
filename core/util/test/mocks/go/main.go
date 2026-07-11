package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	health_pb "google.golang.org/grpc/health/grpc_health_v1"
)

// run establishes the gRPC server and client sockets, serves a health check,
// and sends an acknowledgement Check back to the test harness.
func run() error {
	// Know that FD3 is the server file, FD4 is the client file
	listenSocket := os.Getenv("LISTEN_SOCKET")
	clientSocket := os.Getenv("CLIENT_SOCKET")
	if listenSocket == "" || clientSocket == "" {
		return fmt.Errorf("LISTEN_SOCKET and CLIENT_SOCKET environment variables must be set")
	}

	// Create the connections
	ln, err := net.Listen("unix", listenSocket)
	if err != nil {
		return fmt.Errorf("failed to listen on %s: %w", listenSocket, err)
	}
	conn, err := grpc.NewClient("unix://"+clientSocket, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return fmt.Errorf("failed to create new client %s: %w", clientSocket, err)
	}

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
	fmt.Println("go_test: starting server")

	// Wait to receive a request, then send another as an ack
	select {
	case <-done:
		client := health_pb.NewHealthClient(conn)
		_, err = client.Check(context.Background(), &health_pb.HealthCheckRequest{})
		if err != nil {
			return err
		}
		fmt.Println("go_test: client check succeeded")
		return nil
	case <-time.After(time.Second * 15):
		// Timeout
		return fmt.Errorf("expected rpc call, but none arrived")
	}
}

// main parses the --error flag and delegates to run.
func main() {
	errPtr := flag.Bool("error", false, "produce an error")
	flag.Parse()

	// Delay is necessary for several tests
	time.Sleep(100 * time.Millisecond)

	if *errPtr {
		fmt.Println("go_test: asked to exit with error")
		os.Exit(1)
	}

	if err := run(); err != nil {
		fmt.Printf("go_test: got the following error %v\n", err)
		os.Exit(1)
	}
}
