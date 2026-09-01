// cmd/dslcompiler/main.go
package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/BurntSushi/toml"
	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/core/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

// Config models the top-level document, matching cmd/swarm/main.go's
// config-loading convention (BurntSushi/toml, a -config flag defaulting
// to "config.toml").
type Config struct {
	ListenPort    int    `toml:"listen-port"`
	SteeleagleRef string `toml:"steeleagle-ref"` // see config.toml.template's comment
}

func main() {
	path := flag.String("config", "config.toml", "path to the TOML config file")
	flag.Parse()

	data, err := os.ReadFile(*path)
	if err != nil {
		log.Fatal().Msgf("reading %s: %v", *path, err)
	}
	var cfg Config
	if _, err := toml.Decode(string(data), &cfg); err != nil {
		log.Fatal().Msgf("parsing TOML: %v", err)
	}

	log.Info().Msg("loading SDK type registry (this runs \"go get\"/\"go build\" once at startup)")
	svc, err := dslcompiler.NewService(compiler.EnsureBaseImports(nil), cfg.SteeleagleRef)
	if err != nil {
		log.Fatal().Msgf("loading SDK registry: %v", err)
	}
	defer svc.Close()
	log.Info().Msg("SDK type registry loaded")

	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.ListenPort))
	if err != nil {
		log.Fatal().Msgf("listening on port %d: %v", cfg.ListenPort, err)
	}

	grpcServer := grpc.NewServer()
	dslcompilerpb.RegisterDslCompilerServiceServer(grpcServer, svc)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Info().Msgf("DslCompilerService listening on :%d", cfg.ListenPort)
		if err := grpcServer.Serve(ln); err != nil {
			log.Error().Msgf("DslCompilerService server exited: %v", err)
		}
	}()

	<-ctx.Done()
	log.Info().Msg("shutting down")
	grpcServer.GracefulStop()
}
