// mockaviary is a minimal fixture standing in for steeleagle-aviary in
// cmd/eagled's black-box tests. It reads the --config file eagled generates
// (see spawnAviary), then for each vehicle listed creates the aviary socket
// at the same path util.GetPluginDir()-based convention
// (vehicle.go's aviarySocketPath) expects, and blocks serving an empty gRPC
// server on it until killed.
package main

import (
	"net"
	"os"
	"path/filepath"

	"github.com/BurntSushi/toml"
	"github.com/cmusatyalab/steeleagle/core/util"
	"google.golang.org/grpc"
)

type vehicleConfig struct {
	Name string `toml:"name"`
}

type configFile struct {
	Vehicles []vehicleConfig `toml:"vehicles"`
}

func main() {
	configPath := ""
	for i, arg := range os.Args {
		if arg == "--config" && i+1 < len(os.Args) {
			configPath = os.Args[i+1]
		}
	}
	if configPath == "" {
		os.Exit(1)
	}

	var cfg configFile
	if _, err := toml.DecodeFile(configPath, &cfg); err != nil {
		os.Exit(1)
	}

	pluginDir, err := util.GetPluginDir()
	if err != nil {
		os.Exit(1)
	}

	for _, v := range cfg.Vehicles {
		dir := filepath.Join(pluginDir, "aviary", v.Name)
		if err := os.MkdirAll(dir, 0755); err != nil {
			os.Exit(1)
		}
		ln, err := net.Listen("unix", filepath.Join(dir, "services.sock"))
		if err != nil {
			os.Exit(1)
		}
		go grpc.NewServer().Serve(ln) // blocks until ln closes or the process is killed
	}

	select {}
}
