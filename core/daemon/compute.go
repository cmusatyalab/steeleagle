package daemon

import (
	"net"
	"strconv"

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
		d.Config.Daemon.Hostname,
		uriel.WithBindAddr(addr),
		uriel.WithIdentityDir(path),
	)
	if err != nil {
		return err
	}
	for endpoint, _ := range d.engines {
		if err := server.AddEngine(endpoint); err != nil {
			server.Close()
			return err
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
