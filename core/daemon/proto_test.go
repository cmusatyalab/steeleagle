package daemon

import (
	"context"
	"net"
	"slices"
	"testing"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"google.golang.org/grpc"
)

// TestServiceProto checks that a service survives conversion to its
// protobuf form and back, except for what stays local.
func TestServiceProto(t *testing.T) {
	conf, err := config.ParsePluginConfigFromFilepath("testdata/pkg/detector.plugin.toml")
	if err != nil {
		t.Fatal(err)
	}
	s := &daemonService{
		name:       "100.64.0.2.e",
		category:   daemonpb.ServiceCategory_SERVICE_CATEGORY_ENGINE,
		uri:        testPkg,
		pluginName: "detector.plugin.toml",
		config:     conf,
		auth:       listener.UserCode,
		isolation:  daemonpb.Isolation_ISOLATION_SANDBOX,
		path:       "/local/only",
		args:       `{"local":"only"}`,
		local:      true,
	}
	p, err := s.toProto(true)
	if err != nil {
		t.Fatal(err)
	}
	if !p.GetRunning() || p.GetAuth() != "user" {
		t.Errorf("proto = %v, want running with user auth", p)
	}
	got, err := serviceFromProto(p)
	if err != nil {
		t.Fatal(err)
	}
	if got.name != s.name || got.category != s.category || got.uri != s.uri ||
		got.pluginName != s.pluginName || got.auth != s.auth || got.isolation != s.isolation {
		t.Errorf("serviceFromProto() = %+v, want %+v", got, s)
	}
	if got.local || got.path != "" || got.args != "" {
		t.Errorf("serviceFromProto() = %+v, want a remote service without local details", got)
	}
	if got.config == nil || got.config.Engine == nil || got.config.Engine.Type != "detection" {
		t.Errorf("config = %+v, want the engine config", got.config)
	}

	// A service without a config, like the simulator, has none on the other side
	p, err = (&daemonService{name: "sim"}).toProto(false)
	if err != nil {
		t.Fatal(err)
	}
	if got, err := serviceFromProto(p); err != nil || got.config != nil {
		t.Errorf("serviceFromProto() without config = %+v, %v, want no config", got, err)
	}

	p = daemonpb.Service_builder{Name: "bad", Config: []byte("[plugin")}.Build()
	if _, err := serviceFromProto(p); err == nil {
		t.Error("serviceFromProto() with a bad config = nil, want error")
	}
}

// stubPlugin is a plugin that is only ever running or not.
type stubPlugin struct {
	running bool
}

func (p *stubPlugin) Start(context.Context) (net.Listener, *grpc.ClientConn, error) {
	return nil, nil, nil
}

func (p *stubPlugin) Watch() <-chan error { return nil }

func (p *stubPlugin) Wait() error { return nil }

func (p *stubPlugin) Name() string { return "stub" }

func (p *stubPlugin) Code() listener.AuthCode { return listener.UnknownCode }

func (p *stubPlugin) Running() bool { return p.running }

// TestServiceProtos checks that services are listed in order, each running
// only if its plugin is.
func TestServiceProtos(t *testing.T) {
	d := &Daemon{
		services: []*daemonService{{name: "a"}, {name: "b"}, {name: "c"}},
		plugins: map[string]*daemonPlugin{
			"a": {plugin: &stubPlugin{running: true}},
			"b": {plugin: &stubPlugin{running: false}},
		},
	}
	got, err := d.serviceProtos()
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	var states []bool
	for _, p := range got {
		names = append(names, p.GetName())
		states = append(states, p.GetRunning())
	}
	if !slices.Equal(names, []string{"a", "b", "c"}) || !slices.Equal(states, []bool{true, false, false}) {
		t.Errorf("services = %v, running = %v, want a, b, c with only a running", names, states)
	}
}
