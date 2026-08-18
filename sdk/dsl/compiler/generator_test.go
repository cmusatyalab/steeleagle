package main

import (
	"os"
	"os/exec"
	"strings"
	"testing"
)

// missionSource is a DSL mission exercising every value shape Generate has
// to render: a plain literal field (Altitude), a Data declaration
// referenced later by Ident (home), an inline constructor inside an array
// (Waypoints), a functional option (Speed), and an enum-valued option
// (EndBehavior, referencing enums.ReturnToHomeEndBehaviorHover by bare
// identifier), plus both an event-driven and a "done" transition.
const missionSource = `Import:
    "github.com/cmusatyalab/steeleagle/sdk/dsl/compiler/testdata/fixture"
Data:
    fixture.Waypoint home(Alt = 10.5, Area = 'home')
Actions:
    TakeOff takeoff(Altitude = 3.0)
    ReturnToHome return_to_home(EndBehavior = ReturnToHomeEndBehaviorHover)
    fixture.Patrol patrol(Home = home, Waypoints = [fixture.Waypoint(Alt = 15.0, Area = 'poly')], Speed = 2.5)
Events:
    fixture.Timer timeout(Seconds = 5)
Mission:
    Start takeoff
    During takeoff:
        done -> patrol
    During patrol:
        timeout -> return_to_home
`

// linkMissionSource parses and links missionSource against this repo's own
// base packages plus the dsl/compiler/testdata/fixture package (which
// resolves locally, no network fetch needed), returning the resulting
// missionIR, the type registry's Alias map (as Generate expects), and a
// scratch workspace usable to build the generated output. The caller must
// invoke the returned cleanup.
func linkMissionSource(t *testing.T, source string) (ir *missionIR, aliases map[string]string, workspace string, cleanup func()) {
	t.Helper()

	mission, err := Parse(t.Name()+".dsl", strings.NewReader(source))
	if err != nil {
		t.Fatalf("Parse() = %v", err)
	}

	repoRoot, err := findRepoRoot()
	if err != nil {
		t.Fatalf("findRepoRoot() = %v", err)
	}

	workspace, cleanup, err = newWorkspace(repoRoot, nil)
	if err != nil {
		t.Fatalf("newWorkspace() = %v", err)
	}

	var imports []*ImportSpec
	if mission.Import != nil {
		imports = mission.Import.Imports
	}

	overlay, err := scrubPackages(imports, workspace, map[string]struct{}{})
	if err != nil {
		cleanup()
		t.Fatalf("scrubPackages() = %v", err)
	}

	registry, err := loadPackages(imports, workspace, overlay)
	if err != nil {
		cleanup()
		t.Fatalf("loadPackages() = %v", err)
	}

	ir, err = Link(mission, registry)
	if err != nil {
		cleanup()
		t.Fatalf("Link() = %v", err)
	}

	return ir, registry.Alias, workspace, cleanup
}

// TestGenerateProducesACompilingMain links missionSource against the real
// base packages and fixture package, generates main.go from the result,
// and builds it, proving the generator's output is valid Go that actually
// compiles against the types it references -- not just well-formed source.
func TestGenerateProducesACompilingMain(t *testing.T) {
	ir, aliases, workspace, cleanup := linkMissionSource(t, missionSource)
	defer cleanup()

	if err := Generate(ir, aliases, workspace); err != nil {
		t.Fatalf("Generate() = %v", err)
	}

	cmd := exec.Command("go", "build", "-o", os.DevNull, ".")
	cmd.Dir = workspace
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("generated main.go does not compile: %v\n%s", err, out)
	}
}
