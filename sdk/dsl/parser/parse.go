package parser

import (
    "io"
)

// Parse parses a DSL mission file and unquotes every Override and Import
// path (captured raw as String tokens) in place.
func Parse(filename string, r io.Reader) (*Ast, error) {
	ast, err := dslParser.Parse(filename, r)
	if err != nil {
		return nil, err
	}
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
