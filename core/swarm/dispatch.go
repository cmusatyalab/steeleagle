package swarm

import (
	"context"
	"sync"
	"time"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// vehicleDialer produces a ready-to-use connection to the named vehicle,
// resolving its address and dialing/reusing a pooled connection as needed, and
// bounds how long any single proxied call to a vehicle may run.
type vehicleDialer interface {
	clientConn(vehicleName string) (*grpc.ClientConn, error)
	callTimeout() time.Duration
	logger() zerolog.Logger
}

// dispatch resolves+dials each named vehicle, invokes call against it
// concurrently under d's bounded per-call timeout, and streams one Resp per
// vehicle back to the caller as it completes. A vehicle that fails to resolve,
// dial, or errors on the proxied call still produces a Resp (via
// buildResponse), so a failure never aborts the overall RPC.
func dispatch[Req, DriverResp, Resp any](
	d vehicleDialer,
	rpcName string,
	vehicles []string,
	stream grpc.ServerStreamingServer[Resp],
	req *Req,
	sendRpc func(ctx context.Context, conn *grpc.ClientConn, req *Req) (*DriverResp, error),
	buildResp func(vehicle string, resp *DriverResp, err error) *Resp,
) error {
	ctx := stream.Context()
	log := d.logger()
	results := make(chan *Resp, len(vehicles))
	var wg sync.WaitGroup
	for _, vehicle := range vehicles {
		wg.Add(1)
		go func(vehicle string) {
			defer wg.Done()
			conn, err := d.clientConn(vehicle)
			var resp *DriverResp
			if err == nil {
				rpcCtx, cancel := context.WithTimeout(ctx, d.callTimeout())
				defer cancel()
				resp, err = sendRpc(rpcCtx, conn, req)
			}
			if err != nil {
				log.Warn().Str("vehicle", vehicle).Str("rpc", rpcName).Err(err).Msg("vehicle command failed")
			} else {
				log.Debug().Str("vehicle", vehicle).Str("rpc", rpcName).Msg("vehicle command dispatched")
			}
			results <- buildResp(vehicle, resp, err)
		}(vehicle)
	}
	go func() {
		wg.Wait()
		close(results)
	}()

	for resp := range results {
		if err := stream.Send(resp); err != nil {
			return err
		}
	}
	return nil
}

// statusOf extracts a gRPC status code and message from err, treating a nil
// err as success.
func statusOf(err error) (uint32, string) {
	if err == nil {
		return uint32(codes.OK), ""
	}
	st, ok := status.FromError(err)
	if !ok {
		return uint32(codes.Unknown), err.Error()
	}
	return uint32(st.Code()), st.Message()
}
