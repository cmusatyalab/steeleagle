// sdk/dsl/compiler/schema_test.go

package compiler

import (
	"go/types"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
)

// TestSchemaFromRegistryPatrolAction checks that a Base with one required
// float field and one optional enum-typed field translates into the
// FieldSchema shape the frontend's palette expects (required flag, "type"
// bucketed to the JSON-schema-style categories, enum_type set).
func TestSchemaFromRegistryPatrolAction(t *testing.T) {
	float32Type := types.Typ[types.Float32]
	pkg := types.NewPackage("github.com/cmusatyalab/steeleagle/sdk/dsl/actions", "actions")
	patrolMode := types.NewNamed(
		types.NewTypeName(0, pkg, "PatrolMode", nil), types.Typ[types.Uint32], nil,
	)

	registry := &loader.TypeRegistry{
		Actions: map[string]*loader.Base{
			"actions.Patrol": {
				Comment: "Patrol visits waypoints.",
				Fields: []loader.Field{
					{Name: "Altitude", Type: float32Type, Comment: "altitude for each point"},
				},
				OptFields: []loader.Field{
					{Name: "Pattern", Type: patrolMode, Comment: "patrol pattern"},
				},
			},
		},
		Events:    map[string]*loader.Base{},
		Datatypes: map[string]*loader.Base{},
		Enums: map[string]*loader.Base{
			"actions.PatrolMode": {
				Comment: "Patrol pattern modes",
				Fields: []loader.Field{
					{Name: "FORWARD"},
					{Name: "SPIRAL"},
				},
			},
		},
	}

	resp := SchemaFromRegistry(registry, nil, "")

	action, ok := resp.GetActions()["actions.Patrol"]
	if !ok {
		t.Fatalf("actions.Patrol missing from schema, got %v", resp.GetActions())
	}
	if action.GetDescription() != "Patrol visits waypoints." {
		t.Errorf("description = %q, want %q", action.GetDescription(), "Patrol visits waypoints.")
	}
	if len(action.GetFields()) != 2 {
		t.Fatalf("len(fields) = %d, want 2", len(action.GetFields()))
	}

	altitude := action.GetFields()[0]
	if altitude.GetName() != "Altitude" || altitude.GetType() != "number" || !altitude.GetRequired() {
		t.Errorf("Altitude field = %+v, want name=Altitude type=number required=true", altitude)
	}

	pattern := action.GetFields()[1]
	if pattern.GetName() != "Pattern" || pattern.GetRequired() {
		t.Errorf("Pattern field = %+v, want name=Pattern required=false", pattern)
	}
	if !pattern.HasEnumType() || pattern.GetEnumType() != "actions.PatrolMode" {
		t.Errorf("Pattern.EnumType = %q (has=%v), want actions.PatrolMode", pattern.GetEnumType(), pattern.HasEnumType())
	}
}
