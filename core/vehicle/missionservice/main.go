// missionservice is a mission launcher: it stays running for the vehicle's
// whole lifetime, handling MissionService calls, while UploadMission stores a
// self-contained mission binary and StartMission execs it as a subprocess. The
// mission binary talks to the drone directly over the client socket it is
// provided.
package main

import (
	"context"
	"flag"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
)

func main() {
	logLevel := flag.String("log-level", zerolog.InfoLevel.String(), "log level: trace, debug, info, warn, error, fatal, panic, or disabled")
	flag.Parse()

	level, err := zerolog.ParseLevel(*logLevel)
	if err != nil {
		log.Fatal().Msgf("parsing -log-level: %v", err)
	}
	zerolog.SetGlobalLevel(level)

	listenSocket := os.Getenv(util.ListenSockEnv)
	if listenSocket == "" {
		log.Fatal().Msgf("%s not set", util.ListenSockEnv)
	}
	clientSocket := os.Getenv(util.ClientSockEnv)
	if clientSocket == "" {
		log.Fatal().Msgf("%s not set", util.ClientSockEnv)
	}

	runDir, err := os.MkdirTemp("", "missionservice-")
	if err != nil {
		log.Fatal().Err(err).Msg("creating run directory")
	}
	defer os.RemoveAll(runDir)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	ln, err := net.Listen("unix", listenSocket)
	if err != nil {
		log.Fatal().Err(err).Str("socket", listenSocket).Msg("listening on plugin socket")
	}

	srv := newServer(clientSocket, runDir)
	grpcServer := grpc.NewServer()
	missionpb.RegisterMissionServiceServer(grpcServer, srv)

	go func() {
		<-ctx.Done()
		log.Info().Msg("shutting down")
		srv.stop(context.Background())
		grpcServer.GracefulStop()
	}()

	log.Info().Str("socket", listenSocket).Msg("missionservice listening")
	if err := grpcServer.Serve(ln); err != nil {
		log.Fatal().Err(err).Msg("serving MissionService")
	}
}
