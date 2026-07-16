package vehicle_test

import (
	"context"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"

	streampb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/stream"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// ServerSocket is the location of the server listener.
const ServerSocket = "server.sock"

// DriverServerSocket is the location of the driver server.
const DriverServerSocket = "driver-server.sock"

// MissionServerSocket is the location of the mission server.
const MissionServerSocket = "mission-server.sock"

// MissionListenSocket is the location of the mission listener.
const MissionListenSocket = "mission-listen.sock"

// ControlService mocks a ControlService gRPC server.
type ControlService struct {
	driverpb.UnimplementedControlServiceServer
	commCh chan string
}

// TakeOff mocks and logs a TakeOff endpoint.
func (c *ControlService) TakeOff(ctx context.Context, req *driverpb.TakeOffRequest) (*driverpb.TakeOffResponse, error) {
	c.commCh <- "ControlService.TakeOff"
	return &driverpb.TakeOffResponse{}, nil
}

// Land mocks and logs a Land endpoint.
func (c *ControlService) Land(ctx context.Context, req *driverpb.LandRequest) (*driverpb.LandResponse, error) {
	c.commCh <- "ControlService.Land"
	return &driverpb.LandResponse{}, nil
}

// Hold mocks and logs a Hold endpoint.
func (c *ControlService) Hold(ctx context.Context, req *driverpb.HoldRequest) (*driverpb.HoldResponse, error) {
	c.commCh <- "ControlService.Hold"
	return &driverpb.HoldResponse{}, nil
}

// StreamService mocks a StreamService gRPC server.
type StreamService struct {
	driverpb.UnimplementedStreamServiceServer
	url string
}

// GetVideoStreamURL mocks and logs a GetVideoStreamURL request and sends back
// a mock URL. This is called automatically by the vehicle's background driver
// streaming as soon as it starts, so unlike the other mocked RPCs it does not
// report on commCh: doing so would race with (and starve) the command-routing
// assertions that tests make against explicit RPCs.
func (s *StreamService) GetVideoStreamURL(
	ctx context.Context,
	req *driverpb.GetVideoStreamURLRequest) (*driverpb.GetVideoStreamURLResponse, error) {
	return &driverpb.GetVideoStreamURLResponse{StreamUrl: s.url}, nil
}

// StreamTelemetry mocks and logs a StreamTelemetry request. Like
// GetVideoStreamURL, it is triggered automatically on vehicle start and so
// does not report on commCh.
func (s *StreamService) StreamTelemetry(
	req *driverpb.StreamTelemetryRequest,
	stream driverpb.StreamService_StreamTelemetryServer) error {
	for {
		err := stream.Send(&driverpb.StreamTelemetryResponse{
			Telemetry: &streampb.Telemetry{},
		})
		if err != nil {
			return err
		}
		time.Sleep(1 * time.Second)
	}
}

func (s *StreamService) StreamVideoFrames(
	req *driverpb.StreamVideoFramesRequest,
	stream driverpb.StreamService_StreamVideoFramesServer) error {
	frameId := 1
	for {
		data := make([]byte, 10)
		frame := &streampb.EncodedFrame{
			Timestamp:   timestamppb.Now(),
			Id:          uint64(frameId),
			EncodedData: data,
		}
		frameId += 1
		err := stream.Send(&driverpb.StreamVideoFramesResponse{
			Frame: frame,
		})
		if err != nil {
			return err
		}
		time.Sleep(1 * time.Second)
	}
}

// MissionService mocks a MissionService gRPC server.
type MissionService struct {
	missionpb.UnimplementedMissionServiceServer
	commCh chan string
}

// StartMission mocks and logs a StartMission endpoint.
func (m *MissionService) StartMission(ctx context.Context, req *missionpb.StartMissionRequest) (*missionpb.StartMissionResponse, error) {
	m.commCh <- "MissionService.StartMission"
	return &missionpb.StartMissionResponse{}, nil
}

// StopMission mocks and logs a StopMission endpoint.
func (m *MissionService) StopMission(ctx context.Context, req *missionpb.StopMissionRequest) (*missionpb.StopMissionResponse, error) {
	m.commCh <- "MissionService.StopMission"
	return &missionpb.StopMissionResponse{}, nil
}

// setupPlugins creates the mission and driver gRPC servers/plugins for tests.
// Can provide a stream url that the StreamService will respond with as well.
// Returns the driver plugin, mission plugin, a client for the mission gRPC
// service, and a communication channel.
func setupPlugins(t *testing.T, url string) (util.Plugin, util.Plugin, *grpc.ClientConn, chan string, error) {
	t.Helper()

	// Create command channel
	commCh := make(chan string, 2)

	// Create a temporary directory to hold the sockets
	tempDir := t.TempDir()

	// Create listeners
	driverLn, err := net.Listen("unix", filepath.Join(tempDir, DriverServerSocket))
	if err != nil {
		return nil, nil, nil, nil, err
	}
	missionLn, err := net.Listen("unix", filepath.Join(tempDir, MissionServerSocket))
	if err != nil {
		return nil, nil, nil, nil, err
	}

	// Server driver and mission services
	driverServer := grpc.NewServer()
	driverpb.RegisterControlServiceServer(driverServer, &ControlService{commCh: commCh})
	driverpb.RegisterStreamServiceServer(driverServer, &StreamService{url: url})
	missionServer := grpc.NewServer()
	missionpb.RegisterMissionServiceServer(missionServer, &MissionService{commCh: commCh})
	go driverServer.Serve(driverLn)
	go missionServer.Serve(missionLn)

	// Register cleanup for servers
	t.Cleanup(driverServer.GracefulStop)
	t.Cleanup(missionServer.GracefulStop)

	// Create shim plugins that attach to the pre-created listeners
	driverAddr := filepath.Join(tempDir, DriverServerSocket)
	driverPlugin, err := util.CreateShimPlugin(driverAddr, "")
	if err != nil {
		return nil, nil, nil, nil, err
	}
	missionAddr := filepath.Join(tempDir, MissionServerSocket)
	missionListener := filepath.Join(tempDir, MissionListenSocket)
	acl := util.GetACL([]string{}, []int{os.Getpid()})
	missionPlugin, err := util.CreateShimPlugin(
		missionAddr,
		missionListener,
		util.WithACL(acl),
		util.WithAuthCode(util.MissionCode),
	)
	if err != nil {
		return nil, nil, nil, nil, err
	}

	// Create a mission client
	target := fmt.Sprintf("unix://%s", missionListener)
	client, err := grpc.NewClient(
		target,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)

	return driverPlugin, missionPlugin, client, commCh, nil
}

// testLogger implements the io.Writer interface to allow zerolog to write logs
// to the testing log method. By using testLogger, zerolog logs are printed to
// the console only when a test fails.
type testLogger struct{ t *testing.T }

func (l testLogger) Write(p []byte) (n int, err error) {
	l.t.Log(string(p))
	return len(p), nil
}

var _ io.Writer = (*testLogger)(nil)

// NewVehicle shadows vehicle.NewVehicle to add a logger that writes to testLogger.
func NewVehicle(t *testing.T, cfg vehicle.PluginConfig, options ...vehicle.VehicleOption) (*vehicle.Vehicle, error) {
	t.Helper()
	out := testLogger{t}
	logger := zerolog.New(zerolog.ConsoleWriter{Out: out}).With().Timestamp().Logger()
	options = append(options, vehicle.WithLogger(logger))
	return vehicle.NewVehicle(cfg, options...)
}
