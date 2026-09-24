package logstore

import (
	"strings"
	"testing"
)

func TestEscapeNameOrdinaryNamesUnchanged(t *testing.T) {
	for _, name := range []string{"daemon", "aviary", "steppeeagle-driver", "harpy-mockdriver", "a_b.c", "V1"} {
		if got := EscapeName(name); got != name {
			t.Errorf("EscapeName(%q) = %q, want unchanged", name, got)
		}
	}
}

func TestEscapeNameNeutralizesDangerousNames(t *testing.T) {
	cases := map[string]string{
		"../../etc/passwd": "%2E.%2F..%2Fetc%2Fpasswd",
		".":                "%2E",
		"..":               "%2E.",
		".hidden":          "%2Ehidden",
		"a b":              "a%20b",
		"100%":             "100%25",
		"a\x00b":           "a%00b",
		"café":             "caf%C3%A9",
		"a~b":              "a%7Eb",
		"a\\b":             "a%5Cb",
	}
	for in, want := range cases {
		if got := EscapeName(in); got != want {
			t.Errorf("EscapeName(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestEscapeNameNeverProducesUnsafeStem(t *testing.T) {
	for _, in := range []string{"", ".", "..", "../x", "/abs", "a/b", strings.Repeat("/", 300), strings.Repeat("x", 500)} {
		got := EscapeName(in)
		if strings.ContainsAny(got, "/\\\x00") || got == "." || got == ".." || strings.HasPrefix(got, ".") || len(got) > 200 {
			t.Errorf("EscapeName(%q) = %q is unsafe", in, got)
		}
	}
}

func TestEscapeNameRoundTrips(t *testing.T) {
	for _, in := range []string{"daemon", "a b", "../x", "100%", "café", ".hidden", "a~b", "a%2Fb"} {
		got, exact := UnescapeName(EscapeName(in))
		if got != in || !exact {
			t.Errorf("round trip of %q = (%q, %v)", in, got, exact)
		}
	}
}

func TestEscapeNameIsInjective(t *testing.T) {
	if EscapeName("a%2Fb") == EscapeName("a/b") {
		t.Fatal(`"a%2Fb" and "a/b" must map to different stems`)
	}
}

func TestEscapeNameTruncatesLongNamesUniquely(t *testing.T) {
	a := EscapeName(strings.Repeat("x", 300) + "a")
	b := EscapeName(strings.Repeat("x", 300) + "b")
	if a == b {
		t.Fatal("long names differing only at the end must stay distinct")
	}
	if len(a) > 200 || !strings.Contains(a, "~") {
		t.Fatalf("expected truncated stem with hash suffix within 200 bytes, got %q (%d)", a, len(a))
	}
	if again := EscapeName(strings.Repeat("x", 300) + "a"); again != a {
		t.Fatal("truncation must be deterministic")
	}
	if _, exact := UnescapeName(a); exact {
		t.Fatal("a truncated stem must not report an exact source")
	}
}

func TestEscapeNameTruncationNeverSplitsAnEscape(t *testing.T) {
	for n := 60; n < 90; n++ {
		stem := EscapeName(strings.Repeat("/", n))
		i := strings.LastIndex(stem, "~")
		if i < 0 {
			continue // short enough not to be truncated
		}
		prefix := stem[:i]
		if _, ok := unescapeBody(prefix); !ok {
			t.Errorf("n=%d: truncated prefix %q ends in a broken escape", n, prefix)
		}
	}
}
