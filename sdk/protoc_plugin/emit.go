package main

import (
	"google.golang.org/protobuf/compiler/protogen"
)

// emitCommonFieldInterface declares a per-field-scoped interface
// containing only the Getter methods. fieldPath is field's own capability
// path (see capFilePrefix); each inner getter is tagged with fieldPath
// plus that inner field's own name.
func emitCommonFieldInterface(g *protogen.GeneratedFile, parentGoName, fieldPath string, field *protogen.Field) {
	name := commonFieldInterfaceName(parentGoName, field)
	g.P("type ", name, " interface {")
	for _, innerField := range field.Message.Fields {
		innerPath := fieldPath + "/" + string(innerField.Desc.Name())
		g.P(excludeTagPrefix, innerPath)
		emitGetter(g, field.Message.GoIdent.GoName, innerField)
	}
	g.P("}")
	g.P()
}

// emitGetter writes a field's Get<Field>() interface method signature
// only — no Has, no Setter.
func emitGetter(g *protogen.GeneratedFile, parentGoName string, field *protogen.Field) {
	getterName := "Get" + field.GoName
	optional := isOptional(field)

	switch {
	case field.Desc.IsList() && field.Message != nil && isPassthroughType(field):
		typ, _ := passthroughType(g, field)
		g.P(getterName, "() []", typ)

	case field.Desc.IsList() && field.Message != nil && needsCommonFieldInterface(field):
		g.P(getterName, "() []", commonFieldInterfaceName(parentGoName, field))

	case field.Desc.IsList() && field.Message != nil:
		g.P(getterName, "() []", fieldMessageType(field))

	case field.Message != nil && !isPassthroughType(field) && needsCommonFieldInterface(field):
		emitGetterSignature(g, getterName, commonFieldInterfaceName(parentGoName, field), optional)

	case field.Message != nil && !isPassthroughType(field):
		emitGetterSignature(g, getterName, fieldMessageType(field), optional)

	default:
		emitGetterSignature(g, getterName, fieldReturnType(g, field), optional)
	}
}

// emitInterfaceMethod replicates the opaque protobuf API for a given
// message field: a Getter (via emitGetter) and an unexported has<Field>()
// if optional. No Setters are generated anywhere. fieldPath is field's own
// capability path (see capFilePrefix); every line this emits is preceded
// by an #exclude-requires tag naming it, so a vehicle that doesn't
// support the field loses the whole method.
func emitInterfaceMethod(g *protogen.GeneratedFile, parentGoName, fieldPath string, field *protogen.Field) {
	g.P(excludeTagPrefix, fieldPath)
	emitGetter(g, parentGoName, field)

	if isOptional(field) {
		g.P(excludeTagPrefix, fieldPath)
		g.P("has", field.GoName, "() bool")
	}
}

// emitGetterSignature writes a single interface method signature, either
// "Name() Type" or "Name() (Type, error)" depending on optional.
func emitGetterSignature(g *protogen.GeneratedFile, getterName, typ string, optional bool) {
	if optional {
		g.P(getterName, "() (", typ, ", error)")
	} else {
		g.P(getterName, "() ", typ)
	}
}

// emitAdapterMethod creates adapters that plug in to the protocol with
// opaque interfaces.
func emitAdapterMethod(g *protogen.GeneratedFile, parentGoName, wrapperName string, field *protogen.Field) {
	getterName := "Get" + field.GoName
	recv := "w"
	optional := isOptional(field)

	switch {
	case field.Desc.IsList() && field.Message != nil && isPassthroughType(field):
		typ, _ := passthroughType(g, field)
		g.P("func (", recv, " *", wrapperName, ") ", getterName, "() []", typ, " {")
		g.P("return ", recv, ".inner.", getterName, "()")
		g.P("}")

	case field.Desc.IsList() && field.Message != nil:
		elemWrapper := messageWrapperName(field.Message)
		elemType := fieldMessageType(field)
		if needsCommonFieldInterface(field) {
			elemType = commonFieldInterfaceName(parentGoName, field)
		}
		g.P("func (", recv, " *", wrapperName, ") ", getterName, "() []", elemType, " {")
		g.P("src := ", recv, ".inner.", getterName, "()")
		g.P("out := make([]", elemType, ", len(src))")
		g.P("for i, v := range src {")
		g.P("out[i] = &", elemWrapper, "{inner: v}")
		g.P("}")
		g.P("return out")
		g.P("}")

	case field.Message != nil && !isPassthroughType(field):
		wrapperTypeName := messageWrapperName(field.Message)
		declaredType := fieldMessageType(field)
		if needsCommonFieldInterface(field) {
			declaredType = commonFieldInterfaceName(parentGoName, field)
		}
		emitMessageGetterBody(g, recv, wrapperName, getterName, field, declaredType, wrapperTypeName, optional)

	default:
		returnType := fieldReturnType(g, field)
		emitScalarGetterBody(g, recv, wrapperName, getterName, field, returnType, optional)
	}
	g.P()

	if optional {
		g.P("func (", recv, " *", wrapperName, ") has", field.GoName, "() bool {")
		g.P("return ", recv, ".inner.Has", field.GoName, "()")
		g.P("}")
		g.P()
	}
}

// emitMessageGetterBody writes the Get<Field>() body for a message-typed
// field, wrapping the concrete value in its adapter/wrapper type.
func emitMessageGetterBody(g *protogen.GeneratedFile, recv, wrapperName, getterName string, field *protogen.Field, ifaceType, nestedWrapper string, optional bool) {
	if optional {
		g.P("func (", recv, " *", wrapperName, ") ", getterName, "() (", ifaceType, ", error) {")
		g.P("if !", recv, ".has", field.GoName, "() {")
		g.P("return nil, ", fieldNotPresentError)
		g.P("}")
		g.P("return &", nestedWrapper, "{inner: ", recv, ".inner.", getterName, "()}, nil")
		g.P("}")
		return
	}
	g.P("func (", recv, " *", wrapperName, ") ", getterName, "() ", ifaceType, " {")
	g.P("return &", nestedWrapper, "{inner: ", recv, ".inner.", getterName, "()}")
	g.P("}")
}

// emitScalarGetterBody writes the Get<Field>() body for a scalar, enum, or
// well-known-type field.
func emitScalarGetterBody(g *protogen.GeneratedFile, recv, wrapperName, getterName string, field *protogen.Field, returnType string, optional bool) {
	readExpr := recv + ".inner." + getterName + "()"
	if field.Enum != nil {
		readExpr = returnType + "(" + readExpr + ")"
	}

	if optional {
		g.P("func (", recv, " *", wrapperName, ") ", getterName, "() (", returnType, ", error) {")
		g.P("if !", recv, ".has", field.GoName, "() {")
		g.P("var zero ", returnType)
		g.P("return zero, ", fieldNotPresentError)
		g.P("}")
		g.P("return ", readExpr, ", nil")
		g.P("}")
		return
	}
	g.P("func (", recv, " *", wrapperName, ") ", getterName, "() ", returnType, " {")
	g.P("return ", readExpr)
	g.P("}")
}
