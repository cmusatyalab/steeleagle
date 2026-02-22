package core

import (
    "fmt"
    "os"

    "github.com/pelletier/go-toml/v2"
)

type controlLawState struct {
    Name      string     `toml:"name" json:"name"`
    Enter     []string   `toml:"enter,omitempty" json:"enter"`
    Allowed   []string   `toml:"allowed,omitempty" json:"allowed"`
    Match     [][]string `toml:"match,omitempty" json:"match"`
}

type controlLaw struct {
    First     string               `toml:"first" json:"first"`
    States    []controlLawState    `toml:"states,omitempty" json:"states"`
}

func getLaw(filename string) (map[string]controlLawState, string) {
    // If no file is provided, ignore and load default laws
    if filename == "" {
       return getDefaultLaw()
    }

    data, err := os.ReadFile(filename)
    if err != nil {
        logger.Warn().Err(err).Msg("could not find law file, using default laws")
        return getDefaultLaw()
    }

    l := &controlLaw{}
    err = toml.Unmarshal(data, l)
    if err != nil {
        logger.Warn().Err(err).Msg("something went wrong reading law file, using default laws")
        return getDefaultLaw()
    }
    
    m, err := createLawMap(l)
    if err != nil {
        logger.Warn().Err(err).Msg("something went wrong reading law file, using default laws")
        return getDefaultLaw() 
    }

    return m, l.First
}

func getDefaultLaw() (map[string]controlLawState, string) {
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

func createLawMap(l *controlLaw) (map[string]controlLawState, error) {
    m := make(map[string]controlLawState)
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

func parseDefaultLaw() (*controlLaw, error) {
    l := &controlLaw{}
    err := toml.Unmarshal(DefaultLaw, l)
    return l, err
}
