package main

import (
	"fmt"
	"go/types"
)

// resolveValue resolves val to its Go type and, if it links to another
// typeIR rather than being a plain Go generic.
func (l *linker) resolveValue(val *Value) (types.Type, *typeIR, bool) {
	switch {
	case val.Float != nil:
		t, _ := genericType("float64")
		return t, nil, true
	case val.Int != nil:
		t, _ := genericType("int64")
		return t, nil, true
	case val.String != nil:
		t, _ := genericType("string")
		return t, nil, true
	case val.GeoJson != nil:
		t, _ := genericType("string")
		return t, nil, true
	case val.Ident != nil:
		info, ok := l.names[*val.Ident]
		if !ok || info.ir == nil {
			l.errorf(val.Pos, "identifier %q does not refer to a previously declared Data, Actions, or Events declaration", *val.Ident)
			return nil, nil, false
		}
		return info.ir.Type, info.ir, true
	case val.Inline != nil:
		return l.resolveInline(val.Pos, val.Inline)
	case val.Array != nil:
		return l.resolveArray(val.Pos, val.Array)
	default:
		l.errorf(val.Pos, "value has no recognized literal form")
		return nil, nil, false
	}
}

// resolveInline links an inline constructor value to a synthesized typeIR.
// ctor.Type must be a DSL Datatype; its own Args are recursively linked
// into the synthesized typeIR's Fields.
func (l *linker) resolveInline(pos fmt.Stringer, ctor *InlineCtor) (types.Type, *typeIR, bool) {
	bt, ok := l.lookupBase(l.registry.Datatypes, typesPkgPath, string(ctor.Type))
	if !ok {
		l.errorf(pos, "constructor %q: not a datatype", ctor.Type)
		return nil, nil, false
	}

	ir := &typeIR{Name: string(ctor.Type), Type: bt.Type}
	ir.Fields = l.linkAttrs(bt.Type, bt.Options, ctor.Args)
	return bt.Type, ir, true
}

// resolveArray resolves an array value to a slice of its element type.
// Every element must resolve to the same type.
func (l *linker) resolveArray(pos fmt.Stringer, arr *ArrayValue) (types.Type, *typeIR, bool) {
	if len(arr.Elems) == 0 {
		l.errorf(pos, "empty array: cannot infer an element type")
		return nil, nil, false
	}
	var elemType types.Type
	for _, e := range arr.Elems {
		t, _, ok := l.resolveValue(e)
		if !ok {
			return nil, nil, false
		}
		if elemType == nil {
			elemType = t
			continue
		}
		if !types.Identical(elemType, t) {
			l.errorf(e.Pos, "array element type %s does not match earlier element type %s", t, elemType)
			return nil, nil, false
		}
	}
	return types.NewSlice(elemType), nil, true
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
