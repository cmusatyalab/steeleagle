//go:build ignore

package sdk

import (
	"context"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
)

// vehicleContext holds the context object for the task and the RPC stubs.
type vehicleContext struct {
	ctx     context.Context
	control driverpb.ControlServiceClient
	data    vehiclepb.DataServiceClient
}

// call is the underlying structure of all RPC calls.
type call[T, U any] struct {
	ctx  context.Context
	exec func(context.Context, T) (U, error)
}

// run runs a call and returns a waiter object which can be used to wait for
// a result.
func (c *call[T, U]) run() *waiter[U] {
	resp, err := c.exec(c.ctx)
	return &waiter[U]{resp: resp, err: err}
}
