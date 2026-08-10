package main

import (
	"context"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/cmusatyalab/steeleagle/core/util"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// InstallPlugin fetches and installs a plugin under req's name and category,
// recording the ref it installed so a restarted eagled knows what's on disk
// without re-fetching it.
func (d *daemon) InstallPlugin(ctx context.Context, req *eagledpb.InstallPluginRequest) (*eagledpb.InstallPluginResponse, error) {
	d.mu.Lock()
	configured := d.configured
	d.mu.Unlock()
	if !configured {
		return nil, status.Error(codes.FailedPrecondition, "daemon must be configured (Configure) before installing plugins")
	}

	category, err := categoryName(req.GetCategory())
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}
	installDir, err := util.GetInstalledPluginDir(category)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "determining install directory: %v", err)
	}

	if err := installPlugin(ctx, installDir, req.GetName(), req.GetRepo(), req.GetRef(), req.GetSubpath()); err != nil {
		return eagledpb.InstallPluginResponse_builder{Ok: false, Error: err.Error()}.Build(), nil
	}

	d.mu.Lock()
	d.installed[req.GetName()] = installedPluginRecord{Ref: req.GetRef(), Category: category}
	d.mu.Unlock()
	d.persistInstalled()

	return eagledpb.InstallPluginResponse_builder{Ok: true}.Build(), nil
}

// GetInstalledPlugins lists every plugin name this daemon has installed, the
// ref it was last installed at, and its category.
func (d *daemon) GetInstalledPlugins(ctx context.Context, req *eagledpb.GetInstalledPluginsRequest) (*eagledpb.GetInstalledPluginsResponse, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	plugins := make([]*eagledpb.InstalledPlugin, 0, len(d.installed))
	for name, rec := range d.installed {
		plugins = append(plugins, eagledpb.InstalledPlugin_builder{
			Name:     name,
			Ref:      rec.Ref,
			Category: protoCategory(rec.Category),
		}.Build())
	}
	return eagledpb.GetInstalledPluginsResponse_builder{Plugins: plugins}.Build(), nil
}
