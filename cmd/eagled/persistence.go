package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"

	"github.com/BurntSushi/toml"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog/log"
)

// PersistedConfigFile is the name of the last-applied eagled config, kept in
// core/util.GetDataDir() so a restarted eagled can bring its vehicles back
// without another Configure call.
const PersistedConfigFile = "applied-config.toml"

// PersistedPluginsFile is the name of the last-installed-plugin record, kept
// in core/util.GetDataDir() so a restarted eagled knows which plugins are
// installed.
const PersistedPluginsFile = "installed-plugins.toml"

// persist writes the daemon's current desired state (baseCfg plus every known
// vehicle) to disk, so a restarted eagled can reload it.
func (d *daemon) persist() {
	d.mu.Lock()
	cfg := d.baseCfg
	cfg.Vehicles = make([]VehicleConfig, 0, len(d.vehicleCfgs))
	for _, v := range d.vehicleCfgs {
		cfg.Vehicles = append(cfg.Vehicles, v)
	}
	d.mu.Unlock()

	path, err := persistedConfigPath()
	if err != nil {
		log.Warn().Err(err).Msg("could not determine config persistence path")
		return
	}
	persistToml(path, cfg, "config")
}

// loadPersisted reads and applies the last-persisted config, if any.
func (d *daemon) loadPersisted() error {
	path, err := persistedConfigPath()
	if err != nil {
		return err
	}
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("reading %s: %w", path, err)
	}

	cfg, err := decodeConfig(string(data))
	if err != nil {
		return fmt.Errorf("parsing %s: %w", path, err)
	}
	if err := d.ensureConfigured(cfg); err != nil {
		return err
	}
	if err := d.ensureAviary(cfg.Vehicles); err != nil {
		return err
	}
	for _, result := range d.startVehicles(cfg.Vehicles) {
		if !result.GetOk() {
			log.Error().Str("vehicle", result.GetName()).Str("error", result.GetError()).
				Msg("failed to restart vehicle from persisted config")
		}
	}
	return nil
}

// installedPluginRecord is one entry in installedPluginsDoc.
type installedPluginRecord struct {
	Ref      string `toml:"ref"`      // commit SHA, branch, or tag last installed
	Category string `toml:"category"` // "driver", "mission", or "extra"
}

// installedPluginsDoc is persisted to PersistedPluginsFile.
type installedPluginsDoc struct {
	Plugins map[string]installedPluginRecord `toml:"plugins"` // plugin name -> {ref, category}
}

// persistInstalled writes the daemon's current name->{ref,category} record to
// disk.
func (d *daemon) persistInstalled() {
	d.mu.Lock()
	installed := make(map[string]installedPluginRecord, len(d.installed))
	for name, rec := range d.installed {
		installed[name] = rec
	}
	d.mu.Unlock()

	path, err := persistedPluginsPath()
	if err != nil {
		log.Warn().Err(err).Msg("could not determine plugin persistence path")
		return
	}
	persistToml(path, installedPluginsDoc{Plugins: installed}, "installed plugins")
}

// loadPersistedInstalled reads the last-persisted name->{ref,category}
// record, if any.
func (d *daemon) loadPersistedInstalled() error {
	path, err := persistedPluginsPath()
	if err != nil {
		return err
	}
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("reading %s: %w", path, err)
	}

	var doc installedPluginsDoc
	if _, err := toml.Decode(string(data), &doc); err != nil {
		return fmt.Errorf("parsing %s: %w", path, err)
	}

	d.mu.Lock()
	for name, rec := range doc.Plugins {
		d.installed[name] = rec
	}
	d.mu.Unlock()
	return nil
}

// persistedPluginsPath returns the path of the installed-plugins record file.
func persistedPluginsPath() (string, error) {
	dataDir, err := util.GetDataDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dataDir, PersistedPluginsFile), nil
}

// decodeConfig parses a TOML document into a Config, warning (but not failing)
// on unrecognized keys.
func decodeConfig(data string) (Config, error) {
	var cfg Config
	md, err := toml.Decode(data, &cfg)
	if err != nil {
		return Config{}, err
	}
	if undecoded := md.Undecoded(); len(undecoded) > 0 {
		keys := make([]string, len(undecoded))
		for i, k := range undecoded {
			keys[i] = k.String()
		}
		log.Warn().Strs("keys", keys).Msg("unrecognized keys in config")
	}
	return cfg, nil
}

// persistedConfigPath returns the path of the eagled config file.
func persistedConfigPath() (string, error) {
	dataDir, err := util.GetDataDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dataDir, PersistedConfigFile), nil
}

// persistToml encodes v as TOML and atomically writes it to path, warning
// (without failing) on any error. what names v for the warning message.
func persistToml(path string, v any, what string) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(v); err != nil {
		log.Warn().Err(err).Msgf("could not encode %s for persistence", what)
		return
	}
	if err := writeFileAtomic(path, buf.Bytes()); err != nil {
		log.Warn().Err(err).Msgf("could not write persisted %s", what)
	}
}

// writeFileAtomic replaces path's contents with data without a reader ever
// observing a partially-written file. Data is written to a temp file in path's
// own directory and only swapped into place once fully flushed.
func writeFileAtomic(path string, data []byte) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".*.tmp")
	if err != nil {
		return fmt.Errorf("creating temp file: %w", err)
	}
	defer os.Remove(tmp.Name()) // no-op once the rename below succeeds

	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return fmt.Errorf("writing temp file: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("closing temp file: %w", err)
	}
	if err := os.Rename(tmp.Name(), path); err != nil {
		return fmt.Errorf("renaming into place: %w", err)
	}
	return nil
}
