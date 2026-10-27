package daemon

import (
	"fmt"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
)

// serviceProtos returns the local services in protobuf form, each marked
// running if its plugin is. The caller must hold svcMu.
func (d *Daemon) serviceProtos() ([]*daemonpb.Service, error) {
	out := make([]*daemonpb.Service, 0, len(d.services))
	for _, s := range d.services {
		p, ok := d.plugins[s.name]
		running := ok && p.plugin.Running()
		svc, err := s.toProto(running)
		if err != nil {
			return nil, fmt.Errorf("service %q: %w", s.name, err)
		}
		out = append(out, svc)
	}
	return out, nil
}

// toProto converts a daemon service to its protobuf form.
func (s *daemonService) toProto(running bool) (*daemonpb.Service, error) {
	var conf []byte
	if s.config != nil {
		var err error
		if conf, err = s.config.ToBytes(); err != nil {
			return nil, err
		}
	}
	return daemonpb.Service_builder{
		Name:      s.name,
		Category:  s.category,
		Plugin:    s.pluginName,
		Uri:       s.uri,
		Config:    conf,
		Isolation: s.isolation,
		Running:   running,
		Auth:      s.auth.String(),
	}.Build(), nil
}

// serviceFromProto converts a service from another daemon to a daemon
// service.
func serviceFromProto(p *daemonpb.Service) (*daemonService, error) {
	var conf *config.PluginConfig
	if len(p.GetConfig()) > 0 {
		var err error
		if conf, err = config.ParsePluginConfigFromBytes(p.GetConfig()); err != nil {
			return nil, err
		}
	}
	return &daemonService{
		name:       p.GetName(),
		category:   p.GetCategory(),
		uri:        p.GetUri(),
		pluginName: p.GetPlugin(),
		config:     conf,
		auth:       listener.ToCode(p.GetAuth()),
		isolation:  p.GetIsolation(),
		local:      false,
	}, nil
}
