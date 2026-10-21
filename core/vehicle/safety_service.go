package vehicle

import (
	"context"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ConfigureDMS adjusts the manual command timeout for the dead man's switch.
func (v *Vehicle) ConfigureDMS(
	ctx context.Context,
	req *vehiclepb.ConfigureDMSRequest,
) (*vehiclepb.ConfigureDMSResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "ConfigureDMS not implemented")
}

// SetGeofence sets (or turns off) the vehicle geofence.
func (v *Vehicle) SetGeofence(
	ctx context.Context,
	req *vehiclepb.SetGeofenceRequest,
) (*vehiclepb.SetGeofenceResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "SetGeofence not implemented")
}

// SetMissionGeofence sets (or turns off) the mission geofence.
func (v *Vehicle) SetMissionGeofence(
	ctx context.Context,
	req *vehiclepb.SetMissionGeofenceRequest,
) (*vehiclepb.SetMissionGeofenceResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "SetMissionGeofence not implemented")
}

// SetFallbackBehavior sets the vehicle fallback behavior.
func (v *Vehicle) SetFallbackBehavior(
	ctx context.Context,
	req *vehiclepb.SetFallbackBehaviorRequest,
) (*vehiclepb.SetFallbackBehaviorResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "SetFallbackBehavior not implemented")
}
