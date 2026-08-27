package main

import (
	"os"
	"strings"

	"golang.org/x/tools/go/packages"
)

// steeleagleModule is the module every scrubbable/const-generated package
// (sdk, sdk/dsl/actions, sdk/params, sdk/dsl/swarm, ...) lives in. Only
// packages under it can carry the compiler's own directive comments
// (#optional, #exclude-ifndef, ...), so loadSteeleaglePackages restricts
// itself to this prefix rather than walking every transitive dependency
// (stdlib, grpc, ...) a mission's imports pull in.
const steeleagleModule = "github.com/cmusatyalab/steeleagle"

// loadSteeleaglePackages loads every package under steeleagleModule
// transitively reachable from pkgPaths (as resolved in workspace), for
// sdk.CreateOverlay to scrub. This is a plain, un-overlaid load: it needs
// each package's GoFiles to exist on disk so CreateOverlay can read and
// rewrite them, which is exactly what the *loader.LoadTypes reload with
// the resulting overlay is for.
func loadSteeleaglePackages(workspace string, pkgPaths []string) ([]*packages.Package, error) {
	cfg := &packages.Config{
		Dir:  workspace,
		Env:  append(os.Environ(), "GOFLAGS=-mod=mod"),
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedImports | packages.NeedDeps,
	}
	roots, err := packages.Load(cfg, pkgPaths...)
	if err != nil {
		return nil, err
	}

	var all []*packages.Package
	seen := map[string]bool{}
	packages.Visit(roots, func(p *packages.Package) bool {
		if seen[p.PkgPath] {
			return false
		}
		seen[p.PkgPath] = true
		if p.PkgPath == steeleagleModule || strings.HasPrefix(p.PkgPath, steeleagleModule+"/") {
			all = append(all, p)
		}
		return true
	}, nil)
	return all, nil
}
