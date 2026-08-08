package swarm

import (
	"context"
	"os"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// defaultCallTimeout bounds each per-vehicle proxied call.
const defaultCallTimeout = 5 * time.Second

// SwarmServer implements swarmpb.SwarmServiceServer, proxying each request to
// the targeted vehicles' driver/mission services.
type SwarmServer struct {
	swarmpb.UnimplementedSwarmServiceServer
	resolver VehicleResolver // resolves vehicle names to addresses
	pool     *connPool       // pooled client connections, keyed by vehicle name
	timeout  time.Duration   // bound on each per-vehicle proxied call
	log      zerolog.Logger  // logger object
}

// NewSwarmServer creates a new swarm server that reaches vehicles through the
// given VehicleResolver.
func NewSwarmServer(resolver VehicleResolver, options ...Option) *SwarmServer {
	s := &SwarmServer{
		resolver: resolver,
		timeout:  defaultCallTimeout,
		log:      zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(s)
	}
	// Built after options are applied so the pool picks up a WithLogger
	// override instead of always using the default.
	s.pool = newConnPool(s.log)
	return s
}

// clientConn resolves the named vehicle and returns a pooled connection to it.
func (s *SwarmServer) clientConn(name string) (*grpc.ClientConn, error) {
	addr, ok := s.resolver.Resolve(name)
	if !ok {
		return nil, status.Errorf(codes.NotFound, "unknown vehicle %q", name)
	}
	return s.pool.get(name, addr)
}

// callTimeout bounds each per-vehicle proxied call.
func (s *SwarmServer) callTimeout() time.Duration {
	return s.timeout
}

// logger returns the logger dispatch uses to report per-vehicle command
// outcomes.
func (s *SwarmServer) logger() zerolog.Logger {
	return s.log
}

// Close closes every pooled connection to a vehicle.
func (s *SwarmServer) Close() {
	s.pool.close()
}

func (s *SwarmServer) SwarmTakeOff(
	req *swarmpb.SwarmTakeOffRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmTakeOffResponse],
) error {
	return dispatch(
		s,
		"SwarmTakeOff",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.TakeOffRequest) (*driverpb.TakeOffResponse, error) {
			return driverpb.NewControlServiceClient(conn).TakeOff(ctx, r)
		},
		func(vehicle string, resp *driverpb.TakeOffResponse, err error) *swarmpb.SwarmTakeOffResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmTakeOffResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmLand(
	req *swarmpb.SwarmLandRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmLandResponse],
) error {
	return dispatch(
		s,
		"SwarmLand",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.LandRequest) (*driverpb.LandResponse, error) {
			return driverpb.NewControlServiceClient(conn).Land(ctx, r)
		},
		func(vehicle string, resp *driverpb.LandResponse, err error) *swarmpb.SwarmLandResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmLandResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmHold(
	req *swarmpb.SwarmHoldRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmHoldResponse],
) error {
	return dispatch(
		s,
		"SwarmHold",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.HoldRequest) (*driverpb.HoldResponse, error) {
			return driverpb.NewControlServiceClient(conn).Hold(ctx, r)
		},
		func(vehicle string, resp *driverpb.HoldResponse, err error) *swarmpb.SwarmHoldResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmHoldResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmKill(
	req *swarmpb.SwarmKillRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmKillResponse],
) error {
	return dispatch(
		s,
		"SwarmKill",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.KillRequest) (*driverpb.KillResponse, error) {
			return driverpb.NewControlServiceClient(conn).Kill(ctx, r)
		},
		func(vehicle string, resp *driverpb.KillResponse, err error) *swarmpb.SwarmKillResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmKillResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmReturnToHome(
	req *swarmpb.SwarmReturnToHomeRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmReturnToHomeResponse],
) error {
	return dispatch(
		s,
		"SwarmReturnToHome",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.ReturnToHomeRequest) (*driverpb.ReturnToHomeResponse, error) {
			return driverpb.NewControlServiceClient(conn).ReturnToHome(ctx, r)
		},
		func(vehicle string, resp *driverpb.ReturnToHomeResponse, err error) *swarmpb.SwarmReturnToHomeResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmReturnToHomeResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmSetVelocity(
	req *swarmpb.SwarmSetVelocityRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmSetVelocityResponse],
) error {
	return dispatch(
		s,
		"SwarmSetVelocity",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.SetVelocityRequest) (*driverpb.SetVelocityResponse, error) {
			return driverpb.NewControlServiceClient(conn).SetVelocity(ctx, r)
		},
		func(vehicle string, resp *driverpb.SetVelocityResponse, err error) *swarmpb.SwarmSetVelocityResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmSetVelocityResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmSetGimbalPose(
	req *swarmpb.SwarmSetGimbalPoseRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmSetGimbalPoseResponse],
) error {
	return dispatch(
		s,
		"SwarmSetGimbalPose",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *driverpb.SetGimbalPoseRequest) (*driverpb.SetGimbalPoseResponse, error) {
			return driverpb.NewControlServiceClient(conn).SetGimbalPose(ctx, r)
		},
		func(vehicle string, resp *driverpb.SetGimbalPoseResponse, err error) *swarmpb.SwarmSetGimbalPoseResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmSetGimbalPoseResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmStartMission(
	req *swarmpb.SwarmStartMissionRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmStartMissionResponse],
) error {
	return dispatch(
		s,
		"SwarmStartMission",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *missionpb.StartMissionRequest) (*missionpb.StartMissionResponse, error) {
			return missionpb.NewMissionServiceClient(conn).StartMission(ctx, r)
		},
		func(vehicle string, resp *missionpb.StartMissionResponse, err error) *swarmpb.SwarmStartMissionResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmStartMissionResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmUploadMission(
	req *swarmpb.SwarmUploadMissionRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmUploadMissionResponse],
) error {
	return dispatch(
		s,
		"SwarmUploadMission",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *missionpb.UploadMissionRequest) (*missionpb.UploadMissionResponse, error) {
			return missionpb.NewMissionServiceClient(conn).UploadMission(ctx, r)
		},
		func(vehicle string, resp *missionpb.UploadMissionResponse, err error) *swarmpb.SwarmUploadMissionResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmUploadMissionResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

func (s *SwarmServer) SwarmStopMission(
	req *swarmpb.SwarmStopMissionRequest,
	stream grpc.ServerStreamingServer[swarmpb.SwarmStopMissionResponse],
) error {
	return dispatch(
		s,
		"SwarmStopMission",
		req.GetVehicles(),
		stream,
		req.GetRequest(),
		func(ctx context.Context, conn *grpc.ClientConn, r *missionpb.StopMissionRequest) (*missionpb.StopMissionResponse, error) {
			return missionpb.NewMissionServiceClient(conn).StopMission(ctx, r)
		},
		func(vehicle string, resp *missionpb.StopMissionResponse, err error) *swarmpb.SwarmStopMissionResponse {
			code, details := statusOf(err)
			return swarmpb.SwarmStopMissionResponse_builder{
				Vehicle:  vehicle,
				Response: resp,
				Code:     code,
				Details:  details,
			}.Build()
		},
	)
}

var _ vehicleDialer = (*SwarmServer)(nil)
