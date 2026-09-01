package compiler

import (
	"fmt"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
)

// BuildAst constructs a parser.Ast directly from a MissionGraph -- the
// canvas-shaped request the GCS backend sends -- without going through
// the text lexer/parser at all. defaultImports/defaultRole are used when
// mission doesn't set its own Imports/Role (the common case; see the
// spec's "Frontend Changes" section on default Import/Role generation).
func BuildAst(mission *dslcompilerpb.MissionGraph, defaultImports []ImportEntry, defaultRole string) (*parser.Ast, error) {
	ast := &parser.Ast{}

	role := defaultRole
	if mission.HasRole() {
		role = mission.GetRole()
	}
	if role != "" {
		ast.Role = &parser.RoleStanza{Name: role}
	}

	imports := mission.GetImports()
	if len(imports) == 0 {
		ast.Import = &parser.ImportStanza{Imports: importSpecsFromEntries(defaultImports)}
	} else {
		specs := make([]*parser.ImportSpec, len(imports))
		for i, imp := range imports {
			specs[i] = &parser.ImportSpec{Alias: imp.GetAlias(), Path: imp.GetPath(), Version: imp.GetVersion()}
		}
		ast.Import = &parser.ImportStanza{Imports: specs}
	}

	actionDecls, err := declsFromNodes(mission.GetNodes())
	if err != nil {
		return nil, err
	}
	ast.Actions = &parser.ActionsStanza{Decls: actionDecls}

	eventDecls, err := declsFromEvents(mission.GetEvents())
	if err != nil {
		return nil, err
	}
	if len(eventDecls) > 0 {
		ast.Events = &parser.EventsStanza{Decls: eventDecls}
	}

	blocks := blocksFromEdges(mission.GetEdges())
	ast.Mission = &parser.MissionStanza{Start: mission.GetStartId(), Blocks: blocks}

	return ast, nil
}

func importSpecsFromEntries(entries []ImportEntry) []*parser.ImportSpec {
	specs := make([]*parser.ImportSpec, len(entries))
	for i, e := range entries {
		specs[i] = &parser.ImportSpec{Alias: e.Alias, Path: e.Path}
	}
	return specs
}

func declsFromNodes(nodes []*dslcompilerpb.Node) ([]*parser.Decl, error) {
	decls := make([]*parser.Decl, len(nodes))
	for i, n := range nodes {
		attrs, err := attrsFromParams(n.GetParams())
		if err != nil {
			return nil, fmt.Errorf("node %q: %w", n.GetInstanceId(), err)
		}
		decls[i] = &parser.Decl{Type: parser.TypeName(n.GetTypeName()), Name: n.GetInstanceId(), Attrs: attrs}
	}
	return decls, nil
}

func declsFromEvents(events []*dslcompilerpb.EventInstance) ([]*parser.Decl, error) {
	decls := make([]*parser.Decl, len(events))
	for i, e := range events {
		attrs, err := attrsFromParams(e.GetParams())
		if err != nil {
			return nil, fmt.Errorf("event %q: %w", e.GetInstanceId(), err)
		}
		decls[i] = &parser.Decl{Type: parser.TypeName(e.GetTypeName()), Name: e.GetInstanceId(), Attrs: attrs}
	}
	return decls, nil
}

func blocksFromEdges(edges []*dslcompilerpb.Edge) []*parser.DuringBlock {
	var order []string
	rulesBySource := map[string][]*parser.Rule{}
	seen := map[string]bool{}
	for _, e := range edges {
		src := e.GetSource()
		if !seen[src] {
			seen[src] = true
			order = append(order, src)
		}
		rulesBySource[src] = append(rulesBySource[src], &parser.Rule{Event: e.GetEventId(), Next: e.GetTarget()})
	}
	blocks := make([]*parser.DuringBlock, len(order))
	for i, src := range order {
		blocks[i] = &parser.DuringBlock{Action: src, Rules: rulesBySource[src]}
	}
	return blocks
}

func attrsFromParams(params map[string]*dslcompilerpb.FieldValue) ([]*parser.Attr, error) {
	if len(params) == 0 {
		return nil, nil
	}
	attrs := make([]*parser.Attr, 0, len(params))
	for key, fv := range params {
		v, err := valueFromFieldValue(fv)
		if err != nil {
			return nil, fmt.Errorf("field %q: %w", key, err)
		}
		attrs = append(attrs, &parser.Attr{Key: key, Value: v})
	}
	return attrs, nil
}

// valueFromFieldValue converts one wire FieldValue into a parser.Value.
// parser.Value.String stores the RAW lexed token INCLUDING its
// surrounding quote characters (see resolveValue's v.StringValue(), which
// unconditionally strips the first and last byte) -- so a string value
// must be re-quoted here, not assigned as-is.
func valueFromFieldValue(fv *dslcompilerpb.FieldValue) (*parser.Value, error) {
	switch {
	case fv.HasFloatValue():
		f := fv.GetFloatValue()
		return &parser.Value{Float: &f}, nil
	case fv.HasIntValue():
		n := fv.GetIntValue()
		return &parser.Value{Int: &n}, nil
	case fv.HasStringValue():
		quoted := fmt.Sprintf("%q", fv.GetStringValue())
		return &parser.Value{String: &quoted}, nil
	case fv.HasBoolValue():
		return nil, fmt.Errorf("boolean literal fields are not yet supported by the DSL compiler")
	case fv.HasIdentRef():
		ident := fv.GetIdentRef()
		return &parser.Value{Ident: &ident}, nil
	case fv.HasArrayValue():
		elems := fv.GetArrayValue().GetElems()
		vals := make([]*parser.Value, len(elems))
		for i, e := range elems {
			v, err := valueFromFieldValue(e)
			if err != nil {
				return nil, err
			}
			vals[i] = v
		}
		return &parser.Value{Array: &parser.ArrayValue{Elems: vals}}, nil
	case fv.HasInlineValue():
		inline := fv.GetInlineValue()
		attrs, err := attrsFromParams(inline.GetArgs())
		if err != nil {
			return nil, err
		}
		return &parser.Value{Inline: &parser.InlineCtor{Type: parser.TypeName(inline.GetTypeName()), Args: attrs}}, nil
	default:
		return nil, fmt.Errorf("empty FieldValue")
	}
}
