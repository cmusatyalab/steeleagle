package daemon

import (
	"net"
	"strconv"

	gabriel "github.com/cmusatyalab/gabriel/go"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
)

// startGabrielServer starts the local compute service, a Gabriel server that
// accepts remote clients on the LCS port and serves the running engines, each
// at the endpoint named after it. An engine may start before or after the
// server.
func (d *Daemon) startGabrielServer() error {
	// The identity is made before the server starts, so the server presents
	// the same cert that remote daemons are given
	identityDir, _, err := d.lcsIdentity()
	if err != nil {
		return err
	}
	addr := net.JoinHostPort(lcsBindHost, strconv.Itoa(d.Config.Daemon.Lcs))
	server, err := gabriel.NewServer(d.Config.Daemon.Hostname,
		gabriel.WithBindAddr(addr), gabriel.WithIdentityDir(identityDir))
	if err != nil {
		return err
	}
	var endpoints []string
	for _, s := range d.selectServices(func(s *serviceInfo) bool {
		return s.category == daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE && s.running()
	}) {
		endpoints = append(endpoints, s.name)
	}
	for _, endpoint := range endpoints {
		if err := server.AddEngine(endpoint); err != nil {
			server.Close()
			return err
		}
	}
	d.gabriel = server
	d.log.Info().Str("address", addr).Strs("engines", endpoints).
		Msg("local compute service started")
	return nil
}

// stopGabrielServer stops the local compute service, if it was started.
func (d *Daemon) stopGabrielServer() {
	if d.gabriel == nil {
		return
	}
	if err := d.gabriel.Close(); err != nil {
		d.log.Warn().Err(err).Msg("could not stop local compute service")
	}
	d.gabriel = nil
}
