package main

import (
	"fmt"

	eagledpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/eagled"
)

// Plugin category names, used both as the on-disk directory name (see
// util.GetInstalledPluginDir) and as the persisted category string in
// installedPluginRecord.
const (
	categoryDriver  = "driver"
	categoryMission = "mission"
	categoryExtra   = "extra"
)

// categoryName converts a protocol PluginCategory to its string form, or
// errors if it's missing/unrecognized.
func categoryName(c eagledpb.PluginCategory) (string, error) {
	switch c {
	case eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER:
		return categoryDriver, nil
	case eagledpb.PluginCategory_PLUGIN_CATEGORY_MISSION:
		return categoryMission, nil
	case eagledpb.PluginCategory_PLUGIN_CATEGORY_EXTRA:
		return categoryExtra, nil
	default:
		return "", fmt.Errorf("category must be one of %q, %q, %q", categoryDriver, categoryMission, categoryExtra)
	}
}

// protoCategory converts a persisted category string back to its protocol
// PluginCategory, for GetInstalledPlugins responses.
func protoCategory(name string) eagledpb.PluginCategory {
	switch name {
	case categoryDriver:
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_DRIVER
	case categoryMission:
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_MISSION
	case categoryExtra:
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_EXTRA
	default:
		return eagledpb.PluginCategory_PLUGIN_CATEGORY_UNSPECIFIED
	}
}
