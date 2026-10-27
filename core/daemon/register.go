package daemon

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"strconv"
	"strings"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// orchStream is a registration stream to the orchestrator.
type orchStream = grpc.BidiStreamingClient[
	daemonpb.RegisterOrchestratorRequest,
	daemonpb.RegisterOrchestratorResponse,
]

// register connects a daemon to its orchestrator, retrying with backoff until
// it succeeds, then maintains a heartbeat to it in the background, reconnecting
// whenever the heartbeat breaks. No-op if no orchestrator is set.
func (d *Daemon) register() error {
	if d.Config.Daemon.Orchestrator == "" {
		return nil
	}
	stream, closeStream, err := d.connectWithBackoff(d.ctx)
	if err != nil {
		return err
	}
	d.log.Info().Str("orchestrator", d.Config.Daemon.Orchestrator).
		Msg("daemon connected to orchestrator")
	d.regWg.Go(func() {
		for {
			err := d.heartbeat(stream, closeStream)
			if d.ctx.Err() != nil {
				return
			}
			d.connected.Store(false)
			d.log.Warn().Err(err).Str("orchestrator", d.Config.Daemon.Orchestrator).
				Msg("lost connection to orchestrator, reconnecting")
			stream, closeStream, err = d.connectWithBackoff(d.ctx)
			if err != nil {
				return
			}
			d.log.Info().Str("orchestrator", d.Config.Daemon.Orchestrator).
				Msg("daemon reconnected to orchestrator")
		}
	})
	return nil
}

// connectWithBackoff connects to the orchestrator, retrying after a backoff
// that doubles from RegisterBackoffMin up to RegisterBackoffMax, until it
// succeeds or ctx is done.
func (d *Daemon) connectWithBackoff(ctx context.Context) (orchStream, func(), error) {
	backoff := RegisterBackoffMin
	for {
		stream, closeStream, err := d.connect(ctx)
		if err == nil {
			return stream, closeStream, nil
		}
		d.log.Warn().Err(err).Str("orchestrator", d.Config.Daemon.Orchestrator).
			Dur("retry", backoff).Msg("couldn't connect to orchestrator, retrying")
		select {
		case <-ctx.Done():
			return nil, nil, ctx.Err()
		case <-time.After(backoff):
		}
		backoff = min(backoff*2, RegisterBackoffMax)
	}
}

// connect opens a registration stream to the orchestrator, sends this
// daemon's services and hostname, and stores the orchestrator's answer as its
// orchestrator info. The orchestrator port defaults to this daemon's port. It
// returns the stream and a function that closes it.
func (d *Daemon) connect(ctx context.Context) (orchStream, func(), error) {
	port := strconv.Itoa(d.Config.Daemon.Port)
	if _, p, err := net.SplitHostPort(d.Config.Daemon.Orchestrator); err == nil {
		port = p
	}
	addrs, err := d.network.Resolve(ctx, d.orchestratorHost())
	if err != nil {
		return nil, nil, err
	}
	conn, err := grpc.NewClient(
		"passthrough:///"+net.JoinHostPort(addrs[0].String(), port),
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return d.network.Dial(ctx, "tcp", addr)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, nil, err
	}
	// The stream lives on the registration context, which outlives the
	// daemon's while it stops, but connecting stops with ctx
	streamCtx, cancel := context.WithCancel(d.regCtx)
	stopConnecting := context.AfterFunc(ctx, cancel)
	defer stopConnecting()
	closeStream := func() {
		cancel()
		conn.Close()
	}

	d.svcMu.RLock()
	services, err := d.serviceProtos()
	d.svcMu.RUnlock()
	if err != nil {
		closeStream()
		return nil, nil, err
	}
	// The stream is canceled if the orchestrator doesn't answer in time
	timer := time.AfterFunc(RegisterWait, cancel)
	defer timer.Stop()
	stream, err := daemonpb.NewDaemonServiceClient(conn).RegisterOrchestrator(streamCtx)
	if err == nil {
		err = stream.Send(daemonpb.RegisterOrchestratorRequest_builder{
			Services: services,
			Hostname: d.Hostname,
			Port:     int32(d.Config.Daemon.Port),
		}.Build())
	}
	var resp *daemonpb.RegisterOrchestratorResponse
	if err == nil {
		resp, err = stream.Recv()
	}
	if err != nil {
		closeStream()
		return nil, nil, err
	}

	remotes := make([]*daemonService, 0, len(resp.GetServices()))
	for _, p := range resp.GetServices() {
		s, err := serviceFromProto(p)
		if err != nil {
			closeStream()
			return nil, nil, fmt.Errorf("orchestrator service %q: %w", p.GetName(), err)
		}
		remotes = append(remotes, s)
	}
	d.orchMu.Lock()
	d.orch = &orchInfo{
		hostname: resp.GetHostname(),
		ip:       addrs[0].String(),
		lcsPort:  int(resp.GetLcsPort()),
		cert:     resp.GetCert(),
		services: remotes,
	}
	d.orchMu.Unlock()
	d.connected.Store(true)
	return stream, closeStream, nil
}

// heartbeat sends a heartbeat on the stream every HeartbeatInterval until the
// stream breaks, or the orchestrator doesn't answer within HeartbeatTimeout,
// then closes it and returns why it broke.
func (d *Daemon) heartbeat(stream orchStream, closeStream func()) error {
	defer closeStream()
	timer := time.AfterFunc(HeartbeatTimeout, closeStream)
	defer timer.Stop()
	go func() {
		ticker := time.NewTicker(HeartbeatInterval)
		defer ticker.Stop()
		for {
			select {
			case <-stream.Context().Done():
				return
			case <-ticker.C:
				if err := stream.Send(&daemonpb.RegisterOrchestratorRequest{}); err != nil {
					return
				}
			}
		}
	}()
	for {
		if _, err := stream.Recv(); err != nil {
			return err
		}
		timer.Reset(HeartbeatTimeout)
	}
}

// serveRegistration serves a registration stream from a child daemon, which
// has this daemon as its orchestrator. The stream opens with the child's
// registration, whose services must all be qualified with its IP, and is
// answered with this daemon's services. The child and its services are routes
// to it until the stream ends. After that, each empty request is answered
// with an empty response, until the child stops sending them for
// HeartbeatTimeout.
func (d *Daemon) serveRegistration(
	stream grpc.BidiStreamingServer[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse],
) error {
	ctx := stream.Context()
	caller, err := callerIp(ctx)
	if err != nil {
		return err
	}
	msgs, errs := receive(ctx, stream.Recv)
	timer := time.NewTimer(RegisterWait)
	defer timer.Stop()
	var req *daemonpb.RegisterOrchestratorRequest
	select {
	case req = <-msgs:
	case err := <-errs:
		return err
	case <-timer.C:
		return status.Error(codes.DeadlineExceeded, "no registration received")
	case <-d.ctx.Done():
		return status.Error(codes.Unavailable, "daemon shutting down")
	}

	if req.GetPort() < 1 || req.GetPort() > 65535 {
		return status.Errorf(codes.InvalidArgument, "invalid daemon port %d", req.GetPort())
	}
	// A daemon can only register its own services
	services := make([]*daemonService, 0, len(req.GetServices()))
	for _, p := range req.GetServices() {
		if !strings.HasPrefix(p.GetName(), caller+".") {
			return status.Errorf(codes.PermissionDenied,
				"service %q is not on the calling daemon %s", p.GetName(), caller)
		}
		s, err := serviceFromProto(p)
		if err != nil {
			return status.Errorf(codes.InvalidArgument, "service %q: %v", p.GetName(), err)
		}
		services = append(services, s)
	}
	d.svcMu.RLock()
	own, err := d.serviceProtos()
	d.svcMu.RUnlock()
	if err != nil {
		return status.Errorf(codes.Internal, "couldn't encode services: %v", err)
	}
	child, err := d.addRemote(caller, req.GetHostname(), req.GetPort(), services)
	if err != nil {
		return status.Errorf(codes.Internal, "couldn't connect to daemon: %v", err)
	}
	defer d.removeRemote(child)
	// Vehicles on the child reach this daemon's engines through its compute
	// service, trusting its cert
	resp := daemonpb.RegisterOrchestratorResponse_builder{
		Services: own,
		Hostname: d.Hostname,
		Cert:     d.cert,
		LcsPort:  int32(d.Config.Daemon.Lcs),
	}.Build()
	if err := stream.Send(resp); err != nil {
		return err
	}
	d.log.Info().Str("daemon", caller).Str("hostname", req.GetHostname()).
		Int("services", len(services)).Msg("daemon registered")

	for {
		timer.Reset(HeartbeatTimeout)
		select {
		case <-msgs:
			if err := stream.Send(&daemonpb.RegisterOrchestratorResponse{}); err != nil {
				return err
			}
		case err := <-errs:
			if errors.Is(err, io.EOF) {
				d.log.Info().Str("daemon", caller).Msg("daemon disconnected")
				return nil
			}
			return err
		case <-timer.C:
			d.log.Warn().Str("daemon", caller).Msg("daemon heartbeat timed out")
			return status.Error(codes.DeadlineExceeded, "heartbeat timed out")
		case <-d.ctx.Done():
			return status.Error(codes.Unavailable, "daemon shutting down")
		}
	}
}
