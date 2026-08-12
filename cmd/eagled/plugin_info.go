package main

import (
	"context"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// InstallPlugin fetches and installs a plugin under req's name and category,
// recording the ref it installed so a restarted eagled knows what's on disk
// without re-fetching it.
func (d *daemon) InstallPlugin(ctx context.Context, req *eagledpb.InstallPluginRequest) (*eagledpb.InstallPluginResponse, error) {
	category, err := categoryName(req.GetCategory())
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}
	log.Info().Str("plugin", req.GetName()).Str("category", category).Str("repo", req.GetRepo()).Str("ref", req.GetRef()).
		Msg("InstallPlugin received")
	installDir, err := util.GetInstalledPluginDir(category)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "determining install directory: %v", err)
	}

	if err := installPlugin(ctx, installDir, req.GetName(), req.GetRepo(), req.GetRef(), req.GetSubpath()); err != nil {
		log.Warn().Str("plugin", req.GetName()).Err(err).Msg("plugin install failed")
		return eagledpb.InstallPluginResponse_builder{Ok: false, Error: err.Error()}.Build(), nil
	}

	d.mu.Lock()
	d.installed[installedPluginKey{Name: req.GetName(), Category: category}] = req.GetRef()
	d.mu.Unlock()
	d.persistInstalled()

	log.Info().Str("plugin", req.GetName()).Str("category", category).Str("ref", req.GetRef()).Msg("plugin installed")
	return eagledpb.InstallPluginResponse_builder{Ok: true}.Build(), nil
}

// GetInstalledPlugins lists every plugin name this daemon has installed, the
// ref it was last installed at, and its category.
func (d *daemon) GetInstalledPlugins(ctx context.Context, req *eagledpb.GetInstalledPluginsRequest) (*eagledpb.GetInstalledPluginsResponse, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	plugins := make([]*eagledpb.InstalledPlugin, 0, len(d.installed))
	for key, ref := range d.installed {
		plugins = append(plugins, eagledpb.InstalledPlugin_builder{
			Name:     key.Name,
			Ref:      ref,
			Category: protoCategory(key.Category),
		}.Build())
	}
	return eagledpb.GetInstalledPluginsResponse_builder{Plugins: plugins}.Build(), nil
}
