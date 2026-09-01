// core/dslcompiler/service.go
package dslcompiler

import (
	"context"
	"fmt"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
)

// Service implements dslcompilerpb.DslCompilerServiceServer. It loads the
// SDK's type registry once, at construction (NewService), and reuses it
// (plus the build workspace it was loaded from) for every subsequent
// GetSchema/Validate/Build call -- see the spec's "Architecture" section
// for why a persistent, pre-loaded registry is the whole reason this is a
// standalone service rather than a CLI subprocess invoked per request.
type Service struct {
	dslcompilerpb.UnimplementedDslCompilerServiceServer

	registry       *loader.TypeRegistry
	defaultImports []compiler.ImportEntry
	defaultRole    string
	workspace      string
	cleanup        func()
}

// NewService loads imports (typically compiler.EnsureBaseImports(nil), the
// default SDK package set) into a fresh build workspace and links them
// into a TypeRegistry. steeleagleRef pins every steeleagle-module import
// to a specific branch/tag/commit (see compiler.NewWorkspace) -- this is
// required, not optional in practice: this module's real release tags
// stop at v2.2.1, predating sdk/dsl entirely, so an empty ref falls
// through to "latest" and resolves to that stale tag instead of any SDK
// package this service actually needs. Call Close when done to remove
// the workspace.
func NewService(imports []*parser.ImportSpec, steeleagleRef string) (*Service, error) {
	workspace, cleanup, err := compiler.NewWorkspace(imports, steeleagleRef, nil)
	if err != nil {
		return nil, fmt.Errorf("creating workspace: %w", err)
	}

	pkgPaths := make([]string, len(imports))
	for i, imp := range imports {
		pkgPaths[i] = imp.Path
	}
	rawPkgs, err := compiler.LoadSteeleaglePackages(workspace, pkgPaths)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("loading SDK packages: %w", err)
	}
	// An empty, non-nil CapFile: CreateOverlay's Scrub path calls
	// capFile.Supports(name), which dereferences capFile.unsupportedSet --
	// a nil *CapFile would panic there. An empty CapFile's unsupportedSet
	// is empty (nil map reads return the zero value safely), so
	// Supports always returns true, matching "nothing scrubbed" -- the
	// same behavior the CLI gets from ParseCapFromBytes(nil) on its own
	// no-"-cap"-flag path.
	overlay, compileErrs := sdk.CreateOverlay(&sdk.CapFile{}, nil, nil, rawPkgs)
	if len(compileErrs) > 0 {
		cleanup()
		return nil, fmt.Errorf("scrubbing SDK packages: %v", compileErrs)
	}

	requests := make([]*loader.PackageRequest, len(imports))
	for i, imp := range imports {
		requests[i] = &loader.PackageRequest{Path: imp.Path, Alias: imp.Alias}
	}
	registry, loadErrs := loader.LoadTypes(requests, workspace, overlay, []string{"CGO_ENABLED=0"})
	if len(loadErrs) > 0 {
		cleanup()
		return nil, fmt.Errorf("loading DSL types: %v", loadErrs)
	}

	defaultImports := make([]compiler.ImportEntry, len(imports))
	for i, imp := range imports {
		defaultImports[i] = compiler.ImportEntry{Alias: imp.Alias, Path: imp.Path}
	}

	return &Service{
		registry:       registry,
		defaultImports: defaultImports,
		workspace:      workspace,
		cleanup:        cleanup,
	}, nil
}

// Close releases the workspace NewService created.
func (s *Service) Close() {
	s.cleanup()
}

// GetSchema returns the palette built from the registry NewService loaded.
func (s *Service) GetSchema(ctx context.Context, req *dslcompilerpb.GetSchemaRequest) (*dslcompilerpb.GetSchemaResponse, error) {
	return compiler.SchemaFromRegistry(s.registry, s.defaultImports, s.defaultRole), nil
}
