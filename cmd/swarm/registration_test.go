package main_test

import (
	"context"
	"testing"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// status extracts the gRPC status code from err, failing the test if err is
// non-nil but not a status error.
func statusCode(t *testing.T, err error) codes.Code {
	t.Helper()
	if err == nil {
		return codes.OK
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("non-status error: %v", err)
	}
	return st.Code()
}

// registerVehicle opens a Register stream for name/port and returns a cancel
// func that unregisters it.
func registerVehicle(t *testing.T, inst *swarmInstance, name string, port int) (cancel func()) {
	t.Helper()

	ctx, cancelStream := context.WithCancel(context.Background())
	stream, err := inst.Registry.Register(ctx, swarmpb.RegisterRequest_builder{
		DaemonName: "test-daemon",
		Name:       name,
		Port:       uint32(port),
	}.Build())
	if err != nil {
		cancelStream()
		t.Fatalf("opening Register stream for %s: %v", name, err)
	}

	if _, err := stream.Recv(); err != nil {
		cancelStream()
		t.Fatalf("waiting for %s registration ack: %v", name, err)
	}

	return func() {
		cancelStream()
		stream.Recv() // drains the stream so it observes cancellation
	}
}

// landCode calls SwarmLand against a single vehicle and returns its
// per-vehicle result code. It's used as a side-effect-free liveness/
// resolvability probe.
func landCode(t *testing.T, inst *swarmInstance, vehicle string) codes.Code {
	t.Helper()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	stream, err := inst.Swarm.SwarmLand(ctx, swarmpb.SwarmLandRequest_builder{
		Vehicles: []string{vehicle},
		Request:  driverpb.LandRequest_builder{}.Build(),
	}.Build())
	if err != nil {
		t.Fatalf("calling SwarmLand: %v", err)
	}

	resp, err := stream.Recv()
	if err != nil {
		t.Fatalf("receiving SwarmLand response for %s: %v", vehicle, err)
	}
	return codes.Code(resp.GetCode())
}

func TestRegisterValidation(t *testing.T) {
	inst := startSwarm(t)

	cases := []struct {
		name string
		req  *swarmpb.RegisterRequest
	}{
		{
			name: "empty name",
			req: swarmpb.RegisterRequest_builder{
				DaemonName: "test-daemon",
				Name:       "",
				Port:       9000,
			}.Build(),
		},
		{
			name: "port out of range",
			req: swarmpb.RegisterRequest_builder{
				DaemonName: "test-daemon",
				Name:       "harpy",
				Port:       70000,
			}.Build(),
		},
		{
			name: "empty daemon name",
			req: swarmpb.RegisterRequest_builder{
				DaemonName: "",
				Name:       "harpy",
				Port:       9000,
			}.Build(),
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()

			stream, err := inst.Registry.Register(ctx, tc.req)
			if err != nil {
				t.Fatalf("opening Register stream: %v", err)
			}
			if _, err := stream.Recv(); statusCode(t, err) != codes.InvalidArgument {
				t.Fatalf("Register(%v) = %v, want InvalidArgument", tc.req, err)
			}
		})
	}
}

func TestDispatchFanOut(t *testing.T) {
	inst := startSwarm(t)
	vehicle, port := startFakeVehicle(t)
	defer registerVehicle(t, inst, "harpy", port)()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	stream, err := inst.Swarm.SwarmTakeOff(ctx, swarmpb.SwarmTakeOffRequest_builder{
		Vehicles: []string{"harpy", "ghost"}, // "ghost" was never registered
		Request:  driverpb.TakeOffRequest_builder{}.Build(),
	}.Build())
	if err != nil {
		t.Fatalf("calling SwarmTakeOff: %v", err)
	}

	got := map[string]codes.Code{}
	for range 2 {
		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("receiving SwarmTakeOff response: %v", err)
		}
		got[resp.GetVehicle()] = codes.Code(resp.GetCode())
	}

	if got["harpy"] != codes.OK {
		t.Errorf("harpy code = %v, want OK", got["harpy"])
	}
	if got["ghost"] != codes.NotFound {
		t.Errorf("ghost code = %v, want NotFound", got["ghost"])
	}
	if calls := vehicle.takeOffCalls.Load(); calls != 1 {
		t.Errorf("fake vehicle received %d TakeOff calls, want 1", calls)
	}
}

func TestVehicleEvictedOnDisconnect(t *testing.T) {
	inst := startSwarm(t)
	_, port := startFakeVehicle(t)
	unregister := registerVehicle(t, inst, "harpy", port)

	if code := landCode(t, inst, "harpy"); code != codes.OK {
		t.Fatalf("dispatch before disconnect = %v, want OK", code)
	}

	unregister()

	deadline := time.Now().Add(5 * time.Second)
	for {
		code := landCode(t, inst, "harpy")
		if code == codes.NotFound {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("harpy still dispatchable (code %v) after disconnect", code)
		}
		time.Sleep(50 * time.Millisecond)
	}
}
