package config

import "testing"

type tomlTestType struct {
	Name  string `toml:"name"`
	Count int    `toml:"count"`
}

// TestParseTomlFromBytes checks that TOML bytes are parsed into a new T.
func TestParseTomlFromBytes(t *testing.T) {
	v, err := ParseTomlFromBytes[tomlTestType]([]byte("name = \"a\"\ncount = 2\n"))
	if err != nil {
		t.Fatal(err)
	}
	if v.Name != "a" || v.Count != 2 {
		t.Errorf("got %+v, want {Name:a Count:2}", *v)
	}
}

// TestParseTomlFromBytesInvalid checks that malformed or mistyped TOML is
// rejected.
func TestParseTomlFromBytesInvalid(t *testing.T) {
	cases := map[string]string{
		"malformed":  "name = ",
		"wrong type": "count = \"two\"",
	}
	for label, content := range cases {
		if _, err := ParseTomlFromBytes[tomlTestType]([]byte(content)); err == nil {
			t.Errorf("%s: err = nil, want an error", label)
		}
	}
}

// TestParseTomlFromFilepathMissing checks that a missing file returns an error.
func TestParseTomlFromFilepathMissing(t *testing.T) {
	if _, err := ParseTomlFromFilepath[tomlTestType]("examples/does_not_exist.toml"); err == nil {
		t.Error("err = nil, want an error")
	}
}
