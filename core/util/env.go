package util

import (
	"os"
	"path/filepath"

	"github.com/adrg/xdg"
)

// GetRuntimeDir returns the XDG runtime directory root.
func GetRuntimeDir() string {
	return xdg.RuntimeDir
}

// GetDataHome returns the XDG data home root.
func GetDataHome() string {
	return xdg.DataHome
}

// GetDataDir returns the persistent application data directory, creating it if
// it does not exist.
func GetDataDir() (string, error) {
	dataPath := filepath.Join(GetDataHome(), projectDir)
	err := os.MkdirAll(dataPath, 0755)
	if err != nil {
		return "", err
	}
	return dataPath, nil
}

// GetInstalledPluginDir returns the persistent directory installed plugins of
// the given category (e.g. "driver", "mission", "extra") are stored in, kept
// separate per category so the same name can't collide across categories.
func GetInstalledPluginDir(category string) (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, installedPluginDir, category)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return "", err
	}
	return dir, nil
}

// GetPluginDir returns the runtime directory for all plugins.
func GetPluginDir() (string, error) {
	pluginPath := filepath.Join(GetRuntimeDir(), projectDir, pluginDir)
	err := os.MkdirAll(pluginPath, 0755)
	if err != nil {
		return "", err
	}
	return pluginPath, nil
}

// GetPluginDirByName returns the runtime directory for the plugin with the
// given name and parent, creating it if it does not exist.
func GetPluginDirByName(name, parent string) (string, error) {
	var pluginPath string
	if parent == "" { // if the parent is not set, place the plugin in the main runtime directory
		pluginPath = filepath.Join(xdg.RuntimeDir, projectDir, pluginDir, name)
	} else if filepath.IsAbs(parent) {
		pluginPath = filepath.Join(parent, pluginDir, name)
	} else { // if parent is set, place the plugin in that directory
		pluginPath = filepath.Join(xdg.RuntimeDir, projectDir, parent, pluginDir, name)
	}
	err := os.MkdirAll(pluginPath, 0755)
	if err != nil {
		return "", err
	}
	return pluginPath, nil
}

// GetVehicleRuntimeDir returns the vehicle runtime directory, creating it if
// it does not exist.
func GetVehicleDir() (string, error) {
	vehiclePath := filepath.Join(xdg.RuntimeDir, projectDir, vehicleDir)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return "", err
	}
	return vehiclePath, nil
}

// GetVehicleDirByName returns the runtime directory for the vehicle with the
// given ID, creating it if it does not exist.
func GetVehicleDirByName(name string) (string, error) {
	vehiclePath := filepath.Join(xdg.RuntimeDir, projectDir, vehicleDir, name)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return "", err
	}
	return vehiclePath, nil
}
