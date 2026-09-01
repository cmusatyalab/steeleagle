# GCS FSM Builder: Port to the Go SDK/Compiler

Status: draft, not yet reviewed or implemented.

## Context

The GCS plan page's FSM builder (`gcs/react/prime/src/PlanPage.jsx` +
`gcs/react/backend/app/api.py`'s `/api/schema`, `/api/parse_dsl`,
`/api/compile` routes) currently has no working backend. It was written
against `steeleagle_sdk`, an out-of-tree Python v3.x sibling worktree kept
alive as a stopgap import; that SDK does not reflect the v4.0-beta DSL at
all.

This work was previously brainstormed and shelved on 2026-08-20
(`project-gcs-fsm-builder-go-port` memory) because the Go SDK's compiler
was too immature to design the two hardest pieces concretely: an
action/event library, and vehicle-capability validation. Since then:

- The compiler (`sdk/cmd/compiler`) now runs the **full** pipeline —
  parse → scrub via `cap.toml` → load a `go/types`-based type registry →
  link → generate `main.go` → `go build`, with `-arch` cross-compilation
  — and produces a working binary today via the CLI. Phase 4
  (codegen-to-binary) is almost entirely de-risked by this; it is no
  longer separate, higher-risk work.
- `loader.LoadTypes` already builds exactly the reflection data a
  palette needs (`TypeRegistry.Actions/Events/Datatypes/Enums`, each a
  qualified-name → fields/comments/optionality map) as a side effect of
  linking. No new introspection mechanism needs to be invented.
- The action library grew (`Patrol` added), and — more importantly —
  the FSM runtime treats action-completion (`done`) as an always-present
  synthetic event (`sdk/dsl/fsm/fsm.go`), so action-chain missions work
  today with **zero** real `Event` types implemented. `sdk/dsl/events/events.go`
  is still empty, but this no longer blocks basic mission authoring —
  it just means the palette's Events section stays empty for now.
- Vehicle → `cap.toml` mapping is still unresolved (no registry exists
  anywhere; the only `cap.toml` in the repo is a testdata fixture). This
  design defers capability validation rather than solving it (see
  Non-Goals).
- The frontend's existing `generateDsl()` (`PlanPage.jsx:69`) already
  emits text that matches the Go DSL's grammar (`Type instanceId(k = v,
  ...)` decls, `During X: event -> Y` transitions) almost exactly. It's
  missing only the `Import:`/`Role:`/`Override:` stanzas the Go DSL
  needs that the Python-era DSL never had.

## Goals

- Serve the FSM palette (actions, events, datatypes, enums) from the
  real Go SDK via reflection, not a hand-maintained or stale schema.
- Validate a canvas-authored mission against the Go SDK's actual type
  system (parse/link errors), live, as the user edits.
- Compile a validated mission all the way to a runnable binary
  (`amd64` and `arm64`), downloadable by the user.
- Preserve the frontend's existing HTTP contract wherever possible, so
  this ships without a parallel frontend rewrite.

## Non-Goals

- **Vehicle capability validation / `cap.toml` resolution.** No
  vehicle → `cap.toml` registry exists. Both target-arch builds use an
  empty `CapFile` (nothing scrubbed), identical to running the CLI with
  no `-cap` flag. Revisit once a real mapping mechanism exists.
- **Shipping the compiled binary to a vehicle.** Binaries can be large
  and it's not yet decided whether vehicles pull them from a URL or
  receive them inline; that's its own design. This work replaces the
  old JSON-mission Deploy button with a manual "download binary"
  action instead of inventing a distribution mechanism now.
- **Multi-FSM / per-vehicle FSM assignment.** The DSL grammar still has
  exactly one `Mission: Start ... During ...` block
  (`sdk/dsl/parser/ast.go`); nothing anywhere is designed for more than
  one FSM per mission yet.
- **Real event-driven transitions.** `sdk/dsl/events/events.go` is
  empty. The palette's Events section will be empty until the SDK
  implements some.
- **Porting the FastAPI backend to Go.** Out of scope unless it turns
  out to simplify rather than complicate this work — it doesn't here;
  `api.py`'s routes become thin gRPC proxies, which is straightforward
  in Python.
- **GeoJSON-backed map features for `actions.Patrol`.** `actions.Patrol`'s
  required `Area` field (a `params.MapFeature`) cannot currently resolve
  through this service: `Validate`/`Build` never receive or thread a
  GeoJSON feature collection, and `NewService` never populates `sdkTypes`
  for `sdk.CreateOverlay`, so no `MapFeature` constants exist in the
  palette either. This gap was discovered during this plan's
  implementation, not originally scoped out; full support (new proto
  fields, threading a GeoJSON payload through `Validate`/`Build`/
  `NewService`, and populating `CreateOverlay`'s `sdkTypes`) is deferred
  to a follow-on plan.

## Architecture

```
┌─────────────────────┐        gRPC        ┌──────────────────────────┐
│  gcs/react/backend   │ ──────────────────▶│  cmd/dslcompiler         │
│  app/api.py          │                    │  (thin) + core/dslcompiler│
│  (unchanged HTTP      │◀────────────────── │  (logic)                 │
│   contract for the    │                    │                          │
│   frontend)            │                    │  wraps sdk/dsl/compiler  │
└─────────────────────┘                    │  (new importable library)│
                                            └──────────────────────────┘
                                                       │
                                                       ▼
                                          sdk/dsl/{parser,loader,fsm}
                                          (unchanged)
```

- **New service**: `cmd/dslcompiler/main.go` (thin) + `core/dslcompiler/`
  (logic), matching the existing `cmd/swarm` + `core/swarm` convention.
  Exposes a new gRPC service (new proto package
  `api/steeleagle_protocol/v1/services/dslcompiler/`) with three RPCs:
  `GetSchema`, `Validate`, `Build`.
- **Compiler internals become an importable library.** `sdk/cmd/compiler`
  is currently `package main` — `ir.go`, `generate.go`, workspace/overlay
  setup, and `tidyAndBuild` all get pulled out into a new library package
  (e.g. `sdk/dsl/compiler`, sibling to `parser`/`loader`/`fsm`), fully
  exported. The existing CLI becomes a thin wrapper over the same
  library, so there is exactly one implementation of the pipeline with
  two callers (CLI, service) — this also satisfies the long-standing TODO
  left in commit `ad066d27` ("needs auto-generation of mission script and
  gRPC endpoint").
- **The registry loads once at startup**, not per request. The service
  loads the default import set (base `sdk`, `dsl/actions`, `dsl/events`,
  `dsl/types`) into a `TypeRegistry` and keeps the build workspace/cache
  resident in memory, since a persistent process was already the locked
  interop decision (Go and Python can't share process/state, and the
  frontend debounce-validates every ~500ms — a CLI subprocess per call,
  paying `go/packages.Load()`'s cold-start cost each time, would be too
  slow). Deferring cap.toml scrubbing means there's exactly one registry
  to maintain for now, not one per vehicle-capability-hash; that
  complexity can be added later without restructuring this.
- **`api.py` keeps its current HTTP contract.** `/api/schema`,
  `/api/parse_dsl`, `/api/compile` keep their existing Pydantic
  request/response shapes; their handlers become thin gRPC clients
  translating Pydantic ⇄ protobuf. A new `/api/build` route replaces the
  old Deploy flow (see Frontend Changes).

## Schema / Introspection

`GetSchema` wraps the startup-loaded `TypeRegistry`:

```
SchemaResponse {
  actions:      map<string, TypeSchema>
  events:       map<string, TypeSchema>   // empty today
  datatypes:    map<string, TypeSchema>
  enums:        map<string, EnumSchema>
  imports:      []ImportSpec { alias, path, version }
  default_role: string
}
TypeSchema { description, fields: []FieldSchema }
FieldSchema {
  name, type, required, description,
  default?, object_type?, nested_fields?, enum_type?
}
EnumSchema { description, values: []string }
```

`type`/`object_type`/`nested_fields` are derived from `loader.Base`'s
`go/types.Type` the same way `api.py`'s current
`_extract_fields_from_schema` derives them from a Pydantic JSON schema:
`types.Basic` → `string`/`number`/`integer`/`boolean`, a slice →
`array`, a named struct → `object` with a recursive lookup into
`registry.Datatypes` (depth-capped at 2, matching today's behavior).
`enum_type` is new — it names an `enums` entry a field's value must come
from; there is no equivalent concept in the Pydantic-derived schema
today.

`/api/schema`'s handler calls `GetSchema` once and returns the same
top-level shape the frontend already consumes (`{"actions": {...},
"events": {...}}`), sourced from Go instead of Python, plus the new
`imports`/`default_role` keys the frontend needs to seed
`generateDsl()`'s default `Import:`/`Role:` stanzas.

## Graph → AST Construction

The frontend already sends `/api/compile` a graph shape (`nodes`,
`events`, `edges`, `start_id`) rather than DSL text. Rather than
serializing that to text and round-tripping it through the real lexer,
`Validate`/`Build` build a `parser.Ast` **structurally** — `Decl`,
`DuringBlock`, `Rule` are plain Go structs, trivially constructed
without invoking `participle` at all:

```
ValidateRequest {
  nodes: []Node { instance_id, type_name, params: map<string, FieldValue> }
  events: []EventInstance { instance_id, type_name, params: map<string, FieldValue> }
  edges: []Edge { source, event_id, target }
  start_id: string
  role?: string          // defaults to schema's default_role if unset
  imports?: []ImportSpec // defaults to schema's imports if unset
}
ValidateResponse { ok: bool, errors: []CompileError { node_id?, event_id?, message } }
```

**`FieldValue` is a typed `oneof`, mirroring `parser.Value`'s own union**
(`Float | Int | String | Array | Inline | Ident`) instead of a bare
string, so the wire format states which kind of value it's sending
rather than making the Go side infer it from the target field's schema
type:

```
FieldValue {
  oneof value {
    double            float_value  = 1;
    int64             int_value    = 2;
    string            string_value = 3;
    bool              bool_value   = 4;
    string            ident_ref    = 5;  // enum constant name, or another
                                          // node/data-decl's instance_id
    FieldValueArray   array_value  = 6;
    InlineCtorValue   inline_value = 7;  // keyword-arg constructor call
  }
}
FieldValueArray  { repeated FieldValue elems = 1; }
InlineCtorValue  { string type_name = 1; map<string, FieldValue> args = 2; }
```

This directly resolves the ambiguities a plain string encoding had:
- **Enum fields** (`Patrol.Pattern PatrolMode`, `AltitudeMode
  enums.AltitudeMode`) are sent as `ident_ref`, which maps straight onto
  `resolveEnumConst` — there's no way to confuse an enum constant name
  with an arbitrary string value.
- **Composite/nested fields** (`Patrol.Area params.MapFeature`) can be
  sent either as `inline_value` (an anonymous `InlineCtorValue`,
  matching the DSL grammar's own `Inline` variant directly — no
  synthesized extra `Data:` decl needed) or as `ident_ref` when the user
  explicitly created a named, reusable data node on the canvas. Both
  forms already exist in the DSL grammar (`Value.Inline` vs. `Value.Ident`
  referencing a `Decl`); the typed field lets the frontend say which one
  it means instead of the backend having to guess from a `nested_fields`
  heuristic.
- **Array fields** get a real repeated `FieldValueArray` instead of an
  undefined string encoding that would need ad hoc delimiting/escaping
  rules invented and kept in sync on both ends.

A malformed value (e.g. a `string_value` sent for a field the registry
says is a `float32`) is now a straightforward type-switch mismatch in
`resolveValue`, reported as a clear type error, rather than a
`strconv`/lookup failure several layers down that doesn't point back to
which UI widget produced it.

The real `parser.Parse` (text lexing) is reserved for `/api/parse_dsl`'s
raw-text-upload case only — loading a `.dsl` file the user wrote by hand
still goes through the genuine parser, then `loadFromParsed` rebuilds
the canvas from it exactly as it does today.

`role`/`imports` being optional-with-defaults is what lets the DSL tab's
"Apply" flow (see below) round-trip arbitrary hand-edited imports without
the canvas needing dedicated UI for them.

**Error mapping is direct, not position-based.** Since every `Decl.Name`
is set to the canvas `instance_id` by convention, every
`*sdk.CompileError` the pipeline returns already names the failing
identifier — no line/offset translation is needed. Errors with no
natural node/event owner (a bad `start_id`, a missing base import) come
back with `node_id`/`event_id` unset, same as some cases in today's
Python handler already do; the frontend's existing toast-plus-optional-
highlight logic needs no changes.

Cheap structural checks — duplicate `instance_id`s, edges referencing a
nonexistent node/event — stay in Python, run before ever calling
`Validate`, exactly as `compile_mission()` does today. These aren't
SDK-semantic checks and don't need the Go type system.

## Build

```
BuildRequest  { <same graph fields as ValidateRequest> }
BuildChunk    { arch, data: bytes, done: bool }
Build(BuildRequest) returns (stream BuildChunk)
```

`Build` is a **server-streaming** RPC, not unary — a compiled binary can
easily exceed gRPC's default 4MB unary message cap, especially
statically linked with the full protobuf/gRPC dependency tree. Streaming
avoids tuning a size-cap ceiling that silently breaks again as binaries
grow. It runs the full pipeline (reusing the IR from the last successful
`Validate` for this request, keyed by a hash of the graph, to avoid
redundant work) through `Generate` → `tidyAndBuild`, once for each of the
two hardcoded target arches, `CapFile` empty for both (per Non-Goals).
The **arch matrix is hardcoded to `{amd64, arm64}`**, not configurable —
this is the entire real-world set today
(`ansible/roles/eagled_vehicle/defaults/main.yml`'s `eagled_go_arch_map:
{x86_64: amd64, aarch64: arm64}`); a third arch is a small code change if
one is ever needed. A vehicle's companion-computer architecture is
independent of its `cap.toml`/driver (a Parrot Anafi can fly with a
Particle Tachyon or an Onion Omega), and there is currently no way to
discover which one a given vehicle needs, so both are always built —
picking the right one is future work once that discovery mechanism
exists.

`api.py`'s new `/api/build` route relays each `BuildChunk` stream as a
chunked HTTP download response per arch — no persistent storage, no URL
scheme.

## Frontend Changes

- **Default `Import:`/`Role:` generation.** `generateDsl()` prepends the
  `Import:`/`Role:` stanzas from `/api/schema`'s new `imports`/
  `default_role` fields automatically — no user action needed for the
  common case.
- **The DSL tab becomes editable**, not read-only, as the escape hatch
  for anything the canvas doesn't have a widget for (custom imports, a
  hand-tuned `Role:`). Typing there doesn't live-reparse on every
  keystroke; an explicit "Apply" action calls `/api/parse_dsl` (already
  exists) and rebuilds the canvas via `loadFromParsed` (already exists).
  Canvas edits keep auto-regenerating the DSL tab's text via
  `generateDsl()`, same as today. Only one direction is "hot" at a
  time — canvas is default/live, DSL-tab edits are staged until "Apply"
  hands control back to the canvas — so the two projections never fight.
- **Deploy is replaced.** Sending a JSON mission blob to every selected
  vehicle was trivial; sending an architecture-specific binary is not
  (see Non-Goals). The Deploy button in `PlanPage.jsx` is removed and
  replaced with two "Download binary (amd64 / arm64)" actions wired to
  `/api/build`, mirroring the existing "Download mission.json" pattern
  (`handleDownload`). The user handles getting the binary onto a vehicle
  themselves for now.

## Testing

- **Go**: unit tests on `core/dslcompiler` (schema translation,
  graph→AST construction, streaming `Build`) plus an integration test
  compiling a known-good mission end to end, adapting the existing
  `sdk/cmd/compiler/testdata` fixtures (`test_dsl.dsl`, `patrol.test.dsl`)
  into graph-JSON form.
- **Python**: `api.py`'s handlers keep being tested as pure functions
  against a fake gRPC client, matching the existing pattern
  (`build_schema_response()`/`compile_mission()` are already written to
  be testable without the full app running).
- **Frontend**: no test-suite changes needed since HTTP contracts are
  preserved; manual verification of the DSL-tab Apply round-trip and the
  binary-download flow in a browser.

## Migration / Rollout

There is no cutover risk in the usual sense: `/api/schema`,
`/api/parse_dsl`, `/api/compile` have no working backend today (the
Python SDK behind them is an out-of-tree v3.x stopgap), so swapping
their internals for gRPC calls to the new Go service is a strict
improvement, not a migration of something currently working. The
Deploy-button removal/replacement is the only user-visible UI change
outside of the palette/validation now actually working.

## Open Risks

- **`sdk/cmd/compiler` → library refactor is real surface area.**
  `ir.go`/`generate.go` currently assume `package main`'s global state
  (e.g. `main.go.tmpl` embedding); extracting them cleanly is not
  mechanical and should be scoped as its own implementation step before
  the service is built on top of it.
- **Streaming `Build` doubles compile time** (two full `tidyAndBuild`
  runs per request, one per arch) with no caching across requests today
  beyond the shared workspace/build cache; worth watching whether this
  is fast enough in practice for a "click and wait" UI flow once
  measured.
