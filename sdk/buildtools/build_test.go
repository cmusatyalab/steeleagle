package buildtools

import (
	"debug/elf"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"testing"
)

// Module paths the tests build against.
const (
	sdkModPath = "github.com/cmusatyalab/steeleagle/sdk"
	apiModPath = "github.com/cmusatyalab/steeleagle/api/go"
)

// testGeoJson holds one polygon named area.
const testGeoJson = `{"type":"FeatureCollection","features":[
	{"type":"Feature","properties":{"name":"area"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}}
]}`

// testManifest declares two roles, one squawk and one detection engine.
const testManifest = `
[info]
name = "test"
version = "0.1.0"
roles = ["Patroller", "tracker"]
squawks = ["found"]

[[engines]]
name = "yolo"
result = "messages/result/DetectionResult"
`

// testFlow feeds the front camera to yolo, the flow's only engine.
const testFlow = `
[[producers]]
name = "front"

[[engines]]
name = "yolo"
location = "local"

[[edges]]
from = "front"
to = "yolo"
`

// repoRoot returns the absolute path of the root of the steeleagle
// repository, which holds the SDK's module in sdk/ and the API's in
// api/go/.
func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	// file is <root>/sdk/buildtools/build_test.go
	root, err := filepath.Abs(filepath.Join(filepath.Dir(file), "..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	return root
}

// skipIfShort skips tests that build the SDK in -short mode.
func skipIfShort(t *testing.T) {
	t.Helper()
	if testing.Short() {
		t.Skip("skipping SDK build in -short mode")
	}
}

// requireErrorContaining fails the test unless errs has an error whose
// message contains substr.
func requireErrorContaining(t *testing.T, errs []*CompileError, substr string) {
	t.Helper()
	for _, e := range errs {
		if strings.Contains(e.Error(), substr) {
			return
		}
	}
	t.Fatalf("errors = %v, want one containing %q", errs, substr)
}

// mustGo runs the go tool in dir, failing the test if it fails.
func mustGo(t *testing.T, dir string, args ...string) {
	t.Helper()
	if _, err := goCmd(dir, nil, args...); err != nil {
		t.Fatal(err)
	}
}

// sdkApp writes a Go module whose main package prints the generated const
// params.Polygon_area, then "kill" unless the cap file scrubs it. The
// module resolves the steeleagle modules to this checkout. It returns the
// module's directory.
func sdkApp(t *testing.T) string {
	t.Helper()
	root := repoRoot(t)
	dir := t.TempDir()
	src := `package main

import (
	"fmt"

	"` + paramsPkgPath + `"
)

func main() {
	fmt.Println(params.Polygon_area)
	// #exclude-ifndef services/driver/ControlService/Kill
	fmt.Println("kill")
}
`
	if err := os.WriteFile(filepath.Join(dir, "main.go"), []byte(src), 0o644); err != nil {
		t.Fatal(err)
	}
	mustGo(t, dir, "mod", "init", "example.com/app")
	mustGo(t, dir, "mod", "edit",
		"-require="+sdkModPath+"@v0.0.0", "-replace="+sdkModPath+"="+filepath.Join(root, "sdk"),
		"-require="+apiModPath+"@v0.0.0", "-replace="+apiModPath+"="+filepath.Join(root, "api", "go"),
	)
	// go get raises the module's go version to what the checkout requires
	mustGo(t, dir, "get", sdkModPath+"@v0.0.0")
	mustGo(t, dir, "mod", "tidy")
	return dir
}

// requireStatic fails the test unless the binary at path is statically
// linked, which it is only when built with cgo disabled.
func requireStatic(t *testing.T, path string) {
	t.Helper()
	f, err := elf.Open(path)
	if err != nil {
		t.Fatalf("opening built binary: %v", err)
	}
	defer f.Close()
	libs, err := f.ImportedLibraries()
	if err != nil {
		t.Fatal(err)
	}
	if len(libs) > 0 {
		t.Errorf("binary links %v, want a static binary", libs)
	}
}

// run runs the binary at path and returns its output.
func run(t *testing.T, path string) string {
	t.Helper()
	out, err := exec.Command(path).Output()
	if err != nil {
		t.Fatalf("running %s: %v", path, err)
	}
	return string(out)
}

// TestBuildSdk builds a Go module with consts generated from the GeoJSON,
// and checks the binary runs, unscrubbed without a cap file.
func TestBuildSdk(t *testing.T) {
	skipIfShort(t)
	dir := sdkApp(t)
	before, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(t.TempDir(), "app")
	if errs := BuildSdk(dir, nil, WithGeoJson([]byte(testGeoJson)), WithOutputFile(out)); len(errs) > 0 {
		t.Fatalf("BuildSdk() errors = %v", errs)
	}
	requireStatic(t, out)
	if got, want := run(t, out), "area\nkill\n"; got != want {
		t.Errorf("app printed %q, want %q", got, want)
	}
	// Nothing, the overlay included, may be left in the module
	after, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(after) != len(before) {
		t.Errorf("module had %d entries before the build, %d after", len(before), len(after))
	}
}

// TestBuildSdkScrubsLocalModule checks that the module being built is
// scrubbed according to the cap file, not just the SDK.
func TestBuildSdkScrubsLocalModule(t *testing.T) {
	skipIfShort(t)
	dir := sdkApp(t)
	out := filepath.Join(t.TempDir(), "app")
	cap := "[driver.unsupported]\nmethods = [\"services/driver/ControlService/Kill\"]\n"
	errs := BuildSdk(dir, []string{"."},
		WithPlugin([]byte(cap)), WithGeoJson([]byte(testGeoJson)), WithOutputFile(out))
	if len(errs) > 0 {
		t.Fatalf("BuildSdk() errors = %v", errs)
	}
	if got, want := run(t, out), "area\n"; got != want {
		t.Errorf("app printed %q, want %q", got, want)
	}
}

// TestBuildSdkErrors checks that BuildSdk reports a bad cap file, bad
// GeoJSON, a directory outside any module, and a failing build.
func TestBuildSdkErrors(t *testing.T) {
	requireErrorContaining(t, BuildSdk(t.TempDir(), nil, WithPlugin([]byte("[[[\n"))), "toml")
	if errs := BuildSdk(t.TempDir(), nil, WithGeoJson([]byte("{"))); len(errs) == 0 {
		t.Error("BuildSdk() with invalid GeoJSON succeeded")
	}
	requireErrorContaining(t, BuildSdk(t.TempDir(), nil), "go.mod file not found")
	skipIfShort(t)
	dir := sdkApp(t)
	// Without the GeoJSON, params.Polygon_area isn't generated
	requireErrorContaining(t, BuildSdk(dir, nil), "undefined: params.Polygon_area")
}

// TestOverlayConfig checks that OverlayConfig generates cap file cameras,
// manifest roles and squawks, flow engines and GeoJSON features into the params
// package, and overlays the SDK's module with the cap file's support.
func TestOverlayConfig(t *testing.T) {
	cap := "[driver.unsupported]\nmethods = [\"services/driver/ControlService/Kill\"]\n" +
		"[[driver.cameras]]\nname = \"front\"\n[[driver.cameras]]\nname = \"down\"\n"
	c, errs := NewConfig(WithPlugin([]byte(cap)), WithManifest([]byte(testManifest)),
		WithFlow([]byte(testFlow)), WithGeoJson([]byte(testGeoJson)))
	if len(errs) > 0 {
		t.Fatalf("NewConfig() errors = %v", errs)
	}
	cfg, errs := c.OverlayConfig()
	if len(errs) > 0 {
		t.Fatalf("OverlayConfig() errors = %v", errs)
	}
	types := cfg.Consts[paramsPkgPath]
	if len(cfg.Consts) != 1 || types == nil {
		t.Fatalf("Consts = %v, want constants for %s only", cfg.Consts, paramsPkgPath)
	}
	want := map[string]string{
		"Camera":          "front down",
		"Role":            "Patroller tracker",
		"Squawk":          "found",
		"DetectionEngine": "yolo",
		"Polygon":         "area",
	}
	for typeName, names := range want {
		if got := strings.Join(types[typeName], " "); got != names {
			t.Errorf("%s consts = %q, want %q", typeName, got, names)
		}
	}
	if !slices.Equal(cfg.ModulesOf, []string{sdkPkgPath}) {
		t.Errorf("ModulesOf = %v, want the SDK", cfg.ModulesOf)
	}
	if cfg.Supports == nil || cfg.Supports("services/driver/ControlService/Kill") {
		t.Errorf("Supports doesn't follow the cap file")
	}

	empty, _ := NewConfig()
	if cfg, errs := empty.OverlayConfig(); len(errs) > 0 || cfg.Supports != nil {
		t.Errorf("OverlayConfig() with no files = %+v, %v; want no errors and no Supports", cfg, errs)
	}
}

// TestOverlayConfigLeafEngines checks that only the flow's leaf engines get
// consts, typed by the manifest, and that no engine gets one without a flow.
func TestOverlayConfigLeafEngines(t *testing.T) {
	manifest := "[[engines]]\nname = \"yolo\"\nresult = \"messages/result/DetectionResult\"\n" +
		"[[engines]]\nname = \"pre\"\nresult = \"messages/result/GenericResult\"\n" +
		"[[engines]]\nname = \"unused\"\nresult = \"messages/result/PositionResult\"\n"
	flow := "[[producers]]\nname = \"front\"\n" +
		"[[engines]]\nname = \"pre\"\n[[engines]]\nname = \"yolo\"\n" +
		"[[edges]]\nfrom = \"front\"\nto = \"pre\"\n[[edges]]\nfrom = \"pre\"\nto = \"yolo\"\n"
	c, errs := NewConfig(WithManifest([]byte(manifest)), WithFlow([]byte(flow)))
	if len(errs) > 0 {
		t.Fatalf("NewConfig() errors = %v", errs)
	}
	cfg, errs := c.OverlayConfig()
	if len(errs) > 0 {
		t.Fatalf("OverlayConfig() errors = %v", errs)
	}
	types := cfg.Consts[paramsPkgPath]
	want := map[string]string{"DetectionEngine": "yolo", "GenericEngine": "", "PositionEngine": ""}
	for typeName, names := range want {
		if got := strings.Join(types[typeName], " "); got != names {
			t.Errorf("%s consts = %q, want %q", typeName, got, names)
		}
	}

	c, _ = NewConfig(WithManifest([]byte(manifest)))
	cfg, errs = c.OverlayConfig()
	if len(errs) > 0 {
		t.Fatalf("OverlayConfig() without a flow errors = %v", errs)
	}
	for _, typeName := range []string{"DetectionEngine", "GenericEngine", "PositionEngine"} {
		if got := cfg.Consts[paramsPkgPath][typeName]; len(got) > 0 {
			t.Errorf("%s consts without a flow = %v, want none", typeName, got)
		}
	}
}

// TestOverlayConfigUndeclaredFlowEngine checks that every engine of the
// flow, leaf or not, must be declared in the manifest.
func TestOverlayConfigUndeclaredFlowEngine(t *testing.T) {
	flow := "[[engines]]\nname = \"pre\"\n[[engines]]\nname = \"yolo\"\n" +
		"[[edges]]\nfrom = \"pre\"\nto = \"yolo\"\n"
	for _, manifest := range []string{"", testManifest} {
		c, errs := NewConfig(WithManifest([]byte(manifest)), WithFlow([]byte(flow)))
		if len(errs) > 0 {
			t.Fatalf("NewConfig() errors = %v", errs)
		}
		_, errs = c.OverlayConfig()
		requireErrorContaining(t, errs, `flow engine "pre" is not declared in the manifest`)
	}
}

// TestOverlayConfigErrors checks that malformed and duplicate constants
// are reported.
func TestOverlayConfigErrors(t *testing.T) {
	tests := map[string]string{
		"engine yolo has malformed result":      "[[engines]]\nname = \"yolo\"\nresult = \"messages/result/\"\n",
		`role "a" is declared more than once`:   "[info]\nroles = [\"a\", \"a\"]\n",
		`squawk "s" is declared more than once`: "[info]\nsquawks = [\"s\", \"s\"]\n",
		`engine "yolo" is declared more than once`: "[[engines]]\nname = \"yolo\"\nresult = \"messages/result/DetectionResult\"\n" +
			"[[engines]]\nname = \"yolo\"\nresult = \"messages/result/GenericResult\"\n",
	}
	for want, manifest := range tests {
		c, errs := NewConfig(WithManifest([]byte(manifest)))
		if len(errs) > 0 {
			t.Fatalf("NewConfig() errors = %v", errs)
		}
		_, errs = c.OverlayConfig()
		requireErrorContaining(t, errs, want)
	}
	c, _ := NewConfig(WithPlugin([]byte("[driver]\n[[driver.cameras]]\nname = \"front\"\n[[driver.cameras]]\nname = \"front\"\n")))
	_, errs := c.OverlayConfig()
	requireErrorContaining(t, errs, `camera "front" is declared more than once`)
	c, _ = NewConfig(WithGeoJson([]byte(`{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[0,0]}}]}`)))
	_, errs = c.OverlayConfig()
	requireErrorContaining(t, errs, "has no name property")
}

// TestNewConfigErrors checks that unparseable cap, manifest and flow files
// are reported.
func TestNewConfigErrors(t *testing.T) {
	if _, errs := NewConfig(WithPlugin([]byte("[[[\n"))); len(errs) == 0 {
		t.Error("NewConfig() with a bad cap file succeeded")
	}
	if _, errs := NewConfig(WithManifest([]byte("[[[\n"))); len(errs) == 0 {
		t.Error("NewConfig() with a bad manifest succeeded")
	}
	if _, errs := NewConfig(WithFlow([]byte("[[[\n"))); len(errs) == 0 {
		t.Error("NewConfig() with a bad flow file succeeded")
	}
}

// TestNewConfigParsesFlow checks that a flow file is parsed and kept
// verbatim.
func TestNewConfigParsesFlow(t *testing.T) {
	flow := "[[producers]]\nname = \"front\"\n"
	c, errs := NewConfig(WithFlow([]byte(flow)))
	if len(errs) > 0 {
		t.Fatalf("NewConfig() errors = %v", errs)
	}
	if c.Flow == nil || len(c.Flow.Producers) != 1 || c.Flow.Producers[0].Name != "front" {
		t.Errorf("Flow = %+v, want one producer named front", c.Flow)
	}
	if string(c.FlowToml) != flow {
		t.Errorf("FlowToml = %q, want %q", c.FlowToml, flow)
	}
}
