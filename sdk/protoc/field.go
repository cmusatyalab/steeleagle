package main

import (
	"fmt"

	"google.golang.org/protobuf/compiler/protogen"
	"google.golang.org/protobuf/reflect/protoreflect"
)

// needsCommonFieldInterface reports whether field should get a
// per-field-scoped, getter-only interface.
func needsCommonFieldInterface(field *protogen.Field) bool {
	return field.Message != nil && !isPassthroughType(field) && isCommonType(field)
}

// commonFieldInterfaceName computes the per-field-scoped, getter-only
// interface name for a field whose type is a common message.
func commonFieldInterfaceName(parentGoName string, field *protogen.Field) string {
	return parentGoName + "_" + field.GoName
}

// fieldReturnType computes the Go return type string for a scalar/enum/
// well-known-type field's generated Get* accessor.
func fieldReturnType(g *protogen.GeneratedFile, field *protogen.Field) string {
	desc := field.Desc

	if desc.Kind() == protoreflect.EnumKind {
		return g.QualifiedGoIdent(protogen.GoIdent{
			GoName:       field.Enum.GoIdent.GoName,
			GoImportPath: enumsImportPath,
		})
	}

	if desc.Kind() == protoreflect.MessageKind {
		if typ, ok := passthroughType(g, field); ok {
			return typ
		}
		panic(fmt.Sprintf("fieldReturnType called on non-passthrough message field %q; route through wrapper generation instead", field.Desc.FullName()))
	}

	return scalarGoType(desc.Kind())
}

// scalarGoType maps a protoreflect scalar Kind to protoc-gen-go's Go type.
// Proto3 scalar kinds have a fixed, stable mapping.
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

// isWellKnownProtoType reports whether a message-kind field's type is one
// of protobuf's own well-known types (Timestamp, Any, Duration e.g.).
func isWellKnownProtoType(field *protogen.Field) bool {
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

// isPassthroughType reports whether a message-kind field should be
// represented by its real, concrete protobuf Go type with no wrapper.
func isPassthroughType(field *protogen.Field) bool {
	return isWellKnownProtoType(field)
}

// passthroughType returns the qualified, pointer-typed Go type string for
// a well-known-type field.
func passthroughType(g *protogen.GeneratedFile, field *protogen.Field) (string, bool) {
	if !isPassthroughType(field) {
		return "", false
	}
	return "*" + g.QualifiedGoIdent(field.Message.GoIdent), true
}

// isCommonType reports whether a message-kind field's type is declared
// directly in the v1 common package.
func isCommonType(field *protogen.Field) bool {
	if field.Message == nil {
		return false
	}
	return isCommonMessage(field.Message)
}

// isCommonMessage reports whether a message is declared directly in the v1
// common package.
func isCommonMessage(msg *protogen.Message) bool {
	return string(msg.Desc.ParentFile().Package()) == commonPackage
}

// messageWrapperName returns the Go type name of the wrapper backing
// a message.
func messageWrapperName(msg *protogen.Message) string {
	return unexportedName(msg.GoIdent.GoName) + "Wrapper"
}

// fieldMessageType returns the Go type string to declare for a
// message-typed, non-passthrough field's Getter or Setter signature.
func fieldMessageType(field *protogen.Field) string {
	return field.Message.GoIdent.GoName
}

// isOptional reports whether protoc-gen-go generates a Has<Field>() method
// for this field.
func isOptional(field *protogen.Field) bool {
	if field.Desc.IsList() || field.Desc.IsMap() {
		return false // repeated/map fields never get Has* — presence is len() == 0
	}
	if field.Message != nil {
		return true // singular message fields always have Has*, no optional keyword needed
	}
	return field.Desc.HasOptionalKeyword()
}
