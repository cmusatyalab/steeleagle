package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/BurntSushi/toml"
	swarmpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/swarm"
	"github.com/cmusatyalab/steeleagle/core/swarm"
	"github.com/cmusatyalab/steeleagle/internal/tailscale"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

// TailscaleConfig models the [tailscale] table.
type TailscaleConfig struct {
	Hostname   string `toml:"hostname"`
	AuthKeyEnv string `toml:"authkey-env,omitempty"`
}

// Config models the top-level document.
type Config struct {
	ListenPort     int             `toml:"listen-port"`                // SwarmService, GCS-facing (tailnet)
	GCSPlainListen bool            `toml:"gcs-plain-listen,omitempty"` // whether to bind SwarmService on ListenPort as plain TCP outside tsnet
	VehiclePort    int             `toml:"vehicle-port"`               // RegistryService, eagled-facing (tailnet)
	CallTimeout    string          `toml:"call-timeout,omitempty"`     // Vehicle RPC timeout
	Tailscale      TailscaleConfig `toml:"tailscale"`                  // Tailscale config
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

	var opts []swarm.Option
	if cfg.CallTimeout != "" {
		d, err := time.ParseDuration(cfg.CallTimeout)
		if err != nil {
			log.Fatal().Msgf("parsing call-timeout: %v", err)
		}
		opts = append(opts, swarm.WithCallTimeout(d))
	}

	authKey := ""
	if cfg.Tailscale.AuthKeyEnv != "" {
		authKey = os.Getenv(cfg.Tailscale.AuthKeyEnv)
	}
	ts, err := tailscale.NewServer(cfg.Tailscale.Hostname, authKey)
	if err != nil {
		log.Fatal().Msgf("starting tailscale: %v", err)
	}
	defer ts.Close()
	opts = append(opts, swarm.WithDialer(ts.Dial))

	registry := swarm.NewRegistry()
	registryServer := swarm.NewRegistryServer(registry)
	swarmServer := swarm.NewServer(registry, opts...)
	defer swarmServer.Close()

	vehicleLn, err := ts.Listen("tcp", cfg.VehiclePort)
	if err != nil {
		log.Fatal().Msgf("listening on vehicle port %d: %v", cfg.VehiclePort, err)
	}
	gcsLn, err := ts.Listen("tcp", cfg.ListenPort)
	if err != nil {
		log.Fatal().Msgf("listening on listen port %d: %v", cfg.ListenPort, err)
	}

	vehicleGRPC := grpc.NewServer()
	swarmpb.RegisterRegistryServiceServer(vehicleGRPC, registryServer)

	gcsGRPC := grpc.NewServer()
	swarmpb.RegisterSwarmServiceServer(gcsGRPC, swarmServer)

	var gcsPlainGRPC *grpc.Server
	var gcsPlainLn net.Listener
	if cfg.GCSPlainListen {
		gcsPlainLn, err = net.Listen("tcp", fmt.Sprintf(":%d", cfg.ListenPort))
		if err != nil {
			log.Fatal().Msgf("listening on plain GCS port %d: %v", cfg.ListenPort, err)
		}
		gcsPlainGRPC = grpc.NewServer()
		swarmpb.RegisterSwarmServiceServer(gcsPlainGRPC, swarmServer)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Info().Msgf("RegistryService listening on :%d (tailnet)", cfg.VehiclePort)
		if err := vehicleGRPC.Serve(vehicleLn); err != nil {
			log.Error().Msgf("RegistryService server exited: %v", err)
		}
	}()
	go func() {
		log.Info().Msgf("SwarmService listening on :%d (tailnet)", cfg.ListenPort)
		if err := gcsGRPC.Serve(gcsLn); err != nil {
			log.Error().Msgf("SwarmService server exited: %v", err)
		}
	}()
	if gcsPlainGRPC != nil {
		go func() {
			log.Info().Msgf("SwarmService listening on :%d (plain)", cfg.ListenPort)
			if err := gcsPlainGRPC.Serve(gcsPlainLn); err != nil {
				log.Error().Msgf("plain SwarmService server exited: %v", err)
			}
		}()
	}

	<-ctx.Done()
	log.Info().Msg("shutting down")
	gcsGRPC.GracefulStop()
	if gcsPlainGRPC != nil {
		gcsPlainGRPC.GracefulStop()
	}
	vehicleGRPC.GracefulStop()
}
