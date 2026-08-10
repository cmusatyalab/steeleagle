package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// DefaultCallTimeout bounds how long eagle waits for eagled to respond.
const DefaultCallTimeout = 5 * time.Minute

// DefaultDaemonAddr matches eagled's own DefaultControlPort.
const DefaultDaemonAddr = "localhost:9090"

// dial connects to eagled's control-plane API at daemonAddr.
func dial(daemonAddr string) (eagledpb.DaemonServiceClient, func(), error) {
	conn, err := grpc.NewClient(daemonAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, nil, fmt.Errorf("dialing %s: %w", daemonAddr, err)
	}
	return eagledpb.NewDaemonServiceClient(conn), func() { conn.Close() }, nil
}

// withClient dials daemonAddr, bounds ctx by DefaultCallTimeout, and runs fn
// against it, cleaning up the connection and context regardless of fn's
// outcome.
func withClient(ctx context.Context, daemonAddr string, fn func(context.Context, eagledpb.DaemonServiceClient) error) error {
	client, closeFn, err := dial(daemonAddr)
	if err != nil {
		return err
	}
	defer closeFn()

	ctx, cancel := context.WithTimeout(ctx, DefaultCallTimeout)
	defer cancel()

	return fn(ctx, client)
}

// printResults prints one line per vehicle result and reports whether any
// failed.
func printResults(results []*eagledpb.VehicleResult, verb string) bool {
	failed := false
	for _, v := range results {
		if v.GetOk() {
			fmt.Printf("%s: %s\n", v.GetName(), verb)
			continue
		}
		failed = true
		fmt.Printf("%s: failed: %s\n", v.GetName(), v.GetError())
	}
	return failed
}

// configure pushes the TOML config at configPath to the eagled instance at
// daemonAddr, printing per-vehicle start results.
func configure(ctx context.Context, daemonAddr, configPath string) error {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return fmt.Errorf("reading %s: %w", configPath, err)
	}
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.Configure(ctx, eagledpb.ConfigureRequest_builder{ConfigToml: string(data)}.Build())
		if err != nil {
			return fmt.Errorf("configuring %s: %w", daemonAddr, err)
		}
		if printResults(resp.GetVehicles(), "started") {
			return fmt.Errorf("one or more vehicles failed to start")
		}
		return nil
	})
}

// stopVehicles stops the named vehicles on the eagled instance at daemonAddr.
func stopVehicles(ctx context.Context, daemonAddr string, names []string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.StopVehicles(ctx, eagledpb.StopVehiclesRequest_builder{Names: names}.Build())
		if err != nil {
			return fmt.Errorf("stopping vehicles on %s: %w", daemonAddr, err)
		}
		if printResults(resp.GetVehicles(), "stopped") {
			return fmt.Errorf("one or more vehicles failed to stop")
		}
		return nil
	})
}

// restartVehicles restarts the named vehicles on the eagled instance at
// daemonAddr.
func restartVehicles(ctx context.Context, daemonAddr string, names []string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.RestartVehicles(ctx, eagledpb.RestartVehiclesRequest_builder{Names: names}.Build())
		if err != nil {
			return fmt.Errorf("restarting vehicles on %s: %w", daemonAddr, err)
		}
		if printResults(resp.GetVehicles(), "restarted") {
			return fmt.Errorf("one or more vehicles failed to restart")
		}
		return nil
	})
}

// forgetVehicles stops (if running) and forgets the named vehicles on the
// eagled instance at daemonAddr: they won't come back on restart or
// reconfigure.
func forgetVehicles(ctx context.Context, daemonAddr string, names []string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.ForgetVehicles(ctx, eagledpb.ForgetVehiclesRequest_builder{Names: names}.Build())
		if err != nil {
			return fmt.Errorf("forgetting vehicles on %s: %w", daemonAddr, err)
		}
		if printResults(resp.GetVehicles(), "forgotten") {
			return fmt.Errorf("one or more vehicles failed to be forgotten")
		}
		return nil
	})
}

// pluginCategoryFlag parses the --category flag value into its protocol enum,
// case-insensitively.
func pluginCategoryFlag(category string) (eagledpb.PluginCategory, error) {
	switch strings.ToLower(category) {
	case "driver":
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER, nil
	case "mission":
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_MISSION, nil
	case "extra":
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_EXTRA, nil
	default:
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_UNSPECIFIED, fmt.Errorf("category must be one of %q, %q, %q, got %q", "driver", "mission", "extra", category)
	}
}

// pluginCategoryString renders a protocol PluginCategory back to the flag
// value that produces it.
func pluginCategoryString(category eagledpb.PluginCategory) string {
	switch category {
	case eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER:
		return "driver"
	case eagledpb.PluginCategory_PLUGIN_CATEGORY_MISSION:
		return "mission"
	case eagledpb.PluginCategory_PLUGIN_CATEGORY_EXTRA:
		return "extra"
	default:
		return "unspecified"
	}
}

// installPlugin fetches repo at ref and installs it as name's plugin, under
// category, on the eagled instance at daemonAddr.
func installPlugin(ctx context.Context, daemonAddr, name, repo, ref, subpath, category string) error {
	protoCategory, err := pluginCategoryFlag(category)
	if err != nil {
		return err
	}
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.InstallPlugin(ctx, eagledpb.InstallPluginRequest_builder{
			Name: name, Repo: repo, Ref: ref, Subpath: subpath, Category: protoCategory,
		}.Build())
		if err != nil {
			return fmt.Errorf("installing plugin on %s: %w", daemonAddr, err)
		}
		if !resp.GetOk() {
			return fmt.Errorf("install failed: %s", resp.GetError())
		}
		fmt.Printf("%s: installed at %s\n", name, ref)
		return nil
	})
}

// listPlugins prints every plugin installed on the eagled instance at
// daemonAddr, the ref it was last installed at, and its category.
func listPlugins(ctx context.Context, daemonAddr string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.GetInstalledPlugins(ctx, eagledpb.GetInstalledPluginsRequest_builder{}.Build())
		if err != nil {
			return fmt.Errorf("listing plugins on %s: %w", daemonAddr, err)
		}
		if len(resp.GetPlugins()) == 0 {
			fmt.Println("no plugins installed")
			return nil
		}
		for _, p := range resp.GetPlugins() {
			fmt.Printf("%s: %s (%s)\n", p.GetName(), p.GetRef(), pluginCategoryString(p.GetCategory()))
		}
		return nil
	})
}

// resetConfig deletes the persisted config on the eagled instance at
// daemonAddr and restarts it unconfigured, tearing down every vehicle.
func resetConfig(ctx context.Context, daemonAddr string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		if _, err := client.ResetConfig(ctx, eagledpb.ResetConfigRequest_builder{}.Build()); err != nil {
			return fmt.Errorf("resetting config on %s: %w", daemonAddr, err)
		}
		fmt.Println("config cleared, daemon restarting unconfigured")
		return nil
	})
}

// restartDaemon restarts the eagled process at daemonAddr without touching
// its persisted config, so it comes back up with the same vehicles.
func restartDaemon(ctx context.Context, daemonAddr string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		if _, err := client.RestartDaemon(ctx, eagledpb.RestartDaemonRequest_builder{}.Build()); err != nil {
			return fmt.Errorf("restarting daemon at %s: %w", daemonAddr, err)
		}
		fmt.Println("daemon restarting")
		return nil
	})
}

// status prints the eagled instance's current configuration, if any, and
// the state of every vehicle it knows about.
func status(ctx context.Context, daemonAddr string) error {
	return withClient(ctx, daemonAddr, func(ctx context.Context, client eagledpb.DaemonServiceClient) error {
		resp, err := client.GetStatus(ctx, eagledpb.GetStatusRequest_builder{}.Build())
		if err != nil {
			return fmt.Errorf("getting status of %s: %w", daemonAddr, err)
		}
		if !resp.GetConfigured() {
			fmt.Println("not configured")
			return nil
		}

		cfg := resp.GetConfig()
		fmt.Printf("daemon: %s\n", cfg.GetDaemonName())
		fmt.Printf("swarm controller: %s\n", cfg.GetSwarmControllerAddress())
		fmt.Printf("plugin dir: %s\n", cfg.GetPluginDir())

		if len(resp.GetVehicles()) == 0 {
			fmt.Println("no vehicles configured")
			return nil
		}
		for _, v := range resp.GetVehicles() {
			state := "stopped"
			if v.GetRunning() {
				state = fmt.Sprintf("running on port %d", v.GetPort())
			}
			fmt.Printf("%s (%s): %s\n", v.GetName(), v.GetDriver(), state)
		}
		return nil
	})
}

func usage() {
	fmt.Fprintf(os.Stderr, `usage:
  eagle configure --daemon <host:port> --config <path>
  eagle stop --daemon <host:port> <vehicle> [<vehicle>...]
  eagle restart --daemon <host:port> <vehicle> [<vehicle>...]
  eagle forget --daemon <host:port> <vehicle> [<vehicle>...]
  eagle install-plugin --daemon <host:port> --name <name> --repo <url> --ref <ref> --category <driver|mission|extra> [--subpath <path>]
  eagle plugins --daemon <host:port>
  eagle status --daemon <host:port>
  eagle restart-daemon --daemon <host:port>
  eagle reset-config --daemon <host:port>
(daemon defaults to %s)
`, DefaultDaemonAddr)
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var err error
	switch os.Args[1] {
	case "configure":
		fs := flag.NewFlagSet("configure", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		configPath := fs.String("config", "config.toml", "path to the TOML config file to push")
		fs.Parse(os.Args[2:])
		err = configure(ctx, *daemonAddr, *configPath)
	case "stop":
		fs := flag.NewFlagSet("stop", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		if fs.NArg() == 0 {
			usage()
			os.Exit(2)
		}
		err = stopVehicles(ctx, *daemonAddr, fs.Args())
	case "restart":
		fs := flag.NewFlagSet("restart", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		if fs.NArg() == 0 {
			usage()
			os.Exit(2)
		}
		err = restartVehicles(ctx, *daemonAddr, fs.Args())
	case "forget":
		fs := flag.NewFlagSet("forget", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		if fs.NArg() == 0 {
			usage()
			os.Exit(2)
		}
		err = forgetVehicles(ctx, *daemonAddr, fs.Args())
	case "install-plugin":
		fs := flag.NewFlagSet("install-plugin", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		name := fs.String("name", "", "plugin identifier (matches a vehicle's driver/mission/plugins entry in config.toml)")
		repo := fs.String("repo", "", "git URL to fetch")
		ref := fs.String("ref", "", "commit SHA, branch, or tag to check out")
		subpath := fs.String("subpath", "", "subfolder containing install.sh/run.sh; empty means repo root")
		category := fs.String("category", "", "one of driver, mission, extra")
		fs.Parse(os.Args[2:])
		if *name == "" || *repo == "" || *ref == "" || *category == "" {
			usage()
			os.Exit(2)
		}
		err = installPlugin(ctx, *daemonAddr, *name, *repo, *ref, *subpath, *category)
	case "plugins":
		fs := flag.NewFlagSet("plugins", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		err = listPlugins(ctx, *daemonAddr)
	case "status":
		fs := flag.NewFlagSet("status", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		err = status(ctx, *daemonAddr)
	case "restart-daemon":
		fs := flag.NewFlagSet("restart-daemon", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		err = restartDaemon(ctx, *daemonAddr)
	case "reset-config":
		fs := flag.NewFlagSet("reset-config", flag.ExitOnError)
		daemonAddr := fs.String("daemon", DefaultDaemonAddr, "eagled's control-plane address")
		fs.Parse(os.Args[2:])
		err = resetConfig(ctx, *daemonAddr)
	default:
		usage()
		os.Exit(2)
	}

	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
