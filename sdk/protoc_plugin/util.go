package main

import (
	"path"
	"strings"
	"unicode"

	"google.golang.org/protobuf/compiler/protogen"
)

// capFilePrefix returns the "<category>/<file-basename>" prefix used to
// identify file in the vehicle capability file's path convention - e.g.
// "services/control" for .../steeleagle_protocol/v1/services/driver/control.proto.
// The file's own base name, not its containing directory, disambiguates
// between multiple files sharing one service directory (driver here holds
// control.proto, stream.proto, info.proto, and calibrate.proto).
func capFilePrefix(file *protogen.File) string {
	p := strings.TrimPrefix(string(file.Desc.Path()), "steeleagle_protocol/v1/")
	category, _, _ := strings.Cut(p, "/")
	base := strings.TrimSuffix(path.Base(p), ".proto")
	return category + "/" + base
}

// screamingSnake converts a CamelCase identifier (e.g. "HeadingMode") into
// its SCREAMING_SNAKE_CASE equivalent (e.g. "HEADING_MODE").
func screamingSnake(s string) string {
	runes := []rune(s)
	var b strings.Builder
	for i, r := range runes {
		if i > 0 && unicode.IsUpper(r) && (unicode.IsLower(runes[i-1]) || unicode.IsDigit(runes[i-1])) {
			b.WriteRune('_')
		}
		b.WriteRune(unicode.ToUpper(r))
	}
	return b.String()
}

// camelCaseSnake converts an underscore-delimited segment (e.g. "TO_TARGET")
// into CamelCase ("ToTarget") by titlecasing each word.
func camelCaseSnake(s string) string {
	var b strings.Builder
	for _, part := range strings.Split(s, "_") {
		if part == "" {
			continue
		}
		lower := strings.ToLower(part)
		b.WriteString(strings.ToUpper(lower[:1]) + lower[1:])
	}
	return b.String()
}
