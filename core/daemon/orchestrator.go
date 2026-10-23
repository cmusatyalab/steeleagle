package daemon

import (
	"context"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"maps"
	"math/rand/v2"
	"net"
	"net/netip"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// remoteInfo is a remote daemon registered with this daemon as its
// orchestrator.
type remoteInfo struct {
	conn    *grpc.ClientConn // connection to the remote daemon
	streams int              // open registration streams; a remote with none is disconnected
}

// registration is the state of this daemon's registration with its
// orchestrator, kept across attempts to register.
type registration struct {
	acl        *listener.Acl       // main listener ACL, which grants the orchestrator AdminCode
	allowed    map[netip.Addr]bool // orchestrator IPs already granted AdminCode
	registered chan struct{}       // closed after the first handshake
	once       sync.Once           // closes registered
}

// newRegistration returns the state of a registration with the orchestrator,
// which grants the orchestrator AdminCode on acl once it is resolved.
func newRegistration(acl *listener.Acl) *registration {
	return &registration{acl: acl, allowed: make(map[netip.Addr]bool), registered: make(chan struct{})}
}

// allow grants AdminCode to the orchestrator's IP addresses on the daemon
// network, if they weren't already.
func (r *registration) allow(addrs []netip.Addr) {
	for _, addr := range addrs {
		if r.allowed[addr] {
			continue
		}
		if err := r.acl.AddIp(addr.String(), listener.AdminCode); err == nil {
			r.allowed[addr] = true
		}
	}
}

// serveRegistration serves a registration stream from a daemon that has this
// daemon as its orchestrator. The stream opens with the daemon's registration,
// answered with this daemon's remote compute service, and is then a heartbeat:
// each empty request is answered with an empty response.
func (d *Daemon) serveRegistration(
	stream grpc.BidiStreamingServer[daemonpb.RegisterOrchestratorRequest, daemonpb.RegisterOrchestratorResponse],
) error {
	ctx := stream.Context()
	caller, err := callerIp(ctx)
	if err != nil {
		return err
	}
	msgs, errs := receive(ctx, stream.Recv)
	timer := time.NewTimer(heartbeatTimeout)
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
	if !req.HasRegistration() {
		return status.Error(codes.InvalidArgument, "the first request must be a registration")
	}
	reg := req.GetRegistration()
	compute, err := d.registerOrchestrator(caller, reg.GetVehicles(), reg.GetPort())
	if err != nil {
		return err
	}
	if err := stream.Send(daemonpb.RegisterOrchestratorResponse_builder{Compute: compute}.Build()); err != nil {
		return err
	}
	d.trackRemote(caller, 1)
	defer d.trackRemote(caller, -1)
	d.log.Info().Str("daemon", caller.String()).Strs("vehicles", reg.GetVehicles()).
		Msg("registered as orchestrator")

	for {
		timer.Reset(heartbeatTimeout)
		select {
		case req := <-msgs:
			if req.HasRegistration() {
				return status.Error(codes.InvalidArgument, "registration already received")
			}
			if err := stream.Send(&daemonpb.RegisterOrchestratorResponse{}); err != nil {
				return err
			}
		case err := <-errs:
			if errors.Is(err, io.EOF) {
				d.log.Info().Str("daemon", caller.String()).Msg("remote daemon disconnected")
				return nil
			}
			return err
		case <-timer.C:
			d.log.Warn().Str("daemon", caller.String()).Msg("remote daemon heartbeat timed out")
			return status.Error(codes.DeadlineExceeded, "heartbeat timed out")
		case <-d.ctx.Done():
			return status.Error(codes.Unavailable, "daemon shutting down")
		}
	}
}

// registerOrchestrator registers this daemon as the orchestrator for the
// calling daemon at port. The daemon's IP and its vehicles, given by their
// qualified names, "{daemon IP}.{vehicle name}", become header routes to it.
func (d *Daemon) registerOrchestrator(caller netip.Addr, vehicles []string, port int32) (*daemonpb.RemoteCompute, error) {
	if port < 1 || port > 65535 {
		return nil, status.Errorf(codes.InvalidArgument, "invalid daemon port %d", port)
	}
	for _, v := range vehicles {
		name, ok := strings.CutPrefix(v, caller.String()+".")
		if !ok {
			return nil, status.Errorf(codes.PermissionDenied, "vehicle %q is not on the calling daemon %s", v, caller)
		}
		if name == "" {
			return nil, status.Errorf(codes.InvalidArgument, "vehicle %q has no name", v)
		}
	}
	cert, err := d.lcsCert()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "could not get local compute cert: %v", err)
	}

	conn, err := d.remoteConn(caller, port)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	// The daemon is addressed by its IP, and each vehicle by its name
	d.router.AddHeaderRoute(caller.String(), conn)
	for _, v := range vehicles {
		d.router.AddHeaderRoute(v, conn)
	}
	engines := make(map[string][]byte)
	for _, s := range d.selectServices(func(s *serviceInfo) bool {
		return s.category == daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE && s.setUp() && s.config.Engine != nil
	}) {
		engines[s.name] = s.toml
	}
	return daemonpb.RemoteCompute_builder{
		Cert:    cert,
		Port:    int32(d.Config.Daemon.Lcs),
		Engines: engines,
	}.Build(), nil
}

// maintainRegistration keeps this daemon registered with its orchestrator
// until ctx is done. Whenever an attempt to register fails, or the
// registration stream dies, it registers again after a backoff that doubles
// from registerBackoffMin up to registerBackoffMax, and starts over once a
// handshake succeeds.
func (d *Daemon) maintainRegistration(ctx context.Context, r *registration) {
	backoff := registerBackoffMin
	for {
		handshook, err := d.registerWithOrchestrator(ctx, r)
		if ctx.Err() != nil {
			return
		}
		if handshook {
			backoff = registerBackoffMin
		}
		// Jitter keeps daemons that lost the orchestrator together from
		// registering again together
		wait := backoff/2 + rand.N(backoff/2+1)
		d.log.Warn().Err(err).Str("orchestrator", d.Config.Daemon.Orchestrator).Dur("retry", wait).
			Msg("not registered with orchestrator, retrying")
		select {
		case <-ctx.Done():
			return
		case <-time.After(wait):
		}
		backoff = min(backoff*2, registerBackoffMax)
	}
}

// registerWithOrchestrator registers this daemon's vehicles with the
// orchestrator by their qualified names, along with the daemon port, and keeps
// the address and cert of the remote compute service it returns, and the
// engines it serves, for starting vehicles. It then sends heartbeats until the
// stream dies or ctx is done, and reports whether the handshake succeeded.
func (d *Daemon) registerWithOrchestrator(ctx context.Context, r *registration) (bool, error) {
	host, port := d.Config.Daemon.Orchestrator, strconv.Itoa(d.Config.Daemon.Port)
	if h, p, err := net.SplitHostPort(host); err == nil {
		host, port = h, p
	}
	addrs, err := d.network.Resolve(ctx, host)
	if err != nil {
		return false, err
	}
	r.allow(addrs)
	orchestrator := addrs[0]
	var vehicles []string
	for _, s := range d.selectServices(func(s *serviceInfo) bool {
		return s.category == daemonpb.ServiceCategory_SERVICE_CATEGORY_VEHICLE && s.setUp()
	}) {
		vehicles = append(vehicles, s.name)
	}

	// Dial through the current network
	conn, err := grpc.NewClient(
		"passthrough:///"+net.JoinHostPort(orchestrator.String(), port),
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return d.network.Dial(ctx, "tcp", addr)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return false, err
	}
	defer conn.Close()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	stream, err := daemonpb.NewDaemonServiceClient(conn).RegisterOrchestrator(ctx)
	if err != nil {
		return false, err
	}
	registration := daemonpb.DaemonRegistration_builder{Vehicles: vehicles, Port: int32(d.Config.Daemon.Port)}.Build()
	if err := stream.Send(daemonpb.RegisterOrchestratorRequest_builder{Registration: registration}.Build()); err != nil {
		return false, err
	}
	msgs, errs := receive(ctx, stream.Recv)
	timer := time.NewTimer(orchestratorTimeout)
	defer timer.Stop()
	var resp *daemonpb.RegisterOrchestratorResponse
	select {
	case resp = <-msgs:
	case err := <-errs:
		return false, err
	case <-timer.C:
		return false, fmt.Errorf("orchestrator did not answer the registration")
	}
	if err := d.setRcs(orchestrator, resp.GetCompute()); err != nil {
		return false, err
	}
	r.once.Do(func() { close(r.registered) })
	d.log.Info().Str("orchestrator", d.Config.Daemon.Orchestrator).Strs("vehicles", vehicles).
		Msg("registered with orchestrator")

	// The orchestrator answers each heartbeat, so a stream that goes quiet
	// is dead even if the connection hasn't noticed yet
	ticker := time.NewTicker(heartbeatInterval)
	defer ticker.Stop()
	timer.Reset(heartbeatTimeout)
	for {
		select {
		case <-ctx.Done():
			return true, ctx.Err()
		case <-msgs:
			timer.Reset(heartbeatTimeout)
		case err := <-errs:
			if errors.Is(err, io.EOF) {
				err = fmt.Errorf("orchestrator closed the registration stream")
			}
			return true, err
		case <-ticker.C:
			if err := stream.Send(&daemonpb.RegisterOrchestratorRequest{}); err != nil {
				return true, err
			}
		case <-timer.C:
			return true, fmt.Errorf("orchestrator heartbeat timed out")
		}
	}
}

// setRcs keeps the remote compute service of the orchestrator at addr for
// starting vehicles. Engines without an engine cap have no types, so they
// can't be used and are left out.
func (d *Daemon) setRcs(addr netip.Addr, compute *daemonpb.RemoteCompute) error {
	if compute == nil {
		return fmt.Errorf("orchestrator answered the registration without its remote compute service")
	}
	// The cert comes as PEM, but Uriel takes DER
	block, _ := pem.Decode([]byte(compute.GetCert()))
	if block == nil || block.Type != "CERTIFICATE" {
		return fmt.Errorf("orchestrator returned an invalid remote compute cert")
	}
	engines := make(map[string]config.EngineCap)
	var names []string
	for name, content := range compute.GetEngines() {
		cfg, err := config.ParsePluginConfigFromBytes(content)
		if err != nil || cfg.Engine == nil {
			d.log.Warn().Err(err).Str("engine", name).Msg("ignoring remote engine without an engine cap")
			continue
		}
		engines[name] = *cfg.Engine
		names = append(names, name)
	}
	d.rcsMu.Lock()
	defer d.rcsMu.Unlock()
	d.rcsAddr = net.JoinHostPort(addr.String(), strconv.Itoa(int(compute.GetPort())))
	d.rcsCert = block.Bytes
	d.rcsEngines = engines
	d.log.Info().Str("rcs", d.rcsAddr).Strs("engines", names).Msg("remote compute service set")
	return nil
}

// remoteConn returns the client connection to the remote daemon at ip and
// port, creating it on first use. There is one connection per IP, so a daemon
// that registers again on another port replaces its old connection.
// Connections are dialed through the daemon network.
func (d *Daemon) remoteConn(ip netip.Addr, port int32) (*grpc.ClientConn, error) {
	d.remotesMu.Lock()
	defer d.remotesMu.Unlock()
	target := "passthrough:///" + net.JoinHostPort(ip.String(), strconv.Itoa(int(port)))
	remote, ok := d.remotes[ip]
	if ok && remote.conn.Target() == target {
		return remote.conn, nil
	}
	conn, err := grpc.NewClient(
		target,
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return d.network.Dial(ctx, "tcp", addr)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, err
	}
	if d.remotes == nil {
		d.remotes = make(map[netip.Addr]*remoteInfo)
	}
	if ok {
		// Open streams belong to the daemon, not the connection
		remote.conn.Close()
		remote.conn = conn
	} else {
		d.remotes[ip] = &remoteInfo{conn: conn}
	}
	return conn, nil
}

// listRemoteServices lists the services of every registered remote daemon,
// calling them concurrently, in the order of their IPs. The IPs of remote
// daemons that are disconnected, or that fail to answer within
// remoteListTimeout, are returned as unavailable, so that the rest are still
// listed, along with those that remote orchestrators couldn't reach.
func (d *Daemon) listRemoteServices(ctx context.Context) ([]*daemonpb.ActiveService, []string) {
	d.remotesMu.Lock()
	ips := slices.SortedFunc(maps.Keys(d.remotes), netip.Addr.Compare)
	conns := make([]*grpc.ClientConn, len(ips))
	for i, ip := range ips {
		// Disconnected daemons aren't called, since they can't answer
		if d.remotes[ip].streams > 0 {
			conns[i] = d.remotes[ip].conn
		}
	}
	d.remotesMu.Unlock()

	listed := make([][]*daemonpb.ActiveService, len(ips))
	nested := make([][]string, len(ips))
	reached := make([]bool, len(ips))
	var wg sync.WaitGroup
	for i, ip := range ips {
		if conns[i] == nil {
			continue
		}
		wg.Go(func() {
			// The remote routes its own IP to its own services
			ctx, cancel := context.WithTimeout(router.Embed(ctx, ip.String()), remoteListTimeout)
			defer cancel()
			resp, err := daemonpb.NewDaemonServiceClient(conns[i]).ListServices(ctx, &daemonpb.ListServicesRequest{})
			if err != nil {
				d.log.Warn().Err(err).Str("daemon", ip.String()).Msg("could not list remote services")
				return
			}
			listed[i], nested[i], reached[i] = resp.GetServices(), resp.GetUnavailable(), true
		})
	}
	wg.Wait()
	var unavailable []string
	for i, ip := range ips {
		if !reached[i] {
			unavailable = append(unavailable, ip.String())
		}
		unavailable = append(unavailable, nested[i]...)
	}
	return slices.Concat(listed...), unavailable
}

// trackRemote adds delta to the number of open registration streams of the
// remote daemon at ip.
func (d *Daemon) trackRemote(ip netip.Addr, delta int) {
	d.remotesMu.Lock()
	defer d.remotesMu.Unlock()
	if remote, ok := d.remotes[ip]; ok {
		remote.streams += delta
	}
}

// closeRemotes closes the connections to all registered remote daemons.
func (d *Daemon) closeRemotes() {
	d.remotesMu.Lock()
	defer d.remotesMu.Unlock()
	for ip, remote := range d.remotes {
		remote.conn.Close()
		delete(d.remotes, ip)
	}
}

// receive reads messages from recv on its own goroutine until it fails or ctx
// is done, so that they can be waited for with a timeout. The error recv
// fails with is sent on the error channel.
func receive[T any](ctx context.Context, recv func() (T, error)) (<-chan T, <-chan error) {
	msgs := make(chan T)
	errs := make(chan error, 1)
	go func() {
		for {
			msg, err := recv()
			if err != nil {
				errs <- err
				return
			}
			select {
			case msgs <- msg:
			case <-ctx.Done():
				return
			}
		}
	}()
	return msgs, errs
}
