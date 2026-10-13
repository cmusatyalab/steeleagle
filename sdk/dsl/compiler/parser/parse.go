package parser

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
)

// ParseFromFile parses the DSL mission file at path. See parse.
func ParseFromFile(path string) (*Ast, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return parse(path, f)
}

// ParseFromSource parses a DSL mission from its source text. Errors carry
// no file name, only a line and column. See parse.
func ParseFromSource(src []byte) (*Ast, error) {
	return parse("", bytes.NewReader(src))
}

// ParseFromJson decodes a JSON-encoded mission into an *Ast. The JSON
// mirrors the Ast structs field for field (keys are the Go field names,
// matched case-insensitively), e.g.
//
//	{"Actions": {"Decls": [{"Type": "actions.TakeOff", "Name": "takeoff",
//	  "Attrs": [{"Key": "altitude", "Value": {"Float": 2.5}}]}]}}
//
// Unknown keys are rejected. Modules paths and overrides, Imports paths and
// String values are written unquoted; String values are re-quoted on
// decode so that Value.StringValue behaves the same as for ParseFromFile.
// Absent stanzas are filled in empty, as in ParseFromFile.
func ParseFromJson(data []byte) (*Ast, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
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

// parse parses a DSL mission read from r and unquotes every Modules path and
// override and every Imports path (captured raw as String tokens) in place. Absent stanzas are filled in
// empty, so callers never see them as nil.
func parse(filename string, r io.Reader) (*Ast, error) {
	ast, err := dslParser.Parse(filename, r)
	if err != nil {
		return nil, err
	}
	fillEmptyStanzas(ast)
	for _, mod := range ast.Modules.Modules {
		mod.Path = unquoteString(mod.Path)
		if mod.Override != "" {
			mod.Override = unquoteString(mod.Override)
		}
	}
	for _, imp := range ast.Imports.Imports {
		imp.Path = unquoteString(imp.Path)
	}
	return ast, nil
}

// fillEmptyStanzas replaces every absent stanza with an empty one: an
// empty Role name and Mission Start, and empty Modules, Imports and Decl
// lists. A stanza that is present but has no entries (e.g. a bare
// "Modules:" header) likewise gets an empty, non-nil list.
func fillEmptyStanzas(ast *Ast) {
	if ast.Role == nil {
		ast.Role = &RoleStanza{}
	}
	if ast.Modules == nil {
		ast.Modules = &ModuleStanza{}
	}
	if ast.Modules.Modules == nil {
		ast.Modules.Modules = []*ModuleSpec{}
	}
	if ast.Imports == nil {
		ast.Imports = &ImportStanza{}
	}
	if ast.Imports.Imports == nil {
		ast.Imports.Imports = []*ImportSpec{}
	}
	if ast.Data == nil {
		ast.Data = &DataStanza{}
	}
	if ast.Data.Decls == nil {
		ast.Data.Decls = []*Decl{}
	}
	if ast.Actions == nil {
		ast.Actions = &ActionsStanza{}
	}
	if ast.Actions.Decls == nil {
		ast.Actions.Decls = []*Decl{}
	}
	if ast.Events == nil {
		ast.Events = &EventsStanza{}
	}
	if ast.Events.Decls == nil {
		ast.Events.Decls = []*Decl{}
	}
	if ast.Mission == nil {
		ast.Mission = &MissionStanza{}
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
