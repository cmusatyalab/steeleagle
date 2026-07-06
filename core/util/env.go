package util

import (
	"errors"
	"os"
	"path/filepath"

	"github.com/adrg/xdg"
)

// CreateRuntimeDirs creates the XDG runtime directories for plugins and vehicles.
func CreateRuntimeDirs() error {
	// Create plugin and vehicle paths
	vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return err
	}
	pluginPath := filepath.Join(xdg.RuntimeDir, runtimeDir, pluginDir)
	err = os.MkdirAll(pluginPath, 0755)
	if err != nil {
		return err
	}

	return nil
}

// GetRuntimeDir returns the XDG runtime directory root.
func GetRuntimeDir() string {
	return xdg.RuntimeDir
}

// GetVehicleRuntimeDir returns the vehicle runtime directory, creating it if it does not exist.
func GetVehicleRuntimeDir() (string, error) {
	vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir)
	_, err := os.Stat(vehiclePath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return vehiclePath, CreateRuntimeDirs()
		} else {
			return "", nil
		}
	}

	return vehiclePath, nil
}

// GetPluginDirByName returns the runtime directory for the plugin with the given name and parent, creating it if it does not exist.
func GetPluginDirByName(name, vehicle string) (string, error) {
    var pluginPath string
    if vehicle == "" { // if the vehicle is not set, place the plugin in the main runtime directory
	    pluginPath = filepath.Join(xdg.RuntimeDir, runtimeDir, pluginDir, name)
    } else { // if vehicle is set, place the plugin in that directory
	    pluginPath = filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir, vehicle, pluginDir, name)
    }
	_, err := os.Stat(pluginPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return pluginPath, os.MkdirAll(pluginPath, 0755)
		} else {
			return "", err
		}
	}

	return pluginPath, nil
}

// GetVehicleDirByName returns the runtime directory for the vehicle with the given name, creating it if it does not exist.
func GetVehicleDirByName(name string) (string, error) {
	vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir, name)
	_, err := os.Stat(vehiclePath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return vehiclePath, os.MkdirAll(vehiclePath, 0755)
		} else {
			return "", err
		}
	}

	return vehiclePath, nil
}
