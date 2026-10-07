package loader

import (
	"go/ast"
	"go/doc"
	"go/token"
	"go/types"
	"strings"
)

// structFields returns one field per public (exported) field of st, split
// into the required fields and the ones tagged #optional in their doc
// comment. dt, if resolvable, supplies each field's doc/line comments; dt
// may be nil, in which case every field's Comment is empty.
func structFields(st *types.Struct, dt *doc.Type) ([]Field, []Field) {
	fields := []Field{}
	optFields := []Field{}
	nodes := structFieldNodes(dt)
	for i := 0; i < st.NumFields(); i++ {
		f := st.Field(i)
		if !f.Exported() {
			continue
		}
		var docText, lineText string
		if node, ok := nodes[f.Name()]; ok {
			if node.Doc != nil {
				docText = strings.TrimSpace(node.Doc.Text())
			}
			if node.Comment != nil {
				lineText = strings.TrimSpace(node.Comment.Text())
			}
		}
		scrubbed, optional, value := extractOptional(docText)
		fld := Field{
			Name:    f.Name(),
			Comment: unifyComment(scrubbed, lineText),
			Value:   value,
			Type:    f.Type(),
		}
		if optional {
			optFields = append(optFields, fld)
		} else {
			fields = append(fields, fld)
		}
	}
	return fields, optFields
}

// enumValues returns one field per exported package-level constant in
// scope declared with type t, its Name and Value both set to the
// constant's own identifier (e.g. "PatrolModeCorridor") and Comment read
// from dt (dt.Consts specifically).
func enumValues(scope *types.Scope, t *types.Named, dt *doc.Type) []Field {
	nodes := constNodes(dt)
	var values []Field
	for _, name := range scope.Names() {
		if !token.IsExported(name) {
			continue
		}
		c, ok := scope.Lookup(name).(*types.Const)
		if !ok {
			continue
		}
		named, ok := c.Type().(*types.Named)
		if !ok || named != t {
			continue
		}
		var docText, lineText string
		if node, ok := nodes[name]; ok {
			if node.Doc != nil {
				docText = strings.TrimSpace(node.Doc.Text())
			}
			if node.Comment != nil {
				lineText = strings.TrimSpace(node.Comment.Text())
			}
		}
		values = append(values, Field{
			Name:    name,
			Comment: unifyComment(docText, lineText),
			Value:   name,
			Type:    c.Type(),
		})
	}
	return values
}

// structFieldNodes returns field name -> *ast.Field for the struct type
// declared by dt, so callers can read each field's raw Doc and Comment
// groups independently instead of a single fallback string.
func structFieldNodes(dt *doc.Type) map[string]*ast.Field {
	nodes := map[string]*ast.Field{}
	if dt == nil || dt.Decl == nil {
		return nodes
	}
	for _, spec := range dt.Decl.Specs {
		ts, ok := spec.(*ast.TypeSpec)
		if !ok || ts.Name.Name != dt.Name {
			continue
		}
		st, ok := ts.Type.(*ast.StructType)
		if !ok || st.Fields == nil {
			return nodes
		}
		for _, f := range st.Fields.List {
			if len(f.Names) == 0 {
				if name := embeddedFieldName(f.Type); name != "" {
					nodes[name] = f
				}
				continue
			}
			for _, id := range f.Names {
				nodes[id.Name] = f
			}
		}
		return nodes
	}
	return nodes // failure case where the declaration wasn't found
}

// constNodes returns const name -> *ast.ValueSpec for every constant go/doc
// associated with dt (i.e. dt.Consts, the constants declared with dt's
// type), so callers can read each constant's raw Doc and Comment groups.
func constNodes(dt *doc.Type) map[string]*ast.ValueSpec {
	nodes := map[string]*ast.ValueSpec{}
	if dt == nil {
		return nodes
	}
	for _, v := range dt.Consts {
		if v.Decl == nil {
			continue
		}
		for _, spec := range v.Decl.Specs {
			vs, ok := spec.(*ast.ValueSpec)
			if !ok {
				continue
			}
			for _, id := range vs.Names {
				nodes[id.Name] = vs
			}
		}
	}
	return nodes
}

// embeddedFieldName returns the identifier go/types would use as the field
// name for an embedded (anonymous) struct field declared with expr.
func embeddedFieldName(expr ast.Expr) string {
	switch e := expr.(type) {
	case *ast.Ident:
		return e.Name
	case *ast.SelectorExpr:
		return e.Sel.Name
	case *ast.StarExpr:
		return embeddedFieldName(e.X)
	case *ast.IndexExpr:
		return embeddedFieldName(e.X)
	default:
		return ""
	}
}
