package parser

import "testing"

// TestUnquoteStringStripsSurroundingQuotes checks that unquoteString
// strips exactly one layer of surrounding quotes, for both quote styles
// the String token accepts.
func TestUnquoteStringStripsSurroundingQuotes(t *testing.T) {
	cases := map[string]string{
		`"home"`: "home",
		`'home'`: "home",
		`""`:     "",
		`''`:     "",
	}
	for in, want := range cases {
		if got := unquoteString(in); got != want {
			t.Errorf("unquoteString(%q) = %q, want %q", in, got, want)
		}
	}
}

// TestUnquoteStringShortInputReturnedUnchanged checks that a string too
// short to have a surrounding quote pair (length < 2) is returned
// rather than panicking on the slice bounds.
func TestUnquoteStringShortInputReturnedUnchanged(t *testing.T) {
	for _, in := range []string{"", "x"} {
		if got := unquoteString(in); got != in {
			t.Errorf("unquoteString(%q) = %q, want unchanged", in, got)
		}
	}
}

// TestValueStringValueUnquotes checks that StringValue reports true and
// returns the unquoted text when the Value holds a String.
func TestValueStringValueUnquotes(t *testing.T) {
	raw := `"home"`
	v := &Value{String: &raw}
	s, ok := v.StringValue()
	if !ok {
		t.Fatalf("StringValue() ok = false, want true")
	}
	if s != "home" {
		t.Errorf("StringValue() = %q, want %q", s, "home")
	}
}

// TestValueStringValueFalseWhenNotAString checks that StringValue reports
// false and an empty string when the Value's String field is unset, e.g.
// because the value was actually a Float, Ident, Array, or InlineCtor.
func TestValueStringValueFalseWhenNotAString(t *testing.T) {
	v := &Value{}
	s, ok := v.StringValue()
	if ok {
		t.Errorf("StringValue() ok = true, want false")
	}
	if s != "" {
		t.Errorf("StringValue() = %q, want empty", s)
	}
}
