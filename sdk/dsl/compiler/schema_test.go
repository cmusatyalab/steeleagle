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
	if altitude.GetMapFeature() {
		t.Errorf("Altitude.MapFeature = true, want false (it's not a params.MapFeature field)")
	}
}

// TestSchemaFromRegistryMapFeatureField checks that a field of type
// sdk/params.MapFeature sets map_feature -- identified directly by
// package path + name, not via the registry (registry.Enums never
// carries a MapFeature entry, since CreateOverlay's sdkTypes is always
// nil for the long-lived dslcompiler service; see isMapFeatureType).
func TestSchemaFromRegistryMapFeatureField(t *testing.T) {
	float32Type := types.Typ[types.Float32]
	paramsPkg := types.NewPackage("github.com/cmusatyalab/steeleagle/sdk/params", "params")
	mapFeature := types.NewNamed(
		types.NewTypeName(0, paramsPkg, "MapFeature", nil), types.Typ[types.String], nil,
	)

	registry := &loader.TypeRegistry{
		Actions: map[string]*loader.Base{
			"actions.Patrol": {
				Fields: []loader.Field{
					{Name: "Area", Type: mapFeature, Comment: "area to patrol"},
					{Name: "Altitude", Type: float32Type, Comment: "altitude"},
				},
			},
		},
		Events:    map[string]*loader.Base{},
		Datatypes: map[string]*loader.Base{},
		Enums:     map[string]*loader.Base{},
	}

	resp := SchemaFromRegistry(registry, nil, "")
	fields := resp.GetActions()["actions.Patrol"].GetFields()
	if len(fields) != 2 {
		t.Fatalf("len(fields) = %d, want 2", len(fields))
	}

	area := fields[0]
	if area.GetName() != "Area" || area.GetType() != "string" || !area.GetMapFeature() {
		t.Errorf("Area field = %+v, want name=Area type=string map_feature=true", area)
	}
	if area.HasEnumType() {
		t.Errorf("Area.EnumType = %q, want unset (MapFeature isn't a registry enum)", area.GetEnumType())
	}
}
