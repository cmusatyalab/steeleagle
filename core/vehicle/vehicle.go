package vehicle

import (
	"context"
	"net"

	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"google.golang.org/grpc"
)

type EngineInfo struct {
	Config *config.PluginConfig
	Local  bool
}

type EngineMap map[string]*EngineInfo

type Vehicle struct {
	auth listener.AuthCode // auth code of calls from the vehicle to the daemon
}

func NewVehicle(driver plugin.Plugin, options ...VehicleOption) (*Vehicle, error) {
	return nil, nil
}

func (v *Vehicle) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	// Calls from the vehicle to the daemon carry its auth code; the listener
	// closes when the vehicle stops, which ends the daemon serving it
	ln := listener.NewLocalListener(v.auth)
	context.AfterFunc(ctx, func() { ln.Close() })
	return ln, nil, nil
}

func (v *Vehicle) Wait() error {
	return nil
}
