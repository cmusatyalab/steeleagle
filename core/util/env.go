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

// GetPluginDir returns the runtime directory for all plugins.
func GetPluginDir() (string, error) {
	pluginPath := filepath.Join(GetRuntimeDir(), runtimeDir, pluginDir)
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
		pluginPath = filepath.Join(xdg.RuntimeDir, runtimeDir, pluginDir, name)
	} else if filepath.IsAbs(parent) {
		pluginPath = filepath.Join(parent, pluginDir, name)
	} else { // if parent is set, place the plugin in that directory
		pluginPath = filepath.Join(xdg.RuntimeDir, runtimeDir, parent, pluginDir, name)
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
	vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return "", err
	}
	return vehiclePath, nil
}

// GetVehicleDirByName returns the runtime directory for the vehicle with the
// given ID, creating it if it does not exist.
func GetVehicleDirByName(name string) (string, error) {
	vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir, name)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return "", err
	}
	return vehiclePath, nil
}
