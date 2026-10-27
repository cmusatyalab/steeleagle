package daemon

import (
	"errors"
	"fmt"
	"io/fs"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strings"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/download"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Package changes wait in the pending directory until the next daemon start,
// so that running plugins are never changed under them. An install is the
// downloaded package, under its package name, and a removal is an empty file
// named PendingRemovePrefix followed by the package name. Package names have
// no dots, so the two never collide.

// installPackage installs the package at uri into the pending directory,
// replacing any pending install or removal of it, with a PackageUrlFileName
// file at its root holding the uri. The package is staged outside of the
// pending directory, so that a failed install leaves nothing behind there. It
// takes effect on the next daemon start. The caller must hold pkgMu.
func installPackage(uri string) error {
	pending, err := util.GetPendingDir()
	if err != nil {
		return err
	}
	tmp, err := os.MkdirTemp(filepath.Dir(pending), ".install-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)
	staged := filepath.Join(tmp, "pkg")
	if err := download.InstallPackage(uri, staged); err != nil {
		return err
	}
	plugins, err := readPlugins(staged)
	if err != nil {
		return err
	}
	if len(plugins) == 0 {
		return fmt.Errorf("package has no %s files", PluginFileSuffix)
	}
	if err := os.WriteFile(filepath.Join(staged, PackageUrlFileName), []byte(uri), 0644); err != nil {
		return err
	}
	name := getPackageDir(uri)
	if err := os.Remove(filepath.Join(pending, PendingRemovePrefix+name)); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return err
	}
	target := filepath.Join(pending, name)
	if err := os.RemoveAll(target); err != nil {
		return err
	}
	return os.Rename(staged, target)
}

// removePackage removes the package at uri, dropping any pending install of
// it, and marking it for removal if it is installed. It returns an error
// wrapping fs.ErrNotExist if the package is neither installed nor pending, or
// is already marked for removal. It takes effect on the next daemon start. The
// caller must hold pkgMu.
func removePackage(uri string) error {
	pending, err := util.GetPendingDir()
	if err != nil {
		return err
	}
	name := getPackageDir(uri)
	marker := filepath.Join(pending, PendingRemovePrefix+name)
	if _, err := os.Lstat(marker); err == nil {
		return fmt.Errorf("package %s: %w", uri, fs.ErrNotExist)
	}
	added := filepath.Join(pending, name)
	_, err = os.Lstat(added)
	wasAdded := err == nil
	if err := os.RemoveAll(added); err != nil {
		return err
	}
	if _, err := util.GetPackageDirByName(name); err != nil {
		if wasAdded {
			return nil
		}
		return fmt.Errorf("package %s: %w", uri, fs.ErrNotExist)
	}
	return os.WriteFile(marker, nil, 0644)
}

// listPackages lists the packages as they will be after the next daemon
// start: the installed packages, without those marked for removal, and with
// pending installs in place of the installed versions. Each package is listed
// by the uri in its PackageUrlFileName file; a directory without one isn't a
// package. The caller must hold pkgMu.
func listPackages() ([]*daemonpb.Package, error) {
	pending, err := util.GetPendingDir()
	if err != nil {
		return nil, err
	}
	installed, err := util.GetPackageDir()
	if err != nil {
		return nil, err
	}
	// Package names mapped to their directories, pending installs last so
	// that they replace installed versions
	dirs := map[string]string{}
	for _, root := range []string{installed, pending} {
		entries, err := os.ReadDir(root)
		if err != nil {
			return nil, err
		}
		for _, e := range entries {
			if !e.IsDir() || strings.HasPrefix(e.Name(), ".") {
				continue
			}
			dirs[e.Name()] = filepath.Join(root, e.Name())
		}
	}
	entries, err := os.ReadDir(pending)
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		if name, ok := strings.CutPrefix(e.Name(), PendingRemovePrefix); ok {
			delete(dirs, name)
		}
	}

	var packages []*daemonpb.Package
	for _, name := range slices.Sorted(maps.Keys(dirs)) {
		dir := dirs[name]
		uri, err := os.ReadFile(filepath.Join(dir, PackageUrlFileName))
		if err != nil {
			continue
		}
		plugins, err := readPlugins(dir)
		if err != nil {
			return nil, err
		}
		info, err := os.Stat(dir)
		if err != nil {
			return nil, err
		}
		packages = append(packages, daemonpb.Package_builder{
			Uri:      strings.TrimSpace(string(uri)),
			Plugins:  plugins,
			Modified: timestamppb.New(info.ModTime()),
		}.Build())
	}
	return packages, nil
}

// commitPackages applies the package changes in the pending directory to the
// package directory, leaving it empty. A removal deletes the installed
// package, and an install replaces it. Packages without pending changes are
// left alone, keeping their environments. It is called on every daemon start,
// before any plugin runs.
func commitPackages() error {
	pending, err := util.GetPendingDir()
	if err != nil {
		return err
	}
	installed, err := util.GetPackageDir()
	if err != nil {
		return err
	}
	entries, err := os.ReadDir(pending)
	if err != nil {
		return err
	}
	for _, e := range entries {
		change := filepath.Join(pending, e.Name())
		if name, ok := strings.CutPrefix(e.Name(), PendingRemovePrefix); ok {
			if err := os.RemoveAll(filepath.Join(installed, name)); err != nil {
				return err
			}
			if err := os.Remove(change); err != nil {
				return err
			}
			continue
		}
		target := filepath.Join(installed, e.Name())
		if err := os.RemoveAll(target); err != nil {
			return err
		}
		// Both directories are in the data directory, so this is a move
		if err := os.Rename(change, target); err != nil {
			return err
		}
	}
	return nil
}

// readPlugins reads the plugin files at the root of a package, mapping each
// plugin name to the contents of its file.
func readPlugins(dir string) (map[string][]byte, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	plugins := make(map[string][]byte)
	for _, e := range entries {
		name, ok := strings.CutSuffix(e.Name(), PluginFileSuffix)
		if !ok || !e.Type().IsRegular() {
			continue
		}
		content, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return nil, err
		}
		plugins[name] = content
	}
	return plugins, nil
}
