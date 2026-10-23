package preprocess

import (
	"strings"
	"testing"
)

// TestGenerateConstsAppendsConsts checks that a single declared type with
// entries in types gets one string const per entry, named <Type>_<entry>
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
		"Engine_ObjectDetection": "ObjectDetection",
		"Engine_FaceRecognition": "FaceRecognition",
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
		"Role_Leader":    "Leader",
		"Squawk_Rally":   "Rally",
		"Squawk_Retreat": "Retreat",
	}
	for name, value := range want {
		if got, ok := consts[name]; !ok {
			t.Errorf("const %s not found in output:\n%s", name, out)
		} else if got != value {
			t.Errorf("const %s = %q, want %q", name, got, value)
		}
	}
}

// TestGenerateConstsRawNames checks that each const name is the type name,
// an underscore, then the entry verbatim, so entries differing only in case
// produce distinct consts, and that the value is the entry unchanged.
func TestGenerateConstsRawNames(t *testing.T) {
	src := "package sdk\n\ntype Polygon string\n"
	out, err := GenerateConsts(map[string][]string{
		"Polygon": {"area", "Area", "éclair"},
	}, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	consts := parseConsts(t, out)
	want := map[string]string{
		"Polygon_area":   "area",
		"Polygon_Area":   "Area",
		"Polygon_éclair": "éclair",
	}
	if len(consts) != len(want) {
		t.Errorf("got %d consts, want %d:\n%s", len(consts), len(want), out)
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

// TestGenerateConstsQualifiedNames checks that dots and slashes in entries,
// as in qualified engine names and camera names, become underscores in the
// const names, while the values keep them.
func TestGenerateConstsQualifiedNames(t *testing.T) {
	src := "package sdk\n\ntype Engine string\n\ntype Camera string\n"
	out, err := GenerateConsts(map[string][]string{
		"Engine": {"host.yolo", "remote.lab.yolo"},
		"Camera": {"front/left", "gimbal.cam/rgb"},
	}, []byte(src))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	consts := parseConsts(t, out)
	want := map[string]string{
		"Engine_host_yolo":       "host.yolo",
		"Engine_remote_lab_yolo": "remote.lab.yolo",
		"Camera_front_left":      "front/left",
		"Camera_gimbal_cam_rgb":  "gimbal.cam/rgb",
	}
	for name, value := range want {
		if got, ok := consts[name]; !ok {
			t.Errorf("const %s not found in output:\n%s", name, out)
		} else if got != value {
			t.Errorf("const %s = %q, want %q", name, got, value)
		}
	}
}

// TestGenerateConstsReplacedNameCollisionErrors checks that entries which
// only differ by a separator replaced with an underscore are an error,
// rather than emitting a duplicate const.
func TestGenerateConstsReplacedNameCollisionErrors(t *testing.T) {
	src := "package sdk\n\ntype Engine string\n"
	for _, names := range [][]string{{"host.yolo", "host_yolo"}, {"a/b", "a.b"}} {
		_, err := GenerateConsts(map[string][]string{"Engine": names}, []byte(src))
		if err == nil || !strings.Contains(err.Error(), "both generate const Engine_") {
			t.Errorf("GenerateConsts(%q) error = %v, want a collision error", names, err)
		}
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
