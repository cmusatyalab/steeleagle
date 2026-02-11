package core

import (
    "fmt"
    "log/slog"
    "os"
    "path/filepath"

    "github.com/pelletier/go-toml/v2"
)

type State struct {
    Name      string     `toml:"name" json:"name"`
    Enter     []string   `toml:"enter,omitempty" json:"enter"`
    Allowed   []string   `toml:"allowed,omitempty" json:"allowed"`
    Match     [][]string `toml:"match,omitempty" json:"match"`
}

type Law struct {
    First     string     `toml:"first" json:"first"`
    States    []State    `toml:"states,omitempty" json:"states"`
}

func getLaw() (map[string]State, string) {
    configDir, err := os.UserConfigDir()
    if err != nil {
        slog.Warn("OS config directory could not be found, using default laws")
        return getDefaultLaw()
    }

    appDir := filepath.Join(configDir, ApplicationName)
    configPath := filepath.Join(appDir, LawFilename)
    
    data, err := os.ReadFile(configPath)
    if err != nil {
        slog.Warn("could not find law file, using default laws", "error", err)
        return getDefaultLaw()
    }

    l := &Law{}
    err = toml.Unmarshal(data, l)
    if err != nil {
        slog.Warn("something went wrong reading law file, using default laws", "error", err)
        return getDefaultLaw()
    }
    
    m, err := createLawMap(l)
    if err != nil {
        slog.Warn("something went wrong reading law file, using default laws", "error", err)
        return getDefaultLaw() 
    }

    return m, l.First
}

func getDefaultLaw() (map[string]State, string) {
    l, err := parseDefaultLaw()
    if err != nil {
        panic(err)
    }

    m, err := createLawMap(l)
    if err != nil {
        panic(err)
    }

    return m, l.First
}

func createLawMap(l *Law) (map[string]State, error) {
    m := make(map[string]State)
    for _, value := range l.States {
        if value.Name == "" {
            return nil, fmt.Errorf("unnamed law found in configuration!")
        } else if _, exists := m[value.Name]; exists {
            return nil, fmt.Errorf("duplicate law %v detected!", value.Name)
        }
        m[value.Name] = value
    }
    return m, nil
}

func parseDefaultLaw() (*Law, error) {
    l := &Law{}
    err := toml.Unmarshal(DefaultLaw, l)
    return l, err
}
