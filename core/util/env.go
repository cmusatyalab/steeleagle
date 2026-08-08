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

// GetDriverDir returns the persistent directory installed driver plugins are
// stored in.
func GetDriverDir() (string, error) {
	driverPath := filepath.Join(GetDataHome(), projectDir, driverDir)
	err := os.MkdirAll(driverPath, 0755)
	if err != nil {
		return "", err
	}
	return driverPath, nil
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
