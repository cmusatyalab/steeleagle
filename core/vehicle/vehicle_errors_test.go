package vehicle

import (
	"context"
	"fmt"
	"net"
	"testing"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"google.golang.org/grpc"
)

// failingPlugin is a plugin.Plugin whose Start always returns an error, used to
// exercise the vehicle's plugin start error handling paths.
type failingPlugin struct {
	name string
	code listener.AuthCode
}

func (p *failingPlugin) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	return nil, nil, fmt.Errorf("plugin %s failed to start", p.name)
}

func (p *failingPlugin) Watch() <-chan error { return make(chan error) }

func (p *failingPlugin) Wait() error { return nil }

func (p *failingPlugin) Name() string { return p.name }

func (p *failingPlugin) Code() listener.AuthCode { return p.code }

var _ plugin.Plugin = (*failingPlugin)(nil)

func TestVehicleNoDriverPlugin(t *testing.T) {
	pluginConfig := PluginConfig{}
	_, err := newTestVehicle(t, pluginConfig)
	if err == nil {
		t.Fatal("expected error creating vehicle with no driver, got nil")
	}
}

func TestVehicleDriverPluginStartError(t *testing.T) {
	pluginConfig := PluginConfig{
		Driver: &failingPlugin{name: "driver"},
	}
	v, err := newTestVehicle(t, pluginConfig)
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	err = v.Start(t.Context())
	if err == nil {
		t.Fatal("expected error starting vehicle with failing driver plugin, got nil")
	}
}

func TestVehicleMissionPluginStartError(t *testing.T) {
	driverPlugin, _, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	pluginConfig := PluginConfig{
		Driver:  driverPlugin,
		Mission: &failingPlugin{name: "mission"},
	}
	v, err := newTestVehicle(t, pluginConfig)
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	err = v.Start(t.Context())
	if err == nil {
		t.Fatal("expected error starting vehicle with failing mission plugin, got nil")
	}
}

func TestVehicleThirdPartyPluginStartError(t *testing.T) {
	driverPlugin, missionPlugin, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	pluginConfig := PluginConfig{
		Driver:  driverPlugin,
		Mission: missionPlugin,
		Plugins: []plugin.Plugin{&failingPlugin{name: "thirdparty"}},
	}
	v, err := newTestVehicle(t, pluginConfig)
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	err = v.Start(t.Context())
	if err == nil {
		t.Fatal("expected error starting vehicle with failing third-party plugin, got nil")
	}
}

func TestVehicleAlreadyStarted(t *testing.T) {
	driverPlugin, missionPlugin, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	pluginConfig := PluginConfig{Driver: driverPlugin, Mission: missionPlugin}
	v, err := newTestVehicle(t, pluginConfig)
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	if err := v.Start(t.Context()); err != nil {
		t.Fatalf("couldn't start vehicle: %v", err)
	}
	if err := v.Start(t.Context()); err == nil {
		t.Fatal("expected error starting vehicle that is already running, got nil")
	}
}

func TestVehicleControlState(t *testing.T) {
	driverPlugin, missionPlugin, _, _, err := setupPlugins(t, "")
	if err != nil {
		t.Fatalf("couldn't create plugin config: %v", err)
	}
	pluginConfig := PluginConfig{Driver: driverPlugin, Mission: missionPlugin}
	v, err := newTestVehicle(t, pluginConfig)
	if err != nil {
		t.Fatalf("couldn't create vehicle: %v", err)
	}
	if v.ControlState() == "" {
		t.Error("expected non-empty control state before starting vehicle")
	}
}
