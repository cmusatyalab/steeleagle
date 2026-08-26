package sdk

import (
	"context"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
)

// VehicleContext is the underlying structure that is passed to user code underneath
// a Vehicle interface.
type vehicleContext struct {
	ctx     context.Context
	control driverpb.ControlServiceClient
	data    vehiclepb.DataServiceClient
}

// NewVehicleFromContext creates a new Vehicle interface given a context and
// gRPC client connection.
func NewVehicleFromContext(ctx context.Context, conn *grpc.ClientConn) Vehicle {
	return &vehicleContext{
		ctx:     ctx,
		control: driverpb.NewControlServiceClient(conn),
		data:    vehiclepb.NewDataServiceClient(conn),
	}
}

// call is the underlying structure of all RPC calls.
type call[T any] struct {
	ctx  context.Context
	exec func(context.Context) (T, error)
}

// run runs a call and returns a waiter object which can be used to wait for
// a result.
func (c *call[T]) run() *waiter[T] {
	resp, err := c.exec(c.ctx)
	return &waiter[T]{resp: resp, err: err}
}
