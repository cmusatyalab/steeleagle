package daemon

import (
	"encoding/json"
	"errors"
	"io/fs"
	"maps"
	"os"
	"path/filepath"
	"slices"
)

// loadStopped reads the services stopped by request, by their names in the
// daemon config, from the file at path, a JSON list of names. A missing file
// means that none are.
func loadStopped(path string) (map[string]bool, error) {
	stopped := map[string]bool{}
	content, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return stopped, nil
	}
	if err != nil {
		return nil, err
	}
	var names []string
	if err := json.Unmarshal(content, &names); err != nil {
		return nil, err
	}
	for _, name := range names {
		stopped[name] = true
	}
	return stopped, nil
}

// saveStopped writes the services stopped by request to the file at path, as
// loadStopped reads them.
func saveStopped(path string, stopped map[string]bool) error {
	names := slices.Sorted(maps.Keys(stopped))
	if names == nil {
		names = []string{}
	}
	content, err := json.Marshal(names)
	if err != nil {
		return err
	}
	return writeFileAtomic(path, content)
}

// writeFileAtomic replaces the file at path with content, by writing it to a
// temporary file next to it and renaming that over it, so that the file is
// never left partly written.
func writeFileAtomic(path string, content []byte) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+"-*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	_, err = tmp.Write(content)
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	return os.Rename(tmp.Name(), path)
}
