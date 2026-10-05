package preprocess_test

import (
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/preprocess"
)

// TestScrubNoDirectivesUnchanged checks to make sure that a file with
// no directives set comes back exactly the same.
func TestScrubNoDirectivesUnchanged(t *testing.T) {
	cap := newCapFile(t)
	src := "package foo\n\nfunc Bar() {}\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if dirty {
		t.Error("dirty = true for a file with no directives, want false")
	}
	if string(out) != src {
		t.Errorf("out = %q, want %q", out, src)
	}
}

// TestScrubSingleLineExcludeSatisfied checks to make sure that a single
// line exclude directive works.
func TestScrubSingleLineExcludeSatisfied(t *testing.T) {
	cap := newCapFile(t, "services/driver/TakeOffRequest/altitude")
	src := "// #exclude-ifndef services/driver/TakeOffRequest/altitude\n" +
		"GetAltitude() float32\n" +
		"GetLatitude() float32\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	if lines[1] != "" {
		t.Errorf("excluded line = %q, want blank", lines[1])
	}
	if lines[2] != "GetLatitude() float32" {
		t.Errorf("unrelated line changed: %q", lines[2])
	}
}

// TestScrubSingleLineExcludeNotSatisfied checks to make sure that a
// single line exclude directive leaves its governed line alone when it
// isn't satisfied, even though the tag line itself is still stripped.
func TestScrubSingleLineExcludeNotSatisfied(t *testing.T) {
	cap := newCapFile(t) // altitude is supported, directive shouldn't fire
	src := "// #exclude-ifndef services/driver/TakeOffRequest/altitude\nGetAltitude() float32\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Error("dirty = false, want true: the tag line is always stripped")
	}
	lines := strings.Split(string(out), "\n")
	if lines[0] != "" {
		t.Errorf("tag line = %q, want blank", lines[0])
	}
	if lines[1] != "GetAltitude() float32" {
		t.Errorf("line = %q, want unchanged", lines[1])
	}
}

// TestScrubSingleLineExcludeSkipsCommentLines checks to make sure that
// an #exclude-ifndef directive reaches past intervening comment lines
// (e.g. a doc comment) to exclude the next actual line of code, and that
// the comment lines in between are excluded along with it.
func TestScrubSingleLineExcludeSkipsCommentLines(t *testing.T) {
	cap := newCapFile(t, "services/driver/TakeOffRequest/altitude")
	src := "// #exclude-ifndef services/driver/TakeOffRequest/altitude\n" +
		"// GetAltitude returns the last known altitude.\n" +
		"GetAltitude() float32\n" +
		"GetLatitude() float32\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	if lines[1] != "" {
		t.Errorf("doc comment line = %q, want blank", lines[1])
	}
	if lines[2] != "" {
		t.Errorf("excluded line = %q, want blank", lines[2])
	}
	if lines[3] != "GetLatitude() float32" {
		t.Errorf("unrelated line changed: %q", lines[3])
	}
}

// TestScrubSingleLinePrivateSkipsCommentLines checks to make sure that a
// #private-ifndef directive reaches past intervening comment lines to
// private the next actual line of code.
func TestScrubSingleLinePrivateSkipsCommentLines(t *testing.T) {
	cap := newCapFile(t, "services/control/HeadingMode/HEADING_MODE_START")
	src := "// #private-ifndef services/control/HeadingMode/HEADING_MODE_START\n" +
		"// HeadingMode_HEADING_MODE_START is the starting heading mode.\n" +
		"HeadingMode_HEADING_MODE_START HeadingMode = 0\n" +
		"HeadingMode_HEADING_MODE_MAGNETIC HeadingMode = 1\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	if lines[1] != "// HeadingMode_HEADING_MODE_START is the starting heading mode." {
		t.Errorf("doc comment line = %q, want unchanged (comments aren't privated)", lines[1])
	}
	want := "headingMode_HEADING_MODE_START HeadingMode = 0"
	if lines[2] != want {
		t.Errorf("line = %q, want %q", lines[2], want)
	}
	if lines[3] != "HeadingMode_HEADING_MODE_MAGNETIC HeadingMode = 1" {
		t.Errorf("unrelated line changed: %q", lines[3])
	}
}

// TestScrubSingleLinePrivateSatisfied checks to make sure that a single
// line private directive works.
func TestScrubSingleLinePrivateSatisfied(t *testing.T) {
	cap := newCapFile(t, "services/control/ReturnToHomeEndBehavior/RETURN_TO_HOME_END_BEHAVIOR_HOVER")
	src := "// #private-ifndef services/control/ReturnToHomeEndBehavior/RETURN_TO_HOME_END_BEHAVIOR_HOVER\n" +
		"ReturnToHomeEndBehavior_RETURN_TO_HOME_END_BEHAVIOR_HOVER ReturnToHomeEndBehavior = 3\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	want := "returnToHomeEndBehavior_RETURN_TO_HOME_END_BEHAVIOR_HOVER ReturnToHomeEndBehavior = 3"
	if lines[1] != want {
		t.Errorf("line = %q, want %q", lines[1], want)
	}
}

// TestScrubBeginEndExcludeBlock checks to make sure that a begin/end
// exclude block blanks every line it wraps.
func TestScrubBeginEndExcludeBlock(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := "// #begin-exclude-ifndef services/driver/ControlService/Kill\n" +
		"GetKillReason() string\n" +
		"hasKillReason() bool\n" +
		"// #end-exclude\n" +
		"GetStatus() string\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	if lines[1] != "" || lines[2] != "" {
		t.Errorf("block lines not blanked: %q, %q", lines[1], lines[2])
	}
	if lines[4] != "GetStatus() string" {
		t.Errorf("line after block changed: %q", lines[4])
	}
}

// TestScrubBeginEndPrivateBlock checks to make sure that a begin/end
// private block privates every line it wraps.
func TestScrubBeginEndPrivateBlock(t *testing.T) {
	cap := newCapFile(t, "services/control/HeadingMode/HEADING_MODE_START")
	src := "// #begin-private-ifndef services/control/HeadingMode/HEADING_MODE_START\n" +
		"HeadingMode_HEADING_MODE_START HeadingMode = 0\n" +
		"HeadingMode_HEADING_MODE_MAGNETIC HeadingMode = 1\n" +
		"// #end-private\n" +
		"HeadingMode_HEADING_MODE_GPS HeadingMode = 2\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	want := []string{
		"",
		"headingMode_HEADING_MODE_START HeadingMode = 0",
		"headingMode_HEADING_MODE_MAGNETIC HeadingMode = 1",
		"",
		"HeadingMode_HEADING_MODE_GPS HeadingMode = 2",
		"",
	}
	for i, w := range want {
		if lines[i] != w {
			t.Errorf("lines[%d] = %q, want %q", i, lines[i], w)
		}
	}
}

// TestScrubNestedExcludeDominance checks to make sure that a nested
// exclude block can't un-satisfy a dominant outer block.
func TestScrubNestedExcludeDominance(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := strings.Join([]string{
		"// #begin-exclude-ifndef services/driver/ControlService/Kill",
		"GetKillReason() string",
		"// #begin-exclude-ifndef services/driver/TakeOffRequest/altitude",
		"GetAltitude() float32",
		"// #end-exclude",
		"GetStatus() string",
		"// #end-exclude",
		"GetAircraftID() string",
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := strings.Split(string(out), "\n")
	for _, i := range []int{1, 3, 5} {
		if lines[i] != "" {
			t.Errorf("lines[%d] = %q, want blank (still inside dominant outer block)", i, lines[i])
		}
	}
	if lines[7] != "GetAircraftID() string" {
		t.Errorf("lines[7] = %q, want unchanged after the outer block closes", lines[7])
	}
}

// TestScrubMultipleTypesOrSemantics checks to make sure that a directive
// fires if any of its comma-separated types is unsupported.
func TestScrubMultipleTypesOrSemantics(t *testing.T) {
	cap := newCapFile(t, "services/driver/TakeOffRequest/altitude")
	src := "// #exclude-ifndef services/driver/TakeOffRequest/latitude,services/driver/TakeOffRequest/altitude\n" +
		"GetLatitude() float32\n"
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	if lines[1] != "" {
		t.Errorf("line = %q, want blank", lines[1])
	}
}

// TestScrubPrivateNoOpStillDirty checks to make sure that dirty is true
// even when a private directive doesn't actually change any governed
// line, because the directive lines themselves are still stripped.
func TestScrubPrivateNoOpStillDirty(t *testing.T) {
	cap := newCapFile(t, "services/control/HeadingMode/HEADING_MODE_START")
	src := "// #begin-private-ifndef services/control/HeadingMode/HEADING_MODE_START\n// a comment\n// #end-private\n"
	_, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Error("dirty = false, want true: the begin/end tag lines are always stripped")
	}
}

// TestScrubMismatchedEndExclude checks to make sure that an #end-exclude
// with no matching begin returns an error.
func TestScrubMismatchedEndExclude(t *testing.T) {
	cap := newCapFile(t)
	src := "GetStatus() string\n// #end-exclude\n"
	_, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err == nil {
		t.Fatal("expected error for unmatched #end-exclude, got nil")
	}
}

// TestScrubMismatchedEndPrivate checks to make sure that an #end-private
// with no matching begin returns an error.
func TestScrubMismatchedEndPrivate(t *testing.T) {
	cap := newCapFile(t)
	src := "GetStatus() string\n// #end-private\n"
	_, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err == nil {
		t.Fatal("expected error for unmatched #end-private, got nil")
	}
}

// TestScrubUnclosedExcludeBlock checks to make sure that an unclosed
// begin-exclude block returns an error.
func TestScrubUnclosedExcludeBlock(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := "// #begin-exclude-ifndef services/driver/ControlService/Kill\nGetKillReason() string\n"
	_, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err == nil {
		t.Fatal("expected error for unclosed exclude block, got nil")
	}
}

// TestScrubUnclosedPrivateBlock checks to make sure that an unclosed
// begin-private block returns an error.
func TestScrubUnclosedPrivateBlock(t *testing.T) {
	cap := newCapFile(t, "services/control/HeadingMode/HEADING_MODE_START")
	src := "// #begin-private-ifndef services/control/HeadingMode/HEADING_MODE_START\nHeadingMode_HEADING_MODE_START HeadingMode = 0\n"
	_, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err == nil {
		t.Fatal("expected error for unclosed private block, got nil")
	}
}

// TestScrubTagLinesAlwaysRemoved checks that every directive line itself is
// always stripped from the output, regardless of whether its directive is
// satisfied. Directive lines are preprocessor syntax, not source.
func TestScrubTagLinesAlwaysRemoved(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	tagLines := []string{
		"// #exclude-ifndef services/driver/ControlService/Kill",       // satisfied
		"// #exclude-ifndef services/driver/TakeOffRequest/altitude",   // not satisfied
		"// #private-ifndef services/driver/ControlService/Kill",       // satisfied
		"// #begin-exclude-ifndef services/driver/ControlService/Kill", // satisfied
		"// #end-exclude",
		"// #begin-private-ifndef services/driver/TakeOffRequest/altitude", // not satisfied
		"// #end-private",
	}
	src := strings.Join([]string{
		tagLines[0],
		"GetKillReason() string",
		tagLines[1],
		"GetAltitude() float32",
		tagLines[2],
		"HasKillReason() bool",
		tagLines[3],
		"GetKillReason2() string",
		tagLines[4],
		tagLines[5],
		"GetAltitude2() float32",
		tagLines[6],
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, tag := range tagLines {
		if strings.Contains(string(out), tag) {
			t.Errorf("tag line %q still present in output:\n%s", tag, out)
		}
	}
}

// TestScrubReplaceSupportedKeepsOriginal checks to make sure that a replace
// block keeps its original section and drops its replacement section when
// every tagged type is supported.
func TestScrubReplaceSupportedKeepsOriginal(t *testing.T) {
	cap := newCapFile(t) // everything supported, directive shouldn't fire
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/TakeOffRequest/altitude",
		"return req.GetAltitude()",
		"// #replace-with",
		"return 0",
		"// #end-replace",
		"GetStatus() string",
		"",
	}, "\n")
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Error("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	want := []string{"", "return req.GetAltitude()", "", "", "", "GetStatus() string", ""}
	for i, w := range want {
		if lines[i] != w {
			t.Errorf("lines[%d] = %q, want %q", i, lines[i], w)
		}
	}
}

// TestScrubReplaceUnsupportedKeepsReplacement checks to make sure that a
// replace block drops its original section and keeps its replacement
// section when a tagged type is unsupported.
func TestScrubReplaceUnsupportedKeepsReplacement(t *testing.T) {
	cap := newCapFile(t, "services/driver/TakeOffRequest/altitude")
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/TakeOffRequest/altitude",
		"return req.GetAltitude()",
		"// #replace-with",
		"return 0",
		"// #end-replace",
		"GetStatus() string",
		"",
	}, "\n")
	out, dirty, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !dirty {
		t.Fatal("dirty = false, want true")
	}
	lines := strings.Split(string(out), "\n")
	want := []string{"", "", "", "return 0", "", "GetStatus() string", ""}
	for i, w := range want {
		if lines[i] != w {
			t.Errorf("lines[%d] = %q, want %q", i, lines[i], w)
		}
	}
}

// TestScrubReplaceMultipleTypes checks to make sure that a replace block
// keeps its original section only if all tagged types are supported, and
// falls back to the replacement if any one of them is unsupported.
func TestScrubReplaceMultipleTypes(t *testing.T) {
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/TakeOffRequest/latitude,services/driver/TakeOffRequest/altitude",
		"original",
		"// #replace-with",
		"replacement",
		"// #end-replace",
		"",
	}, "\n")
	tests := []struct {
		name        string
		unsupported []string
		want        string
	}{
		{"all supported", nil, "original"},
		{"first unsupported", []string{"services/driver/TakeOffRequest/latitude"}, "replacement"},
		{"second unsupported", []string{"services/driver/TakeOffRequest/altitude"}, "replacement"},
		{"both unsupported", []string{"services/driver/TakeOffRequest/latitude", "services/driver/TakeOffRequest/altitude"}, "replacement"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cap := newCapFile(t, tt.unsupported...)
			out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			got := strings.TrimSpace(string(out))
			if got != tt.want {
				t.Errorf("kept %q, want %q", got, tt.want)
			}
		})
	}
}

// TestScrubReplaceMultiLineSections checks to make sure that every line in
// each section of a replace block is kept or dropped together.
func TestScrubReplaceMultiLineSections(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/ControlService/Kill",
		"reason := resp.GetKillReason()",
		"log.Print(reason)",
		"return reason",
		"// #replace-with",
		"// Kill is unsupported on this vehicle.",
		"return \"\"",
		"// #end-replace",
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := strings.Split(string(out), "\n")
	want := []string{"", "", "", "", "", "// Kill is unsupported on this vehicle.", "return \"\"", "", ""}
	for i, w := range want {
		if lines[i] != w {
			t.Errorf("lines[%d] = %q, want %q", i, lines[i], w)
		}
	}
}

// TestScrubReplaceEmptySections checks to make sure that a replace block
// with an empty section is valid, so it can be used to only add or only
// remove code.
func TestScrubReplaceEmptySections(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/ControlService/Kill",
		"// #replace-with",
		"stub()",
		"// #end-replace",
		"// #begin-replace-ifndef services/driver/ControlService/Kill",
		"real()",
		"// #replace-with",
		"// #end-replace",
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got := strings.TrimSpace(string(out)); got != "stub()" {
		t.Errorf("output = %q, want only %q", got, "stub()")
	}
}

// TestScrubReplaceNested checks to make sure that a replace block nested
// in a kept section is evaluated on its own, while one nested in a dropped
// section is dropped entirely regardless of its own types.
func TestScrubReplaceNested(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/TakeOffRequest/altitude", // supported: keep original
		"// #begin-replace-ifndef services/driver/ControlService/Kill",     // unsupported: keep replacement
		"inner-original-a",
		"// #replace-with",
		"inner-replacement-a",
		"// #end-replace",
		"// #replace-with",
		"// #begin-replace-ifndef services/driver/TakeOffRequest/altitude", // inside dropped section
		"inner-original-b",
		"// #replace-with",
		"inner-replacement-b",
		"// #end-replace",
		"// #end-replace",
		"after",
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	var kept []string
	for _, l := range strings.Split(string(out), "\n") {
		if l != "" {
			kept = append(kept, l)
		}
	}
	want := []string{"inner-replacement-a", "after"}
	if strings.Join(kept, ",") != strings.Join(want, ",") {
		t.Errorf("kept lines = %q, want %q", kept, want)
	}
}

// TestScrubReplaceInsideExclude checks to make sure that an exclude block
// dominates a replace block nested inside of it, so neither section is kept.
func TestScrubReplaceInsideExclude(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := strings.Join([]string{
		"// #begin-exclude-ifndef services/driver/ControlService/Kill",
		"// #begin-replace-ifndef services/driver/TakeOffRequest/altitude",
		"original",
		"// #replace-with",
		"replacement",
		"// #end-replace",
		"// #end-exclude",
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got := strings.TrimSpace(string(out)); got != "" {
		t.Errorf("output = %q, want blank", got)
	}
}

// TestScrubReplaceWithPrivate checks to make sure that the kept section of
// a replace block is still subject to an enclosing private block.
func TestScrubReplaceWithPrivate(t *testing.T) {
	cap := newCapFile(t, "services/driver/ControlService/Kill")
	src := strings.Join([]string{
		"// #begin-private-ifndef services/driver/ControlService/Kill",
		"// #begin-replace-ifndef services/driver/ControlService/Kill",
		"Kill() error",
		"// #replace-with",
		"KillStub() error",
		"// #end-replace",
		"// #end-private",
		"",
	}, "\n")
	out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got := strings.TrimSpace(string(out)); got != "killStub() error" {
		t.Errorf("output = %q, want %q", got, "killStub() error")
	}
}

// TestScrubReplaceErrors checks to make sure that misordered, unmatched or
// unclosed replace directives return an error.
func TestScrubReplaceErrors(t *testing.T) {
	tests := []struct {
		name string
		src  string
	}{
		{"replace-with without begin", "a\n// #replace-with\nb\n"},
		{"end without begin", "a\n// #end-replace\n"},
		{"end without replace-with", "// #begin-replace-ifndef services/driver/ControlService/Kill\na\n// #end-replace\n"},
		{"duplicate replace-with", "// #begin-replace-ifndef services/driver/ControlService/Kill\na\n// #replace-with\nb\n// #replace-with\nc\n// #end-replace\n"},
		{"unclosed after begin", "// #begin-replace-ifndef services/driver/ControlService/Kill\na\n"},
		{"unclosed after replace-with", "// #begin-replace-ifndef services/driver/ControlService/Kill\na\n// #replace-with\nb\n"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cap := newCapFile(t, "services/driver/ControlService/Kill")
			if _, _, err := preprocess.Scrub(cap.Supports, []byte(tt.src)); err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

// TestScrubReplaceTagLinesAlwaysRemoved checks to make sure that all three
// replace directive lines are stripped whether or not the block fires.
func TestScrubReplaceTagLinesAlwaysRemoved(t *testing.T) {
	src := strings.Join([]string{
		"// #begin-replace-ifndef services/driver/ControlService/Kill",
		"original",
		"// #replace-with",
		"replacement",
		"// #end-replace",
		"",
	}, "\n")
	for _, unsupported := range [][]string{nil, {"services/driver/ControlService/Kill"}} {
		cap := newCapFile(t, unsupported...)
		out, _, err := preprocess.Scrub(cap.Supports, []byte(src))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if strings.Contains(string(out), "#") {
			t.Errorf("directive line still present in output (unsupported=%v):\n%s", unsupported, out)
		}
	}
}
