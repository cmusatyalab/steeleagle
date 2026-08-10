package main

import (
	"context"
	"net"
	"time"

	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// initialRegisterBackoff is the delay before the first reconnect attempt
// after a Register stream breaks.
const initialRegisterBackoff = 1 * time.Second

// maxRegisterBackoff caps the exponential backoff between reconnect attempts.
const maxRegisterBackoff = 30 * time.Second

// dialFunc dials out from a specific network identity — matches
// (*tailscale.Server).Dial's signature, so a vehicle's own tsnet node can be
// passed straight in. A nil dialFunc falls back to gRPC's default dialer.
type dialFunc func(ctx context.Context, network, addr string) (net.Conn, error)

// registerVehicle holds one vehicle registered with the swarm controller at
// addr for exactly as long as ctx is alive. It reconnects with backoff if the
// stream breaks (controller restart, network partition) while the vehicle
// itself keeps running. It returns only once ctx is canceled. dial, if
// non-nil, sources the connection from the vehicle's own tsnet node so the
// controller resolves this vehicle's address correctly.
func registerVehicle(ctx context.Context, addr, daemonName, name string, port int, dial dialFunc) {
	backoff := initialRegisterBackoff
	for ctx.Err() == nil {
		if err := register(ctx, addr, daemonName, name, port, dial); err != nil {
			log.Warn().Err(err).Str("vehicle", name).
				Dur("retry_in", backoff).
				Msg("registration with swarm controller failed, retrying")
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		backoff *= 2
		if backoff > maxRegisterBackoff {
			backoff = maxRegisterBackoff
		}
	}
}

// register dials the swarm controller, opens one Register stream for the
// vehicle, and blocks receiving keepalives until either the stream breaks or
// ctx is canceled. A nil error return means ctx was canceled cleanly.
func register(ctx context.Context, addr, daemonName, name string, port int, dial dialFunc) error {
	opts := []grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}
	if dial != nil {
		opts = append(opts, grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return dial(ctx, "tcp", addr)
		}))
	}
	conn, err := grpc.NewClient(addr, opts...)
	if err != nil {
		return err
	}
	defer conn.Close()

	client := swarmpb.NewRegistryServiceClient(conn)
	stream, err := client.Register(ctx, swarmpb.RegisterRequest_builder{
		DaemonName: daemonName,
		Name:       name,
		Port:       uint32(port),
	}.Build())
	if err != nil {
		return err
	}

	// client.Register only opens the local stream, so wait for registration
	// ack.
	firstRecv := true
	for {
		if _, err := stream.Recv(); err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return err
		}
		if firstRecv {
			log.Info().Str("vehicle", name).Str("controller", addr).Msg("registered with swarm controller")
			firstRecv = false
		}
	}
}
