package vehicle

import (
	"net"
	"os"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog"
)

func newTestVehicleForOptions() *Vehicle {
	return &Vehicle{
		listeners: make(map[string]net.Listener),
	}
}

func TestWithName(t *testing.T) {
	v := newTestVehicleForOptions()
	WithName("vehicle-1")(v)
	if v.Name != "vehicle-1" {
		t.Fatalf("expected name %q, got %q", "vehicle-1", v.Name)
	}
}

func TestWithPolicyConfig(t *testing.T) {
	v := newTestVehicleForOptions()
	cfg := PolicyConfig{Law: ControlLaw{First: "hover"}}
	WithPolicyConfig(cfg)(v)
	if v.policyCfg.Law.First != cfg.Law.First {
		t.Fatalf("expected policy config %v, got %v", cfg, v.policyCfg)
	}
}

func TestWithVideoStreamConfig(t *testing.T) {
	v := newTestVehicleForOptions()
	cfg := VideoStreamConfig{Codec: "h264"}
	WithVideoStreamConfig(cfg)(v)
	if v.videoCfg != cfg {
		t.Fatalf("expected video config %v, got %v", cfg, v.videoCfg)
	}
}

func TestWithGabrielConfig(t *testing.T) {
	v := newTestVehicleForOptions()
	cfg := GabrielConfig{ServerEndpoint: "localhost:9099"}
	WithGabrielConfig(cfg)(v)
	if v.gabrielCfg.ServerEndpoint != cfg.ServerEndpoint {
		t.Fatalf("expected gabriel config %v, got %v", cfg, v.gabrielCfg)
	}
}

func TestWithLogger(t *testing.T) {
	v := newTestVehicleForOptions()
	logger := zerolog.New(os.Stderr)
	WithLogger(logger)(v)
	if v.log.GetLevel() != logger.GetLevel() {
		t.Fatalf("expected logger to be set")
	}
}

func TestWithServerListener(t *testing.T) {
	v := newTestVehicleForOptions()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("couldn't create listener: %v", err)
	}
	defer ln.Close()

	acl := util.GetACL(nil, nil)
	WithServerListener(ln, acl)(v)

	codedLn, ok := v.listeners[ServerListenerName]
	if !ok {
		t.Fatalf("expected listener to be registered under %q", ServerListenerName)
	}
	if codedLn.Addr().String() != ln.Addr().String() {
		t.Fatalf("expected coded listener addr %v, got %v", ln.Addr(), codedLn.Addr())
	}
}
