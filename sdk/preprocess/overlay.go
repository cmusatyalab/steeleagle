package preprocess

import (
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"golang.org/x/tools/go/packages"
)

// OverlayConfig configures CreateOverlay.
type OverlayConfig struct {
	Dir        string   // directory of the Go module to resolve packages in
	Env        []string // environment for the package load, on top of the process's
	BuildFlags []string // build flags for the package load

	// Modules lists the modules whose packages are overlaid. Packages from
	// any other module are left as they are.
	Modules []string
	// ModulesOf lists import paths whose modules are overlaid too: the
	// module of any package in the graph at or under one of these paths,
	// whatever module path or version it resolves to.
	ModulesOf []string
	// Supports reports whether the vehicle supports a feature named by a
	// directive. Nil supports everything.
	Supports func(string) bool
	// Consts maps the import path of each package to generate constants
	// into to the constants to generate there: string type names to the
	// names of their constants (see GenerateConsts).
	Consts map[string]map[string][]string
}

// CreateOverlay creates a Go compiler overlay for the import graph of
// paths, resolved in the module at cfg.Dir the same way a later load or
// build with cfg.Env and cfg.BuildFlags resolves them, so the overlay is
// keyed by the files those actually read. The overlay replaces the source
// files of the graph's packages from the overlaid modules (see
// cfg.Modules and cfg.ModulesOf) with files scrubbed according to
// preprocessor directives, and rewrites the packages in cfg.Consts to
// declare their constants. Constants are generated into the packages' own
// source files as loaded, so they always match the version being built
// against.
func CreateOverlay(cfg OverlayConfig, paths ...string) (map[string][]byte, []*PreprocessError) {
	load := &packages.Config{
		Dir:        cfg.Dir,
		Env:        append(os.Environ(), cfg.Env...),
		BuildFlags: cfg.BuildFlags,
		Mode:       packages.NeedName | packages.NeedFiles | packages.NeedImports | packages.NeedDeps | packages.NeedModule,
	}
	pkgs, err := packages.Load(load, paths...)
	if err != nil {
		return nil, []*PreprocessError{{error: err}}
	}
	supports := cfg.Supports
	if supports == nil {
		supports = func(string) bool { return true }
	}
	return overlayPackages(supports, cfg.Consts, ModulePackages(pkgs, cfg.Modules, cfg.ModulesOf))
}

// ModulePackages returns every package in the import graph of roots that
// belongs to one of the modules in modules, or to the module of a package
// in the graph at or under one of the import paths in modulesOf. Packages
// from any other module, and from the standard library, are left out.
// roots must be loaded with packages.NeedDeps, packages.NeedImports and
// packages.NeedModule.
func ModulePackages(roots []*packages.Package, modules, modulesOf []string) []*packages.Package {
	listed := make(map[string]bool, len(modules))
	for _, m := range modules {
		listed[m] = true
	}
	var all []*packages.Package
	packages.Visit(roots, nil, func(p *packages.Package) {
		if p.Module != nil && underAny(p.PkgPath, modulesOf) {
			listed[p.Module.Path] = true
		}
		all = append(all, p)
	})
	var out []*packages.Package
	for _, p := range all {
		if p.Module != nil && listed[p.Module.Path] {
			out = append(out, p)
		}
	}
	return out
}

// underAny reports whether the import path path is at or under one of
// paths.
func underAny(path string, paths []string) bool {
	for _, p := range paths {
		if path == p || strings.HasPrefix(path, p+"/") {
			return true
		}
	}
	return false
}

// WriteOverlay writes overlay into dir, replacing anything already there,
// in the form go build's -overlay flag expects: one file per replaced
// source file, plus a JSON file mapping each source file to its
// replacement. It returns the absolute path of the JSON file.
func WriteOverlay(dir string, overlay map[string][]byte) (string, error) {
	dir, err := filepath.Abs(dir)
	if err != nil {
		return "", err
	}
	if err := os.RemoveAll(dir); err != nil {
		return "", fmt.Errorf("failed to clear overlay directory: %w", err)
	}
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", fmt.Errorf("failed to create overlay directory: %w", err)
	}
	replace := make(map[string]string, len(overlay))
	for i, file := range slices.Sorted(maps.Keys(overlay)) {
		dst := filepath.Join(dir, fmt.Sprintf("%d_%s", i, filepath.Base(file)))
		if err := os.WriteFile(dst, overlay[file], 0o644); err != nil {
			return "", fmt.Errorf("failed to write overlay file: %w", err)
		}
		replace[file] = dst
	}
	data, err := json.Marshal(struct{ Replace map[string]string }{replace})
	if err != nil {
		return "", err
	}
	overlayJson := filepath.Join(dir, "overlay.json")
	if err := os.WriteFile(overlayJson, data, 0o644); err != nil {
		return "", fmt.Errorf("failed to write overlay file: %w", err)
	}
	return overlayJson, nil
}

// overlayPackages creates the overlay for packages: their source files
// scrubbed with supports, except for the packages in consts, which get
// their constants generated instead.
func overlayPackages(supports func(string) bool, consts map[string]map[string][]string, packages []*packages.Package) (map[string][]byte, []*PreprocessError) {
	overlay := map[string][]byte{}
	var errs []*PreprocessError
	for _, pkg := range packages {
		// Check if this package is a package that contains consts to generate
		if pkgConsts, isConstPkg := consts[pkg.PkgPath]; isConstPkg {
			gen, genErrs := generateConsts(pkg, pkgConsts)
			maps.Copy(overlay, gen)
			errs = append(errs, genErrs...)
			continue
		}
		for _, file := range pkg.GoFiles {
			src, err := os.ReadFile(file)
			if err != nil {
				errs = append(errs, fileError(err, pkg.PkgPath))
				continue
			}
			scrubbed, dirty, err := Scrub(supports, src)
			if err != nil {
				errs = append(errs, fileError(err, pkg.PkgPath))
				continue
			}
			if dirty { // only overwrite file if it was changed
				overlay[file] = scrubbed
			}
		}
	}
	return overlay, errs
}

// generateConsts generates the constants in consts into the files of pkg
// that declare their types, returning an overlay of the rewritten files.
// Every type in consts must be declared as a string type in some file of
// pkg.
func generateConsts(pkg *packages.Package, consts map[string][]string) (map[string][]byte, []*PreprocessError) {
	overlay := map[string][]byte{}
	var errs []*PreprocessError
	remaining := maps.Clone(consts)
	for _, file := range pkg.GoFiles {
		src, err := os.ReadFile(file)
		if err != nil {
			errs = append(errs, fileError(err, pkg.PkgPath))
			continue
		}
		declared, err := DeclaredStringTypes(src)
		if err != nil {
			errs = append(errs, fileError(err, pkg.PkgPath))
			continue
		}
		fileConsts := map[string][]string{}
		for _, typeName := range declared {
			if names, ok := remaining[typeName]; ok {
				fileConsts[typeName] = names
				delete(remaining, typeName)
			}
		}
		if len(fileConsts) == 0 {
			continue
		}
		gen, err := GenerateConsts(fileConsts, src)
		if err != nil {
			errs = append(errs, fileError(err, pkg.PkgPath))
			continue
		}
		overlay[file] = gen
	}
	for _, typeName := range slices.Sorted(maps.Keys(remaining)) {
		errs = append(errs, fileError(
			fmt.Errorf("type %q is not declared as string in package %s", typeName, pkg.PkgPath),
			pkg.PkgPath,
		))
	}
	return overlay, errs
}

// fileError attributes err to file. If err is (or wraps) a
// *PreprocessError, its LineNo carries over, otherwise LineNo is left
// zero.
func fileError(err error, file string) *PreprocessError {
	fileErr := &PreprocessError{error: err, File: file}
	var preprocessErr *PreprocessError
	if errors.As(err, &preprocessErr) {
		fileErr.LineNo = preprocessErr.LineNo
	}
	return fileErr
}
