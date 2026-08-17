package main

import (
	"go/ast"
	"go/doc"
	"strings"

	"golang.org/x/tools/go/packages"
)

// getPackageDoc returns pkg's exported type/func declarations, keyed by name,
// as computed by go/doc.
func getPackageDoc(pkg *packages.Package) (map[string]*doc.Type, map[string]*doc.Func) {
	docTypes := map[string]*doc.Type{}
	docFuncs := map[string]*doc.Func{}
	if pkg.Fset == nil || len(pkg.Syntax) == 0 {
		return docTypes, docFuncs
	}
	docPkg, err := doc.NewFromFiles(pkg.Fset, pkg.Syntax, pkg.PkgPath, doc.PreserveAST)
	if err != nil {
		return docTypes, docFuncs
	}
	for _, t := range docPkg.Types {
		docTypes[t.Name] = t
	}
	for _, f := range docPkg.Funcs {
		docFuncs[f.Name] = f
	}
	return docTypes, docFuncs
}

// fieldComments returns field name -> doc/line comment text for the struct
// type declared by dt. A field's comment is its leading (Doc) comment if
// present, otherwise its trailing same-line (Comment) comment.
func fieldComments(dt *doc.Type) map[string]string {
	comments := map[string]string{}
	if dt == nil || dt.Decl == nil {
		return comments
	}
	for _, spec := range dt.Decl.Specs {
		ts, ok := spec.(*ast.TypeSpec)
		if !ok || ts.Name.Name != dt.Name {
			continue
		}
		st, ok := ts.Type.(*ast.StructType)
		if !ok || st.Fields == nil {
			return comments
		}
		for _, f := range st.Fields.List {
			text := commentText(f.Doc, f.Comment)
			if text == "" {
				continue
			}
			if len(f.Names) == 0 {
				if name := embeddedFieldName(f.Type); name != "" {
					comments[name] = text
				}
				continue
			}
			for _, id := range f.Names {
				comments[id.Name] = text
			}
		}
		return comments
	}
	return comments // failure case where no comment is found
}

// constComments returns const name -> doc/line comment text for every
// constant go/doc associated with dt (i.e. dt.Consts, the constants
// declared with dt's type).
func constComments(dt *doc.Type) map[string]string {
	comments := map[string]string{}
	if dt == nil {
		return comments
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
			text := commentText(vs.Doc, vs.Comment)
			if text == "" {
				continue
			}
			for _, id := range vs.Names {
				comments[id.Name] = text
			}
		}
	}
	return comments
}

// commentText returns doc's text if present, else line's, else "".
func commentText(doc, line *ast.CommentGroup) string {
	if doc != nil {
		return strings.TrimSpace(doc.Text())
	}
	if line != nil {
		return strings.TrimSpace(line.Text())
	}
	return ""
}
