package compiler

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/alecthomas/participle/v2/lexer"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
)

// TestBuildIRPatrolMission is a regression test pinning BuildIR's public
// contract across the sdk/cmd/compiler -> sdk/dsl/compiler move: given a
// registry and AST built from a local fixture (deliberately avoiding the
// geojson/params.MapFeature overlay pipeline, which is exercised separately
// by the CLI smoke test), BuildIR must still return the expected start
// action and transition shape.
func TestBuildIRPatrolMission(t *testing.T) {
	dslPath := "testdata/takeoff_gimbal.test.dsl"
	f, err := os.Open(dslPath)
	if err != nil {
		t.Fatalf("opening %s: %v", dslPath, err)
	}
	defer f.Close()

	ast, err := parser.Parse(dslPath, f)
	if err != nil {
		t.Fatalf("parser.Parse() = %v, want nil", err)
	}

	imports := EnsureBaseImports(ast.Import.Imports)
	// takeoff_gimbal.test.dsl's Import stanza has no version pins, so with an empty
	// steeleagleRef every base import would default to "latest" -- which
	// resolves to this module's real release tags (stop at v2.2.1,
	// predating sdk/dsl entirely) rather than the v4.0-beta branch this SDK
	// work actually lives on. Pin to that branch explicitly.
	workspace, cleanup, err := NewWorkspace(context.Background(), imports, "v4.0-beta", nil)
	if err != nil {
		t.Fatalf("NewWorkspace() = %v, want nil", err)
	}
	defer cleanup()

	pkgPaths := make([]string, len(imports))
	for i, imp := range imports {
		pkgPaths[i] = imp.Path
	}
	requests := make([]*loader.PackageRequest, len(imports))
	for i, imp := range imports {
		requests[i] = &loader.PackageRequest{Path: imp.Path, Alias: imp.Alias}
	}
	registry, errs := loader.LoadTypes(requests, workspace, nil, []string{"CGO_ENABLED=0"})
	if len(errs) > 0 {
		t.Fatalf("loader.LoadTypes() errors = %v, want none", errs)
	}

	ir, err := BuildIR(ast, registry)
	if err != nil {
		t.Fatalf("BuildIR() = %v, want nil", err)
	}
	if ir.Start != "takeoff" {
		t.Errorf("ir.Start = %q, want %q", ir.Start, "takeoff")
	}
	if len(ir.Transitions) != 1 {
		t.Errorf("len(ir.Transitions) = %d, want 1", len(ir.Transitions))
	}
	var sawTakeoffToGimbal bool
	for _, tr := range ir.Transitions {
		if tr.State != "takeoff" {
			continue
		}
		for _, r := range tr.Rules {
			if r.Name == "done" && strings.Contains(r.Value, "gimbal") {
				sawTakeoffToGimbal = true
			}
		}
	}
	if !sawTakeoffToGimbal {
		t.Errorf("expected a done->gimbal transition from takeoff, got %+v", ir.Transitions)
	}
}

// TestPosPrefixDistinguishesRealAndZeroPositions is a unit test for
// posPrefix's contract: a real lexer.Position (as any parsed DSL text
// produces, always starting at 1:1) renders as "line:col: ", while the
// zero value (what a graph-built AST node always has, since it never
// passes through the lexer -- see graph.go) renders as "" rather than
// the meaningless "0:0: " a naive Position.String() call would give.
func TestPosPrefixDistinguishesRealAndZeroPositions(t *testing.T) {
	if got := posPrefix(lexer.Position{}); got != "" {
		t.Errorf("posPrefix(zero value) = %q, want empty string", got)
	}
	real := lexer.Position{Filename: "m.dsl", Line: 3, Column: 5}
	if got, want := posPrefix(real), "m.dsl:3:5: "; got != want {
		t.Errorf("posPrefix(real) = %q, want %q", got, want)
	}
}
