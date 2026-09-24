// Package logstore captures per-source log lines, persists them as rotated
// JSONL files, and fans them out to live subscribers.
package logstore

import (
	"crypto/sha256"
	"fmt"
	"strconv"
	"strings"
)

const (
	maxStemBytes = 200
	hashHexLen   = 8
)

func isSafeByte(c byte) bool {
	return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' ||
		c == '_' || c == '-' || c == '.'
}

// EscapeName maps a source name to a filesystem-safe, human-readable,
// reversible file stem. Bytes in [A-Za-z0-9._-] pass through; every other
// byte (and a leading '.') becomes %XX, so the mapping is injective and no
// source can produce a path separator, ".", "..", or a hidden file. A stem
// over maxStemBytes is truncated and gets "~<hash>" appended; '~' is itself
// escaped in normal stems, so a truncated stem can never collide with an
// untruncated one.
func EscapeName(source string) string {
	var b strings.Builder
	for i := 0; i < len(source); i++ {
		c := source[i]
		if isSafeByte(c) && !(i == 0 && c == '.') {
			b.WriteByte(c)
			continue
		}
		fmt.Fprintf(&b, "%%%02X", c)
	}
	stem := b.String()
	if len(stem) <= maxStemBytes {
		return stem
	}
	sum := sha256.Sum256([]byte(source))
	suffix := "~" + fmt.Sprintf("%x", sum[:])[:hashHexLen]
	keep := maxStemBytes - len(suffix)
	if i := strings.LastIndexByte(stem[:keep], '%'); i >= keep-2 {
		keep = i
	}
	return stem[:keep] + suffix
}

// UnescapeName reverses EscapeName. exact is false for a truncated stem (the
// returned source is only a prefix; the true name lives in the records) and
// for a stem that is not a valid escape (returned unchanged).
func UnescapeName(stem string) (source string, exact bool) {
	body, exact := stem, true
	if i := strings.LastIndexByte(stem, '~'); i >= 0 {
		body, exact = stem[:i], false
	}
	src, ok := unescapeBody(body)
	if !ok {
		return stem, false
	}
	return src, exact
}

func unescapeBody(body string) (string, bool) {
	var b strings.Builder
	for i := 0; i < len(body); i++ {
		if body[i] != '%' {
			b.WriteByte(body[i])
			continue
		}
		if i+3 > len(body) {
			return "", false
		}
		v, err := strconv.ParseUint(body[i+1:i+3], 16, 8)
		if err != nil {
			return "", false
		}
		b.WriteByte(byte(v))
		i += 2
	}
	return b.String(), true
}
