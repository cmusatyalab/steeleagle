// core/dslcompiler/service.go

package dslcompiler

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
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
	overlayPath    string
	schema         *dslcompilerpb.GetSchemaResponse
	cleanup        func()
	buildMu        sync.Mutex
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
	// No meaningful cancellation source exists at startup, so this is a
	// plain background context -- see compiler.NewWorkspace/TidyAndBuild's
	// context threading, which exists so a request-scoped caller (Build)
	// can bound/cancel these subprocess calls.
	ctx := context.Background()

	workspace, cleanup, err := compiler.NewWorkspace(ctx, imports, steeleagleRef, nil)
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

	// Materialize once here and reuse the resulting path for every Build
	// call -- see Task 4: Build previously discarded this and compiled
	// unscrubbed source, a latent mismatch with Validate's LoadTypes call
	// just below, which does type-check against the (currently empty, but
	// not always) overlay.
	overlayPath, err := compiler.MaterializeOverlay(workspace, overlay)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("materializing overlay: %w", err)
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

	const defaultRole = ""
	schema := compiler.SchemaFromRegistry(registry, defaultImports, defaultRole)

	return &Service{
		registry:       registry,
		defaultImports: defaultImports,
		defaultRole:    defaultRole,
		workspace:      workspace,
		overlayPath:    overlayPath,
		schema:         schema,
		cleanup:        cleanup,
	}, nil
}

// Close releases the workspace NewService created.
func (s *Service) Close() {
	s.cleanup()
}

// errImportsUnsupported is returned by Validate/Build when a client
// supplies a non-empty MissionGraph.Imports: compiler.BuildAst turns that
// field into ast.Import, but compiler.BuildIR never reads ast.Import at
// all -- it derives generated imports from the registry instead -- so a
// client-supplied import list currently has zero effect. Rather than
// silently ignoring it, fail loudly until a follow-on plan wires custom
// imports through end to end.
var errImportsUnsupported = errors.New("custom imports are not yet supported by this service")

// GetSchema returns the palette built from the registry NewService loaded,
// computed once at construction time (see NewService) and cached on s --
// GetSchema itself does no work beyond returning it.
func (s *Service) GetSchema(ctx context.Context, req *dslcompilerpb.GetSchemaRequest) (*dslcompilerpb.GetSchemaResponse, error) {
	return s.schema, nil
}

// Validate builds an Ast from req.Mission and links it against the
// service's registry, reporting the first problem BuildIR finds (it is
// fail-fast, not error-accumulating) attributed back to whichever
// node/event instance_id the error message names, if any.
func (s *Service) Validate(ctx context.Context, req *dslcompilerpb.ValidateRequest) (*dslcompilerpb.ValidateResponse, error) {
	mission := req.GetMission()
	if len(mission.GetImports()) > 0 {
		return dslcompilerpb.ValidateResponse_builder{
			Ok:     false,
			Errors: []*dslcompilerpb.CompileError{unattributedError(errImportsUnsupported)},
		}.Build(), nil
	}

	ast, err := compiler.BuildAst(mission, s.defaultImports, s.defaultRole)
	if err != nil {
		return dslcompilerpb.ValidateResponse_builder{
			Ok:     false,
			Errors: []*dslcompilerpb.CompileError{unattributedError(err)},
		}.Build(), nil
	}

	if _, err := compiler.BuildIR(ast, s.registry); err != nil {
		return dslcompilerpb.ValidateResponse_builder{
			Ok:     false,
			Errors: []*dslcompilerpb.CompileError{attributeError(err, mission)},
		}.Build(), nil
	}

	return dslcompilerpb.ValidateResponse_builder{Ok: true}.Build(), nil
}

func unattributedError(err error) *dslcompilerpb.CompileError {
	return dslcompilerpb.CompileError_builder{Message: err.Error()}.Build()
}

// attributeError matches err's message text against every known
// node/event instance_id OR type_name in mission and, on the first
// match, sets that node/event's id on the returned CompileError. Both
// keys are checked because BuildIR's own errors don't consistently name
// the instance_id: "%q is declared more than once" names decl.Name (the
// instance_id), but "unknown %s type %q" names decl.Type (the type_name)
// instead -- a node whose declared type doesn't exist has no instance_id
// in that error's text at all, only its (bad) type name.
func attributeError(err error, mission *dslcompilerpb.MissionGraph) *dslcompilerpb.CompileError {
	msg := err.Error()
	for _, n := range mission.GetNodes() {
		if strings.Contains(msg, "\""+n.GetInstanceId()+"\"") || strings.Contains(msg, "\""+n.GetTypeName()+"\"") {
			return dslcompilerpb.CompileError_builder{NodeId: strPtr(n.GetInstanceId()), Message: msg}.Build()
		}
	}
	for _, e := range mission.GetEvents() {
		if strings.Contains(msg, "\""+e.GetInstanceId()+"\"") || strings.Contains(msg, "\""+e.GetTypeName()+"\"") {
			return dslcompilerpb.CompileError_builder{EventId: strPtr(e.GetInstanceId()), Message: msg}.Build()
		}
	}
	return unattributedError(err)
}

// strPtr is core/dslcompiler's own copy of the same trivial pointer-
// taking helper sdk/dsl/compiler's schema.go defines (Task 5) --
// package-private identifiers don't cross package boundaries, and
// core/dslcompiler (package dslcompiler) is a separate package from
// sdk/dsl/compiler (package compiler), so this package needs its own. It
// covers CompileError.NodeId/EventId, the only optional (pointer-typed)
// fields this task and Task 8 construct in this package -- everything
// else built in core/dslcompiler is a plain field (see the pointer note
// above), so no boolPtr is needed here. Defined here since this is the
// first place in core/dslcompiler that needs it; Task 8 reuses this, it
// does not redefine it.
func strPtr(s string) *string { return &s }

const buildArches = "amd64,arm64" // documents the two Build always targets

var targetArches = []string{"amd64", "arm64"}

// buildChunkSize caps how many binary bytes one BuildChunk carries, so a
// multi-megabyte binary is actually streamed rather than sent as one
// giant chunk that reintroduces the size-cap problem streaming exists to
// avoid.
const buildChunkSize = 256 * 1024

// Build compiles req.Mission to a binary for each of targetArches,
// streaming each one back in buildChunkSize pieces. Build calls
// mutate s.workspace's shared main.go/build cache, so buildMu
// serializes them -- acceptable since Build is an explicit,
// infrequent user action, never the debounced live-edit path Validate is.
func (s *Service) Build(req *dslcompilerpb.BuildRequest, stream dslcompilerpb.DslCompilerService_BuildServer) error {
	s.buildMu.Lock()
	defer s.buildMu.Unlock()

	ctx := stream.Context()

	mission := req.GetMission()
	if len(mission.GetImports()) > 0 {
		return s.sendBuildErrorToAllArches(stream, unattributedError(errImportsUnsupported))
	}

	ast, err := compiler.BuildAst(mission, s.defaultImports, s.defaultRole)
	if err != nil {
		return s.sendBuildErrorToAllArches(stream, unattributedError(err))
	}
	ir, err := compiler.BuildIR(ast, s.registry)
	if err != nil {
		return s.sendBuildErrorToAllArches(stream, attributeError(err, mission))
	}

	// Empty CapFile/GeoJSON: capability scrubbing is out of scope for this
	// plan (see Global Constraints) -- this matches running the CLI with
	// no -cap/-geojson flag.
	if err := compiler.Generate(ir, nil, nil, s.workspace); err != nil {
		return status.Errorf(codes.Internal, "generating main.go: %v", err)
	}

	for i, arch := range targetArches {
		if i > 0 {
			// The client may have disconnected while the previous arch's
			// build was running -- don't burn a second cross-compile on a
			// stream nobody is listening to anymore.
			if err := ctx.Err(); err != nil {
				return err
			}
		}

		outPath, err := compiler.AbsOutPath(filepath.Join(s.workspace, "mission-"+arch))
		if err != nil {
			return status.Errorf(codes.Internal, "resolving output path for %s: %v", arch, err)
		}
		if err := compiler.TidyAndBuild(ctx, s.workspace, s.overlayPath, outPath, arch); err != nil {
			if sendErr := stream.Send(dslcompilerpb.BuildChunk_builder{
				Arch:   arch,
				Errors: []*dslcompilerpb.CompileError{dslcompilerpb.CompileError_builder{Message: err.Error()}.Build()},
			}.Build()); sendErr != nil {
				return sendErr
			}
			continue
		}
		if err := streamFile(stream, arch, outPath); err != nil {
			return err
		}
	}
	return nil
}

func (s *Service) sendBuildErrorToAllArches(stream dslcompilerpb.DslCompilerService_BuildServer, ce *dslcompilerpb.CompileError) error {
	for _, arch := range targetArches {
		if err := stream.Send(dslcompilerpb.BuildChunk_builder{
			Arch:   arch,
			Errors: []*dslcompilerpb.CompileError{ce},
		}.Build()); err != nil {
			return err
		}
	}
	return nil
}

// streamFile sends outPath's contents to stream as a sequence of
// buildChunkSize-sized BuildChunks for arch, the last one carrying Done.
// It reads the file in fixed-size chunks rather than loading the whole
// (potentially 15+MB) binary into memory up front.
func streamFile(stream dslcompilerpb.DslCompilerService_BuildServer, arch, outPath string) error {
	f, err := os.Open(outPath)
	if err != nil {
		return fmt.Errorf("opening built binary for %s: %w", arch, err)
	}
	defer f.Close()

	info, err := f.Stat()
	if err != nil {
		return fmt.Errorf("stat built binary for %s: %w", arch, err)
	}
	total := info.Size()

	var buf [buildChunkSize]byte
	var sent int64
	for sent < total {
		n, err := io.ReadFull(f, buf[:])
		if err != nil && err != io.ErrUnexpectedEOF {
			return fmt.Errorf("reading built binary for %s: %w", arch, err)
		}
		sent += int64(n)
		done := sent >= total
		if err := stream.Send(dslcompilerpb.BuildChunk_builder{
			Arch: arch,
			Data: buf[:n],
			Done: done,
		}.Build()); err != nil {
			return err
		}
	}
	return nil
}
