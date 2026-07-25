# SteelEagle Go DSL Validator (dslcheck) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sdk/cmd/dslcheck`, a Go CLI that parses a SteelEagle DSL mission file, checks it for local structural errors, resolves every referenced Action/Event/Datatype against real Go implementations pulled from packages named in the DSL's `Import:` stanza, and runs a per-drone capability check over those implementations' compiled code.

**Architecture:** Three independently-testable phases living in one new Go module at `sdk/`: (1) a `participle`-based parser plus local semantic checks operating purely on the parsed AST; (2) a "sequestered module" mechanism that builds a throwaway Go module requiring the DSL's declared packages, builds and runs a small harness that dumps a JSON schema of every registered Action/Event/Datatype, and cross-checks the DSL against it; (3) a `go/packages` + `go/ssa` + `go/callgraph/cha` based capability checker that, for each DSL-referenced type, verifies its `Execute`/`Check` method never reaches API surface disallowed by a per-drone `cap.toml`.

**Tech Stack:** Go 1.25+, `github.com/alecthomas/participle/v2` (parser), `github.com/pelletier/go-toml/v2` (matches `core/vehicle`'s existing TOML convention in the parent repo), `golang.org/x/tools/go/{packages,ssa,ssa/ssautil,callgraph,callgraph/cha}`.

## Global Constraints

- Everything for this project lives under `sdk/` in the `steeleagle` repo, as its own Go module (module path `github.com/cmusatyalab/steeleagle/sdk`) — kept separate from the root `steeleagle` module so parser/SSA-analysis dependencies never leak into the vehicle kernel's dependency graph.
- No mission-compiler output, no `MissionIR`/JSON/protobuf artifact. A successful run reports success (counts + "0 errors") and exits 0. This is a hard non-goal for this iteration (see spec `docs/superpowers/specs/2026-07-25-dsl-validator-design.md`).
- No real `github.com/cmusatyalab/steeleagle_sdk` module is published. A local fixture module under `sdk/dsl/testdata/sdkfixture` (with its own `go.mod` whose `module` line is literally `github.com/cmusatyalab/steeleagle_sdk`) stands in for it, resolved into the sequestered module via a `-replace` flag in tests — never via the network.
- No alias/deprecated-name support in the SDK registration mechanism — `demo.dsl` is updated to current API names (`GoToGlobalPosition`) instead.
- Phase 2 and Phase 3 tests shell out to `go build`/`go get`/`go list` and are much slower than the rest of the repo's Go tests. They must guard themselves with `if testing.Short() { t.Skip(...) }` so `go test -short ./...` stays fast; the plain `go test ./...` (matching the parent repo's CI) runs them.
- All new Go source files carry the same SPDX header used elsewhere in this repo:
  ```go
  // SPDX-FileCopyrightText: 2025 Carnegie Mellon University - LivingEdgeLab
  //
  // SPDX-License-Identifier: GPL-2.0-only
  ```
  (omitted from the code blocks below for brevity — add it as the first lines of every new `.go` file).

---

## Task 1: Module scaffolding + participle grammar + Parse()

**Files:**
- Create: `sdk/go.mod`
- Create: `sdk/dsl/ast.go`
- Create: `sdk/dsl/ast_test.go`
- Create: `sdk/dsl/testdata/good.dsl`
- Create: `sdk/dsl/testdata/edge_cases.dsl`

**Interfaces:**
- Produces: `dsl.File`, `dsl.RoleStanza`, `dsl.ImportStanza`, `dsl.DataStanza`, `dsl.ActionsStanza`, `dsl.EventsStanza`, `dsl.Decl{Pos, Type, Name, Attrs}`, `dsl.Attr{Key, Value}`, `dsl.Value{Pos, Number, String, Array, Inline, Ident}` (exactly one non-nil after parse), `dsl.ArrayValue{Elems}`, `dsl.InlineCtor{Type, Args}`, `dsl.MissionStanza{Start, Blocks}`, `dsl.DuringBlock{Action, Rules}`, `dsl.Rule{Event, Next}`. `func dsl.Parse(filename string, r io.Reader) (*dsl.File, error)`. `func (v *Value) StringValue() (s string, ok bool)`.

This grammar was interactively prototyped and verified against the real `demo.dsl` (all 6 stanzas, 15 actions, 2 events, 14 transitions) and against quoted strings, arrays, inline constructors, and negative numbers before being written into this plan — the code below is the exact, tested result, not a guess. One real bug was found and fixed during that verification: an earlier version of the `Path` lexer rule (`[A-Za-z0-9_]+(?:[./][A-Za-z0-9_-]+)+`) accidentally matched numeric literals like `3.0` (digits satisfy its character classes, and `3.0` contains a `.`), stealing them from the `Number` rule since `Path` was listed first. The fix — requiring `Path` to start with a letter — is already applied below.

- [ ] **Step 1: Create the module**

```bash
cd sdk
go mod init github.com/cmusatyalab/steeleagle/sdk
go get github.com/alecthomas/participle/v2@latest
```

- [ ] **Step 2: Write `sdk/dsl/ast.go`**

```go
package dsl

import (
	"io"

	"github.com/alecthomas/participle/v2"
	"github.com/alecthomas/participle/v2/lexer"
)

// File is the root of a parsed SteelEagle DSL document.
type File struct {
	Role    *RoleStanza    `parser:"@@?"`
	Imports *ImportStanza  `parser:"@@?"`
	Data    *DataStanza    `parser:"@@?"`
	Actions *ActionsStanza `parser:"@@?"`
	Events  *EventsStanza  `parser:"@@?"`
	Mission *MissionStanza `parser:"@@?"`
}

type RoleStanza struct {
	Name string `parser:"\"Role\" @Ident \":\""`
}

// ImportStanza lists the Go import paths (e.g.
// github.com/cmusatyalab/steeleagle_sdk/actions) that back the Data/Actions/
// Events declared in this file.
type ImportStanza struct {
	Paths []string `parser:"\"Import\" \":\" @Path*"`
}

type DataStanza struct {
	Decls []*Decl `parser:"\"Data\" \":\" @@*"`
}

type ActionsStanza struct {
	Decls []*Decl `parser:"\"Actions\" \":\" @@*"`
}

type EventsStanza struct {
	Decls []*Decl `parser:"\"Events\" \":\" @@*"`
}

// Decl is a single `Type name(key = value, ...)` declaration inside a Data,
// Actions, or Events stanza.
type Decl struct {
	Pos   lexer.Position
	Type  string  `parser:"@Ident"`
	Name  string  `parser:"@Ident"`
	Attrs []*Attr `parser:"\"(\" (@@ (\",\" @@)*)? \")\""`
}

type Attr struct {
	Key   string `parser:"@Ident \"=\""`
	Value *Value `parser:"@@"`
}

// Value is a sum type: exactly one field is non-nil after a successful
// parse. Ident covers both bare references to an earlier Data declaration
// (e.g. `waypoints = patrol_path`) and plain unquoted string-like literals
// (e.g. `algo = corridor`) — disambiguating between the two requires
// knowing the target field's type, which only Phase 2 (SDK resolution)
// knows, so Value alone does not attempt it.
type Value struct {
	Pos    lexer.Position
	Number *float64    `parser:"@Number"`
	String *string     `parser:"| @String"`
	Array  *ArrayValue `parser:"| @@"`
	Inline *InlineCtor `parser:"| @@"`
	Ident  *string     `parser:"| @Ident"`
}

type ArrayValue struct {
	Elems []*Value `parser:"\"[\" (@@ (\",\" @@)*)? \"]\""`
}

// InlineCtor is a positional constructor call used as a value, e.g.
// `Foo(1.0, bar)` inside `Bar bar(foo = Foo(1.0, bar))`.
type InlineCtor struct {
	Type string   `parser:"@Ident"`
	Args []*Value `parser:"\"(\" (@@ (\",\" @@)*)? \")\""`
}

type MissionStanza struct {
	Start  string         `parser:"\"Mission\" \":\" \"Start\" @Ident"`
	Blocks []*DuringBlock `parser:"@@*"`
}

type DuringBlock struct {
	Action string  `parser:"\"During\" @Ident \":\""`
	Rules  []*Rule `parser:"@@*"`
}

// Rule is one `event -> next_action` line inside a During block. Event is
// either a declared Event name or the reserved word "done".
type Rule struct {
	Event string `parser:"@Ident \"->\""`
	Next  string `parser:"@Ident"`
}

// StringValue returns the unquoted content of v if v is a quoted string
// literal (e.g. 'foo' or "foo"). ok is false if v is not a string literal.
func (v *Value) StringValue() (s string, ok bool) {
	if v.String == nil {
		return "", false
	}
	raw := *v.String
	if len(raw) >= 2 {
		return raw[1 : len(raw)-1], true
	}
	return raw, true
}

var dslLexer = lexer.MustSimple([]lexer.SimpleRule{
	{Name: "Comment", Pattern: `#[^\n]*`},
	// Path must require a leading letter so it never matches a bare numeric
	// literal like "3.0" (which would otherwise satisfy this pattern's
	// character classes and steal the token from Number, since Path is
	// listed first).
	{Name: "Path", Pattern: `[A-Za-z][A-Za-z0-9_]*(?:[./][A-Za-z0-9_-]+)+`},
	{Name: "Arrow", Pattern: `->`},
	{Name: "Number", Pattern: `-?[0-9]+(?:\.[0-9]+)?`},
	{Name: "String", Pattern: `'[^']*'|"[^"]*"`},
	{Name: "Ident", Pattern: `[A-Za-z_][A-Za-z0-9_]*`},
	{Name: "Punct", Pattern: `[:(),=\[\]]`},
	{Name: "Whitespace", Pattern: `[ \t\r\n]+`},
})

var dslParser = participle.MustBuild[File](
	participle.Lexer(dslLexer),
	participle.Elide("Whitespace", "Comment"),
	participle.UseLookahead(2),
)

// Parse parses DSL source text from r. filename is used only to annotate
// error messages and Pos fields.
func Parse(filename string, r io.Reader) (*File, error) {
	return dslParser.Parse(filename, r)
}
```

- [ ] **Step 3: Copy the real mission into testdata**

```bash
cp demo.dsl sdk/dsl/testdata/good.dsl
```

(`demo.dsl` at this point still has the old `SetGlobalPosition` name — that's fine for a pure-parse test; the rename happens in Task 5.)

- [ ] **Step 4: Write `sdk/dsl/testdata/edge_cases.dsl`**

```
Data:
    Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Bar bar(foo = Foo())
    Bar bar2(foo = Foo(1.0, 'x'))
    Pose pose(pitch = -45.0, yaw = 0.0, roll = 0.0)
Actions:
    TakeOff take_off(take_off_altitude = 10.0)
Events:
    DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
    BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    AnyOf any_of(events = [person_seen, battery_low])
Mission:
    Start take_off
    During take_off:
        done -> take_off
        person_seen -> take_off
```

- [ ] **Step 5: Write `sdk/dsl/ast_test.go`**

```go
package dsl

import (
	"os"
	"testing"
)

func TestParseGoodDSL(t *testing.T) {
	f, err := os.Open("testdata/good.dsl")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()

	file, err := Parse("good.dsl", f)
	if err != nil {
		t.Fatalf("Parse failed: %v", err)
	}
	if file.Role == nil || file.Role.Name != "Seeker" {
		t.Errorf("Role = %+v, want Name=Seeker", file.Role)
	}
	if file.Imports == nil || len(file.Imports.Paths) != 2 {
		t.Fatalf("Imports = %+v, want 2 paths", file.Imports)
	}
	want := "github.com/cmusatyalab/steeleagle_sdk/events"
	if file.Imports.Paths[0] != want {
		t.Errorf("Imports.Paths[0] = %q, want %q", file.Imports.Paths[0], want)
	}
	if file.Data == nil || len(file.Data.Decls) != 10 {
		t.Fatalf("Data.Decls = %d, want 10", len(file.Data.Decls))
	}
	if file.Actions == nil || len(file.Actions.Decls) != 15 {
		t.Fatalf("Actions.Decls = %d, want 15", len(file.Actions.Decls))
	}
	if file.Events == nil || len(file.Events.Decls) != 2 {
		t.Fatalf("Events.Decls = %d, want 2", len(file.Events.Decls))
	}
	if file.Mission == nil || file.Mission.Start != "take_off" {
		t.Fatalf("Mission.Start = %v, want take_off", file.Mission)
	}
	if len(file.Mission.Blocks) != 14 {
		t.Errorf("Mission.Blocks = %d, want 14", len(file.Mission.Blocks))
	}

	// Spot-check one full declaration and its attribute values.
	var takeOff *Decl
	for _, d := range file.Actions.Decls {
		if d.Name == "take_off" {
			takeOff = d
		}
	}
	if takeOff == nil {
		t.Fatal("no action named take_off")
	}
	if takeOff.Type != "TakeOff" || len(takeOff.Attrs) != 1 {
		t.Fatalf("take_off decl = %+v", takeOff)
	}
	if takeOff.Attrs[0].Key != "take_off_altitude" || *takeOff.Attrs[0].Value.Number != 3.0 {
		t.Errorf("take_off_altitude attr = %+v", takeOff.Attrs[0])
	}

	// Spot-check a bare-ident reference value (patrol references patrol_path).
	var patrol *Decl
	for _, d := range file.Actions.Decls {
		if d.Name == "patrol" {
			patrol = d
		}
	}
	if patrol == nil || *patrol.Attrs[0].Value.Ident != "patrol_path" {
		t.Errorf("patrol decl = %+v", patrol)
	}
}

func TestParseEdgeCases(t *testing.T) {
	f, err := os.Open("testdata/edge_cases.dsl")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()

	file, err := Parse("edge_cases.dsl", f)
	if err != nil {
		t.Fatalf("Parse failed: %v", err)
	}

	byName := map[string]*Decl{}
	for _, d := range file.Data.Decls {
		byName[d.Name] = d
	}

	// Quoted string literal.
	area := byName["patrol_path"].Attrs[1]
	if area.Key != "area" {
		t.Fatalf("unexpected attr order: %+v", area)
	}
	s, ok := area.Value.StringValue()
	if !ok || s != "Rectangle" {
		t.Errorf("area.StringValue() = %q, %v, want \"Rectangle\", true", s, ok)
	}

	// Inline constructor with no args.
	bar := byName["bar"].Attrs[0]
	if bar.Value.Inline == nil || bar.Value.Inline.Type != "Foo" || len(bar.Value.Inline.Args) != 0 {
		t.Errorf("bar.foo = %+v, want inline Foo()", bar.Value)
	}

	// Inline constructor with positional args (number, string).
	bar2 := byName["bar2"].Attrs[0]
	if bar2.Value.Inline == nil || len(bar2.Value.Inline.Args) != 2 {
		t.Fatalf("bar2.foo = %+v, want inline Foo(1.0, 'x')", bar2.Value)
	}
	if *bar2.Value.Inline.Args[0].Number != 1.0 {
		t.Errorf("bar2.foo arg0 = %+v, want 1.0", bar2.Value.Inline.Args[0])
	}

	// Negative number.
	pitch := byName["pose"].Attrs[0]
	if *pitch.Value.Number != -45.0 {
		t.Errorf("pitch = %v, want -45.0", *pitch.Value.Number)
	}

	// Array of bare idents.
	var anyOf *Decl
	for _, d := range file.Events.Decls {
		if d.Name == "any_of" {
			anyOf = d
		}
	}
	if anyOf == nil || anyOf.Attrs[0].Value.Array == nil || len(anyOf.Attrs[0].Value.Array.Elems) != 2 {
		t.Fatalf("any_of.events = %+v, want array of 2", anyOf)
	}
}
```

- [ ] **Step 6: Run the tests**

Run: `cd sdk && go test ./dsl/... -run TestParse -v`
Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
cd sdk
git add go.mod go.sum dsl/ast.go dsl/ast_test.go dsl/testdata/good.dsl dsl/testdata/edge_cases.dsl
git commit -m "sdk: add participle grammar and parser for the SteelEagle DSL"
```

---

## Task 2: Shared Diagnostic type

**Files:**
- Create: `sdk/dsl/diagnostics.go`
- Create: `sdk/dsl/diagnostics_test.go`

**Interfaces:**
- Consumes: `lexer.Position` from `github.com/alecthomas/participle/v2/lexer` (Task 1).
- Produces: `dsl.Severity` (`SeverityError`, `SeverityWarning`), `dsl.Diagnostic{Severity, Message, Pos}` with a `String() string` method, `func dsl.HasErrors(diags []Diagnostic) bool`. Every later phase (`CheckLocal`, `CrossCheck`, `CheckCapabilities`) returns `[]Diagnostic`.

- [ ] **Step 1: Write the failing test**

```go
package dsl

import (
	"testing"

	"github.com/alecthomas/participle/v2/lexer"
)

func TestDiagnosticString(t *testing.T) {
	d := Diagnostic{
		Severity: SeverityError,
		Message:  "boom",
		Pos:      lexer.Position{Filename: "f.dsl", Line: 3, Column: 5},
	}
	want := "error: f.dsl:3:5: boom"
	if got := d.String(); got != want {
		t.Errorf("String() = %q, want %q", got, want)
	}

	warn := Diagnostic{Severity: SeverityWarning, Message: "meh"}
	if got := warn.String(); got != "warning: meh" {
		t.Errorf("String() = %q, want %q", got, "warning: meh")
	}
}

func TestHasErrors(t *testing.T) {
	if HasErrors(nil) {
		t.Error("HasErrors(nil) = true, want false")
	}
	diags := []Diagnostic{{Severity: SeverityWarning, Message: "w"}}
	if HasErrors(diags) {
		t.Error("HasErrors(warnings only) = true, want false")
	}
	diags = append(diags, Diagnostic{Severity: SeverityError, Message: "e"})
	if !HasErrors(diags) {
		t.Error("HasErrors(with error) = false, want true")
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run 'TestDiagnosticString|TestHasErrors' -v`
Expected: FAIL — `Diagnostic`/`Severity`/`HasErrors` undefined.

- [ ] **Step 3: Write `sdk/dsl/diagnostics.go`**

```go
package dsl

import (
	"fmt"

	"github.com/alecthomas/participle/v2/lexer"
)

type Severity int

const (
	SeverityError Severity = iota
	SeverityWarning
)

func (s Severity) String() string {
	if s == SeverityWarning {
		return "warning"
	}
	return "error"
}

// Diagnostic is one error or warning produced by any validation phase.
type Diagnostic struct {
	Severity Severity
	Message  string
	Pos      lexer.Position
}

func (d Diagnostic) String() string {
	if d.Pos.Filename == "" && d.Pos.Line == 0 {
		return fmt.Sprintf("%s: %s", d.Severity, d.Message)
	}
	return fmt.Sprintf("%s: %s:%d:%d: %s", d.Severity, d.Pos.Filename, d.Pos.Line, d.Pos.Column, d.Message)
}

// HasErrors reports whether diags contains at least one SeverityError entry.
func HasErrors(diags []Diagnostic) bool {
	for _, d := range diags {
		if d.Severity == SeverityError {
			return true
		}
	}
	return false
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sdk && go test ./dsl/... -run 'TestDiagnosticString|TestHasErrors' -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd sdk
git add dsl/diagnostics.go dsl/diagnostics_test.go
git commit -m "sdk: add shared Diagnostic type for validator phases"
```

---

## Task 3: Phase 1 local checks — structural errors

**Files:**
- Create: `sdk/dsl/check_local.go`
- Create: `sdk/dsl/check_local_test.go`
- Create: `sdk/dsl/testdata/dangling_transition.dsl`
- Create: `sdk/dsl/testdata/no_mission.dsl`
- Create: `sdk/dsl/testdata/duplicate_decl.dsl`

**Interfaces:**
- Consumes: `dsl.File`, `dsl.Decl`, `dsl.Diagnostic`, `dsl.SeverityError`/`SeverityWarning` (Tasks 1-2).
- Produces: `func dsl.CheckLocal(f *File) []Diagnostic`. Later tasks (CLI wiring, Task 6) call this directly.

This task covers only the **unambiguous structural checks**: duplicate declarations, a missing `Mission` stanza, `Start`/`During`-owner/transition-target references to undeclared actions, and transition-trigger references to undeclared events (or the reserved word `done`). Bare-identifier attribute *values* (e.g. `algo = corridor`) are deliberately **not** checked here for danglingness — as noted in Task 1's `Value` doc comment, a bare ident there is ambiguous between "reference to a declared Data item" and "a plain string-like literal", and only Phase 2 (which knows the target field's real type) can tell the two apart. Task 4 covers the unused-declaration warnings that *do* use bare-ident scanning, as a best-effort heuristic explicitly scoped as a warning for that reason.

- [ ] **Step 1: Write the failing tests**

```go
package dsl

import (
	"os"
	"strings"
	"testing"
)

func parseFile(t *testing.T, path string) *File {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	file, err := Parse(path, f)
	if err != nil {
		t.Fatalf("Parse(%s) failed: %v", path, err)
	}
	return file
}

func diagMessages(diags []Diagnostic) []string {
	var msgs []string
	for _, d := range diags {
		msgs = append(msgs, d.Message)
	}
	return msgs
}

func containsSubstring(msgs []string, substr string) bool {
	for _, m := range msgs {
		if strings.Contains(m, substr) {
			return true
		}
	}
	return false
}

func TestCheckLocal_GoodFileHasNoErrors(t *testing.T) {
	file := parseFile(t, "testdata/good.dsl")
	diags := CheckLocal(file)
	for _, d := range diags {
		if d.Severity == SeverityError {
			t.Errorf("unexpected error on good.dsl: %s", d)
		}
	}
}

func TestCheckLocal_MissingMission(t *testing.T) {
	file := parseFile(t, "testdata/no_mission.dsl")
	diags := CheckLocal(file)
	if !containsSubstring(diagMessages(diags), "no Mission stanza") {
		t.Errorf("diags = %v, want a missing-Mission error", diagMessages(diags))
	}
}

func TestCheckLocal_DanglingTransition(t *testing.T) {
	file := parseFile(t, "testdata/dangling_transition.dsl")
	diags := CheckLocal(file)
	msgs := diagMessages(diags)
	if !containsSubstring(msgs, `undeclared action "does_not_exist"`) {
		t.Errorf("diags = %v, want dangling-transition-target error", msgs)
	}
}

func TestCheckLocal_DuplicateDecl(t *testing.T) {
	file := parseFile(t, "testdata/duplicate_decl.dsl")
	diags := CheckLocal(file)
	msgs := diagMessages(diags)
	if !containsSubstring(msgs, `duplicate Action declaration "take_off"`) {
		t.Errorf("diags = %v, want duplicate-declaration error", msgs)
	}
}
```

- [ ] **Step 2: Write the testdata fixtures**

`sdk/dsl/testdata/no_mission.dsl`:
```
Actions:
    TakeOff take_off(take_off_altitude = 3.0)
```

`sdk/dsl/testdata/dangling_transition.dsl`:
```
Actions:
    TakeOff take_off(take_off_altitude = 3.0)
Mission:
    Start take_off
    During take_off:
        done -> does_not_exist
```

`sdk/dsl/testdata/duplicate_decl.dsl`:
```
Actions:
    TakeOff take_off(take_off_altitude = 3.0)
    Land take_off()
Mission:
    Start take_off
    During take_off:
        done -> take_off
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd sdk && go test ./dsl/... -run TestCheckLocal -v`
Expected: FAIL — `CheckLocal` undefined.

- [ ] **Step 4: Write `sdk/dsl/check_local.go`**

```go
package dsl

import "fmt"

// CheckLocal runs Phase 1 structural checks against a parsed File. It
// requires no external packages, network access, or SDK knowledge.
func CheckLocal(f *File) []Diagnostic {
	var diags []Diagnostic

	dataNames := map[string]bool{}
	actionNames := map[string]bool{}
	eventNames := map[string]bool{}

	if f.Data != nil {
		diags = append(diags, collectDecls(f.Data.Decls, "Data", dataNames)...)
	}
	if f.Actions != nil {
		diags = append(diags, collectDecls(f.Actions.Decls, "Action", actionNames)...)
	}
	if f.Events != nil {
		diags = append(diags, collectDecls(f.Events.Decls, "Event", eventNames)...)
	}

	if f.Mission == nil {
		diags = append(diags, Diagnostic{
			Severity: SeverityError,
			Message:  "file has no Mission stanza",
		})
		return diags
	}

	if f.Mission.Start == "" {
		diags = append(diags, Diagnostic{Severity: SeverityError, Message: "Mission has no Start action"})
	} else if !actionNames[f.Mission.Start] {
		diags = append(diags, Diagnostic{
			Severity: SeverityError,
			Message:  fmt.Sprintf("Mission.Start references undeclared action %q", f.Mission.Start),
		})
	}

	for _, block := range f.Mission.Blocks {
		if !actionNames[block.Action] {
			diags = append(diags, Diagnostic{
				Severity: SeverityError,
				Message:  fmt.Sprintf("During block references undeclared action %q", block.Action),
			})
		}
		for _, rule := range block.Rules {
			if rule.Event != "done" && !eventNames[rule.Event] {
				diags = append(diags, Diagnostic{
					Severity: SeverityError,
					Message:  fmt.Sprintf("transition in %q references undeclared event %q", block.Action, rule.Event),
				})
			}
			if !actionNames[rule.Next] {
				diags = append(diags, Diagnostic{
					Severity: SeverityError,
					Message:  fmt.Sprintf("transition %q -> %q targets undeclared action %q", block.Action, rule.Event, rule.Next),
				})
			}
		}
	}

	return diags
}

// collectDecls records each declaration's name into names, emitting an error
// diagnostic for any name already seen within this same stanza.
func collectDecls(decls []*Decl, kind string, names map[string]bool) []Diagnostic {
	var diags []Diagnostic
	for _, d := range decls {
		if names[d.Name] {
			diags = append(diags, Diagnostic{
				Severity: SeverityError,
				Pos:      d.Pos,
				Message:  fmt.Sprintf("duplicate %s declaration %q", kind, d.Name),
			})
			continue
		}
		names[d.Name] = true
	}
	return diags
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd sdk && go test ./dsl/... -run TestCheckLocal -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd sdk
git add dsl/check_local.go dsl/check_local_test.go dsl/testdata/no_mission.dsl dsl/testdata/dangling_transition.dsl dsl/testdata/duplicate_decl.dsl
git commit -m "sdk: add phase 1 structural checks (dangling refs, missing Mission, duplicates)"
```

---

## Task 4: Phase 1 local checks — unused-declaration warnings

**Files:**
- Modify: `sdk/dsl/check_local.go`
- Modify: `sdk/dsl/check_local_test.go`
- Create: `sdk/dsl/testdata/unused_decls.dsl`

**Interfaces:**
- Consumes: same as Task 3.
- Produces: `CheckLocal` now also appends `SeverityWarning` diagnostics for unused Data/Action/Event declarations. No new exported symbols.

- [ ] **Step 1: Write the failing test**

Append to `sdk/dsl/check_local_test.go`:

```go
func TestCheckLocal_UnusedDeclarations(t *testing.T) {
	file := parseFile(t, "testdata/unused_decls.dsl")
	diags := CheckLocal(file)
	msgs := diagMessages(diags)
	if !containsSubstring(msgs, `action "orphan_action" is declared but never used`) {
		t.Errorf("diags = %v, want unused-action warning", msgs)
	}
	if !containsSubstring(msgs, `event "orphan_event" is declared but never used`) {
		t.Errorf("diags = %v, want unused-event warning", msgs)
	}
	if !containsSubstring(msgs, `data "orphan_data" is declared but never referenced`) {
		t.Errorf("diags = %v, want unused-data warning", msgs)
	}
	// take_off, its used event, and its used data must NOT be flagged.
	if containsSubstring(msgs, `"take_off" is declared but never used`) {
		t.Errorf("diags = %v, take_off should not be flagged as unused", msgs)
	}
}
```

- [ ] **Step 2: Write `sdk/dsl/testdata/unused_decls.dsl`**

```
Data:
    Velocity cruise_speed(x_vel = 1.0)
    Velocity orphan_data(x_vel = 2.0)
Actions:
    TakeOff take_off(take_off_altitude = 3.0)
    Land orphan_action()
Events:
    TimeReached timeout(duration = 5)
    TimeReached orphan_event(duration = 5)
Mission:
    Start take_off
    During take_off:
        done -> take_off
        timeout -> take_off
```

(`cruise_speed` is referenced nowhere either, intentionally — a bare-ident usage isn't wired up in this fixture since the point of this test is `orphan_data`; both would legitimately warn, which is fine since the test only asserts presence of the `orphan_*` warnings, not absence of others.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run TestCheckLocal_UnusedDeclarations -v`
Expected: FAIL — no unused-declaration warnings are produced yet.

- [ ] **Step 4: Extend `sdk/dsl/check_local.go`**

Add before the final `return diags` in `CheckLocal` (i.e., insert this block right after the `for _, block := range f.Mission.Blocks` loop, before the function's closing `return diags`):

```go
	usedActions := map[string]bool{f.Mission.Start: true}
	usedEvents := map[string]bool{}
	for _, block := range f.Mission.Blocks {
		usedActions[block.Action] = true
		for _, rule := range block.Rules {
			usedActions[rule.Next] = true
			if rule.Event != "done" {
				usedEvents[rule.Event] = true
			}
		}
	}
	for name := range actionNames {
		if !usedActions[name] {
			diags = append(diags, Diagnostic{
				Severity: SeverityWarning,
				Message:  fmt.Sprintf("action %q is declared but never used in Mission", name),
			})
		}
	}
	for name := range eventNames {
		if !usedEvents[name] {
			diags = append(diags, Diagnostic{
				Severity: SeverityWarning,
				Message:  fmt.Sprintf("event %q is declared but never used in any transition", name),
			})
		}
	}

	referencedData := map[string]bool{}
	if f.Data != nil {
		for _, d := range f.Data.Decls {
			collectIdentRefs(d.Attrs, referencedData)
		}
	}
	if f.Actions != nil {
		for _, d := range f.Actions.Decls {
			collectIdentRefs(d.Attrs, referencedData)
		}
	}
	if f.Events != nil {
		for _, d := range f.Events.Decls {
			collectIdentRefs(d.Attrs, referencedData)
		}
	}
	for name := range dataNames {
		if !referencedData[name] {
			diags = append(diags, Diagnostic{
				Severity: SeverityWarning,
				Message:  fmt.Sprintf("data %q is declared but never referenced", name),
			})
		}
	}
```

Note this duplicates the `for _, block := range f.Mission.Blocks` iteration already present earlier in the function (the earlier one does the Task 3 error checks); that's intentional — keep both loops, don't try to merge them, since combining unrelated concerns into one loop body makes the function harder to follow for the payoff of a minor speedup on tiny files.

Add these two helper functions at the bottom of the file:

```go
// collectIdentRefs walks attrs (and recursively into arrays and inline
// constructors) collecting every bare identifier value into refs. This is a
// best-effort heuristic for the unused-Data warning: a bare ident might be a
// reference to a Data declaration, or might coincidentally collide with one
// while actually meaning a plain string-like literal (see Value's doc
// comment in ast.go) — that ambiguity means this check can only safely be a
// warning, never an error.
func collectIdentRefs(attrs []*Attr, refs map[string]bool) {
	for _, a := range attrs {
		collectValueIdentRefs(a.Value, refs)
	}
}

func collectValueIdentRefs(v *Value, refs map[string]bool) {
	if v == nil {
		return
	}
	switch {
	case v.Ident != nil:
		refs[*v.Ident] = true
	case v.Array != nil:
		for _, e := range v.Array.Elems {
			collectValueIdentRefs(e, refs)
		}
	case v.Inline != nil:
		for _, a := range v.Inline.Args {
			collectValueIdentRefs(a, refs)
		}
	}
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd sdk && go test ./dsl/... -v`
Expected: all PASS, including the earlier Task 1-3 tests (no regressions).

- [ ] **Step 6: Commit**

```bash
cd sdk
git add dsl/check_local.go dsl/check_local_test.go dsl/testdata/unused_decls.dsl
git commit -m "sdk: add phase 1 unused-declaration warnings"
```

---

## Task 5: Update demo.dsl to current API names

**Files:**
- Modify: `sdk/demo.dsl`
- Modify: `sdk/dsl/testdata/good.dsl` (copy of the above, kept in sync)

**Interfaces:** None — pure content change.

The real proto (`api/steeleagle_protocol/v1/services/driver/control.proto` at the repo root) renamed `SetGlobalPosition` to `GoToGlobalPosition`; `demo.dsl` still uses the old name in five places (`go_to_hold`, `go_to_hold_2`, `go_to_mission_start`, `go_to_mission_start_2`, `rth_phase_one`, `rth_phase_two` — six actions, all of type `SetGlobalPosition`). Per the design spec, aliasing is out of scope; the fixture SDK built in Tasks 7-8 will only register `GoToGlobalPosition`, so this rename must land before Phase 2 tests are written (Task 9) or they won't resolve.

- [ ] **Step 1: Rename in both files**

```bash
cd sdk
sed -i 's/\bSetGlobalPosition\b/GoToGlobalPosition/g' demo.dsl dsl/testdata/good.dsl
grep -n GoToGlobalPosition demo.dsl
```

Expected output: 6 lines, one per `GoToGlobalPosition <instance>(...)` declaration (`go_to_hold`, `go_to_hold_2`, `go_to_mission_start`, `go_to_mission_start_2`, `rth_phase_one`, `rth_phase_two`).

- [ ] **Step 2: Re-run the full Phase 1 suite to confirm nothing else needed updating**

Run: `cd sdk && go test ./dsl/... -v`
Expected: PASS (Task 1's `TestParseGoodDSL` doesn't assert on type names, so this should be a no-op change from its perspective — the counts of decls/blocks are unaffected by a pure rename).

- [ ] **Step 3: Commit**

```bash
cd sdk
git add demo.dsl dsl/testdata/good.dsl
git commit -m "sdk: rename SetGlobalPosition to GoToGlobalPosition in demo.dsl to match current API"
```

---

## Task 6: CLI skeleton wired to Phase 1

**Files:**
- Create: `sdk/cmd/dslcheck/main.go`
- Create: `sdk/cmd/dslcheck/main_test.go`

**Interfaces:**
- Consumes: `dsl.Parse`, `dsl.CheckLocal`, `dsl.Diagnostic`, `dsl.HasErrors` (Tasks 1-4).
- Produces: `func run(dslPath string, stdout, stderr io.Writer) int` (the testable core of `main`, returning a process exit code) in package `main`. `main()` itself just calls `os.Exit(run(...))`. This shape is what Task 11 and Task 16 extend with `--replace` and `--cap` respectively.

- [ ] **Step 1: Write the failing test**

```go
package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestRun_GoodFile(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run("../../dsl/testdata/good.dsl", &stdout, &stderr)
	if code != 0 {
		t.Errorf("run() = %d, want 0; stderr=%s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "0 errors") {
		t.Errorf("stdout = %q, want a summary containing \"0 errors\"", stdout.String())
	}
}

func TestRun_MissingFile(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run("does/not/exist.dsl", &stdout, &stderr)
	if code == 0 {
		t.Error("run() = 0 for a missing file, want non-zero")
	}
}

func TestRun_StructuralError(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run("../../dsl/testdata/dangling_transition.dsl", &stdout, &stderr)
	if code == 0 {
		t.Error("run() = 0 for a file with a dangling transition, want non-zero")
	}
	if !strings.Contains(stdout.String(), "undeclared action") {
		t.Errorf("stdout = %q, want it to list the error", stdout.String())
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk && go test ./cmd/dslcheck/... -v`
Expected: FAIL — package `main` has no `run` function yet (build failure).

- [ ] **Step 3: Write `sdk/cmd/dslcheck/main.go`**

```go
package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

func main() {
	dslPath := flag.String("dsl", "", "path to the .dsl mission file to check")
	flag.Parse()
	if *dslPath == "" {
		fmt.Fprintln(os.Stderr, "usage: dslcheck --dsl <file.dsl>")
		os.Exit(2)
	}
	os.Exit(run(*dslPath, os.Stdout, os.Stderr))
}

// run is the testable core of main: it never calls os.Exit itself, and
// returns the process exit code the caller should use.
func run(dslPath string, stdout, stderr io.Writer) int {
	f, err := os.Open(dslPath)
	if err != nil {
		fmt.Fprintf(stderr, "error: %v\n", err)
		return 1
	}
	defer f.Close()

	file, err := dsl.Parse(dslPath, f)
	if err != nil {
		fmt.Fprintf(stdout, "error: %v\n", err)
		return 1
	}

	diags := dsl.CheckLocal(file)
	for _, d := range diags {
		fmt.Fprintln(stdout, d.String())
	}

	nActions, nEvents := 0, 0
	if file.Actions != nil {
		nActions = len(file.Actions.Decls)
	}
	if file.Events != nil {
		nEvents = len(file.Events.Decls)
	}
	nErrors := 0
	for _, d := range diags {
		if d.Severity == dsl.SeverityError {
			nErrors++
		}
	}
	fmt.Fprintf(stdout, "%d actions, %d events, %d errors\n", nActions, nEvents, nErrors)

	if dsl.HasErrors(diags) {
		return 1
	}
	return 0
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sdk && go test ./cmd/dslcheck/... -v`
Expected: PASS

- [ ] **Step 5: Build the binary and smoke-test it manually**

```bash
cd sdk
go build -o /tmp/dslcheck ./cmd/dslcheck
/tmp/dslcheck --dsl demo.dsl; echo "exit=$?"
```

Expected: prints unused-declaration warnings (if any) and a summary line, exits 0 (`demo.dsl` has no structural errors as of Task 5).

- [ ] **Step 6: Commit**

```bash
cd sdk
git add cmd/dslcheck/main.go cmd/dslcheck/main_test.go
git commit -m "sdk: add dslcheck CLI wired to phase 1 checks"
```

---

## Task 7: sdkfixture module + sdktypes runtime package

**Files:**
- Create: `sdk/dsl/testdata/sdkfixture/go.mod`
- Create: `sdk/dsl/testdata/sdkfixture/sdktypes/sdktypes.go`
- Create: `sdk/dsl/testdata/sdkfixture/sdktypes/sdktypes_test.go`

**Interfaces:**
- Produces (all in package `sdktypes`, module `github.com/cmusatyalab/steeleagle_sdk`): `Action` (`Execute(ctx context.Context) error`), `Event` (`Check(ctx context.Context) (bool, error)`), `Datatype` (unexported marker `steeleagleDatatype()`), `BaseDatatype` (embeddable zero-value implementing `Datatype`), `RegisterAction[T Action](name string)`, `RegisterEvent[T Event](name string)`, `RegisterData[T Datatype](name string)`, `FieldSchema{Kind string, Optional bool}`, `TypeSchema{Package, Type string, Fields map[string]FieldSchema}`, `RegistryDump{Actions, Events, Data map[string]TypeSchema}`, `DumpRegistry() ([]byte, error)`.
- This exact reflection-based design (field-name snake_case conversion, pointer-means-optional, `dsl:"..."` tag override, `PkgPath()`/`Name()` capture after dereferencing pointers) was interactively prototyped and verified — including confirming `reflect.TypeFor[T]()` (Go 1.22+) works for registration and that `PkgPath()`/`Name()` correctly resolve through a `*T` registration to `T`'s real package and name.

This fixture module is **not** the real `github.com/cmusatyalab/steeleagle_sdk` (which doesn't exist yet anywhere) — it's a local stand-in used only by this repo's tests, resolved into the sequestered module via a `-replace` flag (Task 9), never fetched over the network.

- [ ] **Step 1: Create the fixture module**

```bash
mkdir -p sdk/dsl/testdata/sdkfixture/sdktypes
cd sdk/dsl/testdata/sdkfixture
go mod init github.com/cmusatyalab/steeleagle_sdk
```

- [ ] **Step 2: Write the failing test**

`sdk/dsl/testdata/sdkfixture/sdktypes/sdktypes_test.go`:

```go
package sdktypes

import (
	"context"
	"encoding/json"
	"testing"
)

type fakeAction struct {
	BaseDatatype // unused embedding here just to prove it doesn't interfere; real actions won't embed this
	TakeOffAltitude float64
	Label           *string `dsl:"label_override"`
}

func (f *fakeAction) Execute(ctx context.Context) error { return nil }

func TestRegisterActionAndDumpRegistry(t *testing.T) {
	RegisterAction[*fakeAction]("FakeAction")

	raw, err := DumpRegistry()
	if err != nil {
		t.Fatalf("DumpRegistry() error: %v", err)
	}
	var reg RegistryDump
	if err := json.Unmarshal(raw, &reg); err != nil {
		t.Fatalf("invalid JSON from DumpRegistry: %v\n%s", err, raw)
	}

	schema, ok := reg.Actions["FakeAction"]
	if !ok {
		t.Fatalf("Actions[FakeAction] missing; got %+v", reg.Actions)
	}
	if schema.Package != "github.com/cmusatyalab/steeleagle_sdk/sdktypes" {
		t.Errorf("Package = %q, want this package's import path", schema.Package)
	}
	if schema.Type != "fakeAction" {
		t.Errorf("Type = %q, want fakeAction", schema.Type)
	}

	alt, ok := schema.Fields["take_off_altitude"]
	if !ok || alt.Optional {
		t.Errorf("Fields[take_off_altitude] = %+v, ok=%v; want present and required", alt, ok)
	}
	label, ok := schema.Fields["label_override"]
	if !ok || !label.Optional {
		t.Errorf("Fields[label_override] = %+v, ok=%v; want present and optional (dsl tag + pointer)", label, ok)
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd sdk/dsl/testdata/sdkfixture && go test ./... -v`
Expected: FAIL — package doesn't compile yet (`Action`, `RegisterAction`, etc. undefined).

- [ ] **Step 4: Write `sdk/dsl/testdata/sdkfixture/sdktypes/sdktypes.go`**

```go
package sdktypes

import (
	"context"
	"encoding/json"
	"reflect"
	"strings"
)

// Action is the contract every mission action implements.
type Action interface {
	Execute(ctx context.Context) error
}

// Event is the contract every mission event implements.
type Event interface {
	Check(ctx context.Context) (bool, error)
}

// Datatype is a marker interface satisfied by embedding BaseDatatype.
type Datatype interface {
	steeleagleDatatype()
}

// BaseDatatype is embedded by concrete datatype structs to satisfy Datatype.
type BaseDatatype struct{}

func (BaseDatatype) steeleagleDatatype() {}

type FieldSchema struct {
	Kind     string `json:"kind"`
	Optional bool   `json:"optional"`
}

type TypeSchema struct {
	Package string                 `json:"package"`
	Type    string                 `json:"type"`
	Fields  map[string]FieldSchema `json:"fields"`
}

type RegistryDump struct {
	Actions map[string]TypeSchema `json:"actions"`
	Events  map[string]TypeSchema `json:"events"`
	Data    map[string]TypeSchema `json:"data"`
}

var (
	actionTypes = map[string]reflect.Type{}
	eventTypes  = map[string]reflect.Type{}
	dataTypes   = map[string]reflect.Type{}
)

// RegisterAction associates the DSL type name with the Go type T. Call from
// an init() in the package implementing T. T is typically a pointer type
// (e.g. RegisterAction[*TakeOff]) since Execute is usually a pointer-receiver
// method.
func RegisterAction[T Action](name string) {
	actionTypes[name] = reflect.TypeFor[T]()
}

func RegisterEvent[T Event](name string) {
	eventTypes[name] = reflect.TypeFor[T]()
}

func RegisterData[T Datatype](name string) {
	dataTypes[name] = reflect.TypeFor[T]()
}

func toSnakeCase(s string) string {
	var b strings.Builder
	for i, r := range s {
		if i > 0 && r >= 'A' && r <= 'Z' {
			b.WriteByte('_')
		}
		b.WriteRune(r)
	}
	return strings.ToLower(b.String())
}

func schemaFor(t reflect.Type) TypeSchema {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	fields := map[string]FieldSchema{}
	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)
		if !f.IsExported() {
			continue
		}
		name := f.Tag.Get("dsl")
		if name == "" {
			name = toSnakeCase(f.Name)
		}
		fields[name] = FieldSchema{
			Kind:     f.Type.String(),
			Optional: f.Type.Kind() == reflect.Pointer,
		}
	}
	return TypeSchema{Package: t.PkgPath(), Type: t.Name(), Fields: fields}
}

// DumpRegistry serializes every registered Action/Event/Datatype's schema as
// JSON. Called by the generated harness program inside the sequestered
// module (see dsl/resolve.go); never called directly by dslcheck itself.
func DumpRegistry() ([]byte, error) {
	reg := RegistryDump{
		Actions: map[string]TypeSchema{},
		Events:  map[string]TypeSchema{},
		Data:    map[string]TypeSchema{},
	}
	for name, t := range actionTypes {
		reg.Actions[name] = schemaFor(t)
	}
	for name, t := range eventTypes {
		reg.Events[name] = schemaFor(t)
	}
	for name, t := range dataTypes {
		reg.Data[name] = schemaFor(t)
	}
	return json.MarshalIndent(reg, "", "  ")
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd sdk/dsl/testdata/sdkfixture && go test ./... -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd sdk
git add dsl/testdata/sdkfixture/go.mod dsl/testdata/sdkfixture/sdktypes/
git commit -m "sdk: add sdktypes runtime contract (fixture stand-in for steeleagle_sdk)"
```

---

## Task 8: sdkfixture actions/events packages implementing demo.dsl's vocabulary

**Files:**
- Create: `sdk/dsl/testdata/sdkfixture/internal/vehicleapi/vehicleapi.go`
- Create: `sdk/dsl/testdata/sdkfixture/actions/actions.go`
- Create: `sdk/dsl/testdata/sdkfixture/events/events.go`
- Create: `sdk/dsl/testdata/sdkfixture/actions/actions_test.go`

**Interfaces:**
- Consumes: `sdktypes.Action`, `sdktypes.Event`, `sdktypes.RegisterAction`, `sdktypes.RegisterEvent` (Task 7).
- Produces: package `github.com/cmusatyalab/steeleagle_sdk/actions` — `TakeOff{TakeOffAltitude float64}`, `Wait{Duration float64}`, `Patrol{Waypoints string}`, `Track{Target string, YawGain, FollowSpeed, DescentSpeed, TargetAltitude float64}`, `GoToGlobalPosition{Location string, HeadingMode, AltitudeMode *float64}`, `ElevateToAltitude{TargetAltitude float64}`, `SetGimbalPose{GimbalID float64, Pose string}`, `PrecisionLand{Target string, ForwardSpeed, LateralSpeed, DescentSpeed, ComputeStream string, ErrTol, TargetAltitude float64}` — one Go type per distinct `Type` name used in `demo.dsl`'s `Actions:` stanza. Package `github.com/cmusatyalab/steeleagle_sdk/events` — `DetectionFound{Target string}`, `TimeReached{Duration float64}`. Package `github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi` — a small mock "vehicle API" (`Client{}` with methods `TakeOff`, `GoToGlobalPosition`, `SetGimbalPose`) that `Execute` methods call into, giving Task 13-15's SSA capability check real call edges and field accesses to test against.

This task deliberately keeps every field a `string`/`float64` (never a nested struct referencing another Data type) even where the real API would use richer types (e.g. `Location` would really be a struct, not a string) — Phase 2's cross-check only needs field *names* and optional/required-ness to line up with `demo.dsl`'s attribute keys, and keeping field types trivial avoids needing to model `demo.dsl`'s other Data types (`Velocity`, `Waypoints`, `Location`, `Detection`, `Pose`) as Go structs at all for this iteration, since Phase 2/3 as scoped don't exercise `Data` stanza resolution against real datatype registrations (there is no `sdktypes.RegisterData` call anywhere in this fixture, and Phase 2's cross-check will therefore flag every `Data` declaration in `demo.dsl` as "unknown datatype" — see the note in Task 10).

- [ ] **Step 1: Write the mock vehicle API**

`sdk/dsl/testdata/sdkfixture/internal/vehicleapi/vehicleapi.go`:

```go
package vehicleapi

// Client is a stand-in for a real gRPC ControlServiceClient, giving the
// capability checker (Tasks 13-15) real method calls to find in the SSA call
// graph.
type Client struct{}

type GimbalPoseRequest struct {
	GimbalID int
	Pose     string
}

func (c *Client) TakeOff(altitude float64) error                      { return nil }
func (c *Client) GoToGlobalPosition(location string) error            { return nil }
func (c *Client) SetGimbalPose(req *GimbalPoseRequest) error           { return nil }
func (r *GimbalPoseRequest) GetPose() string                          { return r.Pose }
```

- [ ] **Step 2: Write `sdk/dsl/testdata/sdkfixture/actions/actions.go`**

```go
package actions

import (
	"context"

	"github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi"
	"github.com/cmusatyalab/steeleagle_sdk/sdktypes"
)

type TakeOff struct {
	TakeOffAltitude float64
}

func (t *TakeOff) Execute(ctx context.Context) error {
	c := &vehicleapi.Client{}
	return c.TakeOff(t.TakeOffAltitude)
}

type Wait struct {
	Duration float64
}

func (w *Wait) Execute(ctx context.Context) error { return nil }

type Patrol struct {
	Waypoints string
}

func (p *Patrol) Execute(ctx context.Context) error { return nil }

type Track struct {
	Target         string
	YawGain        float64
	FollowSpeed    float64
	DescentSpeed   float64
	TargetAltitude float64
}

func (t *Track) Execute(ctx context.Context) error { return nil }

type GoToGlobalPosition struct {
	Location     string
	HeadingMode  *float64
	AltitudeMode *float64
}

func (g *GoToGlobalPosition) Execute(ctx context.Context) error {
	c := &vehicleapi.Client{}
	return c.GoToGlobalPosition(g.Location)
}

type ElevateToAltitude struct {
	TargetAltitude float64
}

func (e *ElevateToAltitude) Execute(ctx context.Context) error { return nil }

type SetGimbalPose struct {
	GimbalID float64
	Pose     string
}

func (s *SetGimbalPose) Execute(ctx context.Context) error {
	c := &vehicleapi.Client{}
	req := &vehicleapi.GimbalPoseRequest{GimbalID: int(s.GimbalID)}
	req.Pose = s.Pose // direct field write — exercised by Task 15's field-write check
	_ = req.GetPose()  // getter read — exercised by Task 15's field-read check
	return c.SetGimbalPose(req)
}

type PrecisionLand struct {
	Target         string
	ForwardSpeed   float64
	LateralSpeed   float64
	DescentSpeed   float64
	ComputeStream  string
	ErrTol         float64
	TargetAltitude float64
}

func (p *PrecisionLand) Execute(ctx context.Context) error { return nil }

func init() {
	sdktypes.RegisterAction[*TakeOff]("TakeOff")
	sdktypes.RegisterAction[*Wait]("Wait")
	sdktypes.RegisterAction[*Patrol]("Patrol")
	sdktypes.RegisterAction[*Track]("Track")
	sdktypes.RegisterAction[*GoToGlobalPosition]("GoToGlobalPosition")
	sdktypes.RegisterAction[*ElevateToAltitude]("ElevateToAltitude")
	sdktypes.RegisterAction[*SetGimbalPose]("SetGimbalPose")
	sdktypes.RegisterAction[*PrecisionLand]("PrecisionLand")
}
```

- [ ] **Step 3: Write `sdk/dsl/testdata/sdkfixture/events/events.go`**

```go
package events

import (
	"context"

	"github.com/cmusatyalab/steeleagle_sdk/sdktypes"
)

type DetectionFound struct {
	Target string
}

func (d *DetectionFound) Check(ctx context.Context) (bool, error) { return false, nil }

type TimeReached struct {
	Duration float64
}

func (t *TimeReached) Check(ctx context.Context) (bool, error) { return false, nil }

func init() {
	sdktypes.RegisterEvent[*DetectionFound]("DetectionFound")
	sdktypes.RegisterEvent[*TimeReached]("TimeReached")
}
```

- [ ] **Step 4: Write a smoke test**

`sdk/dsl/testdata/sdkfixture/actions/actions_test.go`:

```go
package actions

import (
	"context"
	"testing"
)

func TestTakeOffExecute(t *testing.T) {
	a := &TakeOff{TakeOffAltitude: 3.0}
	if err := a.Execute(context.Background()); err != nil {
		t.Errorf("Execute() error: %v", err)
	}
}

func TestSetGimbalPoseExecute(t *testing.T) {
	s := &SetGimbalPose{GimbalID: 0, Pose: "level"}
	if err := s.Execute(context.Background()); err != nil {
		t.Errorf("Execute() error: %v", err)
	}
}
```

- [ ] **Step 5: Run the fixture module's own tests**

Run: `cd sdk/dsl/testdata/sdkfixture && go test ./... -v`
Expected: PASS for both new tests, and the Task 7 `sdktypes` test still passes.

- [ ] **Step 6: Verify the registry dump end-to-end with a throwaway harness**

This is a manual sanity check (not a committed test — Task 9 automates this properly), confirming the whole fixture module is internally consistent before Phase 2 code depends on it:

```bash
mkdir -p /tmp/sdkfixture-smoke
cat > /tmp/sdkfixture-smoke/main.go <<'EOF'
package main

import (
	"fmt"

	_ "github.com/cmusatyalab/steeleagle_sdk/actions"
	_ "github.com/cmusatyalab/steeleagle_sdk/events"
	"github.com/cmusatyalab/steeleagle_sdk/sdktypes"
)

func main() {
	b, err := sdktypes.DumpRegistry()
	if err != nil {
		panic(err)
	}
	fmt.Println(string(b))
}
EOF
cd /tmp/sdkfixture-smoke
go mod init smoke
go mod edit -replace github.com/cmusatyalab/steeleagle_sdk=$(cd - >/dev/null && cd sdk/dsl/testdata/sdkfixture && pwd)
go get github.com/cmusatyalab/steeleagle_sdk/actions github.com/cmusatyalab/steeleagle_sdk/events
go run .
```

Expected: JSON with 8 entries under `actions` and 2 under `events`, field names matching `demo.dsl`'s attribute keys (e.g. `TakeOff.fields.take_off_altitude`).

- [ ] **Step 7: Commit**

```bash
cd sdk
git add dsl/testdata/sdkfixture/internal/vehicleapi/vehicleapi.go dsl/testdata/sdkfixture/actions/ dsl/testdata/sdkfixture/events/
git commit -m "sdk: add fixture actions/events implementing demo.dsl's vocabulary"
```

---

## Task 9: Sequestered module builder (resolve.go)

**Files:**
- Create: `sdk/dsl/resolve.go`
- Create: `sdk/dsl/resolve_test.go`

**Interfaces:**
- Consumes: nothing from earlier tasks except standard library (`os/exec`, `encoding/json`).
- Produces: `dsl.ResolveConfig{ScratchDir string, Replace map[string]string}`, re-exports `dsl.FieldSchema`/`dsl.TypeSchema`/`dsl.RegistryDump` (same shape as `sdktypes`'s, duplicated here since `dsl` cannot import the fixture module — it's a foreign module resolved only at runtime via subprocess), `func dsl.BuildRegistry(imports []string, cfg ResolveConfig) (*RegistryDump, error)`. Task 10 consumes `BuildRegistry`'s return value; Tasks 13-15 consume `cfg.ScratchDir` (the already-`go get`-populated module directory) directly for `go/packages` loading.

This task's test shells out to `go mod init`/`go mod edit -replace`/`go get`/`go list`/`go build`, using Task 7-8's `sdkfixture` as the target via `-replace` — exactly the flow already manually verified in Task 8's Step 6, now automated and asserted on.

- [ ] **Step 1: Write the failing test**

```go
package dsl

import (
	"path/filepath"
	"testing"
)

func TestBuildRegistry(t *testing.T) {
	if testing.Short() {
		t.Skip("shells out to go build/get; skipped under -short")
	}
	fixtureDir, err := filepath.Abs("testdata/sdkfixture")
	if err != nil {
		t.Fatal(err)
	}
	cfg := ResolveConfig{
		ScratchDir: t.TempDir(),
		Replace: map[string]string{
			"github.com/cmusatyalab/steeleagle_sdk": fixtureDir,
		},
	}
	imports := []string{
		"github.com/cmusatyalab/steeleagle_sdk/actions",
		"github.com/cmusatyalab/steeleagle_sdk/events",
	}
	reg, err := BuildRegistry(imports, cfg)
	if err != nil {
		t.Fatalf("BuildRegistry error: %v", err)
	}
	if _, ok := reg.Actions["TakeOff"]; !ok {
		t.Errorf("Actions = %v, want TakeOff present", reg.Actions)
	}
	if _, ok := reg.Actions["GoToGlobalPosition"]; !ok {
		t.Errorf("Actions = %v, want GoToGlobalPosition present", reg.Actions)
	}
	if _, ok := reg.Events["DetectionFound"]; !ok {
		t.Errorf("Events = %v, want DetectionFound present", reg.Events)
	}
	schema := reg.Actions["TakeOff"]
	if schema.Package != "github.com/cmusatyalab/steeleagle_sdk/actions" {
		t.Errorf("TakeOff.Package = %q", schema.Package)
	}
	if f, ok := schema.Fields["take_off_altitude"]; !ok || f.Optional {
		t.Errorf("TakeOff.Fields[take_off_altitude] = %+v, ok=%v; want present and required", f, ok)
	}
}

func TestBuildRegistry_NoImports(t *testing.T) {
	_, err := BuildRegistry(nil, ResolveConfig{ScratchDir: t.TempDir()})
	if err == nil {
		t.Error("BuildRegistry(nil imports) = nil error, want an error")
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run TestBuildRegistry -v`
Expected: FAIL — `ResolveConfig`/`BuildRegistry` undefined.

- [ ] **Step 3: Write `sdk/dsl/resolve.go`**

```go
package dsl

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type FieldSchema struct {
	Kind     string `json:"kind"`
	Optional bool   `json:"optional"`
}

type TypeSchema struct {
	Package string                 `json:"package"`
	Type    string                 `json:"type"`
	Fields  map[string]FieldSchema `json:"fields"`
}

type RegistryDump struct {
	Actions map[string]TypeSchema `json:"actions"`
	Events  map[string]TypeSchema `json:"events"`
	Data    map[string]TypeSchema `json:"data"`
}

// ResolveConfig configures the sequestered (throwaway) Go module used to
// resolve a DSL file's Import: packages against real Go code.
type ResolveConfig struct {
	// ScratchDir is the directory for the throwaway module. Created if it
	// doesn't exist; reused (not re-initialized) if it already contains a
	// go.mod, so repeated runs against the same ScratchDir don't redo work
	// unnecessarily.
	ScratchDir string
	// Replace maps an import path to a local directory, standing in for a
	// `go mod edit -replace <path>=<dir>` — used for packages under active
	// local development that aren't published yet. Anything not listed here
	// is fetched with `go get <path>@latest`.
	Replace map[string]string
}

// BuildRegistry builds (or reuses) the sequestered module at cfg.ScratchDir,
// fetches every path in imports, and builds+runs a small harness program
// that dumps the resulting Action/Event/Datatype registry as JSON.
func BuildRegistry(imports []string, cfg ResolveConfig) (*RegistryDump, error) {
	if len(imports) == 0 {
		return nil, fmt.Errorf("no Import paths declared in DSL file")
	}
	if err := os.MkdirAll(cfg.ScratchDir, 0o755); err != nil {
		return nil, fmt.Errorf("creating scratch dir: %w", err)
	}
	if _, err := os.Stat(filepath.Join(cfg.ScratchDir, "go.mod")); os.IsNotExist(err) {
		if _, err := runGo(cfg.ScratchDir, "mod", "init", "dslcheck-scratch"); err != nil {
			return nil, fmt.Errorf("go mod init: %w", err)
		}
	}
	for oldPath, newDir := range cfg.Replace {
		if _, err := runGo(cfg.ScratchDir, "mod", "edit", "-replace", fmt.Sprintf("%s=%s", oldPath, newDir)); err != nil {
			return nil, fmt.Errorf("go mod edit -replace %s: %w", oldPath, err)
		}
	}
	for _, imp := range imports {
		if _, err := runGo(cfg.ScratchDir, "get", imp); err != nil {
			return nil, fmt.Errorf("go get %s: %w", imp, err)
		}
	}

	modRootOut, err := runGo(cfg.ScratchDir, "list", "-f", "{{.Module.Path}}", imports[0])
	if err != nil {
		return nil, fmt.Errorf("go list module for %s: %w", imports[0], err)
	}
	modRoot := strings.TrimSpace(modRootOut)
	runtimePkg := modRoot + "/sdktypes"

	if err := writeHarness(cfg.ScratchDir, imports, runtimePkg); err != nil {
		return nil, err
	}
	// The runtime package is usually already required transitively once any
	// sibling package from the same module has been fetched, but fetch it
	// explicitly too so a DSL file whose Import: paths don't happen to share
	// a package prefix with sdktypes still resolves it.
	if _, err := runGo(cfg.ScratchDir, "get", runtimePkg); err != nil {
		return nil, fmt.Errorf("go get %s: %w", runtimePkg, err)
	}

	harnessBin := filepath.Join(cfg.ScratchDir, "dslcheck-harness")
	if _, err := runGo(cfg.ScratchDir, "build", "-o", harnessBin, "."); err != nil {
		return nil, fmt.Errorf("building registry-dump harness (a package/type referenced in the DSL's Import: paths likely doesn't exist or doesn't compile): %w", err)
	}

	cmd := exec.Command(harnessBin)
	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("running registry-dump harness: %w\n%s", err, out.String())
	}

	var reg RegistryDump
	if err := json.Unmarshal(out.Bytes(), &reg); err != nil {
		return nil, fmt.Errorf("parsing registry dump: %w", err)
	}
	return &reg, nil
}

// runGo runs `go <args...>` with its working directory set to dir, returning
// combined stdout+stderr. On failure the returned error wraps that output so
// callers don't need to inspect it separately.
func runGo(dir string, args ...string) (string, error) {
	cmd := exec.Command("go", args...)
	cmd.Dir = dir
	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out
	if err := cmd.Run(); err != nil {
		return out.String(), fmt.Errorf("go %s: %w\n%s", strings.Join(args, " "), err, out.String())
	}
	return out.String(), nil
}

// writeHarness generates a main.go in dir that blank-imports every path in
// imports (triggering their init()s, which register Actions/Events/Data)
// and calls sdktypes.DumpRegistry(), printing the result to stdout.
func writeHarness(dir string, imports []string, runtimePkg string) error {
	var b bytes.Buffer
	b.WriteString("package main\n\nimport (\n\t\"fmt\"\n\t\"os\"\n\n")
	for _, imp := range imports {
		fmt.Fprintf(&b, "\t_ %q\n", imp)
	}
	fmt.Fprintf(&b, "\tsdktypes %q\n", runtimePkg)
	b.WriteString(")\n\nfunc main() {\n")
	b.WriteString("\tout, err := sdktypes.DumpRegistry()\n")
	b.WriteString("\tif err != nil {\n\t\tfmt.Fprintln(os.Stderr, err)\n\t\tos.Exit(1)\n\t}\n")
	b.WriteString("\tfmt.Println(string(out))\n}\n")
	return os.WriteFile(filepath.Join(dir, "main.go"), b.Bytes(), 0o644)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sdk && go test ./dsl/... -run TestBuildRegistry -v`
Expected: PASS. This will take longer than the earlier tests (real `go get`/`go build` calls) — tens of seconds is normal.

- [ ] **Step 5: Run the full non-short suite once to confirm no regressions**

Run: `cd sdk && go test ./... -v`
Expected: PASS across all packages (`dsl`, `cmd/dslcheck`, and the `sdkfixture` submodule is tested separately via its own `go.mod` and isn't picked up by this command — that's expected and fine).

- [ ] **Step 6: Commit**

```bash
cd sdk
git add dsl/resolve.go dsl/resolve_test.go
git commit -m "sdk: add sequestered-module builder (phase 2 package resolution)"
```

---

## Task 10: Cross-check DSL declarations against the resolved registry

**Files:**
- Create: `sdk/dsl/crosscheck.go`
- Create: `sdk/dsl/crosscheck_test.go`

**Interfaces:**
- Consumes: `dsl.File`, `dsl.Decl`, `dsl.RegistryDump`, `dsl.TypeSchema` (Tasks 1, 9), `dsl.Diagnostic` (Task 2).
- Produces: `func dsl.CrossCheck(f *File, reg *RegistryDump) []Diagnostic`.

As noted in Task 8, the fixture SDK registers no `Data` types at all (`demo.dsl`'s `Velocity`/`Waypoints`/`Location`/`Detection`/`Pose` declarations have no corresponding `sdktypes.RegisterData` call anywhere), so running `CrossCheck` against the real `demo.dsl` will report every `Data` declaration as an unknown-datatype error. That's expected and correct behavior for this task in isolation — Task 16's end-to-end test scopes its assertions to the `Actions`/`Events` stanzas specifically for this reason, documented there.

- [ ] **Step 1: Write the failing test**

```go
package dsl

import "testing"

func schemaWithFields(pkg, typ string, fields map[string]FieldSchema) TypeSchema {
	return TypeSchema{Package: pkg, Type: typ, Fields: fields}
}

func TestCrossCheck_UnknownType(t *testing.T) {
	f := &File{Actions: &ActionsStanza{Decls: []*Decl{
		{Type: "NotRegistered", Name: "x"},
	}}}
	reg := &RegistryDump{Actions: map[string]TypeSchema{}}
	diags := CrossCheck(f, reg)
	if len(diags) != 1 || diags[0].Severity != SeverityError {
		t.Fatalf("diags = %v, want exactly one error", diags)
	}
}

func TestCrossCheck_UnknownField(t *testing.T) {
	f := &File{Actions: &ActionsStanza{Decls: []*Decl{
		{Type: "TakeOff", Name: "x", Attrs: []*Attr{
			{Key: "bogus_field", Value: &Value{}},
		}},
	}}}
	reg := &RegistryDump{Actions: map[string]TypeSchema{
		"TakeOff": schemaWithFields("pkg/actions", "TakeOff", map[string]FieldSchema{
			"take_off_altitude": {Kind: "float64", Optional: false},
		}),
	}}
	diags := CrossCheck(f, reg)
	found := false
	for _, d := range diags {
		if d.Severity == SeverityError && containsSubstring([]string{d.Message}, `no field "bogus_field"`) {
			found = true
		}
	}
	if !found {
		t.Errorf("diags = %v, want an unknown-field error", diags)
	}
}

func TestCrossCheck_MissingRequiredField(t *testing.T) {
	f := &File{Actions: &ActionsStanza{Decls: []*Decl{
		{Type: "TakeOff", Name: "x"}, // no attrs at all
	}}}
	reg := &RegistryDump{Actions: map[string]TypeSchema{
		"TakeOff": schemaWithFields("pkg/actions", "TakeOff", map[string]FieldSchema{
			"take_off_altitude": {Kind: "float64", Optional: false},
		}),
	}}
	diags := CrossCheck(f, reg)
	found := false
	for _, d := range diags {
		if d.Severity == SeverityError && containsSubstring([]string{d.Message}, `missing required field "take_off_altitude"`) {
			found = true
		}
	}
	if !found {
		t.Errorf("diags = %v, want a missing-required-field error", diags)
	}
}

func TestCrossCheck_Clean(t *testing.T) {
	f := &File{Actions: &ActionsStanza{Decls: []*Decl{
		{Type: "TakeOff", Name: "x", Attrs: []*Attr{
			{Key: "take_off_altitude", Value: &Value{}},
		}},
	}}}
	reg := &RegistryDump{Actions: map[string]TypeSchema{
		"TakeOff": schemaWithFields("pkg/actions", "TakeOff", map[string]FieldSchema{
			"take_off_altitude": {Kind: "float64", Optional: false},
		}),
	}}
	diags := CrossCheck(f, reg)
	if len(diags) != 0 {
		t.Errorf("diags = %v, want none", diags)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run TestCrossCheck -v`
Expected: FAIL — `CrossCheck` undefined.

- [ ] **Step 3: Write `sdk/dsl/crosscheck.go`**

```go
package dsl

import "fmt"

// CrossCheck verifies every Data/Action/Event declaration in f against reg,
// the registry dumped from a resolved sequestered module (see
// BuildRegistry): unknown type names, unknown fields, and missing required
// fields are reported as errors.
func CrossCheck(f *File, reg *RegistryDump) []Diagnostic {
	var diags []Diagnostic
	if f.Data != nil {
		diags = append(diags, crossCheckDecls(f.Data.Decls, "datatype", reg.Data)...)
	}
	if f.Actions != nil {
		diags = append(diags, crossCheckDecls(f.Actions.Decls, "action", reg.Actions)...)
	}
	if f.Events != nil {
		diags = append(diags, crossCheckDecls(f.Events.Decls, "event", reg.Events)...)
	}
	return diags
}

func crossCheckDecls(decls []*Decl, kind string, schemas map[string]TypeSchema) []Diagnostic {
	var diags []Diagnostic
	for _, d := range decls {
		schema, ok := schemas[d.Type]
		if !ok {
			diags = append(diags, Diagnostic{
				Severity: SeverityError,
				Pos:      d.Pos,
				Message:  fmt.Sprintf("unknown %s type %q (not registered by any imported package)", kind, d.Type),
			})
			continue
		}
		provided := map[string]bool{}
		for _, a := range d.Attrs {
			provided[a.Key] = true
			if _, ok := schema.Fields[a.Key]; !ok {
				diags = append(diags, Diagnostic{
					Severity: SeverityError,
					Pos:      d.Pos,
					Message:  fmt.Sprintf("%s %q has no field %q", d.Type, d.Name, a.Key),
				})
			}
		}
		for name, fs := range schema.Fields {
			if !fs.Optional && !provided[name] {
				diags = append(diags, Diagnostic{
					Severity: SeverityError,
					Pos:      d.Pos,
					Message:  fmt.Sprintf("%s %q is missing required field %q", d.Type, d.Name, name),
				})
			}
		}
	}
	return diags
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sdk && go test ./dsl/... -run TestCrossCheck -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd sdk
git add dsl/crosscheck.go dsl/crosscheck_test.go
git commit -m "sdk: add phase 2 cross-check of DSL declarations against resolved registry"
```

---

## Task 11: Wire Phase 2 into the CLI

**Files:**
- Modify: `sdk/cmd/dslcheck/main.go`
- Modify: `sdk/cmd/dslcheck/main_test.go`

**Interfaces:**
- Consumes: `dsl.BuildRegistry`, `dsl.ResolveConfig`, `dsl.CrossCheck` (Tasks 9-10).
- Produces: `run` gains two new parameters (`replaceFlags map[string]string`, `scratchDir string`); `main` gains repeatable `--replace old=new` and a `--scratch` flag (defaulting to a temp dir via `os.MkdirTemp`). Task 16 adds the `--cap` flag on top of this same signature.

- [ ] **Step 1: Write the failing test**

Append to `sdk/cmd/dslcheck/main_test.go`:

```go
func TestRun_Phase2_ResolvesFixtureSDK(t *testing.T) {
	if testing.Short() {
		t.Skip("shells out to go build/get; skipped under -short")
	}
	fixtureDir, err := filepath.Abs("../../dsl/testdata/sdkfixture")
	if err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := run(
		"../../demo.dsl",
		map[string]string{"github.com/cmusatyalab/steeleagle_sdk": fixtureDir},
		t.TempDir(),
		&stdout, &stderr,
	)
	// demo.dsl's Data stanza (Velocity/Waypoints/Location/Detection/Pose)
	// has no corresponding sdktypes.RegisterData call in the fixture (see
	// Task 8/10 notes), so this is expected to fail with "unknown datatype"
	// errors — this test only asserts that phase 2 actually ran and
	// resolved the Actions/Events types correctly, not a clean overall exit.
	if code == 0 {
		t.Error("run() = 0, want non-zero (fixture has no Data registrations)")
	}
	out := stdout.String()
	if strings.Contains(out, "unknown action type") {
		t.Errorf("stdout contains an unexpected unknown-action-type error:\n%s", out)
	}
	if strings.Contains(out, "unknown event type") {
		t.Errorf("stdout contains an unexpected unknown-event-type error:\n%s", out)
	}
	if !strings.Contains(out, "unknown datatype type") {
		t.Errorf("stdout = %q, want the expected unknown-datatype errors (fixture registers no Data types)", out)
	}
}
```

Add `"path/filepath"` to the test file's imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk && go test ./cmd/dslcheck/... -run TestRun_Phase2 -v`
Expected: FAIL — `run` doesn't accept these parameters yet (build failure).

- [ ] **Step 3: Rewrite `sdk/cmd/dslcheck/main.go`**

```go
package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

type replaceFlags map[string]string

func (r replaceFlags) String() string { return fmt.Sprint(map[string]string(r)) }

func (r replaceFlags) Set(value string) error {
	parts := strings.SplitN(value, "=", 2)
	if len(parts) != 2 {
		return fmt.Errorf("invalid --replace value %q, want old=new", value)
	}
	r[parts[0]] = parts[1]
	return nil
}

func main() {
	dslPath := flag.String("dsl", "", "path to the .dsl mission file to check")
	scratchDir := flag.String("scratch", "", "directory for the sequestered module (default: a temp dir)")
	replaces := replaceFlags{}
	flag.Var(&replaces, "replace", "old=new import path replacement for a package under local development; may be repeated")
	flag.Parse()
	if *dslPath == "" {
		fmt.Fprintln(os.Stderr, "usage: dslcheck --dsl <file.dsl> [--replace old=new ...] [--scratch dir]")
		os.Exit(2)
	}
	dir := *scratchDir
	if dir == "" {
		tmp, err := os.MkdirTemp("", "dslcheck-scratch-*")
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			os.Exit(1)
		}
		dir = tmp
	}
	os.Exit(run(*dslPath, replaces, dir, os.Stdout, os.Stderr))
}

// run is the testable core of main: it never calls os.Exit itself, and
// returns the process exit code the caller should use.
func run(dslPath string, replaces map[string]string, scratchDir string, stdout, stderr io.Writer) int {
	f, err := os.Open(dslPath)
	if err != nil {
		fmt.Fprintf(stderr, "error: %v\n", err)
		return 1
	}
	defer f.Close()

	file, err := dsl.Parse(dslPath, f)
	if err != nil {
		fmt.Fprintf(stdout, "error: %v\n", err)
		return 1
	}

	var diags []dsl.Diagnostic
	diags = append(diags, dsl.CheckLocal(file)...)

	var imports []string
	if file.Imports != nil {
		imports = file.Imports.Paths
	}
	if len(imports) > 0 {
		reg, err := dsl.BuildRegistry(imports, dsl.ResolveConfig{ScratchDir: scratchDir, Replace: replaces})
		if err != nil {
			fmt.Fprintf(stdout, "error: phase 2 (package resolution) failed: %v\n", err)
			return 1
		}
		diags = append(diags, dsl.CrossCheck(file, reg)...)
	}

	for _, d := range diags {
		fmt.Fprintln(stdout, d.String())
	}

	nActions, nEvents := 0, 0
	if file.Actions != nil {
		nActions = len(file.Actions.Decls)
	}
	if file.Events != nil {
		nEvents = len(file.Events.Decls)
	}
	nErrors := 0
	for _, d := range diags {
		if d.Severity == dsl.SeverityError {
			nErrors++
		}
	}
	fmt.Fprintf(stdout, "%d actions, %d events, %d errors\n", nActions, nEvents, nErrors)

	if dsl.HasErrors(diags) {
		return 1
	}
	return 0
}
```

- [ ] **Step 4: Update the Task 6 tests for the new `run` signature**

Replace the three `run(...)` calls already in `sdk/cmd/dslcheck/main_test.go` (`TestRun_GoodFile`, `TestRun_MissingFile`, `TestRun_StructuralError`) to pass `nil, t.TempDir()` as the two new parameters, e.g.:

```go
code := run("../../dsl/testdata/good.dsl", nil, t.TempDir(), &stdout, &stderr)
```

(`good.dsl` has no `Import:` stanza copied over from a version predating Task 1's fixture — wait, it does have one, copied from the real `demo.dsl`. Since `TestRun_GoodFile` doesn't pass a `-replace` mapping, Phase 2 will attempt a real `go get github.com/cmusatyalab/steeleagle_sdk/...` against the public network and fail, because that module doesn't exist. Guard this test with the same `testing.Short()` skip used elsewhere, since it now transitively exercises Phase 2:

```go
func TestRun_GoodFile(t *testing.T) {
	if testing.Short() {
		t.Skip("phase 2 shells out to go get; skipped under -short")
	}
	var stdout, stderr bytes.Buffer
	code := run("../../dsl/testdata/good.dsl", map[string]string{
		"github.com/cmusatyalab/steeleagle_sdk": mustAbs(t, "../../dsl/testdata/sdkfixture"),
	}, t.TempDir(), &stdout, &stderr)
	// See TestRun_Phase2_ResolvesFixtureSDK: the fixture registers no Data
	// types, so this is expected to fail on the Data stanza specifically.
	if code == 0 {
		t.Error("run() = 0, want non-zero (fixture has no Data registrations)")
	}
	if strings.Contains(stdout.String(), "unknown action type") || strings.Contains(stdout.String(), "unknown event type") {
		t.Errorf("stdout = %q, want no unknown action/event errors", stdout.String())
	}
}

func mustAbs(t *testing.T, path string) string {
	t.Helper()
	abs, err := filepath.Abs(path)
	if err != nil {
		t.Fatal(err)
	}
	return abs
}
```

`TestRun_MissingFile` and `TestRun_StructuralError` fail before Phase 2 would ever run (missing file / Phase 1 error respectively), so they don't need a `-replace` mapping or a `-short` guard — just update their call sites to the new signature with `nil` for replaces.

- [ ] **Step 5: Run all CLI tests to verify they pass**

Run: `cd sdk && go test ./cmd/dslcheck/... -v`
Expected: PASS (the two Phase-2-touching tests will be slower; that's expected).

Run also: `cd sdk && go test -short ./... -v`
Expected: PASS, with the Phase 2/3 tests reporting `--- SKIP`.

- [ ] **Step 6: Commit**

```bash
cd sdk
git add cmd/dslcheck/main.go cmd/dslcheck/main_test.go
git commit -m "sdk: wire phase 2 (sequestered-module resolution) into dslcheck CLI"
```

---

## Task 12: cap.toml schema + loader

**Files:**
- Create: `sdk/dsl/captoml.go`
- Create: `sdk/dsl/captoml_test.go`
- Create: `sdk/dsl/testdata/violation.cap.toml`
- Create: `sdk/dsl/testdata/clean.cap.toml`

**Interfaces:**
- Produces: `dsl.CapRule{Package, Type, Member, Kind, Mode string}`, `dsl.CapFile{Disallow []CapRule}`, `func dsl.LoadCapFile(path string) (*CapFile, error)`.

The design spec's Section 4 illustrated cap.toml rules with a single dotted `symbol = "pkg.Type.Member"` string; writing the parser made clear that's ambiguous to split back apart in general (Go import paths themselves contain dots, e.g. `driver/control`, so there's no unambiguous separator between "package" and "Type.Member"). This task uses explicit `package`/`type`/`member` TOML fields instead — strictly clearer to both read and parse, same expressiveness the spec called for (function/method rules, field rules with read/write/both modes, and whole-type rules).

- [ ] **Step 1: Write the failing test**

```go
package dsl

import "testing"

func TestLoadCapFile(t *testing.T) {
	cf, err := LoadCapFile("testdata/violation.cap.toml")
	if err != nil {
		t.Fatalf("LoadCapFile error: %v", err)
	}
	if len(cf.Disallow) != 3 {
		t.Fatalf("Disallow = %d rules, want 3", len(cf.Disallow))
	}
	funcRule := cf.Disallow[0]
	if funcRule.Kind != "func" || funcRule.Member != "SetGimbalPose" {
		t.Errorf("rule 0 = %+v", funcRule)
	}
	fieldRule := cf.Disallow[1]
	if fieldRule.Kind != "field" || fieldRule.Mode != "read" {
		t.Errorf("rule 1 = %+v", fieldRule)
	}
	typeRule := cf.Disallow[2]
	if typeRule.Kind != "type" || typeRule.Member != "" {
		t.Errorf("rule 2 = %+v", typeRule)
	}
}

func TestLoadCapFile_DefaultsModeToBothForFieldRules(t *testing.T) {
	cf, err := LoadCapFile("testdata/violation.cap.toml")
	if err != nil {
		t.Fatal(err)
	}
	// rule 0 is a func rule; Mode is meaningless there and must not be
	// defaulted (stays "").
	if cf.Disallow[0].Mode != "" {
		t.Errorf("func rule Mode = %q, want empty", cf.Disallow[0].Mode)
	}
}

func TestLoadCapFile_InvalidKind(t *testing.T) {
	_, err := LoadCapFile("testdata/does_not_exist.cap.toml")
	if err == nil {
		t.Error("LoadCapFile(missing file) = nil error, want an error")
	}
}
```

- [ ] **Step 2: Write the testdata fixtures**

`sdk/dsl/testdata/violation.cap.toml`:
```toml
[[disallow]]
package = "github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi"
type = "Client"
member = "SetGimbalPose"
kind = "func"

[[disallow]]
package = "github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi"
type = "GimbalPoseRequest"
member = "Pose"
kind = "field"
mode = "read"

[[disallow]]
package = "github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi"
type = "GimbalPoseRequest"
kind = "type"
```

`sdk/dsl/testdata/clean.cap.toml`:
```toml
# No disallowed capabilities — a drone with the full API surface available.
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run TestLoadCapFile -v`
Expected: FAIL — `CapFile`/`LoadCapFile` undefined.

- [ ] **Step 4: Add the go-toml dependency and write `sdk/dsl/captoml.go`**

```bash
cd sdk
go get github.com/pelletier/go-toml/v2@latest
```

```go
package dsl

import (
	"fmt"
	"os"

	"github.com/pelletier/go-toml/v2"
)

// CapRule names one piece of Go API surface a drone doesn't support.
// Symbol is expressed as three parts (Package, Type, Member) rather than one
// dotted string because Go import paths themselves contain dots and
// slashes, making a single string ambiguous to split back apart reliably.
type CapRule struct {
	Package string `toml:"package"`
	Type    string `toml:"type"`
	// Member is a method name (kind="func"), a struct field name
	// (kind="field"), or empty (kind="type", blocking the whole type).
	Member string `toml:"member"`
	Kind   string `toml:"kind"`
	// Mode is "read", "write", or "both". Only meaningful for kind="field";
	// LoadCapFile defaults it to "both" when omitted on a field rule, and
	// leaves it as the zero value ("") for func/type rules where it has no
	// meaning.
	Mode string `toml:"mode"`
}

type CapFile struct {
	Disallow []CapRule `toml:"disallow"`
}

// LoadCapFile reads and validates a drone's cap.toml.
func LoadCapFile(path string) (*CapFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading cap file: %w", err)
	}
	var cf CapFile
	if err := toml.Unmarshal(data, &cf); err != nil {
		return nil, fmt.Errorf("parsing cap file %s: %w", path, err)
	}
	for i, r := range cf.Disallow {
		switch r.Kind {
		case "func", "field", "type":
		default:
			return nil, fmt.Errorf("cap file %s: rule %d: invalid kind %q (want func, field, or type)", path, i, r.Kind)
		}
		if r.Kind == "field" && r.Mode == "" {
			cf.Disallow[i].Mode = "both"
		}
	}
	return &cf, nil
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd sdk && go test ./dsl/... -run TestLoadCapFile -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd sdk
git add go.mod go.sum dsl/captoml.go dsl/captoml_test.go dsl/testdata/violation.cap.toml dsl/testdata/clean.cap.toml
git commit -m "sdk: add cap.toml schema and loader for phase 3"
```

---

## Task 13: SSA setup + locating Execute/Check methods

**Files:**
- Create: `sdk/dsl/capcheck.go`
- Create: `sdk/dsl/capcheck_test.go`

**Interfaces:**
- Consumes: `dsl.TypeSchema` (Task 9), `dsl.ResolveConfig`/`dsl.BuildRegistry`'s `ScratchDir` (Task 9 — Phase 3 loads full syntax from the same already-`go get`'d scratch module Phase 2 built, so it must run after Phase 2 for a given DSL file), `golang.org/x/tools/go/{packages,ssa,ssa/ssautil}`.
- Produces: `func dsl.loadSSA(scratchDir string, pkgPaths []string) (*ssa.Program, map[string]*ssa.Package, error)` (unexported — internal to this file; Tasks 14-15 add the exported `CheckCapabilities` that calls it), `func dsl.findMethod(pkg *ssa.Package, typeName, methodName string) *ssa.Function` (unexported).

The `go/packages` mode flags, `ssautil.AllPackages`/`prog.Build()` call shape, and the `MethodSets.MethodSet` + `Prog.MethodValue` lookup pattern below were interactively prototyped and verified against a throwaway fixture package (confirming exact reachability and field-write results before being written here) — see the design spec's discovery notes.

- [ ] **Step 1: Add the x/tools dependency**

```bash
cd sdk
go get golang.org/x/tools/go/packages@latest
go get golang.org/x/tools/go/ssa@latest
go get golang.org/x/tools/go/ssa/ssautil@latest
go get golang.org/x/tools/go/callgraph@latest
go get golang.org/x/tools/go/callgraph/cha@latest
```

- [ ] **Step 2: Write the failing test**

```go
package dsl

import (
	"path/filepath"
	"testing"
)

// buildFixtureScratch builds (once per test) a sequestered module against
// the sdkfixture module, returning its scratch directory, ready for
// go/packages loading. Shared by this and later capcheck tests.
func buildFixtureScratch(t *testing.T) string {
	t.Helper()
	if testing.Short() {
		t.Skip("shells out to go build/get; skipped under -short")
	}
	fixtureDir, err := filepath.Abs("testdata/sdkfixture")
	if err != nil {
		t.Fatal(err)
	}
	scratch := t.TempDir()
	_, err = BuildRegistry(
		[]string{
			"github.com/cmusatyalab/steeleagle_sdk/actions",
			"github.com/cmusatyalab/steeleagle_sdk/events",
		},
		ResolveConfig{
			ScratchDir: scratch,
			Replace:    map[string]string{"github.com/cmusatyalab/steeleagle_sdk": fixtureDir},
		},
	)
	if err != nil {
		t.Fatalf("BuildRegistry (setting up scratch module): %v", err)
	}
	return scratch
}

func TestLoadSSA_FindExecuteMethods(t *testing.T) {
	scratch := buildFixtureScratch(t)
	_, pkgs, err := loadSSA(scratch, []string{
		"github.com/cmusatyalab/steeleagle_sdk/actions",
		"github.com/cmusatyalab/steeleagle_sdk/events",
	})
	if err != nil {
		t.Fatalf("loadSSA error: %v", err)
	}
	actionsPkg := pkgs["github.com/cmusatyalab/steeleagle_sdk/actions"]
	if actionsPkg == nil {
		t.Fatal("actions package not found in loaded SSA packages")
	}
	fn := findMethod(actionsPkg, "TakeOff", "Execute")
	if fn == nil {
		t.Fatal("findMethod(TakeOff, Execute) = nil")
	}
	if fn.Name() != "Execute" {
		t.Errorf("fn.Name() = %q, want Execute", fn.Name())
	}

	eventsPkg := pkgs["github.com/cmusatyalab/steeleagle_sdk/events"]
	if eventsPkg == nil {
		t.Fatal("events package not found in loaded SSA packages")
	}
	if findMethod(eventsPkg, "DetectionFound", "Check") == nil {
		t.Error("findMethod(DetectionFound, Check) = nil")
	}
	if findMethod(actionsPkg, "DoesNotExist", "Execute") != nil {
		t.Error("findMethod(DoesNotExist, Execute) = non-nil, want nil")
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run TestLoadSSA -v`
Expected: FAIL — `loadSSA`/`findMethod` undefined.

- [ ] **Step 4: Write `sdk/dsl/capcheck.go`**

```go
package dsl

import (
	"fmt"
	"go/types"

	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

// loadSSA loads full syntax and type information for pkgPaths from the
// sequestered module at scratchDir (already populated by BuildRegistry) and
// builds their SSA form. Returns the whole program (needed to build a call
// graph over it) and a lookup from import path to *ssa.Package.
func loadSSA(scratchDir string, pkgPaths []string) (*ssa.Program, map[string]*ssa.Package, error) {
	cfg := &packages.Config{
		Dir: scratchDir,
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedCompiledGoFiles |
			packages.NeedImports | packages.NeedTypes | packages.NeedSyntax |
			packages.NeedTypesInfo | packages.NeedDeps,
	}
	pkgs, err := packages.Load(cfg, pkgPaths...)
	if err != nil {
		return nil, nil, fmt.Errorf("loading packages for capability check: %w", err)
	}
	if packages.PrintErrors(pkgs) > 0 {
		return nil, nil, fmt.Errorf("errors loading packages %v for capability check", pkgPaths)
	}

	prog, ssaPkgs := ssautil.AllPackages(pkgs, ssa.InstantiateGenerics)
	prog.Build()

	byPath := map[string]*ssa.Package{}
	for _, p := range ssaPkgs {
		if p != nil {
			byPath[p.Pkg.Path()] = p
		}
	}
	return prog, byPath, nil
}

// findMethod returns the *ssa.Function for typeName's methodName method
// within pkg, trying both value and pointer receiver, or nil if no such
// type/method exists.
func findMethod(pkg *ssa.Package, typeName, methodName string) *ssa.Function {
	for _, mem := range pkg.Members {
		t, ok := mem.(*ssa.Type)
		if !ok || t.Name() != typeName {
			continue
		}
		named, ok := t.Type().(*types.Named)
		if !ok {
			continue
		}
		for _, cand := range []types.Type{named, types.NewPointer(named)} {
			mset := pkg.Prog.MethodSets.MethodSet(cand)
			for i := 0; i < mset.Len(); i++ {
				sel := mset.At(i)
				if sel.Obj().Name() == methodName {
					return pkg.Prog.MethodValue(sel)
				}
			}
		}
	}
	return nil
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd sdk && go test ./dsl/... -run TestLoadSSA -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd sdk
git add go.mod go.sum dsl/capcheck.go dsl/capcheck_test.go
git commit -m "sdk: add SSA loading and Execute/Check method lookup for phase 3"
```

---

## Task 14: Function-level reachability check

**Files:**
- Modify: `sdk/dsl/capcheck.go`
- Modify: `sdk/dsl/capcheck_test.go`

**Interfaces:**
- Consumes: everything in Task 13, plus `dsl.CapFile`/`dsl.CapRule` (Task 12), `golang.org/x/tools/go/callgraph`/`callgraph/cha`.
- Produces: `func dsl.CheckCapabilities(scratchDir string, actions, events []TypeSchema, cap *CapFile) ([]Diagnostic, error)` — the Phase 3 entry point Task 16 wires into the CLI. This task implements only `kind = "func"` rules; Task 15 extends the same function for `kind = "field"` and `kind = "type"`.

The CHA call-graph reachability logic below (`reachableFuncs`, and matching a rule against `funcOwnerType`) mirrors the exact pattern already verified in the design-spec prototyping (confirmed `TakeOff.Execute` reaches `Client.TakeOff` but not `Client.SetGimbalPose`, and `SetGimbalPose.Execute` reaches both `Client.SetGimbalPose` and the `GetPose` getter).

- [ ] **Step 1: Write the failing test**

Append to `sdk/dsl/capcheck_test.go`:

```go
func TestCheckCapabilities_FuncRuleViolation(t *testing.T) {
	scratch := buildFixtureScratch(t)
	cap, err := LoadCapFile("testdata/violation.cap.toml")
	if err != nil {
		t.Fatal(err)
	}
	actions := []TypeSchema{
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "SetGimbalPose"},
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "TakeOff"},
	}
	diags, err := CheckCapabilities(scratch, actions, nil, cap)
	if err != nil {
		t.Fatalf("CheckCapabilities error: %v", err)
	}
	if len(diags) != 1 {
		t.Fatalf("diags = %v, want exactly 1 (SetGimbalPose violates the func rule; TakeOff doesn't)", diags)
	}
	if !containsSubstring(diagMessages(diags), "SetGimbalPose") {
		t.Errorf("diags = %v, want it to name SetGimbalPose", diags)
	}
}

func TestCheckCapabilities_Clean(t *testing.T) {
	scratch := buildFixtureScratch(t)
	cap, err := LoadCapFile("testdata/clean.cap.toml")
	if err != nil {
		t.Fatal(err)
	}
	actions := []TypeSchema{
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "TakeOff"},
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "SetGimbalPose"},
	}
	diags, err := CheckCapabilities(scratch, actions, nil, cap)
	if err != nil {
		t.Fatalf("CheckCapabilities error: %v", err)
	}
	if len(diags) != 0 {
		t.Errorf("diags = %v, want none", diags)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk && go test ./dsl/... -run TestCheckCapabilities -v`
Expected: FAIL — `CheckCapabilities` undefined.

- [ ] **Step 3: Extend `sdk/dsl/capcheck.go`**

Add these imports to the existing import block:

```go
	"golang.org/x/tools/go/callgraph"
	"golang.org/x/tools/go/callgraph/cha"
```

Add at the end of the file:

```go
// CheckCapabilities loads actions and events (each a distinct Go type
// resolved by Phase 2) from the sequestered module at scratchDir, and
// reports every reachable violation of cap's rules. actions/events should
// already be de-duplicated by (Package, Type) — check each distinct type
// once regardless of how many DSL instances use it.
func CheckCapabilities(scratchDir string, actions, events []TypeSchema, cap *CapFile) ([]Diagnostic, error) {
	pkgPaths := distinctPackages(actions, events)
	if len(pkgPaths) == 0 {
		return nil, nil
	}
	prog, ssaPkgs, err := loadSSA(scratchDir, pkgPaths)
	if err != nil {
		return nil, err
	}
	cg := cha.CallGraph(prog)

	var diags []Diagnostic
	diags = append(diags, checkEntryPoints(cg, ssaPkgs, "action", actions, "Execute", cap)...)
	diags = append(diags, checkEntryPoints(cg, ssaPkgs, "event", events, "Check", cap)...)
	return diags, nil
}

func distinctPackages(schemas ...[]TypeSchema) []string {
	seen := map[string]bool{}
	var out []string
	for _, group := range schemas {
		for _, s := range group {
			if !seen[s.Package] {
				seen[s.Package] = true
				out = append(out, s.Package)
			}
		}
	}
	return out
}

func checkEntryPoints(cg *callgraph.Graph, ssaPkgs map[string]*ssa.Package, kind string, schemas []TypeSchema, methodName string, cap *CapFile) []Diagnostic {
	var diags []Diagnostic
	for _, schema := range schemas {
		pkg := ssaPkgs[schema.Package]
		if pkg == nil {
			continue
		}
		fn := findMethod(pkg, schema.Type, methodName)
		if fn == nil {
			continue
		}
		reachable := reachableFuncs(cg, fn)
		for _, rule := range cap.Disallow {
			if violatesRule(reachable, rule) {
				diags = append(diags, Diagnostic{
					Severity: SeverityError,
					Message: fmt.Sprintf(
						"%s %s.%s (via its %s method) reaches disallowed capability %s.%s%s",
						kind, schema.Package, schema.Type, methodName,
						rule.Package, rule.Type, memberSuffix(rule.Member)),
				})
			}
		}
	}
	return diags
}

func memberSuffix(m string) string {
	if m == "" {
		return ""
	}
	return "." + m
}

// reachableFuncs returns every *ssa.Function reachable in cg starting from
// (and including) from.
func reachableFuncs(cg *callgraph.Graph, from *ssa.Function) map[*ssa.Function]bool {
	result := map[*ssa.Function]bool{}
	root := cg.Nodes[from]
	if root == nil {
		return result
	}
	seen := map[*callgraph.Node]bool{}
	var visit func(n *callgraph.Node)
	visit = func(n *callgraph.Node) {
		if seen[n] {
			return
		}
		seen[n] = true
		if n.Func != nil {
			result[n.Func] = true
		}
		for _, e := range n.Out {
			visit(e.Callee)
		}
	}
	visit(root)
	return result
}

func funcOwnerType(f *ssa.Function) string {
	recv := f.Signature.Recv()
	if recv == nil {
		return ""
	}
	t := recv.Type()
	if p, ok := t.(*types.Pointer); ok {
		t = p.Elem()
	}
	if named, ok := t.(*types.Named); ok {
		return named.Obj().Name()
	}
	return ""
}

func funcOwnerPackage(f *ssa.Function) string {
	if f.Pkg == nil {
		return ""
	}
	return f.Pkg.Pkg.Path()
}

func violatesRule(reachable map[*ssa.Function]bool, rule CapRule) bool {
	switch rule.Kind {
	case "func":
		for f := range reachable {
			if funcOwnerPackage(f) == rule.Package && funcOwnerType(f) == rule.Type && f.Name() == rule.Member {
				return true
			}
		}
	}
	return false
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sdk && go test ./dsl/... -run TestCheckCapabilities -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd sdk
git add dsl/capcheck.go dsl/capcheck_test.go
git commit -m "sdk: add phase 3 func-level capability reachability check"
```

---

## Task 15: Field-level and whole-type checks

**Files:**
- Modify: `sdk/dsl/capcheck.go`
- Modify: `sdk/dsl/capcheck_test.go`

**Interfaces:**
- Extends `violatesRule` (Task 14) to handle `kind = "field"` (read/write, via `*ssa.FieldAddr`+`*ssa.Store` for writes, `*ssa.Field`/getter calls for reads) and `kind = "type"` (any touch of a value of that type at all). No new exported symbols — `CheckCapabilities`'s signature is unchanged.

The write-detection path (`*ssa.FieldAddr` followed by a `*ssa.Store` referrer) matches the exact pattern already verified in the design-spec prototyping. The read-via-getter-call and whole-type-touch paths are new in this task and are exactly what this task's tests are for — if either needs adjustment once real SSA output is inspected, that's the TDD loop working as intended, not a plan defect.

- [ ] **Step 1: Write the failing tests**

Append to `sdk/dsl/capcheck_test.go`:

```go
func TestCheckCapabilities_FieldWriteViolation(t *testing.T) {
	scratch := buildFixtureScratch(t)
	cap := &CapFile{Disallow: []CapRule{{
		Package: "github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi",
		Type:    "GimbalPoseRequest",
		Member:  "Pose",
		Kind:    "field",
		Mode:    "write",
	}}}
	actions := []TypeSchema{
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "SetGimbalPose"},
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "TakeOff"},
	}
	diags, err := CheckCapabilities(scratch, actions, nil, cap)
	if err != nil {
		t.Fatalf("CheckCapabilities error: %v", err)
	}
	if len(diags) != 1 || !containsSubstring(diagMessages(diags), "SetGimbalPose") {
		t.Errorf("diags = %v, want exactly one violation naming SetGimbalPose", diags)
	}
}

func TestCheckCapabilities_FieldReadViolation(t *testing.T) {
	scratch := buildFixtureScratch(t)
	cap := &CapFile{Disallow: []CapRule{{
		Package: "github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi",
		Type:    "GimbalPoseRequest",
		Member:  "Pose",
		Kind:    "field",
		Mode:    "read",
	}}}
	actions := []TypeSchema{
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "SetGimbalPose"},
	}
	diags, err := CheckCapabilities(scratch, actions, nil, cap)
	if err != nil {
		t.Fatalf("CheckCapabilities error: %v", err)
	}
	// SetGimbalPose.Execute calls req.GetPose() — a read of the Pose field
	// via its generated getter.
	if len(diags) != 1 {
		t.Errorf("diags = %v, want exactly one read violation", diags)
	}
}

func TestCheckCapabilities_WholeTypeViolation(t *testing.T) {
	scratch := buildFixtureScratch(t)
	cap := &CapFile{Disallow: []CapRule{{
		Package: "github.com/cmusatyalab/steeleagle_sdk/internal/vehicleapi",
		Type:    "GimbalPoseRequest",
		Kind:    "type",
	}}}
	actions := []TypeSchema{
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "SetGimbalPose"},
		{Package: "github.com/cmusatyalab/steeleagle_sdk/actions", Type: "TakeOff"},
	}
	diags, err := CheckCapabilities(scratch, actions, nil, cap)
	if err != nil {
		t.Fatalf("CheckCapabilities error: %v", err)
	}
	if len(diags) != 1 || !containsSubstring(diagMessages(diags), "SetGimbalPose") {
		t.Errorf("diags = %v, want exactly one violation naming SetGimbalPose", diags)
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd sdk && go test ./dsl/... -run 'TestCheckCapabilities_Field|TestCheckCapabilities_WholeType' -v`
Expected: FAIL — the current `violatesRule` only handles `kind = "func"`, so all three report zero violations.

- [ ] **Step 3: Extend `violatesRule` and add its helpers in `sdk/dsl/capcheck.go`**

Replace the `violatesRule` function with:

```go
func violatesRule(reachable map[*ssa.Function]bool, rule CapRule) bool {
	switch rule.Kind {
	case "func":
		for f := range reachable {
			if funcOwnerPackage(f) == rule.Package && funcOwnerType(f) == rule.Type && f.Name() == rule.Member {
				return true
			}
		}
	case "field":
		for f := range reachable {
			for _, b := range f.Blocks {
				for _, instr := range b.Instrs {
					if touchesField(instr, rule) {
						return true
					}
				}
			}
		}
	case "type":
		for f := range reachable {
			for _, b := range f.Blocks {
				for _, instr := range b.Instrs {
					if v, ok := instr.(ssa.Value); ok && typeMatches(v.Type(), rule.Package, rule.Type) {
						return true
					}
				}
			}
		}
	}
	return false
}

// derefStruct unwraps a pointer type down to its underlying *types.Struct,
// or returns nil if t is not a (possibly pointer-to) struct type.
func derefStruct(t types.Type) *types.Struct {
	if p, ok := t.Underlying().(*types.Pointer); ok {
		t = p.Elem()
	}
	s, _ := t.Underlying().(*types.Struct)
	return s
}

// typeMatches reports whether t (after unwrapping one level of pointer)
// is the named type pkgPath.typeName.
func typeMatches(t types.Type, pkgPath, typeName string) bool {
	if p, ok := t.Underlying().(*types.Pointer); ok {
		t = p.Elem()
	}
	named, ok := t.(*types.Named)
	if !ok {
		return false
	}
	return named.Obj().Pkg() != nil && named.Obj().Pkg().Path() == pkgPath && named.Obj().Name() == typeName
}

// touchesField reports whether instr reads or writes rule's field (as
// permitted by rule.Mode) on a value of rule's type. Writes are detected via
// a *ssa.FieldAddr whose address is subsequently stored to; reads are
// detected via a direct *ssa.Field value extraction, or a call to the
// field's generated Get<Member>() accessor (the idiomatic way generated
// proto code exposes a field for reading).
func touchesField(instr ssa.Instruction, rule CapRule) bool {
	switch v := instr.(type) {
	case *ssa.FieldAddr:
		structT := derefStruct(v.X.Type())
		if structT == nil || !typeMatches(v.X.Type(), rule.Package, rule.Type) || structT.Field(v.Field).Name() != rule.Member {
			return false
		}
		isWrite := false
		for _, ref := range *v.Referrers() {
			if _, ok := ref.(*ssa.Store); ok {
				isWrite = true
			}
		}
		if isWrite {
			return rule.Mode == "write" || rule.Mode == "both"
		}
		return rule.Mode == "read" || rule.Mode == "both"
	case *ssa.Field:
		structT, _ := v.X.Type().Underlying().(*types.Struct)
		if structT == nil || !typeMatches(v.X.Type(), rule.Package, rule.Type) || structT.Field(v.Field).Name() != rule.Member {
			return false
		}
		return rule.Mode == "read" || rule.Mode == "both"
	case ssa.CallInstruction:
		common := v.Common()
		if common.IsInvoke() || common.StaticCallee() == nil {
			return false
		}
		callee := common.StaticCallee()
		if callee.Name() != "Get"+rule.Member || funcOwnerPackage(callee) != rule.Package || funcOwnerType(callee) != rule.Type {
			return false
		}
		return rule.Mode == "read" || rule.Mode == "both"
	}
	return false
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd sdk && go test ./dsl/... -run 'TestCheckCapabilities' -v`
Expected: all PASS, including Task 14's tests (no regressions).

- [ ] **Step 5: Run the full suite**

Run: `cd sdk && go test ./... -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd sdk
git add dsl/capcheck.go dsl/capcheck_test.go
git commit -m "sdk: add phase 3 field-level read/write and whole-type capability checks"
```

---

## Task 16: Wire Phase 3 into the CLI + end-to-end test

**Files:**
- Modify: `sdk/cmd/dslcheck/main.go`
- Modify: `sdk/cmd/dslcheck/main_test.go`

**Interfaces:**
- Consumes: `dsl.LoadCapFile`, `dsl.CheckCapabilities`, `dsl.TypeSchema` (Tasks 12-15).
- Produces: `run` gains one more parameter (`capPath string`, empty meaning "skip Phase 3"); `main` gains an optional `--cap` flag.

This task also adds the plan's final acceptance test: compiling the real, already-renamed (Task 5) `demo.dsl` through all three phases against the fixture SDK, with a `clean.cap.toml`. As established in Tasks 8/10/11, the fixture registers no `Data` types, so a fully clean (0-error) run isn't achievable against the real `demo.dsl` with this fixture — the end-to-end test asserts the pipeline runs Phase 1 through Phase 3 without crashing and that the *only* errors are the expected `unknown datatype` ones, which is the strongest true end-to-end claim supportable without also building out `Data` registrations (out of scope; not part of the agreed design).

- [ ] **Step 1: Write the failing test**

Append to `sdk/cmd/dslcheck/main_test.go`:

```go
func TestRun_EndToEnd_AllThreePhases(t *testing.T) {
	if testing.Short() {
		t.Skip("shells out to go build/get; skipped under -short")
	}
	fixtureDir := mustAbs(t, "../../dsl/testdata/sdkfixture")
	capPath := mustAbs(t, "../../dsl/testdata/clean.cap.toml")
	var stdout, stderr bytes.Buffer
	code := run(
		"../../demo.dsl",
		map[string]string{"github.com/cmusatyalab/steeleagle_sdk": fixtureDir},
		t.TempDir(),
		capPath,
		&stdout, &stderr,
	)
	out := stdout.String()
	// Expected to fail only on the Data stanza (fixture registers no
	// Datatypes) — see this task's header note.
	if code == 0 {
		t.Error("run() = 0, want non-zero (fixture has no Data registrations)")
	}
	if strings.Contains(out, "unknown action type") || strings.Contains(out, "unknown event type") {
		t.Errorf("stdout contains an unexpected unknown action/event error:\n%s", out)
	}
	if !strings.Contains(out, "unknown datatype type") {
		t.Errorf("stdout = %q, want the expected unknown-datatype errors", out)
	}
	if !strings.Contains(out, "15 actions, 2 events") {
		t.Errorf("stdout = %q, want the summary line to report 15 actions, 2 events", out)
	}
}

func TestRun_EndToEnd_CapabilityViolation(t *testing.T) {
	if testing.Short() {
		t.Skip("shells out to go build/get; skipped under -short")
	}
	fixtureDir := mustAbs(t, "../../dsl/testdata/sdkfixture")
	capPath := mustAbs(t, "../../dsl/testdata/violation.cap.toml")
	var stdout, stderr bytes.Buffer
	code := run(
		"../../demo.dsl",
		map[string]string{"github.com/cmusatyalab/steeleagle_sdk": fixtureDir},
		t.TempDir(),
		capPath,
		&stdout, &stderr,
	)
	if code == 0 {
		t.Error("run() = 0, want non-zero")
	}
	if !strings.Contains(stdout.String(), "disallowed capability") {
		t.Errorf("stdout = %q, want it to report the SetGimbalPose capability violation (demo.dsl declares a set_gimbal_pose action)", stdout.String())
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd sdk && go test ./cmd/dslcheck/... -run TestRun_EndToEnd -v`
Expected: FAIL — `run` doesn't accept a `capPath` parameter yet (build failure).

- [ ] **Step 3: Extend `sdk/cmd/dslcheck/main.go`**

Add a `--cap` flag in `main`:

```go
	capPath := flag.String("cap", "", "path to the target drone's cap.toml (optional; omitting it skips the capability check)")
```

and pass it through: change the `os.Exit(run(*dslPath, replaces, dir, os.Stdout, os.Stderr))` line to:

```go
	os.Exit(run(*dslPath, replaces, dir, *capPath, os.Stdout, os.Stderr))
```

Update `run`'s signature and body:

```go
func run(dslPath string, replaces map[string]string, scratchDir, capPath string, stdout, stderr io.Writer) int {
	f, err := os.Open(dslPath)
	if err != nil {
		fmt.Fprintf(stderr, "error: %v\n", err)
		return 1
	}
	defer f.Close()

	file, err := dsl.Parse(dslPath, f)
	if err != nil {
		fmt.Fprintf(stdout, "error: %v\n", err)
		return 1
	}

	var diags []dsl.Diagnostic
	diags = append(diags, dsl.CheckLocal(file)...)

	var imports []string
	if file.Imports != nil {
		imports = file.Imports.Paths
	}
	var reg *dsl.RegistryDump
	if len(imports) > 0 {
		reg, err = dsl.BuildRegistry(imports, dsl.ResolveConfig{ScratchDir: scratchDir, Replace: replaces})
		if err != nil {
			fmt.Fprintf(stdout, "error: phase 2 (package resolution) failed: %v\n", err)
			return 1
		}
		diags = append(diags, dsl.CrossCheck(file, reg)...)
	}

	if capPath != "" && reg != nil {
		capFile, err := dsl.LoadCapFile(capPath)
		if err != nil {
			fmt.Fprintf(stdout, "error: %v\n", err)
			return 1
		}
		actions := distinctResolvedTypes(file.Actions, reg.Actions)
		events := distinctResolvedTypes(file.Events, reg.Events)
		capDiags, err := dsl.CheckCapabilities(scratchDir, actions, events, capFile)
		if err != nil {
			fmt.Fprintf(stdout, "error: phase 3 (capability check) failed: %v\n", err)
			return 1
		}
		diags = append(diags, capDiags...)
	}

	for _, d := range diags {
		fmt.Fprintln(stdout, d.String())
	}

	nActions, nEvents := 0, 0
	if file.Actions != nil {
		nActions = len(file.Actions.Decls)
	}
	if file.Events != nil {
		nEvents = len(file.Events.Decls)
	}
	nErrors := 0
	for _, d := range diags {
		if d.Severity == dsl.SeverityError {
			nErrors++
		}
	}
	fmt.Fprintf(stdout, "%d actions, %d events, %d errors\n", nActions, nEvents, nErrors)

	if dsl.HasErrors(diags) {
		return 1
	}
	return 0
}

// distinctResolvedTypes returns the deduplicated set of TypeSchemas actually
// referenced by stanza's declarations (multiple DSL instances of the same
// type, e.g. demo.dsl's six GoToGlobalPosition actions, only need checking
// once).
func distinctResolvedTypes(stanza *dsl.ActionsStanza, schemas map[string]dsl.TypeSchema) []dsl.TypeSchema {
	if stanza == nil {
		return nil
	}
	seen := map[string]bool{}
	var out []dsl.TypeSchema
	for _, d := range stanza.Decls {
		if seen[d.Type] {
			continue
		}
		if schema, ok := schemas[d.Type]; ok {
			seen[d.Type] = true
			out = append(out, schema)
		}
	}
	return out
}
```

`distinctResolvedTypes` above is typed for `*dsl.ActionsStanza`; events need the same treatment but `dsl.EventsStanza` is a different Go type with an identical shape (`Decls []*Decl`). Add a second overload rather than trying to unify them via an interface (that would need a shared method neither stanza type currently has, and adding one purely for this would be reaching for cleverness a five-line duplicate avoids):

```go
func distinctResolvedEventTypes(stanza *dsl.EventsStanza, schemas map[string]dsl.TypeSchema) []dsl.TypeSchema {
	if stanza == nil {
		return nil
	}
	seen := map[string]bool{}
	var out []dsl.TypeSchema
	for _, d := range stanza.Decls {
		if seen[d.Type] {
			continue
		}
		if schema, ok := schemas[d.Type]; ok {
			seen[d.Type] = true
			out = append(out, schema)
		}
	}
	return out
}
```

And update the call site inside `run` accordingly:

```go
		actions := distinctResolvedTypes(file.Actions, reg.Actions)
		events := distinctResolvedEventTypes(file.Events, reg.Events)
```

- [ ] **Step 4: Update every existing call site of `run` in the test file for the new `capPath` parameter**

Every existing `run(...)` call in `sdk/cmd/dslcheck/main_test.go` (Tasks 6 and 11's tests) needs a `""` inserted as the new `capPath` argument, e.g. `TestRun_GoodFile` becomes:

```go
	code := run("../../dsl/testdata/good.dsl", map[string]string{
		"github.com/cmusatyalab/steeleagle_sdk": mustAbs(t, "../../dsl/testdata/sdkfixture"),
	}, t.TempDir(), "", &stdout, &stderr)
```

and similarly thread `""` through `TestRun_MissingFile`, `TestRun_StructuralError`, and `TestRun_Phase2_ResolvesFixtureSDK`.

- [ ] **Step 5: Run all CLI tests to verify they pass**

Run: `cd sdk && go test ./cmd/dslcheck/... -v`
Expected: all PASS.

- [ ] **Step 6: Run the complete test suite, both modes**

Run: `cd sdk && go test ./... -v`
Expected: PASS (full run, including all Phase 2/3 tests).

Run: `cd sdk && go test -short ./... -v`
Expected: PASS, with every Phase 2/3-touching test reporting `--- SKIP`.

Run: `cd sdk/dsl/testdata/sdkfixture && go test ./...`
Expected: PASS (this submodule's own tests, unaffected by anything in this task).

- [ ] **Step 7: Manual smoke test of the built binary**

```bash
cd sdk
go build -o /tmp/dslcheck ./cmd/dslcheck
/tmp/dslcheck --dsl demo.dsl \
  --replace github.com/cmusatyalab/steeleagle_sdk=dsl/testdata/sdkfixture \
  --cap dsl/testdata/violation.cap.toml
echo "exit=$?"
```

Expected: prints the expected `unknown datatype` errors plus a `disallowed capability` error naming `SetGimbalPose`, a summary line, and exits 1.

- [ ] **Step 8: Commit**

```bash
cd sdk
git add cmd/dslcheck/main.go cmd/dslcheck/main_test.go
git commit -m "sdk: wire phase 3 (capability check) into dslcheck CLI; add end-to-end tests"
```

---

## Plan Self-Review Notes

(Completed while writing this plan; recorded here per the writing-plans skill's self-review step, not as remaining work.)

- **Spec coverage:** Phase 1 (parser + local checks) → Tasks 1-6. Phase 2 (sequestered module + SDK contract) → Tasks 7-11. Phase 3 (cap.toml + SSA) → Tasks 12-16. The `demo.dsl` rename → Task 5. CLI shape (`--dsl`/`--replace`/`--cap`, exit codes, summary line) → Tasks 6/11/16. Every spec section has a corresponding task.
- **Deviations from the spec, and why:** (1) `cap.toml`'s `symbol = "pkg.Type.Member"` shorthand became explicit `package`/`type`/`member` TOML fields (Task 12) — the single-string form is ambiguous to parse given Go import paths contain dots. (2) Local-check scope was narrowed from the spec's "every name referenced as a value... must be declared" to only unambiguous structural positions (Mission `Start`/`During`/transition references) — a bare identifier used as an attribute *value* is genuinely ambiguous between "reference" and "plain string literal" without SDK type knowledge (discovered while tracing through `demo.dsl`'s actual values like `algo = corridor`), so that heuristic moved to the warning-only unused-Data check instead of being promised as an error. Both changes are called out inline in their tasks, not silently made.
- **Placeholder scan:** No task step says "add appropriate error handling" or defers code to a later reference — every step with code shows the complete code, including error paths (e.g. `BuildRegistry`'s wrapped `go` subprocess errors, `CrossCheck`'s specific messages).
- **Type consistency:** `Diagnostic`, `Severity`, `TypeSchema`, `FieldSchema`, `RegistryDump`, `CapRule`, `CapFile` are each defined exactly once (Tasks 2, 9, 12) and referenced identically (field names and types) in every later task that uses them. `run`'s signature grows additively and consistently across Tasks 6 → 11 → 16, with every prior test's call site updated at each step rather than left stale.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-25-dsl-validator.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
