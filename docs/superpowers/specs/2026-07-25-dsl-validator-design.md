# SteelEagle Go DSL Validator — Design

Date: 2026-07-25
Status: Approved for planning

## Problem

`sdk/demo.dsl` is a SteelEagle mission written in the SteelEagle DSL (a finite-state-machine
mission language). There is a working **Python** implementation of this DSL's compiler
(`steeleagle_sdk` v1.0.16, installed under `/home/ubuntu/Research/steeleagle_plugins/aviary/.venv`
and `/home/ubuntu/Research/roost/aviary/.venv` on this machine, not part of this git repo), with
a four-stage pipeline: **loader** (imports declared Python packages so `@register_action` /
`@register_event` / `@register_data` decorators populate name→class registries) → **transformer**
(Lark grammar parse tree → `MissionIR`) → **resolver** (turns datum-id string references into real
nested model instances) → **validator** (Pydantic-instantiates every action/event/datum to catch
bad/missing fields).

`demo.dsl`'s `Import:` stanza (`github.com/cmusatyalab/steeleagle_sdk/events`,
`github.com/cmusatyalab/steeleagle_sdk/actions`) uses **Go** import paths, not Python ones — this
is a parallel, Go-native track for the same DSL, consistent with the rest of this repo's v4.0-beta
rewrite (Python backend → Go kernel, see root `CLAUDE.md`). No such Go module exists yet anywhere
on this machine or on the public Go module proxy.

Separately, the real proto (`api/steeleagle_protocol/v1/services/driver/control.proto`, in this
repo) has already renamed `SetGlobalPosition` to `GoToGlobalPosition`, while the installed Python
SDK still uses the old name — a live example of the DSL/SDK lagging behind the current API surface
that this tool needs to be able to catch.

## Goal

Build a Go-native validator, `sdk/cmd/dslcheck`, that:

1. Parses a `.dsl` file with `alecthomas/participle`.
2. Runs local semantic checks (unused declarations, dangling references, structural mission
   integrity) that don't require any external package.
3. Resolves every `Data`/`Action`/`Event` type named in the DSL against real Go implementations,
   by building and running a small program inside a **sequestered** (throwaway) Go module that
   depends on the packages named in the DSL's `Import:` stanza.
4. For each resolved Action/Event, runs an SSA-based reachability/dataflow check against a
   per-drone `cap.toml` capability file, to catch code paths that call or touch API surface the
   target drone doesn't support.
5. Reports pass/fail with diagnostics. Does **not** produce a compiled mission artifact (see
   Non-goals).

Delivered in three phases, each independently testable, in this order: (1) parser + local checks,
(2) sequestered-module resolution, (3) SSA capability check.

## Non-goals (for this iteration)

- **No mission compiler output.** The long-term direction (confirmed with the user) is that this
  tool eventually generates a standalone Go binary that directly runs the mission FSM — codegen'd
  into the sequestered module, calling the resolved `Execute`/`Check` methods directly with their
  literal DSL field values, then `go build` into an executable — replacing the old Python
  interpret-a-JSON-IR approach. That codegen step is explicitly out of scope here. This project
  only validates; a successful run reports success (action/event counts, 0 errors) and exits 0.
- **No `MissionIR` JSON or protobuf `Mission` message.** `mission.proto`'s `MissionData.content`
  oneof has a `binary` branch commented "used for Go missions", implying a future protobuf
  representation, but nothing consumes one yet (the mission-runtime plugin referenced in
  `core/vehicle` is unimplemented). Not defined as part of this project.
- **No real `github.com/cmusatyalab/steeleagle_sdk` module.** A local fixture package under
  `sdk/dsl/testdata/sdkfixture` stands in for it. Splitting a real sibling module out is future
  work.
- **No field-level dataflow beyond direct struct access.** The SSA field check looks at composite
  literals, direct `Store`/`FieldAddr`/`Field` instructions, and method calls (which covers
  generated proto getters). It does not attempt general taint/dataflow tracking through
  intermediate variables, wrapper functions, etc. beyond straightforward reachability.

## Repository layout

Everything lives under `sdk/` in this repo, as its own Go module (keeps `participle`,
`golang.org/x/tools/go/{packages,ssa,callgraph}` etc. out of the main `steeleagle` module's
dependency graph, since the vehicle kernel has no need for them):

```
sdk/
  go.mod                          # new, separate module
  demo.dsl                        # existing; will be updated to current API names (e.g. GoToGlobalPosition)
  cmd/dslcheck/main.go             # CLI entrypoint
  dsl/
    ast.go                        # participle grammar structs
    parse.go                      # Parse(io.Reader) (*File, error)
    check_local.go                # phase 1: unused/dangling-reference/structural checks
    resolve.go                    # phase 2: sequestered-module build + registry-dump harness template
    capcheck.go                   # phase 3: go/packages + go/ssa + go/callgraph, cap.toml enforcement
    captoml.go                    # cap.toml schema + loader
  dsl/sdktypes/                   # Action/Event/Datatype interfaces + registration (fixture-local
                                   # stand-in for github.com/cmusatyalab/steeleagle_sdk's runtime pkg)
  dsl/testdata/
    *.dsl                         # phase-1 fixtures (good + deliberately-broken syntax/refs)
    sdkfixture/                   # tiny standalone module implementing demo.dsl's vocabulary,
                                   # used only by phase 2/3 tests
    *.cap.toml                    # phase-3 fixtures with known violations
```

## Phase 1 — Grammar and local checks

Grammar reconstructed from `demo.dsl`, the Docusaurus DSL guide's worked example
(`docs/docs/sdk/guide/dsl/structure.md`), and the Python transformer's parse-tree node names
(`datum_decl`, `action_decl`, `event_decl`, `mission_start`, `during_block`, `transition_rule`,
`attr`, `array`, `datum_inline`) — the actual `.lark` grammar file is missing from the installed
Python wheel (an upstream packaging gap), so there is no literal grammar source to copy, but the
concrete syntax is fully recoverable from these examples.

Stanzas: `Import:`, `Data:`, `Actions:`, `Events:`, `Mission:`. Declarations are
`Type name(key = value, ...)`. Values are numbers, bare names (references to earlier declarations,
or inline `Type(...)` constructors), quoted strings, or `[...]` arrays. `Mission:` has `Start name`
plus `During name:` blocks of `event -> name` rules; `done` is a reserved implicit event.

Local checks (no external packages required):

- Every name referenced as a value, or as a transition source/target, must be declared somewhere
  in the file.
- Every declared `Data`/`Action`/`Event` must be referenced at least once (unused-declaration
  check).
- `Mission.Start` must name a declared action. Every `During` block's action, and every
  transition's target, must be a declared action name.

Known-rename detection (e.g. catching a DSL author still using an old name) is **not** handled
here — the SDK's registration mechanism no longer supports multi-name aliasing (see Phase 2), and
`demo.dsl` will be updated to current names as part of this work, so this is not needed for the
one concrete case that prompted the discussion.

## Phase 2 — SDK contract + sequestered-module resolution

### `dsl/sdktypes` contract

```go
type Action interface {
    Execute(ctx context.Context) error
}
type Event interface {
    Check(ctx context.Context) (bool, error)
}
type Datatype interface {
    steeleagleDatatype() // unexported marker; satisfied by embedding sdktypes.BaseDatatype
}

func RegisterAction[T Action](name string)
func RegisterEvent[T Event](name string)
func RegisterData[T Datatype](name string)

func DumpRegistry() ([]byte, error) // JSON: per-registry {name: {fields: {name: kind, ...}}}
```

Single canonical name per registration — no alias list (simplified from an earlier draft of this
design once the `SetGlobalPosition`/`GoToGlobalPosition` case was resolved by just updating
`demo.dsl`).

**Field mapping**: DSL params are snake_case (`take_off_altitude`); Go struct fields are exported
PascalCase (`TakeOffAltitude`). Auto-convert snake_case → PascalCase (matching the convention
`protoc-gen-go` already uses elsewhere in this repo), with a `dsl:"..."` struct tag as an escape
hatch. **Optional vs. required**: pointer-typed field = optional, non-pointer = required — same
convention already used by `api/go`'s generated types, which these SDK structs will typically wrap.

### Sequestered module mechanism

Given a DSL file and optional `--replace old=new` flags:

1. Create/reuse a scratch directory (e.g. `.dslcheck-cache/<hash>/`), `go mod init` it once if not
   already a module.
2. For each path in the DSL's `Import:` stanza: if a `--replace` was given for it, run
   `go mod edit -replace <path>=<local-dir>`; otherwise `go get <path>@latest`.
3. Generate a small `main.go` "registry-dump harness" that imports each `Import:` path (triggering
   their `init()`s, which call `RegisterAction`/`RegisterEvent`/`RegisterData`) and calls
   `sdktypes.DumpRegistry()`, printing the result to stdout.
4. `go build` the scratch module. A build failure (bad import path, package doesn't exist, doesn't
   compile) is reported as a validation error, not a tool crash.
5. Run the built harness; parse its JSON stdout.
6. Cross-check every DSL `Data`/`Action`/`Event` declaration against the dump: unknown type name →
   error; unknown field name → error; missing required (non-pointer) field → error.

### Fixture SDK (`dsl/testdata/sdkfixture`)

A local, standalone Go module (not the real `github.com/cmusatyalab/steeleagle_sdk`) implementing
enough of `demo.dsl`'s vocabulary to exercise phases 2-3 end to end: `TakeOff`, `Patrol`, `Track`,
`GoToGlobalPosition`, `Wait`, `SetGimbalPose`, `PrecisionLand`, `ElevateToAltitude`,
`DetectionFound`, `TimeReached` and the `Velocity`/`Waypoints`/`Location`/`Detection`/`Pose`
datatypes. `Execute`/`Check` bodies call a small mock "vehicle API" package inside the fixture
(standing in for the real `ControlServiceClient`/telemetry accessors), giving Phase 3 real call
edges and field accesses to check against.

## Phase 3 — SSA capability check

### `cap.toml` schema

```toml
[[disallow]]
symbol = "driver/control.ControlServiceClient.SetGimbalPose"
kind = "func"          # func | field
mode = "write"         # read | write | both — ignored for kind = "func" (always a "reachability" hit)

[[disallow]]
symbol = "messages/telemetry.GimbalInfo.PoseNeu"
kind = "field"
mode = "read"
```

- `kind = "func"`: covers both RPC calls (setters, e.g. `ControlServiceClient.SetGimbalPose`) and
  generated proto `GetXxx()` accessors (getters) — both are ordinary Go methods, so both are
  handled by the same call-graph-reachability mechanism.
- `kind = "field"`: covers direct struct-field access that bypasses a method — a composite-literal
  init or `x.Field = v` (write), or a bare `x.Field` read not going through a getter.
- A rule whose `symbol` names only a type (no trailing field/method, e.g.
  `messages/telemetry.RTKInfo`) blocks the entire type — any read, write, or construction — for
  drones missing that capability entirely.

### Analysis

Using `golang.org/x/tools/go/packages` (load full syntax + types for the resolved packages inside
the sequestered module — this is why Phase 3 needs real source, not just the Phase 2 harness
binary), `golang.org/x/tools/go/ssa` (build SSA via `ssautil.AllPackages`), and
`golang.org/x/tools/go/callgraph/cha` (Class Hierarchy Analysis call graph — over-approximates at
interface dispatch sites, which is the safe direction for a capability gate: a false "might reach
it" is acceptable, a missed real violation is not).

For each Action/Event type resolved in Phase 2, locate its `Execute`/`Check` method's SSA function
and check:

- **func rules**: is the named method/function reachable in the call graph from this entry point?
- **field rules**: walking the SSA instructions of every function reachable from this entry point,
  does any `*ssa.FieldAddr`/`*ssa.Store` (write) or `*ssa.Field`/direct read (read) instruction
  touch the named field on a value of the named type, matching the rule's `mode`?

A violation is reported naming the DSL action/event, the offending symbol, and — where CHA can
produce one — a call path.

## CLI

```
dslcheck --dsl demo.dsl --cap anafi.cap.toml [--replace old=new ...]
```

- `--cap` is optional; omitting it skips Phase 3 (useful while iterating on Phases 1-2 without a
  concrete drone target).
- `--replace` may be repeated, one per package path needing a local source instead of `@latest`.
- Exit 0 with a summary line (action/event counts, "0 errors") on success. Exit non-zero with the
  full list of errors/warnings (file:line where available) otherwise.

## Testing strategy

Table-driven Go tests per phase:

- Phase 1: parse a set of good and deliberately-broken `.dsl` fixtures under `dsl/testdata/`;
  assert specific diagnostics.
- Phase 2: against `sdktypes` + `sdkfixture`; assert unknown-type/unknown-field/missing-required
  errors, and a clean pass for well-formed input.
- Phase 3: against `sdkfixture` + a couple of hand-written `cap.toml` fixtures with known
  func-level and field-level (read and write) violations, plus a clean pass with an empty/no-op
  cap.toml.
- One end-to-end test compiling the real, updated `demo.dsl` through all three phases.

Phase 2/3 tests shell out to `go build`/`go get` and are noticeably slower than the rest of the
repo's Go test suite (root `go test ./...` currently runs in ~20s); they should be skippable under
`-short` so they don't become the default cost of iterating on unrelated code.
