package loader

import "testing"

// TestOptionalNoTag checks that a doc comment with no "#optional"
// directive is returned unchanged, with optional reported false.
func TestOptionalNoTag(t *testing.T) {
	scrubbed, optional, value := extractOptional("Duration is how long to hover, in seconds.")
	if optional {
		t.Errorf("optional = true, want false")
	}
	if value != "" {
		t.Errorf("value = %q, want empty", value)
	}
	if scrubbed != "Duration is how long to hover, in seconds." {
		t.Errorf("scrubbed = %q, want input unchanged", scrubbed)
	}
}

// TestOptionalBareTag checks that a bare "#optional" directive (no
// bracketed default) is scrubbed out, reports optional true, and leaves an
// empty default value.
func TestOptionalBareTag(t *testing.T) {
	scrubbed, optional, value := extractOptional("#optional")
	if !optional {
		t.Fatalf("optional = false, want true")
	}
	if value != "" {
		t.Errorf("value = %q, want empty", value)
	}
	if scrubbed != "" {
		t.Errorf("scrubbed = %q, want empty", scrubbed)
	}
}

// TestOptionalWithBracketedDefault checks that "#optional[<value>]"
// captures <value> as the default and scrubs the whole directive out.
func TestOptionalWithBracketedDefault(t *testing.T) {
	scrubbed, optional, value := extractOptional("#optional[10]")
	if !optional {
		t.Fatalf("optional = false, want true")
	}
	if value != "10" {
		t.Errorf("value = %q, want %q", value, "10")
	}
	if scrubbed != "" {
		t.Errorf("scrubbed = %q, want empty", scrubbed)
	}
}

// TestOptionalTagMidText checks that the directive can appear
// anywhere in the doc comment, and that the surrounding text is preserved
// (trimmed) once the directive itself is removed.
func TestOptionalTagMidText(t *testing.T) {
	scrubbed, optional, value := extractOptional("Altitude to hover at. #optional[1.5] Measured in meters.")
	if !optional {
		t.Fatalf("optional = false, want true")
	}
	if value != "1.5" {
		t.Errorf("value = %q, want %q", value, "1.5")
	}
	want := "Altitude to hover at.  Measured in meters."
	if scrubbed != want {
		t.Errorf("scrubbed = %q, want %q", scrubbed, want)
	}
}

// TestOptionalEmptyBrackets checks that "#optional[]" is treated as
// carrying a present-but-empty default rather than no default at all.
func TestOptionalEmptyBrackets(t *testing.T) {
	scrubbed, optional, value := extractOptional("#optional[]")
	if !optional {
		t.Fatalf("optional = false, want true")
	}
	if value != "" {
		t.Errorf("value = %q, want empty", value)
	}
	if scrubbed != "" {
		t.Errorf("scrubbed = %q, want empty", scrubbed)
	}
}
