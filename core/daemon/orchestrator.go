package daemon

import (
	"context"
	"net"
	"net/netip"
	"strconv"
	"strings"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// registerOrchestrator registers this daemon as the orchestrator for the
// calling daemon at port. The daemon's IP and its vehicles, given as
// "{daemon IP}/{vehicle name}", become header routes to it, and the cert of
// this daemon's local compute service is returned. The IP of every vehicle
// must be the IP of the caller, so that a daemon can only register its own
// vehicles.
func (d *Daemon) registerOrchestrator(ctx context.Context, vehicles []string, port int32) (string, error) {
	caller, err := callerIp(ctx)
	if err != nil {
		return "", err
	}
	if port < 1 || port > 65535 {
		return "", status.Errorf(codes.InvalidArgument, "invalid daemon port %d", port)
	}
	for _, v := range vehicles {
		ip, name, ok := strings.Cut(v, "/")
		if !ok || name == "" {
			return "", status.Errorf(codes.InvalidArgument, "vehicle %q is not of the form {daemon IP}/{vehicle name}", v)
		}
		if addr, err := netip.ParseAddr(ip); err != nil || addr.Unmap() != caller {
			return "", status.Errorf(codes.PermissionDenied, "vehicle %q is not on the calling daemon %s", v, caller)
		}
	}
	cert, err := d.lcsCert()
	if err != nil {
		return "", status.Errorf(codes.Internal, "could not get local compute cert: %v", err)
	}

	conn, err := d.remoteConn(caller, port)
	if err != nil {
		return "", status.Error(codes.Internal, err.Error())
	}
	// The daemon is addressed by its IP, and each vehicle by its name
	d.router.AddHeaderRoute(caller.String(), conn)
	for _, v := range vehicles {
		d.router.AddHeaderRoute(v, conn)
	}
	d.log.Info().Str("daemon", caller.String()).Strs("vehicles", vehicles).
		Msg("registered as orchestrator")
	return cert, nil
}

// registerWithOrchestrator registers this daemon's vehicles with the
// orchestrator as "{daemon IP}/{vehicle name}", along with the daemon port, and
// keeps the address and cert of the remote compute service it returns for
// starting vehicles.
func (d *Daemon) registerWithOrchestrator(ctx context.Context) error {
	host, port := d.Config.Daemon.Orchestrator, strconv.Itoa(d.Config.Daemon.Port)
	if h, p, err := net.SplitHostPort(host); err == nil {
		host, port = h, p
	}
	addrs, err := d.network.Resolve(ctx, host)
	if err != nil {
		return err
	}
	orchestrator := addrs[0]
	self, err := d.network.LocalAddr(ctx, orchestrator)
	if err != nil {
		return err
	}
	// Calls the orchestrator routes here by this daemon's IP are for its own
	// services; the route is added first, so that none are rejected once the
	// orchestrator has the route back here
	d.router.AddHeaderRoute(self.String(), d.serverConn)
	var vehicles []string
	for _, name := range d.vehicleNames() {
		vehicles = append(vehicles, self.String()+"/"+name)
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
		return err
	}
	defer conn.Close()
	ctx, cancel := context.WithTimeout(ctx, orchestratorTimeout)
	defer cancel()
	resp, err := daemonpb.NewDaemonServiceClient(conn).RegisterOrchestrator(ctx,
		daemonpb.RegisterOrchestratorRequest_builder{
			Vehicles: vehicles,
			Port:     int32(d.Config.Daemon.Port),
		}.Build())
	if err != nil {
		return err
	}

	// Set RCS information
	d.selfAddr = self
	d.rcsAddr = net.JoinHostPort(orchestrator.String(), strconv.Itoa(int(resp.GetPort())))
	d.rcsCert = resp.GetCert()
	d.log.Info().Str("orchestrator", d.Config.Daemon.Orchestrator).Strs("vehicles", vehicles).
		Str("rcs", d.rcsAddr).Msg("registered with orchestrator")
	return nil
}

// addOrchestratorToAcl grants AdminCode to the orchestrator's IP addresses on
// the daemon network.
func (d *Daemon) addOrchestratorToAcl(ctx context.Context, acl *listener.Acl) error {
	host := d.Config.Daemon.Orchestrator
	if h, _, err := net.SplitHostPort(host); err == nil {
		host = h
	}
	addrs, err := d.network.Resolve(ctx, host)
	if err != nil {
		return err
	}
	for _, addr := range addrs {
		if err := acl.AddIp(addr.String(), listener.AdminCode); err != nil {
			return err
		}
	}
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
	if conn, ok := d.remotes[ip]; ok {
		if conn.Target() == target {
			return conn, nil
		}
		conn.Close()
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
		d.remotes = make(map[netip.Addr]*grpc.ClientConn)
	}
	d.remotes[ip] = conn
	return conn, nil
}

// closeRemotes closes the connections to all registered remote daemons.
func (d *Daemon) closeRemotes() {
	d.remotesMu.Lock()
	defer d.remotesMu.Unlock()
	for ip, conn := range d.remotes {
		conn.Close()
		delete(d.remotes, ip)
	}
}
