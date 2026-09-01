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
