package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os/signal"
	"syscall"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

func main() {
	controlPort := flag.Int("control-port", DefaultControlPort, "port DaemonService listens on")
	logLevel := flag.String("log-level", zerolog.InfoLevel.String(), "log level: trace, debug, info, warn, error, fatal, panic, or disabled")
	flag.Parse()

	level, err := zerolog.ParseLevel(*logLevel)
	if err != nil {
		log.Fatal().Msgf("parsing -log-level: %v", err)
	}
	zerolog.SetGlobalLevel(level)

	sigCtx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	ctx, cancel := context.WithCancel(sigCtx)
	defer cancel()

	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", *controlPort))
	if err != nil {
		log.Fatal().Msgf("listening on control port %d: %v", *controlPort, err)
	}

	d := newDaemon(ctx, cancel)

	grpcServer := grpc.NewServer()
	eagledpb.RegisterDaemonServiceServer(grpcServer, d)
	// Set before any persisted config is loaded below, so ensureNetwork can
	// also serve DaemonService over eagled's own tsnet node as soon as it
	// joins the tailnet, not just main's plain-TCP listener.
	d.grpcServer = grpcServer
	d.controlPort = *controlPort

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
	grpcServer.GracefulStop()
}
