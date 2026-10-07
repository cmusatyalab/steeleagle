package parser

import (
	"strings"
	"testing"
)

// mustParse parses src as a DSL mission file, failing the test
// on a parse error.
func mustParse(t *testing.T, src string) *Ast {
	t.Helper()
	ast, err := Parse("test.dsl", strings.NewReader(src))
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}
	return ast
}
