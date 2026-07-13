package main

import (
	"fmt"
	"net"

	"tailscale.com/tsnet"
)

type TailscaleServer struct {
	server *tsnet.Server
}

func NewTailscaleServer(hostname string) (*TailscaleServer, error) {
	server := new(tsnet.Server)
	server.Hostname = hostname

	// Start the Tailscale server
	if err := server.Start(); err != nil {
		return nil, err
	}

	return &TailscaleServer{
		server: server,
	}, nil
}

func (i *TailscaleServer) Listen(protocol string, port int) (net.Listener, error) {
	conn, err := i.server.Listen(protocol, fmt.Sprintf(":%d", port))
	if err != nil {
		return nil, err
	}

	return conn, nil
}

func (i *TailscaleServer) Close() {
	i.server.Close()
}
