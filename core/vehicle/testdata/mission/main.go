// Command mission is a test mission for vehicle tests. Like a compiled
// mission, it serves MissionService on its listen socket and does nothing
// until StartMission is called, which it reports by writing StartedMarker to
// stderr. It then runs until it is killed, writing StoppedMarker to stderr
// when StopMission is called. Copied to a file named "callback",
// its StartMission instead calls the vehicle's DataService through its client
// socket, which the vehicle's law allows a running mission, and it exits
// successfully once the call succeeds. Copied to a file named "reject", its
// StartMission fails, and copied to a file named "stuck", its StopMission
// never returns.
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/status"
)

// StartedMarker is written to stderr once the mission is started, matching
// the vehicle tests' missionStartedMarker.
const StartedMarker = "test mission started"

// StoppedMarker is written to stderr when the mission is asked to stop,
// matching the vehicle tests' missionStoppedMarker.
const StoppedMarker = "test mission stopped"

// server serves the mission's MissionService.
type server struct {
	missionpb.UnimplementedMissionServiceServer
	mode string           // base name the mission was run as
	conn *grpc.ClientConn // conn to the vehicle
	done chan error       // receives why the mission should exit
}

func (s *server) StartMission(
	ctx context.Context,
	req *missionpb.StartMissionRequest,
) (*missionpb.StartMissionResponse, error) {
	switch s.mode {
	case "reject":
		return nil, status.Error(codes.Aborted, "test mission rejected start")
	case "callback":
		// A compiled mission likewise sets its dataflow when it is started
		ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
		defer cancel()
		_, err := vehiclepb.NewDataServiceClient(s.conn).GetFlow(ctx, &vehiclepb.GetFlowRequest{}, grpc.WaitForReady(true))
		s.done <- err
		if err != nil {
			return nil, err
		}
	}
	fmt.Fprintln(os.Stderr, StartedMarker)
	return &missionpb.StartMissionResponse{}, nil
}

func (s *server) StopMission(
	ctx context.Context,
	req *missionpb.StopMissionRequest,
) (*missionpb.StopMissionResponse, error) {
	fmt.Fprintln(os.Stderr, StoppedMarker)
	if s.mode == "stuck" {
		<-ctx.Done()
		return nil, ctx.Err()
	}
	return &missionpb.StopMissionResponse{}, nil
}

func run() error {
	// The plugin waits for the listen socket before it is started
	ln, err := net.Listen("unix", os.Getenv("STEELEAGLE_LISTEN_SOCKET"))
	if err != nil {
		return err
	}
	conn, err := grpc.NewClient("unix://"+os.Getenv("STEELEAGLE_CLIENT_SOCKET"),
		grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer conn.Close()

	s := &server{mode: filepath.Base(os.Args[0]), conn: conn, done: make(chan error, 1)}
	grpcServer := grpc.NewServer()
	healthpb.RegisterHealthServer(grpcServer, health.NewServer())
	missionpb.RegisterMissionServiceServer(grpcServer, s)
	served := make(chan error, 1)
	go func() { served <- grpcServer.Serve(ln) }()

	select {
	case err := <-served:
		return err
	case err := <-s.done:
		// StartMission's response is sent before the mission exits
		grpcServer.GracefulStop()
		return err
	}
}

func main() {
	if err := run(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
