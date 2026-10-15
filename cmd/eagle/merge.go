package main

import (
	"bytes"
	"fmt"
	"os"
	"strings"

	"github.com/BurntSushi/toml"
)

// configFiles is the --config flag, which may be given more than once.
type configFiles []string

func (c *configFiles) String() string {
	return strings.Join(*c, ", ")
}

func (c *configFiles) Set(path string) error {
	*c = append(*c, path)
	return nil
}

// readConfig returns the TOML config in the files at paths. One file is
// returned as it is. Several are merged in order, as `docker compose -f`
// merges its files: a later file's values replace an earlier one's, tables
// merge key by key, and arrays, e.g. [[vehicles]] or a flow's engines, are
// replaced whole. So a vehicle's own settings can stay in one file, and each
// Gabriel flow it may run in a file of its own.
func readConfig(paths []string) (string, error) {
	if len(paths) == 1 {
		data, err := os.ReadFile(paths[0])
		if err != nil {
			return "", fmt.Errorf("reading %s: %w", paths[0], err)
		}
		return string(data), nil
	}
	merged := make(map[string]any)
	for _, path := range paths {
		var config map[string]any
		if _, err := toml.DecodeFile(path, &config); err != nil {
			return "", fmt.Errorf("reading %s: %w", path, err)
		}
		mergeTables(merged, config)
	}
	var out bytes.Buffer
	if err := toml.NewEncoder(&out).Encode(merged); err != nil {
		return "", fmt.Errorf("merging %s: %w", strings.Join(paths, ", "), err)
	}
	return out.String(), nil
}

// mergeTables merges src into dst: a table in both is merged key by key, and
// any other value of src replaces dst's.
func mergeTables(dst, src map[string]any) {
	for key, value := range src {
		if srcTable, ok := value.(map[string]any); ok {
			if dstTable, ok := dst[key].(map[string]any); ok {
				mergeTables(dstTable, srcTable)
				continue
			}
		}
		dst[key] = value
	}
}
