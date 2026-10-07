package parser

import (
	"encoding/json"
	"fmt"
	"io"
)

// Parse parses a DSL mission file and unquotes every Override and Import
// path (captured raw as String tokens) in place. Absent Data, Actions and
// Events stanzas are filled in with an empty Decl list so callers never see
// them as nil.
func Parse(filename string, r io.Reader) (*Ast, error) {
	ast, err := dslParser.Parse(filename, r)
	if err != nil {
		return nil, err
	}
	fillEmptyStanzas(ast)
	if ast.Override != nil {
		for _, o := range ast.Override.Paths {
			o.Path = unquoteString(o.Path)
		}
	}
	if ast.Import != nil {
		for _, imp := range ast.Import.Imports {
			imp.Path = unquoteString(imp.Path)
		}
	}
	return ast, nil
}

// ParseFromJson decodes a JSON-encoded mission into an *Ast. The JSON
// mirrors the Ast structs field for field (keys are the Go field names,
// matched case-insensitively), e.g.
//
//	{"Actions": {"Decls": [{"Type": "actions.TakeOff", "Name": "takeoff",
//	  "Attrs": [{"Key": "altitude", "Value": {"Float": 2.5}}]}]}}
//
// Unknown keys are rejected. Override/Import paths and String values are
// written unquoted; String values are re-quoted on decode so that
// Value.StringValue behaves the same as for Parse. Absent Data, Actions and
// Events stanzas are filled in with an empty Decl list, as in Parse.
func ParseFromJson(r io.Reader) (*Ast, error) {
	dec := json.NewDecoder(r)
	dec.DisallowUnknownFields()
	ast := &Ast{}
	if err := dec.Decode(ast); err != nil {
		return nil, fmt.Errorf("decoding mission JSON: %w", err)
	}
	if dec.More() {
		return nil, fmt.Errorf("decoding mission JSON: unexpected data after top-level object")
	}
	fillEmptyStanzas(ast)
	for _, decls := range [][]*Decl{ast.Data.Decls, ast.Actions.Decls, ast.Events.Decls} {
		for _, d := range decls {
			if d == nil {
				return nil, fmt.Errorf("decoding mission JSON: null Decl")
			}
			if err := quoteAttrStrings(d.Attrs); err != nil {
				return nil, err
			}
		}
	}
	return ast, nil
}

// fillEmptyStanzas replaces absent Data, Actions and Events stanzas with
// ones holding an empty Decl list.
func fillEmptyStanzas(ast *Ast) {
	if ast.Data == nil {
		ast.Data = &DataStanza{Decls: []*Decl{}}
	}
	if ast.Actions == nil {
		ast.Actions = &ActionsStanza{Decls: []*Decl{}}
	}
	if ast.Events == nil {
		ast.Events = &EventsStanza{Decls: []*Decl{}}
	}
}

// quoteAttrStrings wraps every String value reachable from attrs in double
// quotes, matching the raw String-token form the DSL parser captures.
func quoteAttrStrings(attrs []*Attr) error {
	for _, a := range attrs {
		if a == nil || a.Value == nil {
			return fmt.Errorf("decoding mission JSON: attribute missing a Value")
		}
		if err := quoteValueStrings(a.Value); err != nil {
			return err
		}
	}
	return nil
}

func quoteValueStrings(v *Value) error {
	switch {
	case v.String != nil:
		quoted := `"` + *v.String + `"`
		v.String = &quoted
	case v.Array != nil:
		for _, e := range v.Array.Elems {
			if e == nil {
				return fmt.Errorf("decoding mission JSON: null array element")
			}
			if err := quoteValueStrings(e); err != nil {
				return err
			}
		}
	case v.Inline != nil:
		return quoteAttrStrings(v.Inline.Args)
	}
	return nil
}
