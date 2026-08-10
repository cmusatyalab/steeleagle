// mockdriver is a minimal fixture driver plugin for cmd/eagled's black-box
// tests. It only performs the plugin socket handshake and then blocks, serving
// an empty gRPC server, until its process is killed.
package main

import (
	"net"
	"os"

	"google.golang.org/grpc"
)

func main() {
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
