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
	ListenPort int `toml:"listen-port"` // SwarmService port
	// RegistryListen selects how RegistryService (vehicle-facing) is bound:
	// "tailnet" (default) or "plain" (skip tsnet)
	RegistryListen string `toml:"registry-listen,omitempty"`
	// SwarmListen selects how SwarmService (client-facing) is bound:
	// "tailnet" (default), "plain", or "both" (bind both)
	SwarmListen string          `toml:"swarm-listen,omitempty"`
	VehiclePort int             `toml:"vehicle-port"`           // RegistryService port
	CallTimeout string          `toml:"call-timeout,omitempty"` // Vehicle RPC timeout
	Tailscale   TailscaleConfig `toml:"tailscale"`              // Tailscale config
}

const (
	listenTailnet = "tailnet"
	listenPlain   = "plain"
	listenBoth    = "both"
)

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
	if cfg.RegistryListen == "" {
		cfg.RegistryListen = listenTailnet
	}
	if cfg.SwarmListen == "" {
		cfg.SwarmListen = listenTailnet
	}
	if cfg.RegistryListen != listenTailnet && cfg.RegistryListen != listenPlain {
		log.Fatal().Msgf("registry-listen must be %q or %q, got %q", listenTailnet, listenPlain, cfg.RegistryListen)
	}
	if cfg.SwarmListen != listenTailnet && cfg.SwarmListen != listenPlain && cfg.SwarmListen != listenBoth {
		log.Fatal().Msgf("swarm-listen must be %q, %q, or %q, got %q", listenTailnet, listenPlain, listenBoth, cfg.SwarmListen)
	}

	var opts []swarm.Option
	if cfg.CallTimeout != "" {
		d, err := time.ParseDuration(cfg.CallTimeout)
		if err != nil {
			log.Fatal().Msgf("parsing call-timeout: %v", err)
		}
		opts = append(opts, swarm.WithCallTimeout(d))
	}

	// tsnet is only needed if something is actually bound to the tailnet.
	needsTailnet := cfg.RegistryListen == listenTailnet ||
		cfg.SwarmListen == listenTailnet || cfg.SwarmListen == listenBoth

	var ts *tailscale.Server
	if needsTailnet {
		authKey := ""
		if cfg.Tailscale.AuthKeyEnv != "" {
			authKey = os.Getenv(cfg.Tailscale.AuthKeyEnv)
		}
		ts, err = tailscale.NewServer(cfg.Tailscale.Hostname, authKey)
		if err != nil {
			log.Fatal().Msgf("starting tailscale: %v", err)
		}
		defer ts.Close()
	}

	// Vehicles register over whichever network RegistryListen chose, so
	// outbound dispatch has to dial back out over that same network.
	if cfg.RegistryListen == listenTailnet {
		opts = append(opts, swarm.WithDialer(ts.Dial))
	}

	controller := swarm.NewController(opts...)
	defer controller.Close()

	var vehicleLn net.Listener
	if cfg.RegistryListen == listenTailnet {
		vehicleLn, err = ts.Listen("tcp", cfg.VehiclePort)
	} else {
		vehicleLn, err = net.Listen("tcp", fmt.Sprintf(":%d", cfg.VehiclePort))
	}
	if err != nil {
		log.Fatal().Msgf("listening on vehicle port %d: %v", cfg.VehiclePort, err)
	}

	vehicleGRPC := grpc.NewServer()
	swarmpb.RegisterRegistryServiceServer(vehicleGRPC, controller.RegistryServer)

	var swarmTailnetGRPC *grpc.Server
	var swarmTailnetLn net.Listener
	if cfg.SwarmListen == listenTailnet || cfg.SwarmListen == listenBoth {
		swarmTailnetLn, err = ts.Listen("tcp", cfg.ListenPort)
		if err != nil {
			log.Fatal().Msgf("listening on listen port %d: %v", cfg.ListenPort, err)
		}
		swarmTailnetGRPC = grpc.NewServer()
		swarmpb.RegisterSwarmServiceServer(swarmTailnetGRPC, controller.SwarmServer)
	}

	var swarmPlainGRPC *grpc.Server
	var swarmPlainLn net.Listener
	if cfg.SwarmListen == listenPlain || cfg.SwarmListen == listenBoth {
		swarmPlainLn, err = net.Listen("tcp", fmt.Sprintf(":%d", cfg.ListenPort))
		if err != nil {
			log.Fatal().Msgf("listening on plain swarm port %d: %v", cfg.ListenPort, err)
		}
		swarmPlainGRPC = grpc.NewServer()
		swarmpb.RegisterSwarmServiceServer(swarmPlainGRPC, controller.SwarmServer)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Info().Msgf("RegistryService listening on :%d (%s)", cfg.VehiclePort, cfg.RegistryListen)
		if err := vehicleGRPC.Serve(vehicleLn); err != nil {
			log.Error().Msgf("RegistryService server exited: %v", err)
		}
	}()
	if swarmTailnetGRPC != nil {
		go func() {
			log.Info().Msgf("SwarmService listening on :%d (tailnet)", cfg.ListenPort)
			if err := swarmTailnetGRPC.Serve(swarmTailnetLn); err != nil {
				log.Error().Msgf("SwarmService server exited: %v", err)
			}
		}()
	}
	if swarmPlainGRPC != nil {
		go func() {
			log.Info().Msgf("SwarmService listening on :%d (plain)", cfg.ListenPort)
			if err := swarmPlainGRPC.Serve(swarmPlainLn); err != nil {
				log.Error().Msgf("plain SwarmService server exited: %v", err)
			}
		}()
	}

	<-ctx.Done()
	log.Info().Msg("shutting down")
	if swarmTailnetGRPC != nil {
		swarmTailnetGRPC.GracefulStop()
	}
	if swarmPlainGRPC != nil {
		swarmPlainGRPC.GracefulStop()
	}
	vehicleGRPC.GracefulStop()
}
