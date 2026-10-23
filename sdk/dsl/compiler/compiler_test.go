package compiler

import (
	"debug/elf"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/buildtools"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/parser"
	"golang.org/x/mod/module"
	modzip "golang.org/x/mod/zip"
)

// Module and package paths the end-to-end tests compile against.
const (
	apiModPath    = "github.com/cmusatyalab/steeleagle/api/go"
	dslPkgPath    = "github.com/cmusatyalab/steeleagle/sdk/dsl"
	paramsPkgPath = "github.com/cmusatyalab/steeleagle/sdk/params"
	actionsPkg    = "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
)

// testManifest declares two roles, two squawks and one detection engine.
const testManifest = `
[info]
name = "test"
version = "0.1.0"
roles = ["Patroller", "tracker"]
squawks = ["found", "Found"]

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

// flowOf returns a flow of the single engine name.
func flowOf(name string) []byte {
	return []byte("[[engines]]\nname = \"" + name + "\"\nlocation = \"local\"\n")
}

// testGeoJson holds one polygon and one line string with lowercase names.
const testGeoJson = `{
	"type": "FeatureCollection",
	"features": [
		{"type":"Feature","properties":{"name":"area"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}},
		{"type":"Feature","properties":{"name":"path"},"geometry":{"type":"LineString","coordinates":[[0,0],[1,1]]}}
	]
}`

// testMissionBody takes off and lands, using no generated consts.
const testMissionBody = `Actions:
    actions.TakeOff takeoff()
    actions.Land land()
Mission:
Start takeoff
During takeoff:
    done -> land
`

// repoRoot returns the root of the steeleagle repository, which holds the
// SDK's module in sdk/ and the API's in api/go/.
func repoRoot(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	// file is <root>/sdk/dsl/compiler/compiler_test.go
	return filepath.Join(filepath.Dir(file), "..", "..", "..")
}

// skipIfShort skips end-to-end tests in -short mode, since each one
// type-checks and builds the SDK.
func skipIfShort(t *testing.T) {
	t.Helper()
	if testing.Short() {
		t.Skip("skipping end-to-end compile in -short mode")
	}
}

// modulesStanza returns a Modules stanza that resolves the steeleagle
// modules to the checkout at root, so the end-to-end tests compile the
// working tree. root may be relative to the mission file.
func modulesStanza(root string) string {
	return "Modules:\n" +
		"    \"" + sdkModPath + "\" => \"" + filepath.Join(root, "sdk") + "\"\n" +
		"    \"" + apiModPath + "\" => \"" + filepath.Join(root, "api", "go") + "\"\n"
}

// importsStanza returns an Imports stanza importing paths.
func importsStanza(paths ...string) string {
	s := "Imports:\n"
	for _, p := range paths {
		s += "    \"" + p + "\"\n"
	}
	return s
}

// writeMission writes src to a mission file in dir and returns its path.
func writeMission(t *testing.T, dir, src string) string {
	t.Helper()
	path := filepath.Join(dir, "m.dsl")
	if err := os.WriteFile(path, []byte(src), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

// linkedMission writes a mission file whose Modules stanza points at this
// checkout by a path relative to the mission file, followed by imports of
// paths and body, and returns its path.
func linkedMission(t *testing.T, body string, paths ...string) string {
	t.Helper()
	dir := t.TempDir()
	rel, err := filepath.Rel(dir, repoRoot(t))
	if err != nil {
		t.Fatal(err)
	}
	return writeMission(t, dir, modulesStanza(rel)+importsStanza(paths...)+body)
}

// newTestWorkspace returns a fresh workspace with the extra environment
// env, closed when the test ends.
func newTestWorkspace(t *testing.T, env ...string) *Workspace {
	t.Helper()
	w, err := NewWorkspace(env)
	if err != nil {
		t.Fatalf("NewWorkspace() error = %v", err)
	}
	t.Cleanup(w.Close)
	return w
}

// requireErrorContaining fails the test unless errs has an error whose
// message contains substr.
func requireErrorContaining(t *testing.T, errs []*buildtools.CompileError, substr string) {
	t.Helper()
	for _, e := range errs {
		if strings.Contains(e.Error(), substr) {
			return
		}
	}
	t.Fatalf("errors = %v, want one containing %q", errs, substr)
}

// registryJson is the subset of the registry JSON returned by Load that
// the tests inspect.
type registryJson struct {
	Actions map[string]json.RawMessage `json:"actions"`
	Enums   map[string]struct {
		Fields []struct {
			Name string `json:"name"`
		} `json:"fields"`
	} `json:"enums"`
}

// decodeRegistry decodes the registry JSON returned by Load.
func decodeRegistry(t *testing.T, data []byte) registryJson {
	t.Helper()
	var reg registryJson
	if err := json.Unmarshal(data, &reg); err != nil {
		t.Fatalf("unmarshalling registry JSON: %v", err)
	}
	return reg
}

// enumConsts returns the const names of the enum named name in the
// registry JSON returned by Load.
func enumConsts(t *testing.T, data []byte, name string) map[string]bool {
	t.Helper()
	enum, ok := decodeRegistry(t, data).Enums[name]
	if !ok {
		t.Fatalf("enum %s missing from registry JSON:\n%s", name, data)
	}
	consts := map[string]bool{}
	for _, f := range enum.Fields {
		consts[f.Name] = true
	}
	return consts
}

// TestNewWorkspaceInitsModule checks that a new workspace is a temporary
// directory initialized as the "mission" module.
func TestNewWorkspaceInitsModule(t *testing.T) {
	w := newTestWorkspace(t)
	mod, err := os.ReadFile(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		t.Fatalf("reading go.mod: %v", err)
	}
	if !strings.HasPrefix(string(mod), "module mission\n") {
		t.Errorf("go.mod = %q, want module mission", mod)
	}
}

// TestParseMissionResolvesOverridesFromFile checks that relative override
// paths in a mission file are resolved against the file's directory, and
// that absolute paths and modules without overrides are left alone.
func TestParseMissionResolvesOverridesFromFile(t *testing.T) {
	dir := t.TempDir()
	sub := filepath.Join(dir, "missions")
	if err := os.Mkdir(sub, 0o755); err != nil {
		t.Fatal(err)
	}
	abs := filepath.Join(dir, "abs")
	path := writeMission(t, sub, `Modules:
    "example.com/rel" => "../local"
    "example.com/abs" => "`+abs+`"
    "example.com/none" v1.0.0
`)
	ast, err := parseMission(FromFile(path))
	if err != nil {
		t.Fatalf("parseMission() error = %v", err)
	}
	want := []string{filepath.Join(dir, "local"), abs, ""}
	for i, mod := range ast.Modules.Modules {
		if mod.Override != want[i] {
			t.Errorf("%s override = %q, want %q", mod.Path, mod.Override, want[i])
		}
	}
}

// TestParseMissionResolvesOverridesFromWorkingDir checks that relative
// override paths in DSL source text and in a JSON mission are resolved
// against the working directory.
func TestParseMissionResolvesOverridesFromWorkingDir(t *testing.T) {
	t.Chdir(t.TempDir())
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	sources := map[string]Source{
		"source": FromSource([]byte("Modules:\n    \"example.com/foo\" => \"local\"\n")),
		"json":   FromJson([]byte(`{"Modules": {"Modules": [{"Path": "example.com/foo", "Override": "local"}]}}`)),
	}
	for name, src := range sources {
		ast, err := parseMission(src)
		if err != nil {
			t.Fatalf("%s: parseMission() error = %v", name, err)
		}
		if got, want := ast.Modules.Modules[0].Override, filepath.Join(wd, "local"); got != want {
			t.Errorf("%s: override = %q, want %q", name, got, want)
		}
	}
}

// TestCompileParseErrors checks that a missing mission file, a syntax
// error in source text, malformed JSON and a nil Source are reported.
func TestCompileParseErrors(t *testing.T) {
	if errs := Compile(FromFile(filepath.Join(t.TempDir(), "missing.dsl"))); len(errs) == 0 {
		t.Error("Compile(missing file) errors = none, want one")
	}
	if errs := Compile(FromJson([]byte("{"))); len(errs) == 0 {
		t.Error("Compile(malformed JSON) errors = none, want one")
	}
	if errs := Compile(FromSource([]byte("Mission:\nStart\n"))); len(errs) == 0 {
		t.Error("Compile(source syntax error) errors = none, want one")
	}
	requireErrorContaining(t, Compile(nil), "no mission given")
}

// TestInstallModulesOverride checks that an overridden module is required
// at its version and replaced with its local directory in go.mod.
func TestInstallModulesOverride(t *testing.T) {
	w := newTestWorkspace(t)
	local := t.TempDir()
	if err := os.WriteFile(filepath.Join(local, "go.mod"), []byte("module example.com/foo\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	err := w.installModules([]*parser.ModuleSpec{{Path: "example.com/foo", Version: "v1.2.3", Override: local}})
	if err != nil {
		t.Fatalf("installModules() error = %v", err)
	}
	mod, err := os.ReadFile(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"example.com/foo v1.2.3", "example.com/foo => " + local} {
		if !strings.Contains(string(mod), want) {
			t.Errorf("go.mod missing %q:\n%s", want, mod)
		}
	}
}

// TestInstallModulesOverrideWithoutVersion checks that an overridden module
// with no version is required at a placeholder version go.mod accepts,
// including for a /vN module path, and that the caller's ModuleSpec is
// left unchanged.
func TestInstallModulesOverrideWithoutVersion(t *testing.T) {
	w := newTestWorkspace(t)
	mods := []*parser.ModuleSpec{
		{Path: "example.com/foo", Override: t.TempDir()},
		{Path: "example.com/bar/v3", Override: t.TempDir()},
	}
	for _, m := range mods {
		if err := os.WriteFile(filepath.Join(m.Override, "go.mod"), []byte("module "+m.Path+"\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if err := w.installModules(mods); err != nil {
		t.Fatalf("installModules() error = %v", err)
	}
	mod, err := os.ReadFile(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"example.com/foo v0.0.0", "example.com/bar/v3 v3.0.0"} {
		if !strings.Contains(string(mod), want) {
			t.Errorf("go.mod missing %q:\n%s", want, mod)
		}
	}
	for _, m := range mods {
		if m.Version != "" {
			t.Errorf("ModuleSpec %s Version = %q, want it left empty", m.Path, m.Version)
		}
	}
	// The module graph must still be readable by the go tool.
	if err := w.goCmd("list", "-m", "all"); err != nil {
		t.Errorf("go list -m all: %v", err)
	}
}

// TestInstallModulesGoError checks that a failing go command is reported
// with its output.
func TestInstallModulesGoError(t *testing.T) {
	w := newTestWorkspace(t)
	err := w.installModules([]*parser.ModuleSpec{{Path: "not a module path", Version: "v1.0.0", Override: t.TempDir()}})
	if err == nil {
		t.Fatal("installModules() error = nil, want one for an invalid module path")
	}
	if !strings.Contains(err.Error(), "go [mod edit") {
		t.Errorf("error = %v, want it to name the failing go command", err)
	}
}

// TestLoadInvalidGeoJson checks that malformed GeoJSON is reported by Load
// instead of producing an empty set of features.
func TestLoadInvalidGeoJson(t *testing.T) {
	path := writeMission(t, t.TempDir(), importsStanza(paramsPkgPath))
	_, errs := Load(FromFile(path), buildtools.WithGeoJson([]byte("not json")))
	if len(errs) == 0 {
		t.Fatal("Load() errors = none, want one for malformed GeoJSON")
	}
}

// TestLoadMalformedEngineResult checks that an engine whose result has no type
// name is reported before any packages are loaded.
func TestLoadMalformedEngineResult(t *testing.T) {
	path := writeMission(t, t.TempDir(), importsStanza(paramsPkgPath))
	for _, result := range []string{"", "messages/result/"} {
		manifest := "[[engines]]\nname = \"x\"\nresult = \"" + result + "\"\n"
		_, errs := Load(FromFile(path), buildtools.WithManifest([]byte(manifest)))
		requireErrorContaining(t, errs, "engine x has malformed result proto message id")
	}
}

// TestLoadUndeclaredEngineType checks that an engine whose output names a type
// params doesn't declare is reported.
func TestLoadUndeclaredEngineType(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, paramsPkgPath)
	manifest := "[[engines]]\nname = \"x\"\nresult = \"messages/result/BogusResult\"\n"
	_, errs := Load(FromFile(path), buildtools.WithManifest([]byte(manifest)), buildtools.WithFlow(flowOf("x")))
	requireErrorContaining(t, errs, `type "BogusEngine" is not declared`)
}

// TestLoadGeneratesConsts checks that Load declares a const per manifest
// role and squawk, flow engine, and GeoJSON feature, named <Type>_<name>,
// and returns them in the registry JSON.
func TestLoadGeneratesConsts(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, paramsPkgPath)
	out, errs := Load(FromFile(path), buildtools.WithManifest([]byte(testManifest)),
		buildtools.WithFlow([]byte(testFlow)), buildtools.WithGeoJson([]byte(testGeoJson)))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	want := map[string][]string{
		"params.Role":            {"Role_Patroller", "Role_tracker"},
		"params.Squawk":          {"Squawk_found", "Squawk_Found"},
		"params.DetectionEngine": {"DetectionEngine_yolo"},
		"params.Polygon":         {"Polygon_area"},
		"params.LineString":      {"LineString_path"},
	}
	for enum, names := range want {
		got := enumConsts(t, out, enum)
		if len(got) != len(names) {
			t.Errorf("%s consts = %v, want %v", enum, got, names)
		}
		for _, name := range names {
			if !got[name] {
				t.Errorf("%s: const %s missing (have %v)", enum, name, got)
			}
		}
	}
}

// TestLoadGeneratesQualifiedConsts checks that qualified engine names and
// camera names with slashes generate consts with underscores in their place.
func TestLoadGeneratesQualifiedConsts(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, paramsPkgPath)
	manifest := "[[engines]]\nname = \"host.yolo\"\nresult = \"messages/result/DetectionResult\"\n"
	cap := "[driver]\n[[driver.cameras]]\nname = \"front/left\"\n"
	out, errs := Load(FromFile(path), buildtools.WithPlugin([]byte(cap)),
		buildtools.WithManifest([]byte(manifest)), buildtools.WithFlow(flowOf("host.yolo")))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	if got := enumConsts(t, out, "params.DetectionEngine"); !got["DetectionEngine_host_yolo"] {
		t.Errorf("params.DetectionEngine consts = %v, want DetectionEngine_host_yolo", got)
	}
	if got := enumConsts(t, out, "params.Camera"); !got["Camera_front_left"] {
		t.Errorf("params.Camera consts = %v, want Camera_front_left", got)
	}
}

// TestLoadMergesEngineAndFeatureConsts checks that an engine and a GeoJSON
// feature generating consts of the same type are both kept.
func TestLoadMergesEngineAndFeatureConsts(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, paramsPkgPath)
	manifest := "[[engines]]\nname = \"zone\"\nresult = \"messages/result/Polygon\"\n"
	out, errs := Load(FromFile(path), buildtools.WithManifest([]byte(manifest)),
		buildtools.WithFlow(flowOf("zone")), buildtools.WithGeoJson([]byte(testGeoJson)))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	got := enumConsts(t, out, "params.Polygon")
	if !got["Polygon_zone"] || !got["Polygon_area"] {
		t.Errorf("params.Polygon consts = %v, want Polygon_zone and Polygon_area", got)
	}
}

// TestLoadOutsideModule checks that Load resolves packages from its
// workspace, not the process's working directory, by running it from a
// directory outside any Go module.
func TestLoadOutsideModule(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, paramsPkgPath)
	t.Chdir(t.TempDir())
	out, errs := Load(FromFile(path), buildtools.WithGeoJson([]byte(testGeoJson)))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	if got := enumConsts(t, out, "params.Polygon"); !got["Polygon_area"] {
		t.Errorf("params.Polygon consts = %v, want Polygon_area", got)
	}
}

// TestLoadGeneratesCameraConsts checks that Load declares a const per cap
// file camera, named Camera_<name>.
func TestLoadGeneratesCameraConsts(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, paramsPkgPath)
	cap := "[driver.supported]\nservices = [\"steeleagle_protocol/v1/services/driver/ControlService\", " +
		"\"steeleagle_protocol/v1/services/driver/StreamService\"]\n" +
		"[[driver.cameras]]\nname = \"front\"\n[[driver.cameras]]\nname = \"down\"\n"
	out, errs := Load(FromFile(path), buildtools.WithPlugin([]byte(cap)))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	got := enumConsts(t, out, "params.Camera")
	if len(got) != 2 || !got["Camera_front"] || !got["Camera_down"] {
		t.Errorf("params.Camera consts = %v, want Camera_front and Camera_down", got)
	}
}

// TestLoadCapScrubsSdk checks that loading still succeeds when a cap file
// marks a method unsupported, scrubbing it from the SDK.
func TestLoadCapScrubsSdk(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", dslPkgPath, actionsPkg)
	cap := "[driver.supported]\nservices = [\"steeleagle_protocol/v1/services/driver/ControlService\"]\n" +
		"[driver.unsupported]\nmethods = [\"steeleagle_protocol/v1/services/driver/ControlService/Kill\"]\n"
	out, errs := Load(FromFile(path), buildtools.WithPlugin([]byte(cap)))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	if _, ok := decodeRegistry(t, out).Actions["actions.TakeOff"]; !ok {
		t.Errorf("actions.TakeOff missing from registry after scrubbing")
	}
}

// TestCompileEndToEndJson compiles a JSON mission, and checks that a
// binary is produced.
func TestCompileEndToEndJson(t *testing.T) {
	skipIfShort(t)
	out := filepath.Join(t.TempDir(), "mission.bin")
	errs := Compile(FromJson(mustMissionJson(t)),
		buildtools.WithManifest([]byte(testManifest)), buildtools.WithGeoJson([]byte(testGeoJson)), buildtools.WithOutputFile(out))
	if len(errs) > 0 {
		t.Fatalf("Compile() errors = %v", errs)
	}
	requireStatic(t, out)
}

// requireStatic fails the test unless the binary at path is statically
// linked, which it is only when built with cgo disabled.
func requireStatic(t *testing.T, path string) {
	t.Helper()
	f, err := elf.Open(path)
	if err != nil {
		t.Fatalf("opening compiled binary: %v", err)
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

// TestCompileWithGeneratedConsts compiles a mission file that references a
// const generated from the GeoJSON, which only exists in the overlay, and
// whose modules are overridden by paths relative to the mission file. It
// doesn't import the dsl package, which is imported implicitly.
func TestCompileWithGeneratedConsts(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, `Actions:
    actions.Patrol patrol(Area=params.Polygon_area, Altitude=10.0)
Mission:
Start patrol
`, actionsPkg, paramsPkgPath)
	out := filepath.Join(t.TempDir(), "mission")
	if errs := Compile(FromFile(path), buildtools.WithGeoJson([]byte(testGeoJson)), buildtools.WithOutputFile(out)); len(errs) > 0 {
		t.Fatalf("Compile() errors = %v", errs)
	}
	if _, err := os.Stat(out); err != nil {
		t.Errorf("compiled binary missing: %v", err)
	}
}

// mustMissionJson returns the test mission, with its modules overridden by
// absolute paths to this checkout, parsed from its text form and
// re-encoded as JSON.
func mustMissionJson(t *testing.T) []byte {
	t.Helper()
	root, err := filepath.Abs(repoRoot(t))
	if err != nil {
		t.Fatal(err)
	}
	src := modulesStanza(root) + importsStanza(dslPkgPath, actionsPkg) + testMissionBody
	ast, err := parser.ParseFromFile(writeMission(t, t.TempDir(), src))
	if err != nil {
		t.Fatalf("ParseFromFile() error = %v", err)
	}
	out, err := json.Marshal(ast)
	if err != nil {
		t.Fatalf("marshalling AST: %v", err)
	}
	return out
}

// TestGoCmdReportsOutput checks that goCmd folds the go tool's output into
// its error.
func TestGoCmdReportsOutput(t *testing.T) {
	if _, err := exec.LookPath("go"); err != nil {
		t.Skip("go not installed")
	}
	w := &Workspace{Dir: t.TempDir()}
	err := w.goCmd("bogus-subcommand")
	if err == nil || !strings.Contains(err.Error(), "bogus-subcommand") {
		t.Errorf("goCmd() error = %v, want it to include go's output", err)
	}
}

// TestNewWorkspaceEnv checks that a workspace's environment is the
// defaults followed by the caller's, and that the caller's values override
// the defaults in the go commands it runs.
func TestNewWorkspaceEnv(t *testing.T) {
	w := newTestWorkspace(t, "GOARCH=arm64", "CGO_ENABLED=1")
	want := []string{"CGO_ENABLED=0", "GOARCH=arm64", "CGO_ENABLED=1"}
	if !slices.Equal(w.Env, want) {
		t.Errorf("Env = %v, want %v", w.Env, want)
	}
	cmd := exec.Command("go", "env", "CGO_ENABLED", "GOARCH")
	cmd.Dir = w.Dir
	cmd.Env = append(os.Environ(), w.Env...)
	out, err := cmd.Output()
	if err != nil {
		t.Fatal(err)
	}
	if got := strings.Fields(string(out)); !slices.Equal(got, []string{"1", "arm64"}) {
		t.Errorf("go env CGO_ENABLED GOARCH = %v, want [1 arm64]", got)
	}
}

// TestCompileWorkspaceError checks that a workspace that can't be created
// is reported instead of panicking, and that a mission's syntax errors are
// reported before a workspace is created.
func TestCompileWorkspaceError(t *testing.T) {
	t.Setenv("TMPDIR", filepath.Join(t.TempDir(), "missing"))
	if errs := Compile(FromSource([]byte(testMissionBody))); len(errs) == 0 {
		t.Error("Compile() errors = none, want one for the missing temp directory")
	}
	if _, errs := Load(FromSource([]byte(testMissionBody))); len(errs) == 0 {
		t.Error("Load() errors = none, want one for the missing temp directory")
	}
	errs := Compile(FromSource([]byte("Mission:\nStart\n")))
	if len(errs) != 1 || strings.Contains(errs[0].Error(), "missing") {
		t.Errorf("Compile(syntax error) errors = %v, want only the syntax error", errs)
	}
}

// TestLoadWithUserGoflags checks that a GOFLAGS in the workspace's
// environment doesn't stop the load from adding missing requirements.
func TestLoadWithUserGoflags(t *testing.T) {
	skipIfShort(t)
	w := newTestWorkspace(t, "GOFLAGS=-buildvcs=false")
	path := linkedMission(t, "", actionsPkg)
	if _, errs := w.Load(FromFile(path)); len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
}

// TestCompileCrossArch loads and then cross-compiles a mission in one
// workspace set up for an architecture other than the host's, and checks
// the binary is built for it.
func TestCompileCrossArch(t *testing.T) {
	skipIfShort(t)
	arch, machine := "arm64", elf.EM_AARCH64
	if runtime.GOARCH == "arm64" {
		arch, machine = "amd64", elf.EM_X86_64
	}
	w := newTestWorkspace(t, "GOOS=linux", "GOARCH="+arch)
	path := linkedMission(t, testMissionBody, actionsPkg)
	if _, errs := w.Load(FromFile(path)); len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	out := filepath.Join(t.TempDir(), "mission")
	if errs := w.Compile(FromFile(path), buildtools.WithOutputFile(out)); len(errs) > 0 {
		t.Fatalf("Compile() errors = %v", errs)
	}
	f, err := elf.Open(out)
	if err != nil {
		t.Fatalf("opening compiled binary: %v", err)
	}
	defer f.Close()
	if f.Machine != machine {
		t.Errorf("binary machine = %v, want %v", f.Machine, machine)
	}
}

// TestLoadReportsImportCollision checks that two imports under the same
// qualifier are reported at the later import's line in the mission file.
func TestLoadReportsImportCollision(t *testing.T) {
	skipIfShort(t)
	path := linkedMission(t, "", actionsPkg, paramsPkgPath)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	// Import params under the name actions already uses
	data = []byte(strings.Replace(string(data), `"`+paramsPkgPath+`"`, `actions "`+paramsPkgPath+`"`, 1))
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	_, errs := Load(FromFile(path))
	requireErrorContaining(t, errs, paramsPkgPath+" is imported as actions, which conflicts with "+actionsPkg)
	// The Modules stanza takes lines 1-3, then Imports: and actions, so
	// params is on line 6
	if errs[0].LineNo != 6 || errs[0].File != path {
		t.Errorf("error at %s:%d, want %s:6", errs[0].File, errs[0].LineNo, path)
	}
}

// TestLoadFromSource loads the types for a mission given as source text,
// with its modules overridden by absolute paths to this checkout.
func TestLoadFromSource(t *testing.T) {
	skipIfShort(t)
	root, err := filepath.Abs(repoRoot(t))
	if err != nil {
		t.Fatal(err)
	}
	src := modulesStanza(root) + importsStanza(actionsPkg) + testMissionBody
	out, errs := Load(FromSource([]byte(src)))
	if len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	if _, ok := decodeRegistry(t, out).Actions["actions.TakeOff"]; !ok {
		t.Errorf("actions.TakeOff missing from registry")
	}
}

// TestInstallModulesOverrideRaisesGoVersion checks that overriding a
// module that requires a newer Go than the workspace's go.mod raises the
// workspace's go version, which go mod edit alone doesn't do.
func TestInstallModulesOverrideRaisesGoVersion(t *testing.T) {
	w := newTestWorkspace(t)
	if err := w.goCmd("mod", "edit", "-go=1.21"); err != nil {
		t.Fatal(err)
	}
	local := t.TempDir()
	if err := os.WriteFile(filepath.Join(local, "go.mod"), []byte("module example.com/foo\n\ngo 1.22\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := w.installModules([]*parser.ModuleSpec{{Path: "example.com/foo", Override: local}}); err != nil {
		t.Fatalf("installModules() error = %v", err)
	}
	mod, err := os.ReadFile(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(mod), "\ngo 1.22") {
		t.Errorf("go.mod go version not raised to 1.22:\n%s", mod)
	}
}

// TestLoadResetsModule checks that each load starts from the go.mod
// NewWorkspace created, so a module installed by an earlier load is gone
// from go.mod afterwards unless the mission lists it again.
func TestLoadResetsModule(t *testing.T) {
	skipIfShort(t)
	w := newTestWorkspace(t)
	local := t.TempDir()
	if err := os.WriteFile(filepath.Join(local, "go.mod"), []byte("module example.com/foo\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := w.installModules([]*parser.ModuleSpec{{Path: "example.com/foo", Override: local}}); err != nil {
		t.Fatalf("installModules() error = %v", err)
	}
	if _, errs := w.Load(FromFile(linkedMission(t, "", actionsPkg))); len(errs) > 0 {
		t.Fatalf("Load() errors = %v", errs)
	}
	mod, err := os.ReadFile(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(mod), "example.com/foo") {
		t.Errorf("go.mod still has the earlier module:\n%s", mod)
	}
	if !strings.Contains(string(mod), sdkModPath) {
		t.Errorf("go.mod missing the mission's own module:\n%s", mod)
	}
}

// TestCompileRoleNotInManifest checks that a mission whose Role the
// manifest doesn't declare is reported at the Role, and that a declared
// Role is accepted.
func TestCompileRoleNotInManifest(t *testing.T) {
	src := "Role Scout:\n" + testMissionBody
	errs := Compile(FromSource([]byte(src)), buildtools.WithManifest([]byte(testManifest)))
	requireErrorContaining(t, errs, "role Scout is not declared in the manifest")
	if errs[0].LineNo != 1 {
		t.Errorf("error at line %d, want 1", errs[0].LineNo)
	}
	requireErrorContaining(t, Compile(FromSource([]byte(src))), "role Scout is not declared in the manifest")

	m, errs := newMission(FromSource([]byte("Role Patroller:\n"+testMissionBody)), []buildtools.Option{buildtools.WithManifest([]byte(testManifest))})
	if len(errs) > 0 || m.ast.Role.Name != "Patroller" {
		t.Errorf("newMission() with a declared role = %v, %v", m, errs)
	}
}

// proxyModule adds the module at path at version, with the files of dir,
// to the file-based module proxy at proxy.
func proxyModule(t *testing.T, proxy, path, version, dir string) {
	t.Helper()
	esc, err := module.EscapePath(path)
	if err != nil {
		t.Fatal(err)
	}
	vdir := filepath.Join(proxy, esc, "@v")
	if err := os.MkdirAll(vdir, 0o755); err != nil {
		t.Fatal(err)
	}
	mod, err := os.ReadFile(filepath.Join(dir, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	info := `{"Version":"` + version + `","Time":"2026-01-01T00:00:00Z"}`
	for name, data := range map[string][]byte{version + ".mod": mod, version + ".info": []byte(info)} {
		if err := os.WriteFile(filepath.Join(vdir, name), data, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	f, err := os.Create(filepath.Join(vdir, version+".zip"))
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := modzip.CreateFromDir(f, module.Version{Path: path, Version: version}, dir); err != nil {
		t.Fatalf("zipping %s@%s: %v", path, version, err)
	}
	list, err := os.OpenFile(filepath.Join(vdir, "list"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		t.Fatal(err)
	}
	defer list.Close()
	if _, err := list.WriteString(version + "\n"); err != nil {
		t.Fatal(err)
	}
}

// writeModule writes a module at path declaring go version goVersion, with
// one package file, into a new directory, and returns the directory.
func writeModule(t *testing.T, path, goVersion string) string {
	t.Helper()
	dir := t.TempDir()
	files := map[string]string{
		"go.mod": "module " + path + "\n\ngo " + goVersion + "\n",
		"pkg.go": "package " + filepath.Base(path) + "\n",
	}
	for name, src := range files {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(src), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

// proxyEnv returns a workspace environment that downloads modules from the
// file-based proxies, in order, into a fresh module cache, without
// checksum database lookups.
func proxyEnv(t *testing.T, proxies ...string) []string {
	t.Helper()
	urls := make([]string, len(proxies))
	for i, p := range proxies {
		urls[i] = "file://" + filepath.ToSlash(p)
	}
	return []string{
		"GOPROXY=" + strings.Join(urls, ","),
		"GOMODCACHE=" + t.TempDir(),
		"GOFLAGS=-modcacherw", // so the test can remove the module cache
		"GOSUMDB=off",
	}
}

// TestInstallModulesDownloadsOnlyListedModules checks that a module without
// an override is downloaded on its own, without the module at a prefix of
// its path, and copied out of the module cache into the workspace, which
// requires and replaces it with the copy and raises its go version.
func TestInstallModulesDownloadsOnlyListedModules(t *testing.T) {
	proxy := t.TempDir()
	proxyModule(t, proxy, "example.com/root", "v1.0.0", writeModule(t, "example.com/root", "1.21"))
	proxyModule(t, proxy, "example.com/root/lib", "v1.2.0", writeModule(t, "example.com/root/lib", "1.22"))
	env := proxyEnv(t, proxy)
	w := newTestWorkspace(t, env...)
	if err := w.goCmd("mod", "edit", "-go=1.21"); err != nil {
		t.Fatal(err)
	}

	if err := w.installModules([]*parser.ModuleSpec{{Path: "example.com/root/lib"}}); err != nil {
		t.Fatalf("installModules() error = %v", err)
	}

	modCache := strings.TrimPrefix(env[1], "GOMODCACHE=")
	if zips, _ := filepath.Glob(filepath.Join(modCache, "cache", "download", "example.com", "root", "@v", "*.zip")); len(zips) > 0 {
		t.Errorf("downloaded %v, want only the listed module", zips)
	}
	mod, err := os.ReadFile(filepath.Join(w.Dir, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	copyDir := "./" + modulesDir + "/example.com/root/lib@v1.2.0"
	for _, want := range []string{"example.com/root/lib v1.2.0", "example.com/root/lib => " + copyDir, "\ngo 1.22"} {
		if !strings.Contains(string(mod), want) {
			t.Errorf("go.mod missing %q:\n%s", want, mod)
		}
	}
	info, err := os.Stat(filepath.Join(w.Dir, copyDir, "pkg.go"))
	if err != nil {
		t.Fatalf("module not copied into the workspace: %v", err)
	}
	if info.Mode().Perm()&0o200 == 0 {
		t.Errorf("copied file mode = %v, want it writable", info.Mode())
	}
}

// TestInstallModulesDownloadError checks that a module the proxy doesn't
// have is reported with go's reason.
func TestInstallModulesDownloadError(t *testing.T) {
	w := newTestWorkspace(t, proxyEnv(t, t.TempDir())...)
	err := w.installModules([]*parser.ModuleSpec{{Path: "example.com/missing", Version: "v1.0.0"}})
	if err == nil || !strings.Contains(err.Error(), "downloading module example.com/missing@v1.0.0") {
		t.Errorf("installModules() error = %v, want one about downloading example.com/missing", err)
	}
}

// TestWithSdk checks that the SDK's module is added, unversioned, only when
// the mission doesn't list it.
func TestWithSdk(t *testing.T) {
	listed := []*parser.ModuleSpec{{Path: sdkModPath, Version: "v1.0.0"}}
	if got := withSdk(listed); len(got) != 1 || got[0].Version != "v1.0.0" {
		t.Errorf("withSdk() with the SDK listed = %v, want it unchanged", got)
	}
	other := []*parser.ModuleSpec{{Path: "example.com/foo"}}
	got := withSdk(other)
	if len(got) != 2 || got[1].Path != sdkModPath || got[1].Version != "" || len(other) != 1 {
		t.Errorf("withSdk() = %v, want example.com/foo then the SDK at no version, without changing the input", got)
	}
}

// TestCompileDownloadedSdk compiles a mission against this checkout's SDK
// published to a module proxy, rather than overridden by a local path. The
// mission uses a const generated from the GeoJSON, so it only builds if
// the overlay could rewrite the downloaded SDK's files.
func TestCompileDownloadedSdk(t *testing.T) {
	skipIfShort(t)
	root, err := filepath.Abs(repoRoot(t))
	if err != nil {
		t.Fatal(err)
	}
	proxy := t.TempDir()
	const version = "v0.0.0-eaglectest"
	proxyModule(t, proxy, sdkModPath, version, filepath.Join(root, "sdk"))
	realCache, err := exec.Command("go", "env", "GOMODCACHE").Output()
	if err != nil {
		t.Fatal(err)
	}
	// Every other module comes from the local module cache's downloads
	w := newTestWorkspace(t, proxyEnv(t, proxy, filepath.Join(strings.TrimSpace(string(realCache)), "cache", "download"))...)

	src := "Modules:\n" +
		"    \"" + sdkModPath + "\" " + version + "\n" +
		"    \"" + apiModPath + "\" => \"" + filepath.Join(root, "api", "go") + "\"\n" +
		importsStanza(actionsPkg, paramsPkgPath) + `Actions:
    actions.Patrol patrol(Area=params.Polygon_area, Altitude=10.0)
Mission:
Start patrol
`
	out := filepath.Join(t.TempDir(), "mission")
	if errs := w.Compile(FromSource([]byte(src)), buildtools.WithGeoJson([]byte(testGeoJson)), buildtools.WithOutputFile(out)); len(errs) > 0 {
		t.Fatalf("Compile() errors = %v", errs)
	}
	requireStatic(t, out)
}
