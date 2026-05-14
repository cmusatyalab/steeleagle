package util

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type Plugin interface {
	Name() string
	Runtime() PluginRuntime
	Spawn(context.Context) (net.Listener, *grpc.ClientConn, error)
	Stop() error
	IsRunning() bool
	Target() string
}

type BasePlugin struct {
	name    string
	target  string
	runtime PluginRuntime
	start   int64 // plugin start time
	running bool
	code    AuthCode
}

func (p *BasePlugin) Name() string {
	return p.name
}

func (p *BasePlugin) Target() string {
	return p.target
}

func (p *BasePlugin) Runtime() PluginRuntime {
	return p.runtime
}

func (p *BasePlugin) IsRunning() bool {
	return p.running
}

func CreateSocketPairFiles() (*os.File, *os.File, error) {
	// Create a socket pair to communicate with the plugin
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't open socket pair for plugin")
		return nil, nil, err
	}

	// Create internal files
	ln := os.NewFile(uintptr(fds[0]), fmt.Sprintf("listener-%s", p.name))
	client := os.NewFile(uintptr(fds[1]), fmt.Sprintf("client-%s", p.name))
    return ln, client, nil
}

func CreateEndpoints(lnFile, clientFile *os.File) (net.Listener, *grpc.ClientConn, error) {
	// Build the file connections
	lnConn, err := net.FileConn(lnFile)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't open listener socket")
		return nil, nil, err
	}
	clientConn, err := net.FileConn(clientFile)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't open client socket")
		return nil, nil, err
	}
	spClient, err := NewSocketPairClient(clientConn)
	if err != nil {
		log.Error().Err(err).Str("plugin", p.name).Str("code", string(p.code)).Msg("couldn't create socket pair client")
		return nil, nil, err
	}

	return NewSocketPairListener(lnConn, p.code), spClient, nil
}
