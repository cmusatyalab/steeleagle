// Command eagled runs the SteelEagle daemon, which serves the vehicles,
// engines and other services of its config until it is stopped.
//
//	eagled [-config file] [-log-level level] [-console]
//
// The daemon reads its config from the config directory
// ($XDG_CONFIG_HOME/steeleagle/config.toml, ~/.config/steeleagle by default)
// unless -config is given, writing the default config there if there is
// none.
//
// eagled stops gracefully on SIGINT or SIGTERM, exiting 0. When the daemon
// stops for a restart (after a Restart or Configure call), eagled exits with
// RestartExitCode, which its supervisor (see cmd/eagle/eagled.service) restarts it on.
// Any other failure exits 1.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/cmusatyalab/steeleagle/v4/core/daemon"
	"github.com/rs/zerolog"
)

// RestartExitCode is the exit code when the daemon stops for a restart
// (EX_TEMPFAIL), which eagled.service restarts on.
const RestartExitCode = 75

func main() {
	os.Exit(run())
}

// run runs the daemon until it stops, returning the exit code.
func run() int {
	configPath := flag.String("config", "", "daemon config file (default: ~/.config/steeleagle/config.toml)")
	logLevel := flag.String("log-level", "info", "minimum level to log: trace, debug, info, warn or error")
	console := flag.Bool("console", false, "log human-readable lines instead of JSON")
	flag.Parse()
	if flag.NArg() > 0 {
		fmt.Fprintf(os.Stderr, "unexpected arguments: %v\n", flag.Args())
		flag.Usage()
		return 2
	}

	level, err := zerolog.ParseLevel(*logLevel)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid -log-level: %v\n", err)
		return 2
	}
	var out = zerolog.New(os.Stderr)
	if *console {
		out = zerolog.New(zerolog.ConsoleWriter{Out: os.Stderr})
	}
	log := out.Level(level).With().Timestamp().Logger()

	options := []daemon.DaemonOption{daemon.WithLogger(log)}
	if *configPath != "" {
		options = append(options, daemon.WithConfigPath(*configPath))
	}
	d, err := daemon.NewDaemon(options...)
	if err != nil {
		log.Error().Err(err).Msg("could not create daemon")
		return 1
	}

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	err = d.Run(ctx)
	switch {
	case errors.Is(err, daemon.ErrRestart):
		log.Info().Int("code", RestartExitCode).Msg("exiting for restart")
		return RestartExitCode
	case err != nil:
		log.Error().Err(err).Msg("daemon exited with error")
		return 1
	}
	return 0
}
