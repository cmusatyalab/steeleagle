package main

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"sync"

	"github.com/cmusatyalab/steeleagle/core/vehicle"
	"github.com/rs/zerolog"
	"tailscale.com/tsnet"
)

type daemonContext struct {
	channel  chan<- core.LogMessage
	mu       sync.Mutex
	vehicles map[string]*vehicle.Vehicle
	vpn      TailscaleServer
	// Context related attributes
	ctx    context.Context
	cancel context.CancelFunc
}

func (i *daemonContext) start(w http.ResponseWriter, r *http.Request) {
	i.mu.Lock()
	defer i.mu.Unlock()
	defer r.Body.Close()

	var config RunConfig

	if r.Body == nil {
		http.Error(w, "Please send a valid run configuration in the request body", http.StatusBadRequest)
		return
	}

	// Unmarshal run configuration from the JSON body
	err := json.NewDecoder(r.Body).Decode(&config)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Create a reader socket that will read from the vehicles dataOut

	// Start vehicles, tying them to the global context
}

func (i *daemonContext) stop(w http.ResponseWriter, r *http.Request) {
	i.mu.Lock()
	defer i.mu.Unlock()

	// TODO: Cancel the global context
}

func (i *daemonContext) cleanup() {
	i.mu.Lock()
	defer i.mu.Unlock()

	i.cancel()
}

var logger zerolog.Logger

func main() {
	// Create the log channel
	channel := make(chan<- core.LogMessage, 1000)

	// Set up the logger
	logger = core.NewChannelLogger(core.LogConfig{
		Name:    "daemon",
		Level:   "info",
		Channel: channel,
	})

	// Create daemon context
	daemon := daemonContext{
		channel: channel,
	}
	defer daemon.cleanup()

	// Set up HTTP listeners
	http.HandleFunc("/start", daemon.start)
	http.HandleFunc("/stop", daemon.stop)
}
