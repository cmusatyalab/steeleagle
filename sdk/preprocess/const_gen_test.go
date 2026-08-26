package preprocess

import "testing"

// TestGenerateConstsAppendsConsts checks that a single declared type with
// entries in types gets one string const per entry, named <Type><entry>
// and holding <entry> as its value.
func TestGenerateConstsAppendsConsts(t *testing.T) {
	src := "package sdk\n\ntype Engine string\n"
	out, err := GenerateConsts(map[string][]string{
		"Engine": {"ObjectDetection", "FaceRecognition"},
	}, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	consts := parseConsts(t, out)
	want := map[string]string{
		"EngineObjectDetection": "ObjectDetection",
		"EngineFaceRecognition": "FaceRecognition",
	}
	for name, value := range want {
		if got, ok := consts[name]; !ok {
			t.Errorf("const %s not found in output:\n%s", name, out)
		} else if got != value {
			t.Errorf("const %s = %q, want %q", name, got, value)
		}
	}
}

// TestGenerateConstsMultipleTypes checks that every declared type present
// in types gets its own const block, and that types are independent of
// each other.
func TestGenerateConstsMultipleTypes(t *testing.T) {
	src := "package dsl\n\ntype Role string\n\ntype Squawk string\n"
	out, err := GenerateConsts(map[string][]string{
		"Role":   {"Leader"},
		"Squawk": {"Rally", "Retreat"},
	}, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	consts := parseConsts(t, out)
	want := map[string]string{
		"RoleLeader":    "Leader",
		"SquawkRally":   "Rally",
		"SquawkRetreat": "Retreat",
	}
	for name, value := range want {
		if got, ok := consts[name]; !ok {
			t.Errorf("const %s not found in output:\n%s", name, out)
		} else if got != value {
			t.Errorf("const %s = %q, want %q", name, got, value)
		}
	}
}

// TestGenerateConstsUndeclaredKeyErrors checks that a types key with no
// matching `type <Name> string` declaration in src returns an error instead
// of being silently skipped.
func TestGenerateConstsUndeclaredKeyErrors(t *testing.T) {
	src := "package sdk\n\ntype Engine string\n"
	_, err := GenerateConsts(map[string][]string{
		"Engine": {"ObjectDetection"},
		"Role":   {"Leader"}, // not declared in src
	}, []byte(src))
	if err == nil {
		t.Fatal("expected error for type not declared in source, got nil")
	}
}

// TestGenerateConstsNonStringTypeErrors checks that a declared type whose
// underlying type isn't string (e.g. an int32 enum type) is never treated
// as a const type, even if it shares a name with a types key -- it's
// reported as an error rather than silently accepted.
func TestGenerateConstsNonStringTypeErrors(t *testing.T) {
	src := "package sdk\n\ntype Engine int32\n"
	_, err := GenerateConsts(map[string][]string{
		"Engine": {"ObjectDetection"},
	}, []byte(src))
	if err == nil {
		t.Fatal("expected error for type not declared as string, got nil")
	}
}

// TestGenerateConstsNoMatchingKeysUnchanged checks that src comes back
// unchanged (aside from gofmt) when types has no entry for any declared
// type.
func TestGenerateConstsNoMatchingKeysUnchanged(t *testing.T) {
	src := "package sdk\n\ntype Engine string\n"
	out, err := GenerateConsts(map[string][]string{}, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if string(out) != src {
		t.Errorf("out = %q, want unchanged %q", out, src)
	}
}

// TestGenerateConstsInvalidIdentifierErrors checks that an entry which
// would produce an invalid Go identifier once prefixed with its type name
// returns an error instead of emitting broken source.
func TestGenerateConstsInvalidIdentifierErrors(t *testing.T) {
	src := "package sdk\n\ntype Engine string\n"
	_, err := GenerateConsts(map[string][]string{
		"Engine": {"Object-Detection"},
	}, []byte(src))
	if err == nil {
		t.Fatal("expected error for entry that is not a valid Go identifier, got nil")
	}
}

// TestGenerateConstsInvalidSourceErrors checks that malformed source is
// reported as an error rather than panicking.
func TestGenerateConstsInvalidSourceErrors(t *testing.T) {
	_, err := GenerateConsts(map[string][]string{"Engine": {"Foo"}}, []byte("not valid go"))
	if err == nil {
		t.Fatal("expected error for invalid source, got nil")
	}
}
