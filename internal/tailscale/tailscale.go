package tailscale

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"

	"github.com/cmusatyalab/steeleagle/core/util"
	"tailscale.com/ipn/store/mem"
	"tailscale.com/tsnet"
)

type Server struct {
	server *tsnet.Server
}

// StateDir returns the persistent directory a tsnet node keeps its state in,
// creating it if it does not exist. name identifies the node, so each node's
// identity survives process restarts independently of the others.
func StateDir(name string) (string, error) {
	dataDir, err := util.GetDataDir()
	if err != nil {
		return "", err
	}
	dir := filepath.Join(dataDir, "tsnet", name)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", err
	}
	return dir, nil
}

// NewServer starts a tsnet node under the given hostname. If authKey is
// non-empty it's used to join the tailnet non-interactively. Otherwise, tsnet
// falls back to its interactive login flow. Tags, if any, should be baked
// into authKey itself (created with those tags in the admin console) so the
// node registers already-tagged in one step, rather than being set here via
// a post-boot EditPrefs call. Whether the node is ephemeral (auto-removed
// from the tailnet once it goes offline for good) is likewise determined by
// authKey, not by anything set here.
//
// If memStore is true, the node's state lives only in memory. Every call to
// NewServer starts from a blank identity and re-registers under hostname from
// scratch. If memStore is false, state persists on disk under
// StateDir(stateName), so a node restarting under the same hostname reconnects
// with its existing identity instead of requesting a new one. stateName must
// be unique per node and non-empty.
func NewServer(hostname, authKey, stateName string, memStore bool) (*Server, error) {
	server := new(tsnet.Server)
	server.Hostname = hostname
	server.AuthKey = authKey
	if memStore {
		server.Ephemeral = true
		server.Store = new(mem.Store)
	} else {
		if stateName == "" {
			return nil, fmt.Errorf("stateName must be set when memStore is false")
		}
		dir, err := StateDir(stateName)
		if err != nil {
			return nil, fmt.Errorf("determining tsnet state directory: %w", err)
		}
		server.Dir = dir
	}

	// Start the Tailscale server
	if err := server.Start(); err != nil {
		return nil, err
	}

	return &Server{
		server: server,
	}, nil
}

func (i *Server) Listen(protocol string, port int) (net.Listener, error) {
	conn, err := i.server.Listen(protocol, fmt.Sprintf(":%d", port))
	if err != nil {
		return nil, err
	}

	return conn, nil
}

// Dial opens an outbound connection sourced from this node's own tailnet
// identity, so peers see this node's address, not the host's.
func (i *Server) Dial(ctx context.Context, network, addr string) (net.Conn, error) {
	return i.server.Dial(ctx, network, addr)
}

func (i *Server) Close() {
	i.server.Close()
}
