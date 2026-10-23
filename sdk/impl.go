package sdk

import (
	"context"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/rs/zerolog"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Ctx gets the current context attached to a vehicleContext.
func (v *vehicleContext) Ctx() context.Context {
	return v.ctx
}

// commandLog returns the logger for one call of the named command.
func (v *vehicleContext) commandLog(command string) zerolog.Logger {
	return v.log.With().Str("command", command).Logger()
}

// commandError logs err, the error of a command's RPC, with its gRPC status,
// and returns the sentinel error the command reports it as. The sentinel
// error alone loses the cause (e.g. ErrInternal for an unreachable vehicle).
func commandError(log zerolog.Logger, err error) error {
	if err == nil {
		return nil
	}
	sentinel := grpcToSentinel(err)
	log.Debug().
		Err(err).
		Stringer("code", status.Code(err)).
		Str("returned", sentinel.Error()).
		Msg("command failed")
	return sentinel
}

// TakeOff implements Vehicle.TakeOff for a vehicleContext.
func (v *vehicleContext) TakeOff(options ...opt.Option[opt.TakeOffOption]) *Waiter[TakeOffResponse] {
	log := v.commandLog("TakeOff")
	req := &driverpb.TakeOffRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.TakeOff(v.ctx, req)

	return newWaiter[TakeOffResponse](
		log,
		&takeOffResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// Land implements Vehicle.Land for a vehicleContext.
func (v *vehicleContext) Land() *Waiter[LandResponse] {
	log := v.commandLog("Land")
	req := &driverpb.LandRequest{}
	resp, err := v.control.Land(v.ctx, req)

	return newWaiter[LandResponse](
		log,
		&landResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// Stand implements Vehicle.Stand for a vehicleContext.
func (v *vehicleContext) Stand() *Waiter[StandResponse] {
	log := v.commandLog("Stand")
	req := &driverpb.StandRequest{}
	resp, err := v.control.Stand(v.ctx, req)

	return newWaiter[StandResponse](
		log,
		&standResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// Sit implements Vehicle.Sit for a vehicleContext.
func (v *vehicleContext) Sit() *Waiter[SitResponse] {
	log := v.commandLog("Sit")
	req := &driverpb.SitRequest{}
	resp, err := v.control.Sit(v.ctx, req)

	return newWaiter[SitResponse](
		log,
		&sitResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// Hold implements Vehicle.Hold for a vehicleContext.
func (v *vehicleContext) Hold() *Waiter[HoldResponse] {
	log := v.commandLog("Hold")
	req := &driverpb.HoldRequest{}
	resp, err := v.control.Hold(v.ctx, req)

	return newWaiter[HoldResponse](
		log,
		&holdResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// Kill implements Vehicle.Kill for a vehicleContext.
func (v *vehicleContext) Kill() *Waiter[KillResponse] {
	log := v.commandLog("Kill")
	req := &driverpb.KillRequest{}
	resp, err := v.control.Kill(v.ctx, req)

	return newWaiter[KillResponse](
		log,
		&killResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// ReturnToHome implements Vehicle.ReturnToHome for a vehicleContext.
func (v *vehicleContext) ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *Waiter[ReturnToHomeResponse] {
	log := v.commandLog("ReturnToHome")
	req := &driverpb.ReturnToHomeRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.ReturnToHome(v.ctx, req)

	return newWaiter[ReturnToHomeResponse](
		log,
		&returnToHomeResponseWrapper{inner: resp},
		commandError(log, err),
		actionPoller(log, v, resp),
	)
}

// SetGlobalPositionTarget implements Vehicle.SetGlobalPositionTarget for a vehicleContext.
func (v *vehicleContext) SetGlobalPositionTarget(
	latitude float64, longitude float64, altitude, heading float32,
	options ...opt.Option[opt.SetGlobalPositionTargetOption]) *Waiter[SetGlobalPositionTargetResponse] {
	log := v.commandLog("SetGlobalPositionTarget")
	req := &driverpb.SetGlobalPositionTargetRequest{}
	for _, option := range options {
		option(req)
	}
	position := &commonpb.GlobalPosition{}
	position.SetLatitude(latitude)
	position.SetLongitude(longitude)
	position.SetAltitude(altitude)
	position.SetHeading(heading)
	req.SetPosition(position)
	resp, err := v.control.SetGlobalPositionTarget(v.ctx, req)

	return newWaiter[SetGlobalPositionTargetResponse](
		log,
		&setGlobalPositionTargetResponseWrapper{inner: resp},
		commandError(log, err),
		guidancePoller(log, v, resp),
	)
}

// SetRelativePositionTarget implements Vehicle.SetRelativePositionTarget for a vehicleContext.
func (v *vehicleContext) SetRelativePositionTarget(
	x, y, z, angle float32,
	options ...opt.Option[opt.SetRelativePositionTargetOption]) *Waiter[SetRelativePositionTargetResponse] {
	log := v.commandLog("SetRelativePositionTarget")
	req := &driverpb.SetRelativePositionTargetRequest{}
	for _, option := range options {
		option(req)
	}
	position := &commonpb.RelativePosition{}
	position.SetX(x)
	position.SetY(y)
	position.SetZ(z)
	position.SetAngle(angle)
	req.SetPosition(position)
	resp, err := v.control.SetRelativePositionTarget(v.ctx, req)

	return newWaiter[SetRelativePositionTargetResponse](
		log,
		&setRelativePositionTargetResponseWrapper{inner: resp},
		commandError(log, err),
		guidancePoller(log, v, resp),
	)
}

// SetVelocityTarget implements Vehicle.SetVelocityTarget for a vehicleContext.
func (v *vehicleContext) SetVelocityTarget(
	xVel, yVel, zVel, angularVel float32,
	options ...opt.Option[opt.SetVelocityTargetOption]) *Waiter[SetVelocityTargetResponse] {
	log := v.commandLog("SetVelocityTarget")
	req := &driverpb.SetVelocityTargetRequest{}
	for _, option := range options {
		option(req)
	}
	velocity := &commonpb.Velocity{}
	velocity.SetXVel(xVel)
	velocity.SetYVel(yVel)
	velocity.SetZVel(zVel)
	velocity.SetAngularVel(angularVel)
	req.SetVelocity(velocity)
	resp, err := v.control.SetVelocityTarget(v.ctx, req)

	return newWaiter[SetVelocityTargetResponse](
		log,
		&setVelocityTargetResponseWrapper{inner: resp},
		commandError(log, err),
		guidancePoller(log, v, resp),
	)
}

// SetGimbalAngleTarget implements Vehicle.SetGimbalAngleTarget for a vehicleContext.
func (v *vehicleContext) SetGimbalAngleTarget(
	pitch, roll, yaw float32,
	options ...opt.Option[opt.SetGimbalAngleTargetOption]) *Waiter[SetGimbalAngleTargetResponse] {
	log := v.commandLog("SetGimbalAngleTarget")
	req := &driverpb.SetGimbalAngleTargetRequest{}
	for _, option := range options {
		option(req)
	}
	pose := &commonpb.Pose{}
	pose.SetPitch(pitch)
	pose.SetRoll(roll)
	pose.SetYaw(yaw)
	req.SetPose(pose)
	resp, err := v.control.SetGimbalAngleTarget(v.ctx, req)

	return newWaiter[SetGimbalAngleTargetResponse](
		log,
		&setGimbalAngleTargetResponseWrapper{inner: resp},
		commandError(log, err),
		gimbalPoller(log, v, resp),
	)
}

// SetGimbalVelocityTarget implements Vehicle.SetGimbalVelocityTarget for a vehicleContext.
func (v *vehicleContext) SetGimbalVelocityTarget(
	pitchVel, rollVel, yawVel float32) *Waiter[SetGimbalVelocityTargetResponse] {
	log := v.commandLog("SetGimbalVelocityTarget")
	req := &driverpb.SetGimbalVelocityTargetRequest{}
	pose_vel := &commonpb.PoseVelocity{}
	pose_vel.SetPitchVel(pitchVel)
	pose_vel.SetRollVel(rollVel)
	pose_vel.SetYawVel(yawVel)
	req.SetPoseVelocity(pose_vel)
	resp, err := v.control.SetGimbalVelocityTarget(v.ctx, req)

	return newWaiter[SetGimbalVelocityTargetResponse](
		log,
		&setGimbalVelocityTargetResponseWrapper{inner: resp},
		commandError(log, err),
		gimbalPoller(log, v, resp),
	)
}

// GetTelemetry implements Vehicle.GetTelemetry for a vehicleContext.
func (v *vehicleContext) GetTelemetry(options ...opt.Option[opt.QueryOption]) *Waiter[[]Telemetry] {
	log := v.commandLog("GetTelemetry")
	req := &vehiclepb.GetTelemetryRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.data.GetTelemetry(v.ctx, req)
	src := resp.GetTelemetry()
	telemetry := make([]Telemetry, len(src))
	for i, t := range src {
		telemetry[i] = &telemetryWrapper{inner: t}
	}
	if err == nil {
		logQuery(log.Debug(), req).Int("count", len(telemetry)).Msg("fetched telemetry")
	}

	return newWaiter(log, telemetry, commandError(log, err), noPoll)
}

// GetDetectionResult implements Vehicle.GetDetectionResult for a vehicleContext.
func (v *vehicleContext) GetDetectionResult(
	engine params.DetectionEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]DetectionResult] {
	log := v.resultLog("GetDetectionResult", string(engine))
	results, err := v.getResults(log, string(engine), options)
	wrap := func(r *resultpb.ComputeResult) DetectionResult {
		return &detectionResultWrapper{inner: r.GetDetectionResult()}
	}

	return newWaiter(
		log,
		typedResults(log, results, (*resultpb.ComputeResult).HasDetectionResult, wrap),
		commandError(log, err),
		noPoll,
	)
}

// GetClassificationResult implements Vehicle.GetClassificationResult for a vehicleContext.
func (v *vehicleContext) GetClassificationResult(
	engine params.ClassificationEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]ClassificationResult] {
	log := v.resultLog("GetClassificationResult", string(engine))
	results, err := v.getResults(log, string(engine), options)
	wrap := func(r *resultpb.ComputeResult) ClassificationResult {
		return &classificationResultWrapper{inner: r.GetClassificationResult()}
	}

	return newWaiter(
		log,
		typedResults(log, results, (*resultpb.ComputeResult).HasClassificationResult, wrap),
		commandError(log, err),
		noPoll,
	)
}

// GetGuidanceResult implements Vehicle.GetGuidanceResult for a vehicleContext.
func (v *vehicleContext) GetGuidanceResult(
	engine params.GuidanceEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]GuidanceResult] {
	log := v.resultLog("GetGuidanceResult", string(engine))
	results, err := v.getResults(log, string(engine), options)
	wrap := func(r *resultpb.ComputeResult) GuidanceResult {
		return &guidanceResultWrapper{inner: r.GetGuidanceResult()}
	}

	return newWaiter(
		log,
		typedResults(log, results, (*resultpb.ComputeResult).HasGuidanceResult, wrap),
		commandError(log, err),
		noPoll,
	)
}

// GetPositionResult implements Vehicle.GetPositionResult for a vehicleContext.
func (v *vehicleContext) GetPositionResult(
	engine params.PositionEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]PositionResult] {
	log := v.resultLog("GetPositionResult", string(engine))
	results, err := v.getResults(log, string(engine), options)
	wrap := func(r *resultpb.ComputeResult) PositionResult {
		return &positionResultWrapper{inner: r.GetPositionResult()}
	}

	return newWaiter(
		log,
		typedResults(log, results, (*resultpb.ComputeResult).HasPositionResult, wrap),
		commandError(log, err),
		noPoll,
	)
}

// GetGenericResult implements Vehicle.GetGenericResult for a vehicleContext.
func (v *vehicleContext) GetGenericResult(
	engine params.GenericEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]GenericResult] {
	log := v.resultLog("GetGenericResult", string(engine))
	results, err := v.getResults(log, string(engine), options)
	wrap := func(r *resultpb.ComputeResult) GenericResult {
		return &genericResultWrapper{inner: r.GetGenericResult()}
	}

	return newWaiter(
		log,
		typedResults(log, results, (*resultpb.ComputeResult).HasGenericResult, wrap),
		commandError(log, err),
		noPoll,
	)
}

// resultLog returns the logger for one call of the named result command,
// querying engine.
func (v *vehicleContext) resultLog(command, engine string) zerolog.Logger {
	return v.commandLog(command).With().Str("engine", engine).Logger()
}

// getResults queries the compute results of engine, the most recent one
// unless options give a time range. An engine with no results yet has none,
// rather than failing.
func (v *vehicleContext) getResults(
	log zerolog.Logger, engine string,
	options []opt.Option[opt.QueryOption]) ([]*resultpb.ComputeResult, error) {
	req := &vehiclepb.GetResultRequest{}
	req.SetEngine(engine)
	for _, option := range options {
		option(req)
	}
	resp, err := v.data.GetResult(v.ctx, req)
	if status.Code(err) == codes.NotFound {
		log.Debug().Msg("engine has no results")
		return nil, nil
	} else if err != nil {
		return nil, err
	}
	results := resp.GetResult()
	logQuery(log.Debug(), req).Int("count", len(results)).Msg("fetched engine results")
	return results, nil
}

// typedResults wraps every result that holds a result of the requested
// type, skipping (and logging) any other.
func typedResults[T any](
	log zerolog.Logger, results []*resultpb.ComputeResult,
	has func(*resultpb.ComputeResult) bool, wrap func(*resultpb.ComputeResult) T) []T {
	out := make([]T, 0, len(results))
	for _, r := range results {
		if has(r) {
			out = append(out, wrap(r))
		}
	}
	if skipped := len(results) - len(out); skipped > 0 {
		log.Debug().Int("skipped", skipped).Msg("skipped engine results not of the requested type")
	}
	return out
}

// timeRange is a query with an optional start and end time.
type timeRange interface {
	HasTimeStart() bool
	GetTimeStart() *timestamppb.Timestamp
	HasTimeEnd() bool
	GetTimeEnd() *timestamppb.Timestamp
}

// logQuery adds the time range of q, if it has one, to ev.
func logQuery(ev *zerolog.Event, q timeRange) *zerolog.Event {
	if q.HasTimeStart() {
		ev.Time("start", q.GetTimeStart().AsTime())
	}
	if q.HasTimeEnd() {
		ev.Time("end", q.GetTimeEnd().AsTime())
	}
	return ev
}

var _ Vehicle = &vehicleContext{}
