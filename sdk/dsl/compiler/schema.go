// sdk/dsl/compiler/schema.go

package compiler

import (
	"go/types"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/loader"
)

// SchemaFromRegistry translates a loaded TypeRegistry into the wire
// schema the FSM builder's palette consumes, matching the field-shape
// conventions gcs/react/backend/app/api.py's Python-SDK-era
// _extract_fields_from_schema already established (type bucketed into
// "string"/"number"/"integer"/"boolean"/"array"/"object", object_type +
// nested_fields for composite types, depth-capped at 2) plus the new
// enum_type this design adds.
func SchemaFromRegistry(registry *loader.TypeRegistry, defaultImports []ImportEntry, defaultRole string) *dslcompilerpb.GetSchemaResponse {
	imports := make([]*dslcompilerpb.ImportSpec, len(defaultImports))
	for i, e := range defaultImports {
		imports[i] = dslcompilerpb.ImportSpec_builder{Alias: e.Alias, Path: e.Path}.Build()
	}

	return dslcompilerpb.GetSchemaResponse_builder{
		Actions:     typeSchemas(registry, registry.Actions),
		Events:      typeSchemas(registry, registry.Events),
		Datatypes:   typeSchemas(registry, registry.Datatypes),
		Enums:       enumSchemas(registry.Enums),
		Imports:     imports,
		DefaultRole: defaultRole,
	}.Build()
}

func typeSchemas(registry *loader.TypeRegistry, bases map[string]*loader.Base) map[string]*dslcompilerpb.TypeSchema {
	out := make(map[string]*dslcompilerpb.TypeSchema, len(bases))
	for name, base := range bases {
		fields := make([]*dslcompilerpb.FieldSchema, 0, len(base.Fields)+len(base.OptFields))
		for _, f := range base.Fields {
			fields = append(fields, fieldSchema(registry, f, true, 0))
		}
		for _, f := range base.OptFields {
			fields = append(fields, fieldSchema(registry, f, false, 0))
		}
		out[name] = dslcompilerpb.TypeSchema_builder{Description: base.Comment, Fields: fields}.Build()
	}
	return out
}

func enumSchemas(bases map[string]*loader.Base) map[string]*dslcompilerpb.EnumSchema {
	out := make(map[string]*dslcompilerpb.EnumSchema, len(bases))
	for name, base := range bases {
		values := make([]string, len(base.Fields))
		for i, f := range base.Fields {
			values[i] = f.Name
		}
		out[name] = dslcompilerpb.EnumSchema_builder{Description: base.Comment, Values: values}.Build()
	}
	return out
}

// fieldSchema categorizes f.Type the same way api.py's
// _extract_fields_from_schema categorizes a Pydantic JSON-schema type:
// a Go basic numeric kind -> "number" or "integer", string -> "string",
// bool -> "boolean", a slice/array -> "array", anything else (a named
// struct, i.e. a registered Datatype) -> "object" with object_type set
// and (depth-capped at 2) nested_fields populated from that Datatype's
// own Base. A named non-struct type whose Base lives in registry.Enums
// additionally sets enum_type, regardless of its "type" bucket.
//
// NOTE on pointer usage below: this proto's Opaque API only generates a
// pointer type in a _builder struct for a field the .proto marks
// `optional` (DefaultValue/ObjectType/EnumType here), or a oneof member.
// Every plain (non-optional) field -- Name, Required, Description, Type
// -- is a concrete value (string/bool) in the builder, not a pointer.
// Wrapping those in strPtr/boolPtr is a compile error, not just style.
func fieldSchema(registry *loader.TypeRegistry, f loader.Field, required bool, depth int) *dslcompilerpb.FieldSchema {
	fs := dslcompilerpb.FieldSchema_builder{
		Name:        f.Name,
		Required:    required,
		Description: f.Comment,
	}
	if f.Value != "" {
		fs.DefaultValue = strPtr(f.Value)
	}

	if enumName, ok := enumTypeName(registry, f.Type); ok {
		fs.EnumType = strPtr(enumName)
	}

	switch t := f.Type.Underlying().(type) {
	case *types.Basic:
		switch {
		case t.Info()&types.IsInteger != 0:
			fs.Type = "integer"
		case t.Info()&types.IsFloat != 0:
			fs.Type = "number"
		case t.Info()&types.IsBoolean != 0:
			fs.Type = "boolean"
		default:
			fs.Type = "string"
		}
	case *types.Slice, *types.Array:
		fs.Type = "array"
	default:
		fs.Type = "object"
		if name, base, ok := datatypeFor(registry, f.Type); ok {
			fs.ObjectType = strPtr(name)
			if depth < 2 {
				nested := make([]*dslcompilerpb.FieldSchema, 0, len(base.Fields)+len(base.OptFields))
				for _, nf := range base.Fields {
					nested = append(nested, fieldSchema(registry, nf, true, depth+1))
				}
				for _, nf := range base.OptFields {
					nested = append(nested, fieldSchema(registry, nf, false, depth+1))
				}
				fs.NestedFields = nested
			}
		}
	}
	return fs.Build()
}

// enumTypeName reports the registry.Enums key for t (a named type,
// possibly behind a pointer), if any -- the same qualified-name
// convention loader.LoadTypes used to populate registry.Enums.
func enumTypeName(registry *loader.TypeRegistry, t types.Type) (string, bool) {
	named, ok := underlyingNamed(t)
	if !ok {
		return "", false
	}
	obj := named.Obj()
	pkg := obj.Pkg()
	if pkg == nil {
		return "", false
	}
	qualifier := pkg.Name()
	if alias, ok := registry.PackToAlias[pkg.Path()]; ok {
		qualifier = alias
	}
	name := qualifier + "." + obj.Name()
	if _, ok := registry.Enums[name]; !ok {
		return "", false
	}
	return name, true
}

// datatypeFor reports the registry.Datatypes entry for t (a named
// struct, possibly behind a pointer), if any.
func datatypeFor(registry *loader.TypeRegistry, t types.Type) (string, *loader.Base, bool) {
	named, ok := underlyingNamed(t)
	if !ok {
		return "", nil, false
	}
	obj := named.Obj()
	pkg := obj.Pkg()
	if pkg == nil {
		return "", nil, false
	}
	qualifier := pkg.Name()
	if alias, ok := registry.PackToAlias[pkg.Path()]; ok {
		qualifier = alias
	}
	name := qualifier + "." + obj.Name()
	base, ok := registry.Datatypes[name]
	return name, base, ok
}

func strPtr(s string) *string { return &s }
