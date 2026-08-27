package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"

	"github.com/BurntSushi/toml"
	"github.com/rs/zerolog/log"
)

// uvInstallScriptURL is astral.sh's official installer, the same one used to
// bootstrap uv for steeleagle_plugins driver builds (see e.g.
// drivers/parrot_anafi/install.sh).
const uvInstallScriptURL = "https://astral.sh/uv/install.sh"

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

	// exec.CommandContext resolves command[0] via LookPath against the
	// current process's PATH immediately, at construction time -- setting
	// cmd.Env afterward only changes the child's environment, not that
	// lookup. So uv has to be resolved to an absolute path (and installed,
	// if necessary) before constructing cmd, not after.
	bin, childPath := command[0], ""
	if filepath.Base(command[0]) == "uv" {
		var err error
		if bin, childPath, err = ensureUv(ctx); err != nil {
			os.Remove(f.Name())
			return fmt.Errorf("ensuring uv is installed: %w", err)
		}
	}

	args := make([]string, 0, len(command)-1+2)
	args = append(args, command[1:]...)
	args = append(args, "--config", f.Name())
	cmd := exec.CommandContext(ctx, bin, args...)
	cmd.Dir = dir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if childPath != "" {
		cmd.Env = append(os.Environ(), "PATH="+childPath)
	}
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

// ensureUv makes sure a uv executable is reachable for launching aviary,
// installing it into $HOME/.local/bin via astral.sh's official installer if
// it isn't already on PATH there or anywhere else. eagled commonly runs as a
// systemd service with a minimal PATH that doesn't include the user-local bin
// directories uv is normally installed into, so this can't rely on PATH
// lookups alone. It returns the absolute path to the uv binary to exec, and
// the PATH aviary's subprocess should run with.
func ensureUv(ctx context.Context) (bin, path string, err error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", "", fmt.Errorf("determining home directory: %w", err)
	}
	localBin := filepath.Join(home, ".local", "bin")
	localUv := filepath.Join(localBin, "uv")
	path = localBin + string(os.PathListSeparator) + os.Getenv("PATH")

	if p, err := exec.LookPath("uv"); err == nil {
		return p, path, nil
	}
	if _, err := os.Stat(localUv); err == nil {
		return localUv, path, nil
	}

	log.Info().Str("installer", uvInstallScriptURL).Msg("uv not found; installing")
	install := exec.CommandContext(ctx, "sh", "-c", "curl -LsSf "+uvInstallScriptURL+" | sh")
	install.Env = append(os.Environ(), "HOME="+home)
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		return "", "", fmt.Errorf("running uv installer: %w", err)
	}
	if _, err := os.Stat(localUv); err != nil {
		return "", "", fmt.Errorf("uv installer completed but %s is still missing: %w", localUv, err)
	}
	return localUv, path, nil
}
