package daemon

import (
	"net"
	"strconv"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	uriel "github.com/cmusatyalab/uriel/go"
)

// startComputeServer starts the local compute service, a Uriel server that
// accepts remote clients on the LCS port and serves the running engines.
func (d *Daemon) startComputeServer() error {
	path, err := util.GetCredsDir()
	if err != nil {
		return err
	}
	addr := net.JoinHostPort(LcsBindHost, strconv.Itoa(d.Config.Daemon.Lcs))
	server, err := uriel.NewServer(
		d.Hostname,
		uriel.WithBindAddr(addr),
		uriel.WithIdentityDir(path),
	)
	if err != nil {
		return err
	}
	d.svcMu.RLock()
	defer d.svcMu.RUnlock()
	for _, svc := range d.services {
		if svc.category == daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE {
			if err := server.AddEngine(svc.name); err != nil {
				server.Close()
				return err
			}
		}
	}
	d.lcs = server
	d.log.Info().Str("address", addr).Msg("local compute service started")
	return nil
}

// stopComputeServer stops the local compute service, if it was started.
func (d *Daemon) stopComputeServer() {
	if d.lcs == nil {
		return
	}
	if err := d.lcs.Close(); err != nil {
		d.log.Error().Err(err).Msg("could not stop local compute service")
	}
	d.lcs = nil
}
