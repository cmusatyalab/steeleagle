package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	stdlog "log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	gabriel "github.com/cmusatyalab/gabriel/go"
	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/cmusatyalab/steeleagle/cmd/eagled/logstore"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

// shutdownGracePeriod bounds how long a shutdown waits for in-flight RPCs
// (e.g. a Configure call still spawning a vehicle) to finish on their own
// before forcing the gRPC server closed, so a single wedged RPC can't hang
// RestartDaemon/ResetConfig or a systemd stop forever.
const shutdownGracePeriod = 30 * time.Second

func main() {
	controlPort := flag.Int("control-port", DefaultControlPort, "port DaemonService listens on")
	metricsPort := flag.Int("metrics-port", 0, "port to serve Prometheus metrics on, at "+metricsPath+"; 0 serves none")
	gabrielMetricsPort := flag.Int("gabriel-metrics-port", 0, "port for Gabriel to serve its own Prometheus metrics on, at "+metricsPath+"; 0 serves none")
	gabrielWheel := flag.String("gabriel-wheel", "", "Gabriel's Python wheel, built from the same Gabriel commit as eagled, for plugins to install; plugins' install.sh get its path as $"+GabrielWheelEnv)
	logLevel := flag.String("log-level", zerolog.InfoLevel.String(), "log level: trace, debug, info, warn, error, fatal, panic, or disabled")
	flag.Parse()

	level, err := zerolog.ParseLevel(*logLevel)
	if err != nil {
		log.Fatal().Msgf("parsing -log-level: %v", err)
	}
	zerolog.SetGlobalLevel(level)

	// Absolute, since install.sh runs in the plugin's own directory.
	wheel, err := absoluteGabrielWheel(*gabrielWheel)
	if err != nil {
		log.Fatal().Msgf("-gabriel-wheel: %v", err)
	}

	logs := logstore.Open(logstore.Options{Dir: logDir()})
	daemonLog := logs.Writer("daemon")
	log.Logger = zerolog.New(zerolog.MultiLevelWriter(os.Stderr, daemonLog)).With().Timestamp().Logger()
	// tsnet and other libraries write through stdlib log, not zerolog.
	stdlog.SetOutput(io.MultiWriter(os.Stderr, daemonLog))

	sigCtx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	ctx, cancel := context.WithCancel(sigCtx)
	defer cancel()

	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", *controlPort))
	if err != nil {
		log.Fatal().Msgf("listening on control port %d: %v", *controlPort, err)
	}

	if *metricsPort != 0 {
		serveMetrics(ctx, *metricsPort)
	}
	// Before any vehicle starts its Gabriel client, whose metrics are
	// recorded only from then on.
	if *gabrielMetricsPort != 0 {
		if err := gabriel.ServeMetrics(fmt.Sprintf("0.0.0.0:%d", *gabrielMetricsPort)); err != nil {
			log.Fatal().Msgf("serving Gabriel's metrics on port %d: %v", *gabrielMetricsPort, err)
		}
		log.Info().Int("port", *gabrielMetricsPort).Msgf("Gabriel serving Prometheus metrics on port %d", *gabrielMetricsPort)
	}

	d := newDaemon(ctx, cancel, logs)

	grpcServer := grpc.NewServer()
	eagledpb.RegisterDaemonServiceServer(grpcServer, d)
	d.grpcServer = grpcServer
	d.controlPort = *controlPort
	d.gabrielWheel = wheel

	if err := d.loadPersistedInstalled(); err != nil {
		log.Error().Err(err).Msg("could not reload persisted plugin refs")
	}
	if err := d.loadPersistedNetwork(); err != nil {
		log.Error().Err(err).Msg("could not reload persisted network config")
	}
	if err := d.loadPersisted(); err != nil {
		log.Error().Err(err).Msg("could not reload persisted config")
	}

	go func() {
		log.Info().Int("port", *controlPort).Msgf("DaemonService listening on port %d", *controlPort)
		if err := grpcServer.Serve(ln); err != nil {
			log.Error().Err(err).Msg("DaemonService exited")
		}
	}()

	<-ctx.Done()
	log.Info().Msg("shutting down")

	stopped := make(chan struct{})
	go func() {
		grpcServer.GracefulStop()
		close(stopped)
	}()
	select {
	case <-stopped:
	case <-time.After(shutdownGracePeriod):
		log.Warn().Dur("grace_period", shutdownGracePeriod).Msg("graceful stop timed out, forcing shutdown")
		grpcServer.Stop()
		<-stopped
	}
}

// absoluteGabrielWheel returns wheel's absolute path, after checking that it
// exists, or "" if no wheel was given.
func absoluteGabrielWheel(wheel string) (string, error) {
	if wheel == "" {
		return "", nil
	}
	if _, err := os.Stat(wheel); err != nil {
		return "", err
	}
	return filepath.Abs(wheel)
}

// logDir returns the directory eagled persists logs under. If the data
// directory can't be resolved it returns "", which makes the store disable
// persistence (with one warning) while live streaming keeps working.
func logDir() string {
	dataDir, err := util.GetDataDir()
	if err != nil {
		fmt.Fprintf(os.Stderr, "eagled: log persistence disabled, cannot resolve data dir: %v\n", err)
		return ""
	}
	return filepath.Join(dataDir, "logs")
}
