package preprocess

import (
	"go/ast"
	"go/parser"
	"go/token"
	"strconv"
	"testing"
)

// parseConsts parses src and returns a map from every top-level const
// identifier to its string literal value, for asserting on GenerateConsts'
// output without depending on gofmt's exact formatting.
func parseConsts(t *testing.T, src []byte) map[string]string {
	t.Helper()
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, "", src, 0)
	if err != nil {
		t.Fatalf("output is not valid Go: %v\n%s", err, src)
	}
	out := map[string]string{}
	for _, decl := range file.Decls {
		genDecl, ok := decl.(*ast.GenDecl)
		if !ok || genDecl.Tok != token.CONST {
			continue
		}
		for _, spec := range genDecl.Specs {
			valueSpec, ok := spec.(*ast.ValueSpec)
			if !ok || len(valueSpec.Names) != len(valueSpec.Values) {
				continue
			}
			for i, name := range valueSpec.Names {
				lit, ok := valueSpec.Values[i].(*ast.BasicLit)
				if !ok || lit.Kind != token.STRING {
					continue
				}
				value, err := strconv.Unquote(lit.Value)
				if err != nil {
					t.Fatalf("unquoting const value %s: %v", lit.Value, err)
				}
				out[name.Name] = value
			}
		}
	}
	return out
}
