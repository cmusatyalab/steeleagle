package core

import (
    "log"
    "log/slog"
    "os"
    "encoding/json"
    "path/filepath"

    "github.com/pelletier/go-toml/v2"
)

type law struct {
    first     string     `toml:"first"`
    states    []State    `toml:"states,omitempty"`
}

type state struct {
    name      string     `toml:"name" json:"name"`
    enter     []string   `toml:"enter,omitempty" json:"enter"`
    allowed   []string   `toml:"allowed,omitempty" json:"allowed"`
    match     [][]string `toml:"match,omitempty" json:"match"`
}

func getLaw() (map[string]state, string) {
    configDir, err := os.UserConfigDir()
    if err != nil {
        slog.warn("OS config directory could not be found! Using default laws.")
        return getDefaultLaw()
    }

    appDir := filepath.join(configDir, ApplicationName)
    configPath := filepath.Join(appDir, LawFilename)
    
    data, err := os.ReadFile(configPath)
    if err != nil {
        slog.warn(fmt.Sprintf("Could not find law file %s:\n%v\nUsing default laws.", configPath, err))
        return getDefaultLaw()
    }

    var l law
    err := toml.Unmarshal(data, &l)
    if err != nil {
        slog.warn(fmt.Sprintf("Something went wrong reading law file %s:\n%v\nUsing default laws.", configPath, err))
        return getDefaultLaw()
    }
    
    return createLawMap(l), l.first
}

func getDefaultLaw() (map[string]state, string) {
    l, err := parseDefaultLaw()
    if err != nil {
        panic(err)
    }

    return createLawMap(l), l.first
}

func createLawMap(l law) (map[string]state) {
    var m map[string]state
    for index, value := range l.states {
        m[value.name] = value
    }
    return m
}

func parseDefaultLaw() (law, error) {
    var l law
    err := toml.Unmarshal(constants.DefaultLaw, &l)
    return l, err
}
