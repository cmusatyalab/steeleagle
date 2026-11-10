package daemon

import (
	"net"
	"strconv"

	uriel "github.com/cmusatyalab/uriel/go"
)

// startMetricsServer serves Uriel's Prometheus metrics at /metrics on the
// configured metrics port, bound to the network's address like the compute
// server. It does nothing if no port is configured. It must run before the
// daemon creates Uriel clients and servers, since Uriel records no metrics for
// those created earlier. Uriel serves them for the life of the process, which
// is the life of the daemon: a restart exits it.
func (d *Daemon) startMetricsServer() error {
	port := d.Config.Daemon.MetricsPort
	if port == 0 {
		return nil
	}
	host := d.network.BindHost()
	if host == "" {
		host = MetricsBindHost
	}
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	if err := uriel.ServeMetrics(addr); err != nil {
		return err
	}
	d.log.Info().Str("address", addr).Msg("serving metrics")
	return nil
}
