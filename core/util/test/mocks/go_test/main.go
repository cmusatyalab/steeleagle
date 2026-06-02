package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	health_pb "google.golang.org/grpc/health/grpc_health_v1"
)

func run() error {
	// Know that FD3 is the server file, FD4 is the client file
	lnFile := os.NewFile(3, "listener-file")
	clientFile := os.NewFile(4, "client-file")
	ln, conn, err := util.CreateSocketPairEndpoints(util.AdminCode, lnFile, clientFile)
	if err != nil {
		return err
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

	// Wait to receive a request, then send another as an ack
	select {
	case <-done:
		client := health_pb.NewHealthClient(conn)
		_, err = client.Check(context.Background(), &health_pb.HealthCheckRequest{})
		if err != nil {
			return err
		}
		return nil
	case <-time.After(time.Second):
		// Timeout
		return fmt.Errorf("expected rpc call, but none arrived")
	}
}

func main() {
	errPtr := flag.Bool("error", false, "produce an error")
	flag.Parse()

	if *errPtr {
		fmt.Println("asked to exit with error")
		os.Exit(1)
	}

	if err := run(); err != nil {
		fmt.Printf("got the following error %v", err)
		os.Exit(1)
	}
}
