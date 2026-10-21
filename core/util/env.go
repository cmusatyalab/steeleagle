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

// GetVpnDir returns the persistent vpn data directory, creating it if it does
// not exist.
func GetVpnDir() (string, error) {
	vpnPath := filepath.Join(GetDataHome(), projectDir, vpnDir)
	err := os.MkdirAll(vpnPath, 0755)
	if err != nil {
		return "", err
	}
	return vpnPath, nil
}

// GetPackageDir returns the persistent directory installed packages.
func GetPackageDir(category string) (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, packageDir)
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
		pluginPath = filepath.Join(GetRuntimeDir(), projectDir, pluginDir, name)
	} else if filepath.IsAbs(parent) {
		pluginPath = filepath.Join(parent, pluginDir, name)
	} else { // if parent is set, place the plugin in that directory
		pluginPath = filepath.Join(GetRuntimeDir(), projectDir, parent, pluginDir, name)
	}
	err := os.MkdirAll(pluginPath, 0755)
	if err != nil {
		return "", err
	}
	return pluginPath, nil
}

// GetVehicleRunDir returns the vehicle parent runtime directory, creating it if
// it does not exist.
func GetVehicleRunDir() (string, error) {
	vehiclePath := filepath.Join(GetRuntimeDir(), projectDir, vehicleDir)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return "", err
	}
	return vehiclePath, nil
}

// GetVehicleRunDirByName returns the runtime directory for the vehicle with the
// given name, creating it if it does not exist.
func GetVehicleRunDirByName(name string) (string, error) {
	vehiclePath := filepath.Join(GetRuntimeDir(), projectDir, vehicleDir, name)
	err := os.MkdirAll(vehiclePath, 0755)
	if err != nil {
		return "", err
	}
	return vehiclePath, nil
}

// GetVehicleMissionDirByName returns the persistent mission directory for the vehicle
// with the given name, creating it if it does not exist.
func GetVehicleMissionDirByName(name string) (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, vehicleDir, name, missionDir)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return "", err
	}
	return dir, nil
}

// GetDaemonRunDir returns the daemon runtime directory, creating it if it does
// not exist.
func GetDaemonRunDir() (string, error) {
	daemonPath := filepath.Join(GetRuntimeDir(), projectDir)
	err := os.MkdirAll(daemonPath, 0755)
	if err != nil {
		return "", err
	}
	return daemonPath, nil
}
