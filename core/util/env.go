package util

import (
    "os"
    "path/filepath"

	"github.com/adrg/xdg"
)

func CreateRuntimeDirs() error {
    // Create plugin and vehicle paths
    vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir)
    err := os.MkdirAll(vehiclePath, 0755)
    if err != nil {
        return err
    }
    pluginPath := filepath.Join(xdg.RuntimeDir, runtimeDir, pluginDir)
    err := os.MkdirAll(pluginPath, 0755)
    if err != nil {
        return err
    }

    return nil
}

func GetRuntimeDir() (string, error) {
    return xdg.RuntimeDir
}

func GetPluginRuntimeDir() (string, error) {
    pluginPath := filepath.Join(xdg.RuntimeDir, runtimeDir, pluginDir)
    info, err := os.Stat(pluginPath)
    if err != nil {
        if errors.Is(err, os.ErrNotExist) {
            return pluginPath, CreateRuntimeDirst()
        } else {
            return "", nil
        }
    }

    return pluginPath, nil
}

func GetVehicleRuntimeDir() (string, error) {
    vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir)
    info, err := os.Stat(vehiclePath)
    if err != nil {
        if errors.Is(err, os.ErrNotExist) {
            return vehiclePath, CreateRuntimeDirs()
        } else {
            return "", nil
        }
    }

    return vehiclePath, nil
}

func GetPluginDirByName(name string) (string, error) {
    pluginPath := filepath.Join(xdg.RuntimeDir, runtimeDir, pluginDir, name)
    info, err := os.Stat(pluginPath)
    if err != nil {
        if errors.Is(err, os.ErrNotExist) {
            return pluginPath, os.MkdirAll(pluginPath, 0755)
        } else {
            return "", err
        }
    }

    return pluginPath
}

func GetVehicleDirByName(name string) (string, error) {
    vehiclePath := filepath.Join(xdg.RuntimeDir, runtimeDir, vehicleDir, name)
    info, err := os.Stat(vehiclePath)
    if err != nil {
        if errors.Is(err, os.ErrNotExist) {
            return vehiclePath, os.MkdirAll(vehiclePath, 0755)
        } else {
            return "", err
        }
    }

    return vehiclePath, nil
}
