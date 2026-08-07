package swarm_test

import (
	"context"
	"net"
	"net/netip"
	"testing"
	"time"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"github.com/cmusatyalab/steeleagle/core/swarm"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// slowVehicle is a ControlService fixture whose TakeOff blocks until released,
// for exercising per-vehicle call-timeout enforcement.
type slowVehicle struct {
	driverpb.UnimplementedControlServiceServer
	release chan struct{}
}

func (v *slowVehicle) TakeOff(ctx context.Context, _ *driverpb.TakeOffRequest) (*driverpb.TakeOffResponse, error) {
	select {
	case <-v.release:
	case <-ctx.Done():
	}
	return driverpb.TakeOffResponse_builder{}.Build(), nil
}

// erroringVehicle is a ControlService fixture whose TakeOff always rejects the
// command with a specific gRPC status, for verifying dispatch propagates a
// vehicle's own RPC-level errors rather than masking them as a connectivity
// failure.
type erroringVehicle struct {
	driverpb.UnimplementedControlServiceServer
}

func (v *erroringVehicle) TakeOff(context.Context, *driverpb.TakeOffRequest) (*driverpb.TakeOffResponse, error) {
	return nil, status.Error(codes.FailedPrecondition, "vehicle not armed")
}

// startFixtureVehicle serves srv on a real loopback listener, torn down via
// t.Cleanup.
func startFixtureVehicle(t *testing.T, srv driverpb.ControlServiceServer) netip.AddrPort {
	t.Helper()

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listening for fixture vehicle: %v", err)
	}

	grpcServer := grpc.NewServer()
	driverpb.RegisterControlServiceServer(grpcServer, srv)
	go grpcServer.Serve(ln)
	t.Cleanup(grpcServer.Stop)

	addr, err := netip.ParseAddrPort(ln.Addr().String())
	if err != nil {
		t.Fatalf("parsing fixture vehicle addr %v: %v", ln.Addr(), err)
	}
	return addr
}

// startSwarmServer wires a swarm.SwarmServer with the given options up to a
// real SwarmService listener and returns a client dialed to it.
func startSwarmServer(t *testing.T, registry *swarm.Registry, opts ...swarm.Option) swarmpb.SwarmServiceClient {
	t.Helper()

	server := swarm.NewSwarmServer(registry, opts...)
	t.Cleanup(server.Close)

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listening for SwarmService: %v", err)
	}
	grpcServer := grpc.NewServer()
	swarmpb.RegisterSwarmServiceServer(grpcServer, server)
	go grpcServer.Serve(ln)
	t.Cleanup(grpcServer.Stop)

	conn, err := grpc.NewClient(ln.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatalf("dialing SwarmService: %v", err)
	}
	t.Cleanup(func() { conn.Close() })

	return swarmpb.NewSwarmServiceClient(conn)
}

func takeOff(t *testing.T, client swarmpb.SwarmServiceClient, vehicle string) *swarmpb.SwarmTakeOffResponse {
	t.Helper()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	stream, err := client.SwarmTakeOff(ctx, swarmpb.SwarmTakeOffRequest_builder{
		Vehicles: []string{vehicle},
		Request:  driverpb.TakeOffRequest_builder{}.Build(),
	}.Build())
	if err != nil {
		t.Fatalf("calling SwarmTakeOff: %v", err)
	}
	resp, err := stream.Recv()
	if err != nil {
		t.Fatalf("receiving SwarmTakeOff response: %v", err)
	}
	return resp
}

func TestServer_CallTimeoutIsolatesSlowVehicle(t *testing.T) {
	release := make(chan struct{}) // never closed: TakeOff blocks until the timeout fires
	defer close(release)
	addr := startFixtureVehicle(t, &slowVehicle{release: release})

	registry := swarm.NewRegistry()
	defer registry.Register("harpy", addr)()

	client := startSwarmServer(t, registry, swarm.WithCallTimeout(200*time.Millisecond))

	start := time.Now()
	resp := takeOff(t, client, "harpy")
	elapsed := time.Since(start)

	if codes.Code(resp.GetCode()) != codes.DeadlineExceeded {
		t.Errorf("code = %v, want DeadlineExceeded", codes.Code(resp.GetCode()))
	}
	if elapsed > 2*time.Second {
		t.Errorf("SwarmTakeOff took %s, want it bounded by the ~200ms call timeout, not the RPC's overall context", elapsed)
	}
}

func TestServer_PropagatesVehicleRPCError(t *testing.T) {
	addr := startFixtureVehicle(t, &erroringVehicle{})

	registry := swarm.NewRegistry()
	defer registry.Register("harpy", addr)()

	client := startSwarmServer(t, registry)

	resp := takeOff(t, client, "harpy")

	if codes.Code(resp.GetCode()) != codes.FailedPrecondition {
		t.Errorf("code = %v, want FailedPrecondition", codes.Code(resp.GetCode()))
	}
	if resp.GetDetails() != "vehicle not armed" {
		t.Errorf("details = %q, want %q", resp.GetDetails(), "vehicle not armed")
	}
}
