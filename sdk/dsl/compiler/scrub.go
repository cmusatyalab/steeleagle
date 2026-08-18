package main

import (
	"bytes"
	"fmt"
	"os"
	"strings"

	"golang.org/x/tools/go/packages"
)

// The six preprocessor-style directive comments scrub.go understands.
// Single-line forms govern the one line immediately following them;
// begin/end forms govern every line between them (and may nest).
const (
	tagExclude      = "// #exclude-ifndef"
	tagPrivate      = "// #private-ifndef"
	tagBeginExclude = "// #begin-exclude-ifndef"
	tagEndExclude   = "// #end-exclude"
	tagBeginPrivate = "// #begin-private-ifndef"
	tagEndPrivate   = "// #end-private"
)

// scrubPkgPaths returns steeleaglePkgs plus every unique path named in
// imports, matching the package selection loadPackages itself uses.
func scrubPkgPaths(imports []*ImportSpec) []string {
	pkgPaths := append([]string{}, steeleaglePkgs...)
	seen := make(map[string]bool, len(pkgPaths))
	for _, p := range pkgPaths {
		seen[p] = true
	}
	for _, imp := range imports {
		if !seen[imp.Path] {
			seen[imp.Path] = true
			pkgPaths = append(pkgPaths, imp.Path)
		}
	}
	return pkgPaths
}

// scrubPackages walks every base steeleagle package and every package
// named in imports, applies the #exclude-requires/#private-requires
// directives found in their source (see scrubSource) using unsupported as
// the blacklist, and returns every file whose content actually changed as
// a map from absolute file path to new content.
func scrubPackages(imports []*ImportSpec, workspace string, unsupported map[string]struct{}) (map[string][]byte, error) {
	cfg := &packages.Config{
		Dir: workspace,
		// The scratch go.mod's require/replace directives, copied
		// wholesale from repoRoot's own go.mod, don't preserve its
		// direct/indirect split; -mod=mod lets the go command settle
		// that itself instead of refusing to load anything.
		Env:  append(os.Environ(), "GOFLAGS=-mod=mod"),
		Mode: packages.NeedName | packages.NeedFiles,
	}
	pkgs, err := packages.Load(cfg, scrubPkgPaths(imports)...)
	if err != nil {
		return nil, fmt.Errorf("failed to load packages for scrubbing: %w", err)
	}

	overlay := map[string][]byte{}
	for _, pkg := range pkgs {
		for _, e := range pkg.Errors {
			return nil, fmt.Errorf("package %q: %s", pkg.PkgPath, e.Error())
		}
		for _, file := range pkg.GoFiles {
			src, err := os.ReadFile(file)
			if err != nil {
				return nil, fmt.Errorf("reading %s: %w", file, err)
			}
			scrubbed, err := scrubSource(src, unsupported)
			if err != nil {
				return nil, fmt.Errorf("%s: %w", file, err)
			}
			if !bytes.Equal(src, scrubbed) {
				overlay[file] = scrubbed
			}
		}
	}
	return overlay, nil
}

// scrubSource applies #exclude-requires/#private-requires directives (and
// their #begin/#end multi-line, nestable forms) to src, returning the
// transformed source.
func scrubSource(src []byte, unsupported map[string]struct{}) ([]byte, error) {
	lines := strings.Split(string(src), "\n")
	out := make([]string, len(lines))
	copy(out, lines)

	triggeredBy := func(ids []string) bool {
		for _, id := range ids {
			if _, no := unsupported[id]; no {
				return true
			}
		}
		return false
	}

	// excludeStack/privateStack are the two independent nesting chains;
	// pendingExclude/pendingPrivate hold a single-line tag's effect until
	// the next line consumes it
	var excludeStack, privateStack []bool
	var pendingExclude, pendingPrivate *bool

	for i, raw := range lines {
		line := strings.TrimSpace(raw)

		excludeParent := len(excludeStack) > 0 && excludeStack[len(excludeStack)-1]
		privateParent := len(privateStack) > 0 && privateStack[len(privateStack)-1]

		if ids, ok := cutTag(line, tagExclude); ok {
			t := triggeredBy(ids) || excludeParent
			pendingExclude = &t
			continue
		}
		if ids, ok := cutTag(line, tagPrivate); ok {
			t := triggeredBy(ids) || privateParent
			pendingPrivate = &t
			continue
		}
		if ids, ok := cutTag(line, tagBeginExclude); ok {
			excludeStack = append(excludeStack, triggeredBy(ids) || excludeParent)
			continue
		}
		if ids, ok := cutTag(line, tagBeginPrivate); ok {
			privateStack = append(privateStack, triggeredBy(ids) || privateParent)
			continue
		}
		if _, ok := cutTag(line, tagEndExclude); ok {
			if len(excludeStack) == 0 {
				return nil, fmt.Errorf("line %d: %s with no matching %s", i+1, tagEndExclude, tagBeginExclude)
			}
			excludeStack = excludeStack[:len(excludeStack)-1]
			continue
		}
		if _, ok := cutTag(line, tagEndPrivate); ok {
			if len(privateStack) == 0 {
				return nil, fmt.Errorf("line %d: %s with no matching %s", i+1, tagEndPrivate, tagBeginPrivate)
			}
			privateStack = privateStack[:len(privateStack)-1]
			continue
		}

		excludeActive := (pendingExclude != nil && *pendingExclude) || excludeParent
		privateActive := (pendingPrivate != nil && *pendingPrivate) || privateParent
		pendingExclude, pendingPrivate = nil, nil

		switch {
		case excludeActive:
			out[i] = ""
		case privateActive:
			out[i] = privateLine(raw)
		}
	}

	if len(excludeStack) > 0 || len(privateStack) > 0 {
		return nil, fmt.Errorf("%d unclosed directive block(s) at end of file", len(excludeStack)+len(privateStack))
	}
	return []byte(strings.Join(out, "\n")), nil
}

// cutTag reports whether trimmedLine is an occurrence of the directive
// tag, returning its comma-separated, whitespace-trimmed id list (nil for
// the #end forms, which take none).
func cutTag(trimmedLine, tag string) ([]string, bool) {
	if !strings.HasPrefix(trimmedLine, tag) {
		return nil, false
	}
	rest := strings.TrimSpace(trimmedLine[len(tag):])
	if rest == "" {
		return nil, true
	}
	parts := strings.Split(rest, ",")
	ids := make([]string, 0, len(parts))
	for _, p := range parts {
		if id := strings.TrimSpace(p); id != "" {
			ids = append(ids, id)
		}
	}
	return ids, true
}

// privateLine lowercases the first character of line's leading exported
// identifier, preserving indentation and everything else, e.g.
// "SetAltitude(float32)" -> "setAltitude(float32)".
func privateLine(line string) string {
	trimmed := strings.TrimLeft(line, " \t")
	indent := line[:len(line)-len(trimmed)]

	i := 0
	for i < len(trimmed) && isIdentByte(trimmed[i], i == 0) {
		i++
	}
	if i == 0 || trimmed[0] < 'A' || trimmed[0] > 'Z' {
		return line
	}
	return indent + strings.ToLower(trimmed[:1]) + trimmed[1:]
}

// isIdentByte is used to check if a token byte is valid within a Go
// identifier.
func isIdentByte(b byte, first bool) bool {
	switch {
	case b == '_', b >= 'a' && b <= 'z', b >= 'A' && b <= 'Z':
		return true
	case !first && b >= '0' && b <= '9':
		return true
	default:
		return false
	}
}
