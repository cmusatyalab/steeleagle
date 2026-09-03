package compiler

import (
	"fmt"
	"regexp"

	dslcompilerpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/dslcompiler"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/parser"
)

// identRe is the same character class as the lexer's Ident token rule
// (see parser.lexerRules' `[a-zA-Z][a-zA-Z_\d]*`), anchored so it matches
// the WHOLE candidate. A graph-built Decl.Name bypasses the lexer
// entirely, but still ends up embedded unquoted in generated Go source as
// a variable name (main.go.tmpl's `var {{.Name}} = ...`), so anything the
// hand-written-DSL path could never produce -- a newline, a brace, a
// space, a leading digit -- must be rejected here instead of being
// compiled into the mission binary.
var identRe = regexp.MustCompile(`^[a-zA-Z][a-zA-Z_0-9]*$`)

// validateInstanceID rejects an instance id that isn't a legal DSL
// identifier. See identRe on why this is a security boundary and not just
// a tidiness check.
func validateInstanceID(id string) error {
	if !identRe.MatchString(id) {
		return fmt.Errorf("invalid instance id %q: must be a valid identifier", id)
	}
	return nil
}

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
		if err := validateInstanceID(n.GetInstanceId()); err != nil {
			return nil, err
		}
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
		if err := validateInstanceID(e.GetInstanceId()); err != nil {
			return nil, err
		}
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

// AstToGraph converts a parsed parser.Ast back into a MissionGraph -- the
// mechanical reverse of BuildAst above, used by ParseDsl to turn raw DSL
// text (which only the real lexer/parser can read) into the same
// canvas-shaped wire format Validate/Build accept. ast.Mission must be
// set (a DSL file with no Mission stanza has no start_id to report).
func AstToGraph(ast *parser.Ast) (*dslcompilerpb.MissionGraph, error) {
	if ast.Mission == nil {
		return nil, fmt.Errorf("DSL has no Mission stanza")
	}

	var actionDecls []*parser.Decl
	if ast.Actions != nil {
		actionDecls = ast.Actions.Decls
	}
	nodes, err := nodesFromDecls(actionDecls)
	if err != nil {
		return nil, err
	}

	var eventDecls []*parser.Decl
	if ast.Events != nil {
		eventDecls = ast.Events.Decls
	}
	events, err := eventsFromDecls(eventDecls)
	if err != nil {
		return nil, err
	}

	mg := dslcompilerpb.MissionGraph_builder{
		Nodes:   nodes,
		Events:  events,
		Edges:   edgesFromBlocks(ast.Mission.Blocks),
		StartId: ast.Mission.Start,
	}
	if ast.Role != nil {
		mg.Role = strPtr(ast.Role.Name)
	}
	if ast.Import != nil {
		mg.Imports = importSpecsFromAst(ast.Import.Imports)
	}
	return mg.Build(), nil
}

func importSpecsFromAst(specs []*parser.ImportSpec) []*dslcompilerpb.ImportSpec {
	out := make([]*dslcompilerpb.ImportSpec, len(specs))
	for i, s := range specs {
		out[i] = dslcompilerpb.ImportSpec_builder{Alias: s.Alias, Path: s.Path, Version: s.Version}.Build()
	}
	return out
}

func nodesFromDecls(decls []*parser.Decl) ([]*dslcompilerpb.Node, error) {
	if len(decls) == 0 {
		return nil, nil
	}
	nodes := make([]*dslcompilerpb.Node, len(decls))
	for i, d := range decls {
		params, err := paramsFromAttrs(d.Attrs)
		if err != nil {
			return nil, fmt.Errorf("decl %q: %w", d.Name, err)
		}
		nodes[i] = dslcompilerpb.Node_builder{InstanceId: d.Name, TypeName: string(d.Type), Params: params}.Build()
	}
	return nodes, nil
}

func eventsFromDecls(decls []*parser.Decl) ([]*dslcompilerpb.EventInstance, error) {
	if len(decls) == 0 {
		return nil, nil
	}
	events := make([]*dslcompilerpb.EventInstance, len(decls))
	for i, d := range decls {
		params, err := paramsFromAttrs(d.Attrs)
		if err != nil {
			return nil, fmt.Errorf("decl %q: %w", d.Name, err)
		}
		events[i] = dslcompilerpb.EventInstance_builder{InstanceId: d.Name, TypeName: string(d.Type), Params: params}.Build()
	}
	return events, nil
}

func edgesFromBlocks(blocks []*parser.DuringBlock) []*dslcompilerpb.Edge {
	var edges []*dslcompilerpb.Edge
	for _, b := range blocks {
		for _, r := range b.Rules {
			edges = append(edges, dslcompilerpb.Edge_builder{Source: b.Action, EventId: r.Event, Target: r.Next}.Build())
		}
	}
	return edges
}

func paramsFromAttrs(attrs []*parser.Attr) (map[string]*dslcompilerpb.FieldValue, error) {
	if len(attrs) == 0 {
		return nil, nil
	}
	out := make(map[string]*dslcompilerpb.FieldValue, len(attrs))
	for _, a := range attrs {
		fv, err := fieldValueFromValue(a.Value)
		if err != nil {
			return nil, fmt.Errorf("field %q: %w", a.Key, err)
		}
		out[a.Key] = fv
	}
	return out, nil
}

// fieldValueFromValue converts one parser.Value into a wire FieldValue --
// the mechanical reverse of valueFromFieldValue above. v.String holds the
// RAW lexed token including its surrounding quotes; v.StringValue()
// strips them, matching how the rest of the compiler (resolveValue)
// already reads a String value.
func fieldValueFromValue(v *parser.Value) (*dslcompilerpb.FieldValue, error) {
	switch {
	case v.Float != nil:
		return dslcompilerpb.FieldValue_builder{FloatValue: v.Float}.Build(), nil
	case v.Int != nil:
		return dslcompilerpb.FieldValue_builder{IntValue: v.Int}.Build(), nil
	case v.String != nil:
		s, ok := v.StringValue()
		if !ok {
			return nil, fmt.Errorf("malformed string value")
		}
		return dslcompilerpb.FieldValue_builder{StringValue: &s}.Build(), nil
	case v.Array != nil:
		elems := make([]*dslcompilerpb.FieldValue, len(v.Array.Elems))
		for i, e := range v.Array.Elems {
			fv, err := fieldValueFromValue(e)
			if err != nil {
				return nil, err
			}
			elems[i] = fv
		}
		return dslcompilerpb.FieldValue_builder{
			ArrayValue: dslcompilerpb.FieldValueArray_builder{Elems: elems}.Build(),
		}.Build(), nil
	case v.Inline != nil:
		args, err := paramsFromAttrs(v.Inline.Args)
		if err != nil {
			return nil, err
		}
		return dslcompilerpb.FieldValue_builder{
			InlineValue: dslcompilerpb.InlineCtorValue_builder{
				TypeName: string(v.Inline.Type),
				Args:     args,
			}.Build(),
		}.Build(), nil
	case v.Ident != nil:
		return dslcompilerpb.FieldValue_builder{IdentRef: v.Ident}.Build(), nil
	default:
		return nil, fmt.Errorf("empty parser.Value")
	}
}
