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
	SteeleagleRef string `toml:"steeleagle-ref"` // see config.template.toml's comment
}

func main() {
	path := flag.String("config", "config.toml", "path to the TOML config file")
	flag.Parse()

	data, err := os.ReadFile(*path)
	if err != nil {
		log.Fatal().Msgf("reading %s: %v", *path, err)
	}
	var cfg Config
	md, err := toml.Decode(string(data), &cfg)
	if err != nil {
		log.Fatal().Msgf("parsing TOML: %v", err)
	}
	if undecoded := md.Undecoded(); len(undecoded) > 0 {
		fmt.Println("warning: unrecognized keys in config:")
		for _, k := range undecoded {
			fmt.Printf("  - %s\n", k)
		}
	}
	if cfg.ListenPort == 0 {
		log.Fatal().Msg("listen-port is not set in config")
	}

	// Resolving the ref once here (rather than passing cfg.SteeleagleRef
	// straight through) matters more for a long-lived daemon than for the
	// one-shot CLI: ResolveSteeleagleRef's own doc notes the module
	// proxy's branch->commit cache can lag behind the real branch tip, and
	// this service resolves once at startup and then serves for days.
	// Matches sdk/cmd/compiler/main.go's own -steeleagle-ref handling,
	// including only resolving when a ref was actually given.
	var resolvedRef string
	if cfg.SteeleagleRef != "" {
		resolvedRef, err = compiler.ResolveSteeleagleRef(cfg.SteeleagleRef)
		if err != nil {
			log.Fatal().Msgf("resolving steeleagle-ref %s: %v", cfg.SteeleagleRef, err)
		}
	}

	log.Info().Msg("loading SDK type registry (this runs \"go get\"/\"go build\" once at startup)")
	svc, err := dslcompiler.NewService(compiler.EnsureBaseImports(nil), resolvedRef)
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
