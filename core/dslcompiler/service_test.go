// core/dslcompiler/service_test.go

package dslcompiler

import (
	"context"
	"fmt"
	"os"
	"testing"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
)

// testSvc is a single Service shared across every test in this file,
// built once by TestMain. Each of these integration tests would
// otherwise pay NewService's real "go get" + registry-load cost
// (fast with a warm module cache, but a needless multiple of the
// pre-commit hook's 30s -short budget on a cold one) -- sharing one
// instance removes that redundancy without changing what any
// individual test exercises.
var testSvc *Service

func TestMain(m *testing.M) {
	svc, err := NewService(compiler.EnsureBaseImports(nil), "v4.0-beta")
	if err != nil {
		fmt.Fprintf(os.Stderr, "NewService() = %v, want nil\n", err)
		os.Exit(1)
	}
	testSvc = svc

	code := m.Run()
	svc.Close()
	os.Exit(code)
}

// TestNewServiceLoadsDefaultRegistryAndServesSchema is an integration test:
// it starts a real Service against the actual default SDK import set (base
// sdk, dsl/actions, dsl/events, dsl/types) -- the same packages every
// generated mission needs -- and checks GetSchema returns the known
// actions.Patrol action with its Altitude field. Requires module-proxy
// access, same as sdk/dsl/compiler's own tests (NewWorkspace runs a real
// "go get").
func TestNewServiceLoadsDefaultRegistryAndServesSchema(t *testing.T) {
	svc := testSvc

	resp, err := svc.GetSchema(context.Background(), dslcompilerpb.GetSchemaRequest_builder{}.Build())
	if err != nil {
		t.Fatalf("GetSchema() = %v, want nil", err)
	}
	patrol, ok := resp.GetActions()["actions.Patrol"]
	if !ok {
		t.Fatalf("actions.Patrol missing from schema, got keys %v", mapKeys(resp.GetActions()))
	}
	var sawAltitude bool
	for _, f := range patrol.GetFields() {
		if f.GetName() == "Altitude" {
			sawAltitude = true
		}
	}
	if !sawAltitude {
		t.Errorf("actions.Patrol fields = %+v, want an Altitude field", patrol.GetFields())
	}
}

func mapKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

// TestValidateGoodMissionReportsOk checks a well-formed graph (takeoff ->
// land) validates clean.
func TestValidateGoodMissionReportsOk(t *testing.T) {
	svc := testSvc

	mission := dslcompilerpb.MissionGraph_builder{
		Nodes: []*dslcompilerpb.Node{
			dslcompilerpb.Node_builder{InstanceId: "takeoff", TypeName: "actions.TakeOff"}.Build(),
			dslcompilerpb.Node_builder{InstanceId: "land", TypeName: "actions.Land"}.Build(),
		},
		Edges: []*dslcompilerpb.Edge{
			dslcompilerpb.Edge_builder{Source: "takeoff", EventId: "done", Target: "land"}.Build(),
		},
		StartId: "takeoff",
	}.Build()

	resp, err := svc.Validate(context.Background(), dslcompilerpb.ValidateRequest_builder{Mission: mission}.Build())
	if err != nil {
		t.Fatalf("Validate() = %v, want nil", err)
	}
	if !resp.GetOk() {
		t.Errorf("resp.Ok = false, errors = %+v, want true", resp.GetErrors())
	}
}

// TestValidateUnknownActionTypeReportsNodeError checks that an unknown
// action type_name comes back as a CompileError naming the offending
// node_id, not a generic/opaque failure.
func TestValidateUnknownActionTypeReportsNodeError(t *testing.T) {
	svc := testSvc

	mission := dslcompilerpb.MissionGraph_builder{
		Nodes: []*dslcompilerpb.Node{
			dslcompilerpb.Node_builder{InstanceId: "bogus", TypeName: "actions.DoesNotExist"}.Build(),
		},
		StartId: "bogus",
	}.Build()

	resp, err := svc.Validate(context.Background(), dslcompilerpb.ValidateRequest_builder{Mission: mission}.Build())
	if err != nil {
		t.Fatalf("Validate() = %v, want nil", err)
	}
	if resp.GetOk() {
		t.Fatal("resp.Ok = true, want false for an unknown action type")
	}
	if len(resp.GetErrors()) != 1 {
		t.Fatalf("len(errors) = %d, want 1", len(resp.GetErrors()))
	}
	got := resp.GetErrors()[0]
	if !got.HasNodeId() || got.GetNodeId() != "bogus" {
		t.Errorf("error.NodeId = %q (has=%v), want %q", got.GetNodeId(), got.HasNodeId(), "bogus")
	}
}

// TestValidateRejectsCustomImports checks that a MissionGraph with a
// non-empty Imports field is rejected outright (rather than silently
// having no effect, since compiler.BuildIR never reads ast.Import) --
// see errImportsUnsupported.
func TestValidateRejectsCustomImports(t *testing.T) {
	svc := testSvc

	mission := dslcompilerpb.MissionGraph_builder{
		Nodes:   []*dslcompilerpb.Node{dslcompilerpb.Node_builder{InstanceId: "takeoff", TypeName: "actions.TakeOff"}.Build()},
		StartId: "takeoff",
		Imports: []*dslcompilerpb.ImportSpec{dslcompilerpb.ImportSpec_builder{Path: "example.com/custom"}.Build()},
	}.Build()

	resp, err := svc.Validate(context.Background(), dslcompilerpb.ValidateRequest_builder{Mission: mission}.Build())
	if err != nil {
		t.Fatalf("Validate() = %v, want nil", err)
	}
	if resp.GetOk() {
		t.Fatal("resp.Ok = true, want false for a mission with custom imports")
	}
	if len(resp.GetErrors()) != 1 || resp.GetErrors()[0].GetMessage() != errImportsUnsupported.Error() {
		t.Errorf("errors = %+v, want one error %q", resp.GetErrors(), errImportsUnsupported.Error())
	}
}

// fakeBuildStream is a minimal DslCompilerService_BuildServer test double
// that just accumulates every chunk sent, so the test can assert on the
// resulting sequence without a real gRPC connection.
type fakeBuildStream struct {
	dslcompilerpb.DslCompilerService_BuildServer
	chunks []*dslcompilerpb.BuildChunk
}

func (f *fakeBuildStream) Send(c *dslcompilerpb.BuildChunk) error {
	f.chunks = append(f.chunks, c)
	return nil
}
func (f *fakeBuildStream) Context() context.Context { return context.Background() }

// TestBuildRejectsCustomImports mirrors
// TestValidateRejectsCustomImports for the Build RPC: a MissionGraph
// with a non-empty Imports field should be reported as a CompileError
// on every arch's chunk, not silently ignored.
func TestBuildRejectsCustomImports(t *testing.T) {
	svc := testSvc

	mission := dslcompilerpb.MissionGraph_builder{
		Nodes:   []*dslcompilerpb.Node{dslcompilerpb.Node_builder{InstanceId: "takeoff", TypeName: "actions.TakeOff"}.Build()},
		StartId: "takeoff",
		Imports: []*dslcompilerpb.ImportSpec{dslcompilerpb.ImportSpec_builder{Path: "example.com/custom"}.Build()},
	}.Build()

	stream := &fakeBuildStream{}
	err := svc.Build(dslcompilerpb.BuildRequest_builder{Mission: mission}.Build(), stream)
	if err != nil {
		t.Fatalf("Build() = %v, want nil", err)
	}
	if len(stream.chunks) != len(targetArches) {
		t.Fatalf("len(chunks) = %d, want %d (one per arch)", len(stream.chunks), len(targetArches))
	}
	for _, c := range stream.chunks {
		if len(c.GetErrors()) != 1 || c.GetErrors()[0].GetMessage() != errImportsUnsupported.Error() {
			t.Errorf("arch %s errors = %+v, want one error %q", c.GetArch(), c.GetErrors(), errImportsUnsupported.Error())
		}
	}
}

// TestBuildProducesBothArchBinaries is an integration test: it runs the
// full pipeline (Generate -> go mod tidy -> go build) for a minimal
// takeoff-only mission, for both amd64 and arm64, and checks each arch's
// stream ends with a non-empty binary and no errors. This is slow (two
// real "go build" cross-compiles) -- skip it in short test runs.
func TestBuildProducesBothArchBinaries(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping a real go-build integration test in -short mode")
	}
	svc := testSvc

	mission := dslcompilerpb.MissionGraph_builder{
		Nodes:   []*dslcompilerpb.Node{dslcompilerpb.Node_builder{InstanceId: "takeoff", TypeName: "actions.TakeOff"}.Build()},
		StartId: "takeoff",
	}.Build()

	stream := &fakeBuildStream{}
	err := svc.Build(dslcompilerpb.BuildRequest_builder{Mission: mission}.Build(), stream)
	if err != nil {
		t.Fatalf("Build() = %v, want nil", err)
	}

	got := map[string][]byte{}
	for _, c := range stream.chunks {
		if len(c.GetErrors()) > 0 {
			t.Fatalf("arch %s errors: %+v", c.GetArch(), c.GetErrors())
		}
		got[c.GetArch()] = append(got[c.GetArch()], c.GetData()...)
	}
	for _, arch := range []string{"amd64", "arm64"} {
		if len(got[arch]) == 0 {
			t.Errorf("no binary bytes received for arch %q", arch)
		}
	}
}
