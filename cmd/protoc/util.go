package main

import (
	"strings"
	"unicode"
)

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
