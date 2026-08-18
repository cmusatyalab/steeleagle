package main

import (
	"fmt"
	"go/types"
	"math"
)

// lookupEnumConst looks up name as an exported package-level constant of
// enumType's own declaring package, returning it only if its type is
// exactly enumType -- i.e. name is one of enumType's own declared values,
// such as enums.ReturnToHomeEndBehaviorHover for enums.ReturnToHomeEndBehavior.
func lookupEnumConst(enumType *types.Named, name string) (*types.Const, bool) {
	pkg := enumType.Obj().Pkg()
	if pkg == nil {
		return nil, false
	}
	c, ok := pkg.Scope().Lookup(name).(*types.Const)
	if !ok || !types.Identical(c.Type(), enumType) {
		return nil, false
	}
	return c, true
}

// basicKind returns t's underlying *types.Basic type info, if t has one.
func basicKind(t types.Type) (types.BasicInfo, bool) {
	b, ok := t.Underlying().(*types.Basic)
	if !ok {
		return 0, false
	}
	return b.Info(), true
}

// resolveValue resolves val into a fieldIR whose value is assignable to
// target -- a struct field's declared type, an option's argument type, or a
// slice's element type.
func (l *linker) resolveValue(target types.Type, val *Value) (*fieldIR, bool) {
	switch {
	case val.Float != nil:
		return l.resolveNumber(target, val.Pos, *val.Float)
	case val.Int != nil:
		return l.resolveNumber(target, val.Pos, float64(*val.Int))
	case val.String != nil:
		info, ok := basicKind(target)
		if !ok || info&types.IsString == 0 {
			l.errorf(val.Pos, "string value not valid for type %s", target)
			return nil, false
		}
		s, _ := val.StringValue()
		return &fieldIR{Type: target, String: &s}, true
	case val.Ident != nil:
		if named, ok := target.(*types.Named); ok {
			if c, ok := lookupEnumConst(named, *val.Ident); ok {
				return &fieldIR{Type: target, Const: c}, true
			}
		}
		info, ok := l.names[*val.Ident]
		if !ok || info.ir == nil {
			l.errorf(val.Pos, "identifier %q does not refer to a previously declared Data, Actions, or Events declaration, or a value of enum type %s", *val.Ident, target)
			return nil, false
		}
		return &fieldIR{Type: target, Link: info.ir}, true
	case val.Inline != nil:
		return l.resolveInline(target, val.Pos, val.Inline)
	case val.Array != nil:
		return l.resolveArray(target, val.Pos, val.Array)
	default:
		l.errorf(val.Pos, "value has no recognized literal form")
		return nil, false
	}
}

// resolveNumber resolves a Float or Int literal (both surface as a float64
// here -- the DSL lexer tokenizes any bare integer as a Float, see
// dslLexer's Float pattern in ast.go) against target, which may be an
// integer or floating-point type.
func (l *linker) resolveNumber(target types.Type, pos fmt.Stringer, v float64) (*fieldIR, bool) {
	info, ok := basicKind(target)
	if !ok || info&(types.IsFloat|types.IsInteger) == 0 {
		l.errorf(pos, "numeric value not valid for type %s", target)
		return nil, false
	}
	if info&types.IsInteger != 0 {
		if v != math.Trunc(v) {
			l.errorf(pos, "value %v is not a whole number, required for integer type %s", v, target)
			return nil, false
		}
		i := int64(v)
		return &fieldIR{Type: target, Int: &i}, true
	}
	return &fieldIR{Type: target, Float: &v}, true
}

// resolveInline links an inline constructor value to a synthesized typeIR.
// ctor.Type must be a DSL Datatype; its own Args are recursively linked
// into the synthesized typeIR's Fields and Options.
func (l *linker) resolveInline(target types.Type, pos fmt.Stringer, ctor *InlineCtor) (*fieldIR, bool) {
	bt, ok := l.lookupBase(l.registry.Datatypes, typesPkgPath, string(ctor.Type))
	if !ok {
		l.errorf(pos, "constructor %q: not a datatype", ctor.Type)
		return nil, false
	}

	ir := &typeIR{Name: string(ctor.Type), Type: bt.Type}
	ir.Fields, ir.Options = l.linkAttrs(bt.Type, bt.Options, ctor.Args)
	return &fieldIR{Type: target, Link: ir, Inline: true}, true
}

// resolveArray resolves an array value against target, which must be a
// slice type; every element is resolved against target's element type.
func (l *linker) resolveArray(target types.Type, pos fmt.Stringer, arr *ArrayValue) (*fieldIR, bool) {
	slice, ok := target.Underlying().(*types.Slice)
	if !ok {
		l.errorf(pos, "array value not valid for type %s", target)
		return nil, false
	}
	if len(arr.Elems) == 0 {
		return &fieldIR{Type: target}, true
	}

	elems := make([]*fieldIR, 0, len(arr.Elems))
	for _, e := range arr.Elems {
		f, ok := l.resolveValue(slice.Elem(), e)
		if !ok {
			return nil, false
		}
		elems = append(elems, f)
	}
	return &fieldIR{Type: target, Elems: elems}, true
}

// resolveData resolves a Data declaration's type: a DSL Datatype, or a Go
// generic/builtin type. A generic type has no optionalTypes.
func (l *linker) resolveData(d *Decl) (types.Type, []optionalType, bool) {
	if bt, ok := l.lookupBase(l.registry.Datatypes, typesPkgPath, string(d.Type)); ok {
		return bt.Type, bt.Options, true
	}
	if t, ok := genericType(string(d.Type)); ok {
		return t, nil, true
	}
	l.errorf(d.Pos, "%s %q: not a datatype or a generic type", d.Name, d.Type)
	return nil, nil, false
}

// resolveAction resolves an Actions declaration's type: it must be a DSL
// Action.
func (l *linker) resolveAction(d *Decl) (types.Type, []optionalType, bool) {
	bt, ok := l.lookupBase(l.registry.Actions, actionsPkgPath, string(d.Type))
	if !ok {
		l.errorf(d.Pos, "%s %q: not a declared action", d.Name, d.Type)
		return nil, nil, false
	}
	return bt.Type, bt.Options, true
}

// resolveEvent resolves an Events declaration's type: it must be a DSL
// Event.
func (l *linker) resolveEvent(d *Decl) (types.Type, []optionalType, bool) {
	bt, ok := l.lookupBase(l.registry.Events, eventsPkgPath, string(d.Type))
	if !ok {
		l.errorf(d.Pos, "%s %q: not a declared event", d.Name, d.Type)
		return nil, nil, false
	}
	return bt.Type, bt.Options, true
}
