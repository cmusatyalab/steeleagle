package sdk

import (
	"context"
	"os"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

// vehicleContext is the underlying structure that is passed to user code
// underneath a Vehicle interface.
type vehicleContext struct {
	ctx     context.Context
	control driverpb.ControlServiceClient
	data    vehiclepb.DataServiceClient
	log     zerolog.Logger
}

// NewVehicleFromContext creates a new Vehicle interface given a context and
// gRPC client connection.
func NewVehicleFromContext(ctx context.Context, conn *grpc.ClientConn, options ...ContextOption) Vehicle {
	vctx := &vehicleContext{
		ctx:     ctx,
		control: driverpb.NewControlServiceClient(conn),
		data:    vehiclepb.NewDataServiceClient(conn),
		log:     zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(vctx)
	}
	return vctx
}
