package vehicle

import (
	"context"
	"strings"
	"sync"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"google.golang.org/grpc"
)

// newDmsInterceptor returns a dead man's switch for the run of ctx. After a
// SetVelocityTarget call, the vehicle holds unless another ControlService call
// comes within DmsTimeout. Calls to the driver are routed as streams, so this
// is a stream interceptor.
func (v *Vehicle) newDmsInterceptor(ctx context.Context) grpc.StreamServerInterceptor {
	prefix := "/" + driverpb.ControlService_ServiceDesc.ServiceName + "/"
	var mu sync.Mutex
	var timer *time.Timer
	// The switch is disarmed when the run stops
	context.AfterFunc(ctx, func() {
		mu.Lock()
		defer mu.Unlock()
		if timer != nil {
			timer.Stop()
		}
	})
	return func(srv any, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
		if strings.HasPrefix(info.FullMethod, prefix) {
			mu.Lock()
			if timer != nil {
				timer.Stop()
			}
			if info.FullMethod == driverpb.ControlService_SetVelocityTarget_FullMethodName {
				// The driver's conn is taken now, while the run is serving calls
				conn := v.driverInfo.conn
				timer = time.AfterFunc(DmsTimeout, func() { v.hold(ctx, conn) })
			}
			mu.Unlock()
		}
		return handler(srv, ss)
	}
}

// hold tells the driver on conn to hold, unless the run of ctx has stopped.
func (v *Vehicle) hold(ctx context.Context, conn *grpc.ClientConn) {
	if ctx.Err() != nil {
		return
	}
	ctx, cancel := context.WithTimeout(ctx, DmsTimeout)
	defer cancel()
	v.log.Warn().Msg("no control after velocity target, holding")
	_, err := driverpb.NewControlServiceClient(conn).Hold(ctx, &driverpb.HoldRequest{})
	if err != nil {
		v.log.Error().Err(err).Msg("could not hold")
	}
}
