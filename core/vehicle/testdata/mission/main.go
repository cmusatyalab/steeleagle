// Command mission is a test mission for vehicle tests. It serves the gRPC
// health service on its listen socket until it is killed. Copied to a file
// named "callback", it instead calls the vehicle's DataService through its
// client socket, which the vehicle's law allows a running mission, and exits
// successfully if the call succeeds.
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"time"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
)

func run() error {
	// The plugin waits for the listen socket before it is started
	ln, err := net.Listen("unix", os.Getenv("STEELEAGLE_LISTEN_SOCKET"))
	if err != nil {
		return err
	}
	server := grpc.NewServer()
	healthpb.RegisterHealthServer(server, health.NewServer())
	if filepath.Base(os.Args[0]) != "callback" {
		return server.Serve(ln)
	}
	go server.Serve(ln)
	conn, err := grpc.NewClient("unix://"+os.Getenv("STEELEAGLE_CLIENT_SOCKET"),
		grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer conn.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err = vehiclepb.NewDataServiceClient(conn).GetFlow(ctx, &vehiclepb.GetFlowRequest{}, grpc.WaitForReady(true))
	return err
}

func main() {
	if err := run(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
