package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"syscall"

	"github.com/BurntSushi/toml"
	"github.com/rs/zerolog/log"
)

// DefaultAviaryCommand is the command line eagled runs to launch the shared
// aviary simulator.
var DefaultAviaryCommand = []string{"uv", "run", "steeleagle-aviary"}

// DefaultAviaryInterface is the aviary driver interface used for a simulated
// vehicle whose config doesn't specify one.
const DefaultAviaryInterface = "steeleagle_aviary.interfaces.steeleagle"

// aviaryVehicleConfig models one [[vehicles]] entry in steeleagle-aviary's own
// config format.
type aviaryVehicleConfig struct {
	Name      string  `toml:"name"`
	Interface string  `toml:"interface"`
	Lat       float64 `toml:"lat"`
	Lon       float64 `toml:"lon"`
	Alt       float64 `toml:"alt"`
}

// aviaryConfigFile is the top-level document steeleagle-aviary reads via
// --config.
type aviaryConfigFile struct {
	Vehicles []aviaryVehicleConfig `toml:"vehicles"`
}

// spawnAviary launches one aviary subprocess simulating every vehicle in
// vehicleCfgs. The subprocess is tied to ctx: canceling ctx kills it. Its
// scratch config file is removed once it exits.
func spawnAviary(ctx context.Context, command []string, dir string, vehicleCfgs []VehicleConfig) error {
	cfg := aviaryConfigFile{Vehicles: make([]aviaryVehicleConfig, 0, len(vehicleCfgs))}
	for _, v := range vehicleCfgs {
		iface := v.Interface
		if iface == "" {
			iface = DefaultAviaryInterface
		}
		cfg.Vehicles = append(cfg.Vehicles, aviaryVehicleConfig{
			Name:      v.Name,
			Interface: iface,
			Lat:       v.Lat,
			Lon:       v.Lon,
			Alt:       v.Alt,
		})
	}

	f, err := os.CreateTemp("", "eagled-aviary-*.toml")
	if err != nil {
		return fmt.Errorf("creating aviary config: %w", err)
	}
	if err := toml.NewEncoder(f).Encode(cfg); err != nil {
		f.Close()
		os.Remove(f.Name())
		return fmt.Errorf("encoding aviary config: %w", err)
	}
	if err := f.Close(); err != nil {
		os.Remove(f.Name())
		return fmt.Errorf("closing aviary config: %w", err)
	}

	if len(command) == 0 {
		command = DefaultAviaryCommand
	}
	args := make([]string, 0, len(command)-1+2)
	args = append(args, command[1:]...)
	args = append(args, "--config", f.Name())
	cmd := exec.CommandContext(ctx, command[0], args...)
	cmd.Dir = dir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Cancel = func() error {
		return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}
	if err := cmd.Start(); err != nil {
		os.Remove(f.Name())
		return fmt.Errorf("starting %s: %w", command, err)
	}

	go func() {
		defer os.Remove(f.Name())
		if err := cmd.Wait(); err != nil && ctx.Err() == nil {
			log.Error().Err(err).Msg("aviary exited unexpectedly")
		}
	}()

	return nil
}
