package daemon

import (
	"net"
	"strconv"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/vehicle"
	"github.com/cmusatyalab/uriel/go"
)

// availableEngines lists the engines that vehicles can use in their
// dataflows, by qualified name, with their types: the engines set up on this
// daemon, which are local, and the engines of the orchestrator's remote
// compute service that this daemon doesn't have, which are remote. Engines
// without an engine cap have no types, so they are left out. The caller must
// hold svcMu.
func (d *Daemon) availableEngines() map[string]vehicle.Engine {
	engines := make(map[string]vehicle.Engine)
	d.rcsMu.Lock()
	for name, cap := range d.rcsEngines {
		engines[name] = vehicle.Engine{Inputs: cap.Inputs, Result: cap.Result}
	}
	d.rcsMu.Unlock()
	for _, s := range d.services[daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE] {
		if s.setUp() && s.config.Engine != nil {
			engines[s.name] = vehicle.Engine{Inputs: s.config.Engine.Inputs, Result: s.config.Engine.Result, Local: true}
		}
	}
	return engines
}

// startUrielServer starts the local compute service, a Uriel server that
// accepts remote clients on the LCS port and serves the running engines, each
// at the endpoint named after it. An engine may start before or after the
// server.
func (d *Daemon) startUrielServer() error {
	// The identity is made before the server starts, so the server presents
	// the same cert that remote daemons are given
	identityDir, _, err := d.lcsIdentity()
	if err != nil {
		return err
	}
	addr := net.JoinHostPort(lcsBindHost, strconv.Itoa(d.Config.Daemon.Lcs))
	server, err := uriel.NewServer(d.Config.Daemon.Hostname,
		uriel.WithBindAddr(addr), uriel.WithIdentityDir(identityDir))
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
	d.uriel = server
	d.log.Info().Str("address", addr).Strs("engines", endpoints).
		Msg("local compute service started")
	return nil
}

// stopUrielServer stops the local compute service, if it was started.
func (d *Daemon) stopUrielServer() {
	if d.uriel == nil {
		return
	}
	if err := d.uriel.Close(); err != nil {
		d.log.Warn().Err(err).Msg("could not stop local compute service")
	}
	d.uriel = nil
}
