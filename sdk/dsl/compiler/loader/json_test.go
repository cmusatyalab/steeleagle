package loader

import (
	"encoding/json"
	"reflect"
	"slices"
	"testing"
)

// TestToJsonFixtures checks that ToJson emits
// exactly the datatypes, actions, events, and enums sections, that each
// section carries every registered type, and that a fully populated entry
// (fixtures.Hover) round-trips with its comments, fields, and optional
// fields intact.
func TestToJsonFixtures(t *testing.T) {
	reg := sharedFixtureRegistry(t)

	b, err := reg.ToJson()
	if err != nil {
		t.Fatalf("ToJson() error = %v, want nil", err)
	}

	var top map[string]json.RawMessage
	if err := json.Unmarshal(b, &top); err != nil {
		t.Fatalf("json.Unmarshal(top level) error = %v", err)
	}
	gotKeys := keys(top)
	slices.Sort(gotKeys)
	wantKeys := []string{"actions", "datatypes", "enums", "events"}
	if !slices.Equal(gotKeys, wantKeys) {
		t.Errorf("top-level keys = %v, want %v", gotKeys, wantKeys)
	}

	var got JsonRegistry
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatalf("json.Unmarshal() error = %v", err)
	}
	sections := []struct {
		name string
		got  map[string]JsonBase
		want map[string]*Base
	}{
		{"datatypes", got.Datatypes, reg.Datatypes},
		{"actions", got.Actions, reg.Actions},
		{"events", got.Events, reg.Events},
		{"enums", got.Enums, reg.Enums},
	}
	for _, s := range sections {
		g, w := keys(s.got), keys(s.want)
		slices.Sort(g)
		slices.Sort(w)
		if !slices.Equal(g, w) {
			t.Errorf("%s keys = %v, want %v", s.name, g, w)
		}
	}

	wantHover := JsonBase{
		Comment: "Hover is a fixture Action with one required and one optional field, used\nto exercise field/comment/optional-tag extraction.",
		Type:    "fixtures.Hover",
		Fields: []JsonField{
			{Name: "Duration", Comment: "Duration is how long to hover, in seconds.", Type: "float32"},
		},
		OptFields: []JsonField{
			{Name: "Altitude", Comment: "meters above ground", Type: "float32"},
		},
	}
	if gotHover := got.Actions["fixtures.Hover"]; !reflect.DeepEqual(gotHover, wantHover) {
		t.Errorf("actions[fixtures.Hover] = %+v, want %+v", gotHover, wantHover)
	}

	if mode, ok := got.Enums["fixtures.Mode"]; !ok {
		t.Errorf("enums = %v, want fixtures.Mode", keys(got.Enums))
	} else {
		for _, f := range mode.Fields {
			if f.Type != "fixtures.Mode" {
				t.Errorf("enums[fixtures.Mode] value %s type = %q, want %q", f.Name, f.Type, "fixtures.Mode")
			}
		}
	}
}

// TestToJsonUsesAlias checks that types from an aliased
// package are qualified by the alias, including when nested inside a
// composite field type.
func TestToJsonUsesAlias(t *testing.T) {
	tpkg, _ := typeCheckFixture(t, "geo", `package geo

type Point struct {
	Next []*Point
}
`)
	named, st := namedStruct(t, tpkg, "Point")
	reg := &TypeRegistry{
		PackToAlias: map[string]string{"geo": "g"},
		Datatypes: map[string]*Base{
			"g.Point": {
				Type:   named,
				Fields: []Field{{Name: "Next", Type: st.Field(0).Type()}},
			},
		},
	}

	b, err := reg.ToJson()
	if err != nil {
		t.Fatalf("ToJson() error = %v, want nil", err)
	}
	var got JsonRegistry
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatalf("json.Unmarshal() error = %v", err)
	}

	want := JsonBase{
		Type:   "g.Point",
		Fields: []JsonField{{Name: "Next", Type: "[]*g.Point"}},
	}
	if p := got.Datatypes["g.Point"]; !reflect.DeepEqual(p, want) {
		t.Errorf("datatypes[g.Point] = %+v, want %+v", p, want)
	}
	if len(got.Actions) != 0 || len(got.Events) != 0 || len(got.Enums) != 0 {
		t.Errorf("actions/events/enums = %v/%v/%v, want all empty", got.Actions, got.Events, got.Enums)
	}
}
