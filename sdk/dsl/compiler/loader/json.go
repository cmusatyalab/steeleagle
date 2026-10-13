package loader

import (
	"encoding/json"
	"go/types"
)

// JsonField is the JSON representation of a Field.
type JsonField struct {
	Name    string `json:"name"`
	Comment string `json:"comment,omitempty"`
	Value   string `json:"value,omitempty"`
	Type    string `json:"type"`
}

// JsonBase is the JSON representation of a Base.
type JsonBase struct {
	Comment   string      `json:"comment,omitempty"`
	Type      string      `json:"type"`
	Fields    []JsonField `json:"fields"`
	OptFields []JsonField `json:"optFields,omitempty"`
}

// JsonRegistry is the JSON representation of a TypeRegistry, limited to
// the DSL-visible types.
type JsonRegistry struct {
	Datatypes map[string]JsonBase `json:"datatypes"`
	Actions   map[string]JsonBase `json:"actions"`
	Events    map[string]JsonBase `json:"events"`
	Enums     map[string]JsonBase `json:"enums"`
}

// ToJson encodes the Datatypes, Actions, Events, and Enums of a
// registry as JSON. Types are rendered as strings, qualified by each
// package's import alias (or package name, if it has no alias).
func (r *TypeRegistry) ToJson() ([]byte, error) {
	qualifier := func(pkg *types.Package) string {
		if alias, ok := r.PackToAlias[pkg.Path()]; ok {
			return alias
		}
		return pkg.Name()
	}
	typeString := func(t types.Type) string {
		if t == nil {
			return ""
		}
		return types.TypeString(t, qualifier)
	}
	convertFields := func(fields []Field) []JsonField {
		out := make([]JsonField, 0, len(fields))
		for _, f := range fields {
			out = append(out, JsonField{
				Name:    f.Name,
				Comment: f.Comment,
				Value:   f.Value,
				Type:    typeString(f.Type),
			})
		}
		return out
	}
	convert := func(bases map[string]*Base) map[string]JsonBase {
		out := make(map[string]JsonBase, len(bases))
		for name, b := range bases {
			out[name] = JsonBase{
				Comment:   b.Comment,
				Type:      typeString(b.Type),
				Fields:    convertFields(b.Fields),
				OptFields: convertFields(b.OptFields),
			}
		}
		return out
	}
	return json.Marshal(JsonRegistry{
		Datatypes: convert(r.Datatypes),
		Actions:   convert(r.Actions),
		Events:    convert(r.Events),
		Enums:     convert(r.Enums),
	})
}
