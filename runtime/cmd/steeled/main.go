package main

import (
    "os"
    "net/http"
    "context"
    "sync"

    "tailscale.com/tsnet"
    "github.com/rs/zerolog"
    "github.com/cmusatyalab/steeleagle/runtime/core"
    "go.nanomsg.org/mangos/v3"
	"go.nanomsg.org/mangos/v3/protocol/sub"
    _ "go.nanomsg.org/mangos/v3/transport/all"
)

type daemonContext struct {
	channel		chan<- core.LogMessage
    mu          sync.Mutex
	mcap		MCAPLogger
	vehicles 	map[string]*core.Vehicle
	// Context related attributes
	ctx			context.Context
	cancel		context.CancelFunc
}

func (i *daemonContext) start(w http.ResponseWriter, r *http.Request) {
    i.mu.Lock()
    defer i.mu.Unlock()

    // TODO: Unmarshal config from JSON

    // Create a reader socket that will read from the vehicles dataOut

    // Start vehicles
}

func (i *daemonContext) stop(w http.ResponseWriter, r *http.Request) {
    i.mu.Lock()
    defer i.mu.Unlock()

}

func (i *daemonContext) info(w http.ResponseWriter, r *http.Request) {
    i.mu.Lock()
    defer i.mu.Unlock()

}

func (i *daemonContext) cleanup() {
    i.mu.Lock()
    defer i.mu.Unlock()

}

var logger zerolog.Logger

func main() {
	// Create the log channel
    channel := make(chan<- core.LogMessage, 1000)

	// Set up the logger
	logger = core.NewChannelLogger(core.LogConfig{
		Name: "daemon",
		Level: "info",
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
    http.HandleFunc("/info", daemon.info)
}
