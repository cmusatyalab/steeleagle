// Command plugin is a test plugin for daemon tests. It reports the plugin
// name, args, and iceoryx service it was started with, then serves the gRPC health service on
// its listen socket until it is killed. Its args can make it fail before it
// serves ({"fail": true}), or exit some time after it does
// ({"exit_after_ms": 100}).
package main

import (
	"encoding/json"
	"fmt"
	"net"
	"os"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
)

type args struct {
	Fail        bool `json:"fail"`
	ExitAfterMs int  `json:"exit_after_ms"`
}

func run() error {
	fmt.Printf("plugin=%s args=%s iceoryx=%s\n", os.Getenv("STEELEAGLE_PLUGIN"),
		os.Getenv("STEELEAGLE_PLUGIN_ARGS"), os.Getenv("STEELEAGLE_ENGINE_ENDPOINT"))
	var a args
	if err := json.Unmarshal([]byte(os.Getenv("STEELEAGLE_PLUGIN_ARGS")), &a); err != nil {
		return fmt.Errorf("bad args: %w", err)
	}
	if a.Fail {
		return fmt.Errorf("asked to fail")
	}
	ln, err := net.Listen("unix", os.Getenv("STEELEAGLE_LISTEN_SOCKET"))
	if err != nil {
		return err
	}
	server := grpc.NewServer()
	healthpb.RegisterHealthServer(server, health.NewServer())
	if a.ExitAfterMs > 0 {
		time.AfterFunc(time.Duration(a.ExitAfterMs)*time.Millisecond, func() {
			fmt.Println("exiting as asked")
			os.Exit(1)
		})
	}
	return server.Serve(ln)
}

func main() {
	if err := run(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
