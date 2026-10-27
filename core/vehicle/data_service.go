package vehicle

import (
	"bytes"
	"context"
	"errors"
	"slices"
	"time"

	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	uriel "github.com/cmusatyalab/uriel/go"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// SetDataflow parses and executes a flow from TOML bytes, replacing the
// vehicle's current dataflow. Setting the current dataflow again does nothing.
func (v *Vehicle) SetDataflow(
	ctx context.Context,
	req *vehiclepb.SetDataflowRequest,
) (*vehiclepb.SetDataflowResponse, error) {
	v.flowInfo.mu.Lock()
	defer v.flowInfo.mu.Unlock()
	if v.flowInfo.flow != nil && bytes.Equal(v.flowInfo.spec, req.GetToml()) {
		return &vehiclepb.SetDataflowResponse{}, nil
	}
	flow, err := config.ParseFlowConfigFromBytes(req.GetToml())
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid dataflow: %v", err)
	}
	cameras, err := v.cameraRequest(flow)
	if err != nil {
		return nil, err
	}

	spec, err := v.urielSpec(flow)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if err := v.streamCameras(ctx, cameras); err != nil {
		v.log.Error().Err(err).Msg("could not stream dataflow cameras")
		return nil, err
	}
	// Each flow gets a new name, so that results of the previous one are not
	// stored as its own
	name := util.ShortId()
	if err := v.swapFlow(name, spec); err != nil {
		v.log.Error().Err(err).Msg("could not set dataflow, keeping the current one")
		// The driver goes back to streaming the cameras of the current flow
		current := &driverpb.StreamCamerasRequest{}
		if v.flowInfo.flow != nil {
			current, _ = v.cameraRequest(v.flowInfo.flow) // it was valid when it was set
		}
		if err := v.streamCameras(ctx, current); err != nil {
			v.log.Error().Err(err).Msg("could not restore dataflow cameras")
		}
		if errors.Is(err, uriel.ErrInvalid) {
			return nil, status.Error(codes.InvalidArgument, err.Error())
		}
		return nil, status.Error(codes.Internal, err.Error())
	}
	v.flowInfo.name, v.flowInfo.spec, v.flowInfo.flow = name, req.GetToml(), flow
	v.log.Info().Str("flow", name).Msg("dataflow set")
	return &vehiclepb.SetDataflowResponse{}, nil
}

// GetFlow returns the TOML bytes of the current dataflow, as they were given
// to SetDataflow, or empty bytes if no dataflow is set.
func (v *Vehicle) GetFlow(
	ctx context.Context,
	req *vehiclepb.GetFlowRequest,
) (*vehiclepb.GetFlowResponse, error) {
	v.flowInfo.mu.Lock()
	defer v.flowInfo.mu.Unlock()
	return vehiclepb.GetFlowResponse_builder{Toml: v.flowInfo.spec}.Build(), nil
}

// GetResult returns all results of a dataflow that match the query
// timestamps, ordered from oldest to newest, or the most recent result if no
// timestamps are given.
func (v *Vehicle) GetResult(
	ctx context.Context,
	req *vehiclepb.GetResultRequest,
) (*vehiclepb.GetResultResponse, error) {
	if req.GetEngine() == "" || req.GetEngine() == TelemetryBucket {
		return nil, status.Errorf(codes.InvalidArgument, "%q is not an engine", req.GetEngine())
	}
	results, err := queryAll[resultpb.ComputeResult](v, req.GetEngine(), req.GetTimeStart(), req.GetTimeEnd())
	if err != nil {
		return nil, err
	}
	return vehiclepb.GetResultResponse_builder{Result: results}.Build(), nil
}

// GetTelemetry returns all received telemetry that matches the query
// timestamps, ordered from oldest to newest, or the most recent telemetry if
// no timestamps are given.
func (v *Vehicle) GetTelemetry(
	ctx context.Context,
	req *vehiclepb.GetTelemetryRequest,
) (*vehiclepb.GetTelemetryResponse, error) {
	telemetry, err := queryAll[telemetrypb.Telemetry](v, TelemetryBucket, req.GetTimeStart(), req.GetTimeEnd())
	if err != nil {
		return nil, err
	}
	return vehiclepb.GetTelemetryResponse_builder{Telemetry: telemetry}.Build(), nil
}

// swapFlow replaces the current Uriel flow with spec under name. If spec
// can't be added, the current flow is put back, so the swap is atomic.
func (v *Vehicle) swapFlow(name, spec string) error {
	if v.flowInfo.flow == nil {
		return v.uriel.AddFlow(name, spec)
	}
	current, err := v.urielSpec(v.flowInfo.flow)
	if err != nil {
		return err
	}
	if err := v.uriel.RemoveFlow(v.flowInfo.name); err != nil {
		return err
	}
	if err := v.uriel.AddFlow(name, spec); err != nil {
		if err := v.uriel.AddFlow(v.flowInfo.name, current); err != nil {
			v.log.Error().Err(err).Msg("could not restore current dataflow")
		}
		return err
	}
	return nil
}

// urielSpec returns the Uriel spec of flow, which knows producers by their
// fully qualified names.
func (v *Vehicle) urielSpec(flow *config.FlowConfig) (string, error) {
	spec := config.FlowConfig{Producers: slices.Clone(flow.Producers), Engines: flow.Engines, Edges: slices.Clone(flow.Edges)}
	for i, p := range spec.Producers {
		spec.Producers[i].Name = v.producerUri(p.Name)
		for j, e := range spec.Edges {
			if e.From == p.Name {
				spec.Edges[j].From = spec.Producers[i].Name
			}
		}
	}
	b, err := spec.ToBytes()
	return string(b), err
}

// queryAll unmarshals every value in bucket stored between start and end,
// either of which may be unset. A bucket with nothing stored has no values.
func queryAll[T any, P interface {
	*T
	proto.Message
}](v *Vehicle, bucket string, start, end *timestamppb.Timestamp) ([]P, error) {
	var values []P
	err := v.query(bucket, timeOf(start), timeOf(end), func(value []byte) error {
		m := P(new(T))
		values = append(values, m)
		return proto.Unmarshal(value, m)
	})
	if status.Code(err) == codes.NotFound {
		return nil, nil
	} else if err != nil {
		v.log.Error().Err(err).Str("bucket", bucket).Msg("could not query datastore")
		return nil, err
	}
	return values, nil
}

// timeOf returns the time of ts, or the zero time if ts is unset.
func timeOf(ts *timestamppb.Timestamp) time.Time {
	if ts == nil {
		return time.Time{}
	}
	return ts.AsTime()
}
