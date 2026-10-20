// mockdriver is a minimal fixture driver plugin for cmd/eagled's black-box
// tests. It only performs the plugin socket handshake and then blocks, serving
// an empty gRPC server, until its process is killed.
//
// It first writes the Gabriel variables eagled gave it, one KEY=value line
// each, to envFile in its working directory, so a test can check them.
package main

import (
	"fmt"
	"net"
	"os"

	"google.golang.org/grpc"
)

// envFile is where the driver records its Gabriel variables.
const envFile = "gabriel.env"

// gabrielVariables are the variables recorded in envFile.
var gabrielVariables = []string{"GABRIEL_RAW_FRAMES_PRODUCER", "GABRIEL_FLOW"}

func main() {
	fmt.Println("mockdriver ready")
	var env []byte
	for _, key := range gabrielVariables {
		env = fmt.Appendf(env, "%s=%s\n", key, os.Getenv(key))
	}
	if err := os.WriteFile(envFile, env, 0644); err != nil {
		os.Exit(1)
	}
	listenSocket := os.Getenv("LISTEN_SOCKET")
	if listenSocket == "" {
		os.Exit(1)
	}
	ln, err := net.Listen("unix", listenSocket)
	if err != nil {
		os.Exit(1)
	}
	grpc.NewServer().Serve(ln) // blocks until ln closes or the process is killed
}
