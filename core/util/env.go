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

// GetConfigHome returns the XDG config home root.
func GetConfigHome() string {
	return xdg.ConfigHome
}

// GetConfigDir returns the application config directory, creating it if it
// does not exist.
func GetConfigDir() (string, error) {
	configPath := filepath.Join(GetConfigHome(), projectDir)
	err := os.MkdirAll(configPath, 0755)
	if err != nil {
		return "", err
	}
	return configPath, nil
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

// GetCredsDir returns the application credentials directory, creating it if it
// does not exist.
func GetCredsDir() (string, error) {
	credsPath := filepath.Join(GetRuntimeDir(), projectDir, credsDir)
	err := os.MkdirAll(credsPath, 0755)
	if err != nil {
		return "", err
	}
	return credsPath, nil
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

// GetPackageDirByCategory returns the persistent directory for installed packages
// by category, creating it if it does not exist.
func GetPackageDirByCategory(category string) (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, packageDir, category)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return "", err
	}
	return dir, nil
}

// GetPackageDirByCategoryAndName returns the directory for a package by name
// and category, returning an error if it does not exist.
func GetPackageDirByCategoryAndName(category, name string) (string, error) {
	dir, err := GetPackageDirByCategory(category)
	if err != nil {
		return "", err
	}
	path := filepath.Join(dir, name)
	if _, err = os.Stat(path); err != nil {
		return "", err
	}
	return path, nil
}

// GetLogByName returns the log file for a service by name, creating it if it does
// not exist.
func GetLogByName(name string) (string, error) {
	file := filepath.Join(GetDataHome(), projectDir, logDir, name+logSuffix)
	err := os.MkdirAll(file, 0755)
	if err != nil {
		return "", err
	}
	return file, nil
}

// GetPendingDir returns the pending directory for a daemon, creating it if it does
// not exist.
func GetPendingDir() (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, pendingDir)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return "", err
	}
	return dir, nil
}

// GetPendingDirByCategory returns the pending directory for a package category,
// creating it if it does not exist.
func GetPendingDirByCategory(category string) (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, pendingDir, category)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return "", err
	}
	return dir, nil
}

// GetModelDir returns the persistent directory for models.
func GetModelDir() (string, error) {
	modelPath := filepath.Join(GetDataHome(), projectDir, modelDir)
	err := os.MkdirAll(modelPath, 0755)
	if err != nil {
		return "", err
	}
	return modelPath, nil
}

// GetFileDir returns the persistent directory for transferred files.
func GetFileDir() (string, error) {
	filePath := filepath.Join(GetDataHome(), projectDir, fileDir)
	err := os.MkdirAll(filePath, 0755)
	if err != nil {
		return "", err
	}
	return filePath, nil
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

// GetPluginDirByCategory returns the runtime directory for plugins given a category,
// creating it if it does not exist.
func GetPluginDirByCategory(category string) (string, error) {
	pluginPath := filepath.Join(GetRuntimeDir(), projectDir, pluginDir, category)
	err := os.MkdirAll(pluginPath, 0755)
	if err != nil {
		return "", err
	}
	return pluginPath, nil
}

// GetPluginDirByCategoryAndName returns the runtime directory for the plugin with the given category
// and name, creating it if it does not exist.
func GetPluginDirByCategoryAndName(category, name string) (string, error) {
	pluginPath := filepath.Join(GetRuntimeDir(), projectDir, pluginDir, category, name)
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

// GetVehicleDataDirByName returns the persistent data directory for the vehicle
// with the given name, creating it if it does not exist.
func GetVehicleDataDirByName(name string) (string, error) {
	dir := filepath.Join(GetDataHome(), projectDir, vehicleDir, name)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return "", err
	}
	return dir, nil
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

// GetDaemonSocketPath returns the path of the daemon's control socket, which
// local tools call the daemon on. It is within the daemon runtime directory,
// which is not created.
func GetDaemonSocketPath() string {
	return filepath.Join(GetRuntimeDir(), projectDir, daemonSocket)
}
