// core/dslcompiler/service_test.go
package dslcompiler

import (
	"context"
	"testing"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler"
)

// TestNewServiceLoadsDefaultRegistryAndServesSchema is an integration test:
// it starts a real Service against the actual default SDK import set (base
// sdk, dsl/actions, dsl/events, dsl/types) -- the same packages every
// generated mission needs -- and checks GetSchema returns the known
// actions.Patrol action with its Altitude field. Requires module-proxy
// access, same as sdk/dsl/compiler's own tests (NewWorkspace runs a real
// "go get").
func TestNewServiceLoadsDefaultRegistryAndServesSchema(t *testing.T) {
	svc, err := NewService(compiler.EnsureBaseImports(nil), "v4.0-beta")
	if err != nil {
		t.Fatalf("NewService() = %v, want nil", err)
	}
	defer svc.Close()

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

// TestValidateGoodMissionReportsOk checks a well-formed graph (the same
// takeoff -> patrol shape used elsewhere in this plan) validates clean.
func TestValidateGoodMissionReportsOk(t *testing.T) {
	svc, err := NewService(compiler.EnsureBaseImports(nil), "v4.0-beta")
	if err != nil {
		t.Fatalf("NewService() = %v, want nil", err)
	}
	defer svc.Close()

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
	svc, err := NewService(compiler.EnsureBaseImports(nil), "v4.0-beta")
	if err != nil {
		t.Fatalf("NewService() = %v, want nil", err)
	}
	defer svc.Close()

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

// TestBuildProducesBothArchBinaries is an integration test: it runs the
// full pipeline (Generate -> go mod tidy -> go build) for a minimal
// takeoff-only mission, for both amd64 and arm64, and checks each arch's
// stream ends with a non-empty binary and no errors. This is slow (two
// real "go build" cross-compiles) -- skip it in short test runs.
func TestBuildProducesBothArchBinaries(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping a real go-build integration test in -short mode")
	}
	svc, err := NewService(compiler.EnsureBaseImports(nil), "v4.0-beta")
	if err != nil {
		t.Fatalf("NewService() = %v, want nil", err)
	}
	defer svc.Close()

	mission := dslcompilerpb.MissionGraph_builder{
		Nodes:   []*dslcompilerpb.Node{dslcompilerpb.Node_builder{InstanceId: "takeoff", TypeName: "actions.TakeOff"}.Build()},
		StartId: "takeoff",
	}.Build()

	stream := &fakeBuildStream{}
	err = svc.Build(dslcompilerpb.BuildRequest_builder{Mission: mission}.Build(), stream)
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
