package config

import (
	"os"

	"github.com/BurntSushi/toml"
)

// ParseTomlFromFilepath parses a TOML file at filepath into a new T.
func ParseTomlFromFilepath[T any](filepath string) (*T, error) {
	content, err := os.ReadFile(filepath)
	if err != nil {
		return nil, err
	}
	return ParseTomlFromBytes[T](content)
}

// ParseTomlFromBytes parses TOML bytes into a new T.
func ParseTomlFromBytes[T any](content []byte) (*T, error) {
	t := new(T)
	if err := toml.Unmarshal(content, t); err != nil {
		return nil, err
	}
	return t, nil
}
