"""
DSL validator

Static normalization and validation utilities for SteelEagle DSL.

This module parses DSL text into lightweight internal structures and performs
batched structural, catalog-based, and semantic checks. It does not invoke the
SDK compiler directly; the surrounding pipeline subsequently uses the SDK
compiler as the authoritative validation step.

The parser is intentionally lenient about common model-generated formatting
errors so it can return targeted diagnostics. `validate()` returns a list of
`ValidationError` objects; an empty list indicates successful validation.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any

from . import catalog


# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------
@dataclass
class Declaration:
    """One declaration line, e.g. `TakeOff take_off(take_off_altitude = 10.0)`."""
    class_name: str
    instance_name: str
    args: dict[str, Any]
    line_no: int


@dataclass
class Transition:
    event_name: str       # done
    target_action: str
    line_no: int


@dataclass
class DuringBlock:
    action_name: str
    transitions: list[Transition] = field(default_factory=list)
    line_no: int = 0


@dataclass
class ParsedMission:
    data: list[Declaration] = field(default_factory=list)
    actions: list[Declaration] = field(default_factory=list)
    events: list[Declaration] = field(default_factory=list)
    start: str | None = None
    during: list[DuringBlock] = field(default_factory=list)


@dataclass
class ValidationError:
    line_no: int | None
    message: str

    def __str__(self) -> str:
        loc = f"line {self.line_no}: " if self.line_no else ""
        return f"{loc}{self.message}"


# -----------------------------------------------------------------------------
# Parsing
# -----------------------------------------------------------------------------
_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"

# Matches `ClassName instance(args)` with optional trailing whitespace.
DECL_RE = re.compile(
    rf"""^
    \s*
    (?P<cls>{_NAME_PATTERN})
    \s+
    (?P<inst>{_NAME_PATTERN})
    \s*
    \(
    (?P<args>.*)
    \)
    \s*$
    """,
    re.VERBOSE,
)

# Matches `event_name -> action_name` (event may be 'done')
TRANSITION_RE = re.compile(
    rf"^\s*(?P<event>{_NAME_PATTERN})\s*->\s*"
    rf"(?P<action>{_NAME_PATTERN})\s*$"
)

# Matches `During <name>:`
DURING_RE = re.compile(
    rf"^\s*During\s+(?P<action>{_NAME_PATTERN})\s*:\s*$"
)

# Recognizes valid `Start <name>` declarations and the common invalid
# `Start: <name>` form so the parser can return a targeted diagnostic.
START_RE = re.compile(
    rf"^\s*Start(?P<colon>\s*:)?\s+(?P<action>{_NAME_PATTERN})\s*$"
)


def _strip_comment(line: str) -> str:
    """Strip `# ...` comments, respecting quotes (simple, single-line)."""
    in_quote = None
    for i, ch in enumerate(line):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
        elif ch == "#":
            return line[:i]
    return line


def _parse_args(arg_str: str) -> tuple[dict[str, Any], list[str]]:
    """
    Parse `name = value, name = value` arg list. Values can be:
      - Numbers (int or float)
      - 'single-quoted strings'
      - "double-quoted strings"
      - true/false (case-insensitive)
      - bare identifiers (treated as references to other instances)
      - [a, b, c] lists of any of the above

    Returns (args_dict, errors). Errors are human-readable strings.
    """
    args: dict[str, Any] = {}
    errors: list[str] = []
    arg_str = arg_str.strip()
    if not arg_str:
        return args, errors

    # Split on top-level commas (respecting brackets and quotes).
    parts: list[str] = []
    depth = 0
    in_quote: str | None = None
    buf: list[str] = []
    for ch in arg_str:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            buf.append(ch)
        elif ch in ("[", "("):
            depth += 1
            buf.append(ch)
        elif ch in ("]", ")"):
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))

    for part in parts:
        if "=" not in part:
            errors.append(f"malformed argument (expected `name = value`): {part!r}")
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not re.fullmatch(_NAME_PATTERN, k):
            errors.append(f"invalid parameter name: {k!r}")
            continue
        try:
            args[k] = _parse_value(v)
        except ValueError as e:
            errors.append(f"value of `{k}`: {e}")
    return args, errors


def _parse_value(v: str) -> Any:
    v = v.strip()
    if not v:
        raise ValueError("empty value")

    # List
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        items: list[Any] = []
        # Reuse top-level splitter for list contents:
        sub, errs = _parse_args(
            ",".join(f"_{i} = {item}" for i, item in enumerate(_split_top(inner)))
        )
        if errs:
            raise ValueError("malformed list: " + "; ".join(errs))
        for i in range(len(sub)):
            items.append(sub[f"_{i}"])
        return items

    # Quoted string
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v[1:-1]

    # Boolean
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False

    # Number
    try:
        if "." in v or "e" in v.lower():
            return float(v)
        return int(v)
    except ValueError:
        pass

    # This lightweight parser does not currently model inline data
    # constructors, although the SDK grammar accepts them. Return an explicit
    # limitation instead of a generic parse error.
    m = re.match(rf"^({_NAME_PATTERN})\s*\(", v)
    if m:
        cls = m.group(1)
        inst = cls.lower()
        raise ValueError(
            f"the static validator does not currently support inline data "
            f"constructors (`{cls}(...)`). Declare the value in the Data "
            f"stanza, e.g. `{cls} {inst}(...)`, then reference it here by "
            f"name: `{inst}`")

    # Bare identifier => reference
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", v):
        return _Ref(v)

    raise ValueError(f"could not parse value {v!r}")


def _split_top(s: str) -> list[str]:
    """Split on top-level commas only (for list contents)."""
    parts: list[str] = []
    depth = 0
    in_quote: str | None = None
    buf: list[str] = []
    for ch in s:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            buf.append(ch)
        elif ch in ("[", "("):
            depth += 1
            buf.append(ch)
        elif ch in ("]", ")"):
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts]


@dataclass
class _Ref:
    """A reference to another instance by name (unquoted bare identifier)."""
    name: str


# -----------------------------------------------------------------------------
# Normalization (forgiving auto-fixes / fallbacks)
# -----------------------------------------------------------------------------
def normalize_dsl(dsl_text: str) -> tuple[str, list[str]]:
    """Apply forgiving auto-fixes for hard grammar rules LLM output violates.

    These are corrections that carry NO semantic ambiguity — the user's intent
    is unchanged — so we fix them silently instead of bouncing the model
    through a retry.

    1. Empty optional stanzas. A `Data:` or `Events:` header with nothing
       declared under it makes the real SteelEagle grammar misparse the *next*
       stanza's name as a declaration and choke on its colon (e.g.
       "Unexpected token COLON at line 2, column 8"). Such empty headers are
       dropped. `Actions:`/`Mission:` are required, so they are left in place
       for the validator to flag as genuine errors if empty.
    2. Stanza order. The grammar mandates the fixed order Data, Actions,
       Events, Mission, but that order carries no semantic meaning — the four
       blocks are independent declarative sections. Generated DSL may place
       them out of order (e.g. Actions before Data), so they are reordered
       into canonical order.
    3. Missing trailing newline. The grammar requires the file to end with a
       newline; otherwise the final transition line hits end-of-input
       ("Unexpected token $END").

    Returns `(normalized_text, fixes)` where `fixes` is a list of
    human-readable descriptions of every change applied (empty == no change).
    These are surfaced to the user so they know what the system corrected.
    """
    lines = dsl_text.splitlines()
    fixes: list[str] = []

    def _stanza_name(line: str) -> str | None:
        s = _strip_comment(line).strip()
        if s.endswith(":") and s[:-1] in catalog.STANZAS:
            return s[:-1]
        return None

    headers = [(idx, name) for idx, name in
               ((i, _stanza_name(l)) for i, l in enumerate(lines)) if name]

    drop: set[int] = set()
    for h, (idx, name) in enumerate(headers):
        if name not in ("Data", "Events"):
            continue
        next_idx = headers[h + 1][0] if h + 1 < len(headers) else len(lines)
        has_content = any(_strip_comment(lines[j]).strip()
                          for j in range(idx + 1, next_idx))
        if not has_content:
            drop.add(idx)
            fixes.append(
                f"removed empty `{name}:` stanza (the grammar rejects a stanza "
                f"header with no declarations under it)")

    if drop:
        lines = [l for i, l in enumerate(lines) if i not in drop]

    # Reorder stanza blocks into the canonical Data, Actions, Events, Mission
    # order. We group lines into a leading preamble (anything before the first
    # stanza header) plus one block per header (the header line through the
    # line just before the next header), then stable-sort the blocks by their
    # position in `catalog.STANZAS`. A stable sort keeps duplicate headers
    # adjacent for the validator to flag.
    block_headers = [(i, name) for i, name in
                     ((i, _stanza_name(l)) for i, l in enumerate(lines)) if name]
    if block_headers:
        preamble = lines[: block_headers[0][0]]
        blocks: list[tuple[str, list[str]]] = []
        for b, (idx, name) in enumerate(block_headers):
            end = block_headers[b + 1][0] if b + 1 < len(block_headers) else len(lines)
            blocks.append((name, lines[idx:end]))
        order = [name for name, _ in blocks]
        reordered = sorted(blocks, key=lambda nb: catalog.STANZAS.index(nb[0]))
        if [name for name, _ in reordered] != order:
            lines = preamble + [l for _, b in reordered for l in b]
            fixes.append(
                "reordered stanzas into the required order "
                "(Data, Actions, Events, Mission)")

    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
        # Only report it as a fix if the *original* lacked the newline;
        # splitlines() drops a pre-existing terminator that we just restore.
        if not dsl_text.endswith("\n"):
            fixes.append("appended a trailing newline (the grammar requires "
                         "the DSL file to end with a newline)")
    return text, fixes


# -----------------------------------------------------------------------------
# Top-level parser
# -----------------------------------------------------------------------------
def parse(dsl_text: str) -> tuple[ParsedMission, list[ValidationError]]:
    """Lenient parser. Records errors but continues so we can collect many."""
    mission = ParsedMission()
    errors: list[ValidationError] = []
    section: str | None = None
    current_during: DuringBlock | None = None
    seen_stanzas: list[str] = []

    for i, raw_line in enumerate(dsl_text.splitlines(), start=1):
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue

        stripped = line.strip()

        # `validate()` normalizes stanza order before calling this parser.
        # Duplicate stanza headers still need to be detected here.
        if stripped.rstrip(":") in catalog.STANZAS and stripped.endswith(":"):
            name = stripped.rstrip(":")
            if name in seen_stanzas:
                errors.append(ValidationError(i, f"duplicate `{name}:` stanza"))
            else:
                seen_stanzas.append(name)
            section = name
            current_during = None
            continue

        if section is None:
            errors.append(ValidationError(
                i, f"declaration outside any stanza: {stripped!r}"))
            continue

        # Inside Mission stanza, lines are either Start/During headers or
        # transitions.
        if section == "Mission":
            m = START_RE.match(line)
            if m:
                if m.group("colon"):
                    errors.append(ValidationError(
                        i, "`Start` takes no colon: write `Start <action>` "
                           "not `Start: <action>`"))
                if mission.start is not None:
                    errors.append(ValidationError(
                        i, "multiple `Start` directives"))
                mission.start = m.group("action")
                current_during = None
                continue
            m = DURING_RE.match(line)
            if m:
                current_during = DuringBlock(
                    action_name=m.group("action"), line_no=i)
                mission.during.append(current_during)
                continue
            m = TRANSITION_RE.match(line)
            if m:
                if current_during is None:
                    errors.append(ValidationError(
                        i, "transition line outside any `During` block"))
                    continue
                current_during.transitions.append(Transition(
                    event_name=m.group("event"),
                    target_action=m.group("action"),
                    line_no=i,
                ))
                continue
            # Common LLM mistake: an inline event constructor on the left of a
            # transition, e.g. `TimeReached hold_time(...) -> patrol`. Events
            # must be declared in the Events stanza and referenced by name.
            im = re.match(
                rf"^\s*(?P<cls>{_NAME_PATTERN})\s+"
                rf"(?P<inst>{_NAME_PATTERN})\s*\(.*\)\s*->\s*"
                rf"(?P<target>{_NAME_PATTERN})\s*$",
                line)
            if im:
                errors.append(ValidationError(
                    i,
                    f"transition cannot declare an event inline "
                    f"(`{im.group('cls')} {im.group('inst')}(...)`). Declare it "
                    f"in the Events: stanza, then reference it by name here: "
                    f"`{im.group('inst')} -> {im.group('target')}`"))
                continue
            errors.append(ValidationError(
                i, f"unrecognized Mission line: {stripped!r}"))
            continue

        # Inside Data / Actions / Events stanza: parse declaration.
        m = DECL_RE.match(line)
        if not m:
            # Common LLM mistake: a transition line (`event -> action`) placed
            # outside the Mission stanza. Give a targeted, fixable message.
            if TRANSITION_RE.match(line) or "->" in stripped:
                errors.append(ValidationError(
                    i,
                    f"transition `{stripped}` appears in the {section} stanza, "
                    f"but all `event -> action` transitions must go inside a "
                    f"`During <action>:` block in the Mission stanza"))
            else:
                errors.append(ValidationError(
                    i, f"unrecognized declaration in {section} stanza: "
                       f"{stripped!r}"))
            continue
        args, arg_errs = _parse_args(m.group("args"))
        for ae in arg_errs:
            errors.append(ValidationError(i, ae))
        decl = Declaration(
            class_name=m.group("cls"),
            instance_name=m.group("inst"),
            args=args,
            line_no=i,
        )
        if section == "Data":
            mission.data.append(decl)
        elif section == "Actions":
            mission.actions.append(decl)
        elif section == "Events":
            mission.events.append(decl)

    return mission, errors


# -----------------------------------------------------------------------------
# Semantic checks
# -----------------------------------------------------------------------------
def _instance_index(decls: list[Declaration]) -> dict[str, Declaration]:
    """Index declarations by instance name, preserving the first declaration."""
    out: dict[str, Declaration] = {}
    for d in decls:
        out.setdefault(d.instance_name, d)
    return out


def _check_declaration_against_catalog(
    decl: Declaration,
    expected_kind: str,
    data_by_name: dict[str, Declaration],
) -> list[ValidationError]:
    """Check class is known, has correct kind, and args type-check."""
    errs: list[ValidationError] = []
    entry = catalog.find(decl.class_name)
    if entry is None:
        errs.append(ValidationError(
            decl.line_no,
            f"unknown class `{decl.class_name}` (not in catalog)"))
        return errs
    if entry.kind != expected_kind:
        errs.append(ValidationError(
            decl.line_no,
            f"`{decl.class_name}` is a {entry.kind} but used in "
            f"{expected_kind.capitalize()} stanza"))
        return errs

    valid_params = {p.name: p for p in entry.params}

    # Unknown params
    for k in decl.args:
        if k not in valid_params:
            errs.append(ValidationError(
                decl.line_no,
                f"`{decl.class_name}` has no parameter `{k}` "
                f"(valid: {sorted(valid_params)})"))

    # Missing required params
    for p in entry.params:
        if p.required and p.name not in decl.args:
            errs.append(ValidationError(
                decl.line_no,
                f"`{decl.class_name}` missing required parameter `{p.name}`"))

    # Conditional-required params (e.g. RoutePlan `algo = survey` needs
    # spacing/angle_degrees/trigger_distance). These come from the
    # hand-maintained overlay, not the field schema.
    for rule in catalog.conditional_rules(decl.class_name):
        matched = True
        for pname, pval in rule.when.items():
            actual = decl.args.get(pname)
            actual_name = actual.name if isinstance(actual, _Ref) else actual
            if actual_name != pval:
                matched = False
                break
        if matched:
            missing = [r for r in rule.require if r not in decl.args]
            if missing:
                cond = ", ".join(f"`{k} = {v}`" for k, v in rule.when.items())
                errs.append(ValidationError(
                    decl.line_no,
                    f"`{decl.class_name}` with {cond} requires "
                    + ", ".join(f"`{m}`" for m in missing)))

    # Type checks for params present
    for k, v in decl.args.items():
        p = valid_params.get(k)
        if p is None:
            continue
        type_err = _check_value_type(v, p, data_by_name)
        if type_err:
            errs.append(ValidationError(decl.line_no, type_err))

    return errs


def _check_value_type(
    v: Any,
    p: catalog.Param,
    data_by_name: dict[str, Declaration],
) -> str | None:
    """Returns an error string or None if OK."""
    if p.type == "ref":
        if not isinstance(v, _Ref):
            return (f"parameter `{p.name}` must reference another declared "
                    f"instance (a bare identifier), got {v!r}")
        decl = data_by_name.get(v.name)
        if decl is None:
            return (f"parameter `{p.name}` references undeclared name "
                    f"`{v.name}`")
        if p.ref_kind and decl.class_name != p.ref_kind:
            return (f"parameter `{p.name}` expects a {p.ref_kind}, but "
                    f"`{v.name}` is a {decl.class_name}")
        return None

    if p.type == "float":
        if isinstance(v, str):
            return (f"parameter `{p.name}` expects a float; quoted strings "
                    f"are not valid DSL values")
        if isinstance(v, _Ref):
            return (f"parameter `{p.name}` expects a float, got the "
                    f"identifier `{v.name}`")
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return f"parameter `{p.name}` expects a float, got {type(v).__name__}"
        return None
    if p.type == "int":
        if not isinstance(v, int) or isinstance(v, bool):
            return f"parameter `{p.name}` expects an int, got {type(v).__name__}"
        return None
    if p.type == "bool":
        if not isinstance(v, bool):
            return f"parameter `{p.name}` expects a bool, got {type(v).__name__}"
        return None
    if p.type == "str":
        if isinstance(v, str):
            return (f"parameter `{p.name}`: quoted strings are not supported "
                    f"by the SteelEagle DSL grammar; write a bare identifier "
                    f"instead: {p.name} = {v}")
        if not isinstance(v, _Ref):
            return (f"parameter `{p.name}` expects a bare identifier "
                    f"(unquoted name), got {type(v).__name__}")
        if p.enum and v.name not in p.enum:
            return (f"parameter `{p.name}` must be one of {p.enum}, "
                    f"got {v.name!r}")
        return None
    if p.type == "list":
        if not isinstance(v, list):
            return f"parameter `{p.name}` expects a list, got {type(v).__name__}"
        return None
    return None


# -----------------------------------------------------------------------------
# Top-level entry point
# -----------------------------------------------------------------------------
def validate(dsl_text: str) -> list[ValidationError]:
    dsl_text, _ = normalize_dsl(dsl_text)
    mission, errors = parse(dsl_text)

    # Catch duplicate instance names within each stanza
    for label, decls in (
        ("Data", mission.data),
        ("Actions", mission.actions),
        ("Events", mission.events),
    ):
        seen: dict[str, int] = {}
        for d in decls:
            if d.instance_name in seen:
                errors.append(ValidationError(
                    d.line_no,
                    f"duplicate instance name `{d.instance_name}` in {label} "
                    f"(also defined at line {seen[d.instance_name]})"))
            else:
                seen[d.instance_name] = d.line_no

    data_by_name = _instance_index(mission.data)
    action_by_name = _instance_index(mission.actions)
    event_by_name = _instance_index(mission.events)

    # Class + arg checks
    for d in mission.data:
        errors.extend(_check_declaration_against_catalog(d, "data", data_by_name))
    for d in mission.actions:
        errors.extend(_check_declaration_against_catalog(d, "action", data_by_name))
    for d in mission.events:
        # Events can reference other events (e.g. AnyOf), so include events
        # in the resolvable name pool for refs:
        ref_pool = {**data_by_name, **event_by_name}
        errors.extend(_check_declaration_against_catalog(d, "event", ref_pool))

    # Special handling for AnyOf-style list-of-event-names: items must be
    # event references, not arbitrary strings.
    for d in mission.events:
        if d.class_name == "AnyOf":
            items = d.args.get("events")
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, _Ref):
                        errors.append(ValidationError(
                            d.line_no,
                            f"AnyOf `events` must contain bare event names, "
                            f"got {it!r}"))
                    elif it.name not in event_by_name:
                        errors.append(ValidationError(
                            d.line_no,
                            f"AnyOf references unknown event `{it.name}`"))

    # Mission stanza checks
    if not mission.actions:
        errors.append(ValidationError(
            None, "the Actions stanza is required and must declare at least "
                  "one action"))
    if mission.start is None:
        errors.append(ValidationError(
            None, "Mission stanza is missing `Start <action>`"))
    elif mission.start not in action_by_name:
        errors.append(ValidationError(
            None,
            f"`Start {mission.start}` references an action that is not "
            f"declared in the Actions stanza"))

    declared_during = {b.action_name for b in mission.during}
    for b in mission.during:
        if b.action_name not in action_by_name:
            errors.append(ValidationError(
                b.line_no,
                f"`During {b.action_name}:` references an action that is "
                f"not declared in the Actions stanza"))
        for t in b.transitions:
            if t.event_name != "done" and t.event_name not in event_by_name:
                errors.append(ValidationError(
                    t.line_no,
                    f"transition uses unknown event `{t.event_name}`"))
            if t.target_action not in action_by_name:
                if t.target_action in ("end", "stop", "terminate", "finish",
                                       "done", "exit"):
                    errors.append(ValidationError(
                        t.line_no,
                        f"transition target `{t.target_action}` is not a real "
                        f"state: SteelEagle DSL has NO terminal/end state. To "
                        f"finish, transition to a terminal action like "
                        f"`Land` or `ReturnToHome` declared in Actions"))
                else:
                    errors.append(ValidationError(
                        t.line_no,
                        f"transition target `{t.target_action}` is not declared "
                        f"in the Actions stanza"))

    # Reachability check: which actions are reachable from Start?
    if mission.start and mission.start in action_by_name:
        reachable = {mission.start}
        # Map action -> list of target actions reachable via transitions
        targets: dict[str, set[str]] = {a: set() for a in action_by_name}
        for b in mission.during:
            if b.action_name in targets:
                for t in b.transitions:
                    if t.target_action in action_by_name:
                        targets[b.action_name].add(t.target_action)
        # BFS
        frontier = [mission.start]
        while frontier:
            cur = frontier.pop()
            for nxt in targets.get(cur, ()):
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        # Suggest a concrete state to wire the orphan into: prefer an action
        # that is reachable and currently has no outgoing transition, so the
        # hint points at a natural predecessor (e.g. ReturnToHome -> Land).
        reachable_actions = [a for a in action_by_name if a in reachable]
        for action_name in action_by_name:
            if action_name not in reachable:
                pred = next(
                    (a for a in reachable_actions if not targets.get(a)),
                    mission.start)
                errors.append(ValidationError(
                    action_by_name[action_name].line_no,
                    f"action `{action_name}` is declared but never reached from "
                    f"Start — either add a transition into it (e.g. "
                    f"`During {pred}:` then `done -> {action_name}`) or remove "
                    f"the declaration"))

    return errors


def to_mission_ir(dsl_text: str) -> dict[str, Any]:
    """Build a lightweight fallback representation from validated DSL.

    This representation is used only when the SDK compiler is unavailable. It
    is not equivalent to `steeleagle_sdk.dsl.compiler.ir.MissionIR` and must
    not be treated as runtime-ready mission JSON.
    """
    dsl_text, _ = normalize_dsl(dsl_text)
    mission, _ = parse(dsl_text)

    def _dump_args(args: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in args.items():
            if isinstance(v, _Ref):
                out[k] = {"$ref": v.name}
            elif isinstance(v, list):
                out[k] = [{"$ref": x.name} if isinstance(x, _Ref) else x for x in v]
            else:
                out[k] = v
        return out

    return {
        "data": [
            {"class": d.class_name, "name": d.instance_name, "args": _dump_args(d.args)}
            for d in mission.data
        ],
        "actions": [
            {"class": d.class_name, "name": d.instance_name, "args": _dump_args(d.args)}
            for d in mission.actions
        ],
        "events": [
            {"class": d.class_name, "name": d.instance_name, "args": _dump_args(d.args)}
            for d in mission.events
        ],
        "mission": {
            "start": mission.start,
            "during": [
                {
                    "action": b.action_name,
                    "transitions": [
                        {"event": t.event_name, "target": t.target_action}
                        for t in b.transitions
                    ],
                }
                for b in mission.during
            ],
        },
    }
