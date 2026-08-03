package main

import (
	"fmt"

	"google.golang.org/protobuf/compiler/protogen"
	"google.golang.org/protobuf/reflect/protoreflect"
)

// fieldReturnType computes the Go return type string for a scalar/enum/
// well-known-type field's generated Get* accessor, matching what
// protoc-gen-go itself would produce
func fieldReturnType(g *protogen.GeneratedFile, field *protogen.Field) string {
	desc := field.Desc

	if desc.Kind() == protoreflect.EnumKind {
		return g.QualifiedGoIdent(field.Enum.GoIdent)
	}

	if desc.Kind() == protoreflect.MessageKind {
		if typ, ok := wellKnownType(g, field); ok {
			return typ // e.g. *timestamppb.Timestamp, *anypb.Any
		}
		panic(fmt.Sprintf("fieldReturnType called on non-well-known message field %q; route through wrapper generation instead", field.Desc.FullName()))
	}

	return scalarGoType(desc.Kind())
}

// scalarGoType maps a protoreflect scalar Kind to protoc-gen-go's Go type.
func scalarGoType(kind protoreflect.Kind) string {
	switch kind {
	case protoreflect.BoolKind:
		return "bool"
	case protoreflect.Int32Kind, protoreflect.Sint32Kind, protoreflect.Sfixed32Kind:
		return "int32"
	case protoreflect.Uint32Kind, protoreflect.Fixed32Kind:
		return "uint32"
	case protoreflect.Int64Kind, protoreflect.Sint64Kind, protoreflect.Sfixed64Kind:
		return "int64"
	case protoreflect.Uint64Kind, protoreflect.Fixed64Kind:
		return "uint64"
	case protoreflect.FloatKind:
		return "float32"
	case protoreflect.DoubleKind:
		return "float64"
	case protoreflect.StringKind:
		return "string"
	case protoreflect.BytesKind:
		return "[]byte"
	default:
		panic(fmt.Sprintf("unhandled scalar kind: %v", kind))
	}
}

// isWellKnownType reports whether a message-kind field's type is one of the
// well-known protobuf types (Timestamp, Any, Duration, wrapper types).
func isWellKnownType(field *protogen.Field) bool {
	if field.Message == nil {
		return false
	}
	switch field.Message.GoIdent.GoImportPath {
	case "google.golang.org/protobuf/types/known/timestamppb",
		"google.golang.org/protobuf/types/known/anypb",
		"google.golang.org/protobuf/types/known/durationpb",
		"google.golang.org/protobuf/types/known/wrapperspb":
		return true
	default:
		return false
	}
}

// wellKnownType returns the qualified Go type string for a well-known-type
// field (registering the necessary import on g as a side effect), or
// ("", false) if the field isn't one of the recognized well-known types.
func wellKnownType(g *protogen.GeneratedFile, field *protogen.Field) (string, bool) {
	if !isWellKnownType(field) {
		return "", false
	}
	return "*" + g.QualifiedGoIdent(field.Message.GoIdent), true
}
