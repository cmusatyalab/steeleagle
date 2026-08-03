package vehicle

import (
	"context"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
)

// Query the driver for static hardware info, e.g. model.
func (v *Vehicle) getDriverModel(ctx context.Context) (string, error) {
	client := driverpb.NewInfoServiceClient(v.driver)
	resp, err := client.GetVehicleInfo(ctx, &driverpb.GetVehicleInfoRequest{})
	if err != nil {
		return "", err
	}
	return resp.Model, nil
}
