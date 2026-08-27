package preprocess

import (
	"bytes"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
)

// GenerateConsts returns a copy of a Go source file declaring one or more
// const types as `type <Name> string` (e.g. sdk/params.go or
// dsl/swarm.go) with a const block appended for every type in types.
// Every key of types must already be declared in src as `type <key>
// string`.
func GenerateConsts(types map[string][]string, src []byte) ([]byte, error) {
	declared, err := declaredStringTypes(src)
	if err != nil {
		return nil, &PreprocessError{error: err}
	}
	declaredSet := make(map[string]struct{}, len(declared))
	for _, t := range declared {
		declaredSet[t] = struct{}{}
	}
	for typeName := range types {
		if _, ok := declaredSet[typeName]; !ok {
			return nil, &PreprocessError{error: fmt.Errorf("type %q is not declared as string in source", typeName)}
		}
	}

	var buf bytes.Buffer
	buf.Write(src)
	for _, typeName := range declared {
		names, ok := types[typeName]
		if !ok {
			continue
		}
		if err := writeConsts(&buf, names, typeName); err != nil {
			return nil, &PreprocessError{error: err}
		}
	}
	formatted, err := format.Source(buf.Bytes())
	if err != nil {
		return nil, &PreprocessError{error: err}
	}
	return formatted, nil
}

// declaredStringTypes parses src and returns, in declaration order, the
// names of every type declared there as `type <name> string`.
func declaredStringTypes(src []byte) ([]string, error) {
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, "", src, 0)
	if err != nil {
		return nil, fmt.Errorf("error parsing source: %w", err)
	}
	var names []string
	for _, decl := range file.Decls {
		genDecl, ok := decl.(*ast.GenDecl)
		if !ok || genDecl.Tok != token.TYPE {
			continue
		}
		for _, spec := range genDecl.Specs {
			typeSpec, ok := spec.(*ast.TypeSpec)
			if !ok {
				continue
			}
			ident, ok := typeSpec.Type.(*ast.Ident)
			if !ok || ident.Name != "string" {
				continue
			}
			names = append(names, typeSpec.Name.Name)
		}
	}
	return names, nil
}

// writeConsts appends a const block to buf declaring one constant of type
// typeName per entry in names, named typeName+entry and holding entry
// as its string value.
func writeConsts(buf *bytes.Buffer, names []string, typeName string) error {
	buf.WriteString("\nconst (\n")
	for _, name := range names {
		constName := typeName + name
		if !token.IsIdentifier(constName) {
			return fmt.Errorf("generated const name %q is not a valid Go identifier", constName)
		}
		fmt.Fprintf(buf, "\t%s %s = %q\n", constName, typeName, name)
	}
	buf.WriteString(")\n")
	return nil
}
