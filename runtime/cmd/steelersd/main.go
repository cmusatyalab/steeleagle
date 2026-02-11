package main

import (
    "log"
    "log/slog"
    "os"

    "github.com/pelletier/go-toml/v2"
    "tailscale.com/tsnet"
)

// Config struct derived from config.toml
type Vehicle struct {
    Name        string `toml:"name"`
    MissionPkg  string `toml:"mission-pkg,omitempty"` 
    MissionSbx  bool   `toml:"mission-sandbox,omitempty"`
    DriverPkg   string `toml:"driver-pkg,omitempty"` 
}

type Config struct {
	Name        string      `toml:"name"`
    Port        int         `toml:"port"`
    Tailscale   bool        `toml:"tailscale,omitempty"`
    Vehicles    []Vehicle   `toml:"vehicles,omitempty"`
}

func main() {
    // Attempt to read configuration file at startup
    data, err := os.ReadFile("config.toml")
    if err != nil {
        slog.Warn("No config.toml found, creating one!")
        //TODO
    }
    var cfg Config
    err = toml.Unmarshal([]byte(data), &cfg)
    if err != nil {
	    panic(err)
    }
    ts_srv := new(tsnet.Server)
    ts_srv.Hostname = cfg.Name
    
    // Start Tailscale server connection
    if err := ts_srv.Start(); err != nil {
	    log.Fatalf("Can't start tsnet server: %v", err)
    }
    defer ts_srv.Close()

    // Specify external exposed ports via Tailscale
    vpn_conn, err := ts_srv.Listen("tcp", ":50051")
    if err != nil {
        log.Fatal(err)
    }
    defer vpn_conn.Close()

    select {}
}
