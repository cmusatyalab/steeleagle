package main_test

import (
	"context"
	"net"
	"sync/atomic"
	"testing"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"google.golang.org/grpc"
)

// fakeVehicle is a minimal ControlService implementation standing in for a
// real vehicle's gRPC server, so tests can verify swarm actually dials out to
// and invokes a registered vehicle, not just that it resolves one.
type fakeVehicle struct {
	driverpb.UnimplementedControlServiceServer
	takeOffCalls atomic.Int32
}

func (v *fakeVehicle) TakeOff(context.Context, *driverpb.TakeOffRequest) (*driverpb.TakeOffResponse, error) {
	v.takeOffCalls.Add(1)
	return driverpb.TakeOffResponse_builder{}.Build(), nil
}

// Land is used solely as a side-effect-free liveness probe by registerVehicle.
func (v *fakeVehicle) Land(context.Context, *driverpb.LandRequest) (*driverpb.LandResponse, error) {
	return driverpb.LandResponse_builder{}.Build(), nil
}

// startFakeVehicle binds a real listener on 127.0.0.1 and serves
// ControlService off it, torn down via t.Cleanup.
func startFakeVehicle(t *testing.T) (*fakeVehicle, int) {
	t.Helper()

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listening for fake vehicle: %v", err)
	}

	v := &fakeVehicle{}
	srv := grpc.NewServer()
	driverpb.RegisterControlServiceServer(srv, v)

	go srv.Serve(ln)
	t.Cleanup(srv.Stop)

	return v, ln.Addr().(*net.TCPAddr).Port
}
