package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
)

// skipIfShort skips tests that load or build the SDK, which take seconds
// to minutes depending on the Go build cache.
func skipIfShort(t *testing.T) {
	t.Helper()
	if testing.Short() {
		t.Skip("skipping SDK load/build in -short mode")
	}
}

func TestAstJsonRoundTrips(t *testing.T) {
	for _, path := range []string{"testdata/patrol.test.dsl", "testdata/values.test.dsl"} {
		t.Run(path, func(t *testing.T) {
			ast, err := parser.ParseFromFile(path)
			if err != nil {
				t.Fatalf("ParseFromFile: %v", err)
			}
			want, err := astJson(ast)
			if err != nil {
				t.Fatalf("astJson: %v", err)
			}
			back, err := parser.ParseFromJson(want)
			if err != nil {
				t.Fatalf("ParseFromJson(astJson(ast)): %v\n%s", err, want)
			}
			got, err := astJson(back)
			if err != nil {
				t.Fatalf("astJson(back): %v", err)
			}
			if !bytes.Equal(got, want) {
				t.Errorf("round trip changed the mission:\n got %s\nwant %s", got, want)
			}
		})
	}
}

func TestAstJsonOmitsPositionsAndUnquotesStrings(t *testing.T) {
	ast, err := parser.ParseFromFile("testdata/values.test.dsl")
	if err != nil {
		t.Fatal(err)
	}
	out, err := astJson(ast)
	if err != nil {
		t.Fatal(err)
	}
	s := string(out)
	for _, unwanted := range []string{`"Pos"`, "null"} {
		if strings.Contains(s, unwanted) {
			t.Errorf("astJson output contains %s: %s", unwanted, s)
		}
	}
	for _, wanted := range []string{`"String":"x"`, `"String":"hi"`, `"Override":"../.."`, `"Version":"v4.0-beta"`, `"Int":5`, `"Ident":"down"`} {
		if !strings.Contains(s, wanted) {
			t.Errorf("astJson output lacks %s: %s", wanted, s)
		}
	}
}

func TestFormatErrorJson(t *testing.T) {
	e := &buildtools.CompileError{Err: errors.New(`bad "x"`), File: "m.json", Decl: "patrol", LineNo: 3}
	var got map[string]any
	if err := json.Unmarshal([]byte(formatError(e, "json")), &got); err != nil {
		t.Fatalf("formatError json output isn't JSON: %v", err)
	}
	want := map[string]any{"file": "m.json", "decl": "patrol", "line": float64(3), "message": `bad "x"`}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("formatError json = %v, want %v", got, want)
	}
}

func TestFormatErrorText(t *testing.T) {
	e := &buildtools.CompileError{Err: errors.New("bad"), File: "m.dsl", LineNo: 3}
	if got := formatError(e, "text"); got != "m.dsl:3: bad" {
		t.Errorf("formatError text = %q", got)
	}
}

func TestPrintParse(t *testing.T) {
	var buf bytes.Buffer
	if errs := printParse([]string{"testdata/patrol.test.dsl"}, &buf); len(errs) > 0 {
		t.Fatalf("printParse: %v", errs)
	}
	ast, err := parser.ParseFromJson(bytes.TrimSpace(buf.Bytes()))
	if err != nil {
		t.Fatalf("printParse output doesn't decode: %v", err)
	}
	if ast.Mission.Start != "takeoff" || ast.Role.Name != "Patroller" {
		t.Errorf("decoded mission start=%q role=%q", ast.Mission.Start, ast.Role.Name)
	}
}

func TestPrintParseReportsSyntaxErrors(t *testing.T) {
	bad := filepath.Join(t.TempDir(), "bad.dsl")
	if err := os.WriteFile(bad, []byte("Actions:\n    actions.Land land(\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	var buf bytes.Buffer
	if errs := printParse([]string{bad}, &buf); len(errs) == 0 {
		t.Fatal("printParse accepted a syntax error")
	}
}

func TestCompileDslJson(t *testing.T) {
	skipIfShort(t)
	out := filepath.Join(t.TempDir(), "mission.dslb")
	errs := compileDsl([]string{"-json", "-geojson", "testdata/poly.test.geojson", "-o", out, "testdata/patrol.test.json"})
	if len(errs) > 0 {
		t.Fatalf("compileDsl: %v", errs)
	}
	data, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasPrefix(data, []byte("\x7fELF")) {
		t.Errorf("compiled mission isn't an ELF binary")
	}
}

func TestCompileDslJsonReportsDecl(t *testing.T) {
	skipIfShort(t)
	out := filepath.Join(t.TempDir(), "mission.dslb")
	errs := compileDsl([]string{"-json", "-geojson", "testdata/poly.test.geojson", "-o", out, "testdata/broken.test.json"})
	for _, e := range errs {
		if e.Decl == "patrol" && strings.Contains(e.Error(), "has no field Altitud") {
			return
		}
	}
	t.Errorf("want an error on decl patrol about Altitud, got %v", errs)
}

func TestPrintSchema(t *testing.T) {
	skipIfShort(t)
	var buf bytes.Buffer
	errs := printSchema([]string{"-json", "-geojson", "testdata/poly.test.geojson", "testdata/header.test.json"}, &buf)
	if len(errs) > 0 {
		t.Fatalf("printSchema: %v", errs)
	}
	var reg struct {
		Actions map[string]json.RawMessage `json:"actions"`
		Enums   map[string]struct {
			Fields []struct {
				Name string `json:"name"`
			} `json:"fields"`
		} `json:"enums"`
	}
	if err := json.Unmarshal(buf.Bytes(), &reg); err != nil {
		t.Fatalf("schema output isn't JSON: %v", err)
	}
	if _, ok := reg.Actions["actions.Patrol"]; !ok {
		t.Errorf("schema lacks actions.Patrol")
	}
	polygons := reg.Enums["params.Polygon"].Fields
	if len(polygons) != 1 || polygons[0].Name != "Polygon_Poly" {
		t.Errorf("params.Polygon constants = %v, want [Polygon_Poly]", polygons)
	}
}
