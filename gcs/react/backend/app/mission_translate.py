"""Pure conversions between the Plan page's shapes and eaglec's -- see
docs/superpowers/specs/2026-10-14-gcs-eaglec-compiler-integration-design.md.

The frontend works in bare type names ("Patrol") and plain-JSON params;
eaglec works in qualified names ("actions.Patrol") and AST JSON (the form
parser.ParseFromJson reads). TypeIndex holds the registry lookups every
conversion needs."""

import json
import math
import re
from collections import Counter

# params types whose constants are generated from the mission's GeoJSON,
# one per drawn feature: the frontend picks these from the Map tab instead
# of from a fixed enum.
FEATURE_TYPES = (
    "params.Point",
    "params.LineString",
    "params.MultiLineString",
    "params.Polygon",
)

_NUMBER = {"float32", "float64"}
_INTEGER = {
    "int",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
}


def bare(qualified: str) -> str:
    """'actions.Patrol' -> 'Patrol'."""
    return qualified.rsplit(".", 1)[-1]


def qualifier(qualified: str) -> str:
    """'enums.AltitudeMode' -> 'enums'; '' for an unqualified name."""
    return qualified.rsplit(".", 1)[0] if "." in qualified else ""


def _all_fields(base: dict) -> list[dict]:
    return list(base.get("fields") or []) + list(base.get("optFields") or [])


def _display_keys(bases: dict) -> dict[str, str]:
    """Qualified name -> frontend key: the bare name, unless another type
    in the same section shares it, in which case the qualified name."""
    counts = Counter(bare(q) for q in bases)
    return {q: bare(q) if counts[bare(q)] == 1 else q for q in bases}


class TypeIndex:
    """Lookups over an eaglec type registry (`eaglec schema` output)."""

    def __init__(self, registry: dict) -> None:
        self.actions: dict = registry.get("actions") or {}
        self.events: dict = registry.get("events") or {}
        self.datatypes: dict = registry.get("datatypes") or {}
        self.enums: dict = registry.get("enums") or {}
        self._keys = {
            "actions": _display_keys(self.actions),
            "events": _display_keys(self.events),
            "enums": _display_keys(
                {q: b for q, b in self.enums.items() if q not in FEATURE_TYPES}
            ),
        }
        self._by_key = {
            section: {k: q for q, k in keys.items()}
            for section, keys in self._keys.items()
        }
        self._fields: dict[str, dict[str, str]] = {}
        for section in (self.actions, self.events, self.datatypes):
            for q, base in section.items():
                self._fields[q] = {f["name"]: f["type"] for f in _all_fields(base)}

    def key(self, section: str, qualified: str) -> str | None:
        return self._keys[section].get(qualified)

    def qualify(self, section: str, key: str) -> str | None:
        return self._by_key[section].get(key)

    def field_type(self, qualified: str, field: str) -> str | None:
        return self._fields.get(qualified, {}).get(field)

    def kind(self, go_type: str) -> str:
        if go_type in FEATURE_TYPES:
            return "feature"
        if go_type in self.enums:
            return "enum"
        if go_type in self.datatypes:
            return "object"
        if go_type.startswith("[]"):
            return "array"
        if go_type in _NUMBER:
            return "number"
        if go_type in _INTEGER:
            return "integer"
        if go_type == "bool":
            return "boolean"
        if go_type == "string":
            return "string"
        return "unknown"


def registry_to_schema(index: TypeIndex) -> dict:
    """The /api/schema body the palette and FieldInput consume."""
    return {
        "actions": {
            index.key("actions", q): _type_schema(index, q, base)
            for q, base in index.actions.items()
        },
        "events": {
            index.key("events", q): _type_schema(index, q, base)
            for q, base in index.events.items()
        },
        "enums": {
            index.key("enums", q): {
                "type": q,
                "description": base.get("comment", ""),
                "values": [f["name"] for f in base.get("fields") or []],
            }
            for q, base in index.enums.items()
            if q not in FEATURE_TYPES
        },
    }


def _type_schema(index: TypeIndex, qualified: str, base: dict) -> dict:
    return {
        "type": qualified,
        "description": base.get("comment", ""),
        "fields": _fields(index, base),
    }


def _fields(index: TypeIndex, base: dict) -> list[dict]:
    return [_field(index, f, required=True) for f in base.get("fields") or []] + [
        _field(index, f, required=False) for f in base.get("optFields") or []
    ]


def _field(index: TypeIndex, f: dict, required: bool) -> dict:
    go_type = f["type"]
    entry = {
        "name": f["name"],
        "go_type": go_type,
        "required": required,
        "description": f.get("comment", ""),
    }
    kind = index.kind(go_type)
    if kind == "feature":
        entry.update(type="string", map_feature=True, feature_type=bare(go_type))
    elif kind == "enum":
        entry.update(type="string", enum_type=index.key("enums", go_type))
    elif kind == "object":
        entry.update(
            type="object",
            object_type=bare(go_type),
            nested_fields=_fields(index, index.datatypes[go_type]),
        )
    elif kind in ("number", "integer", "boolean", "array"):
        entry["type"] = kind
    else:
        entry["type"] = "string"
    if not required and f.get("value"):
        entry["default"] = _typed_default(kind, f["value"])
    return entry


def _typed_default(kind: str, value: str):
    """A field's #optional[...] default (always a string in the registry)
    as the JSON type the frontend's inputs hold."""
    try:
        if kind == "number":
            return float(value)
        if kind == "integer":
            return int(value)
    except ValueError:
        return value
    if kind == "boolean":
        return value == "true"
    if kind == "enum":
        return bare(value)
    return value


_GEOMETRIES = ("Point", "LineString", "MultiLineString", "Polygon")


def graph_to_ast(graph: dict, index: TypeIndex, header: dict) -> dict:
    """The frontend's {nodes, events, edges, start_id} as eaglec AST JSON,
    with header's Modules: and Imports: and no Role:. Unknown type names
    pass through unqualified so the compiler reports them on their decl."""
    blocks: dict[str, list[dict]] = {}
    for edge in graph.get("edges") or []:
        blocks.setdefault(edge["source"], []).append(
            {"Event": edge["event_id"], "Next": edge["target"]}
        )
    ast = {
        "Modules": header["Modules"],
        "Imports": header["Imports"],
        "Actions": {
            "Decls": [_decl(index, "actions", n) for n in graph.get("nodes") or []]
        },
        "Events": {
            "Decls": [_decl(index, "events", e) for e in graph.get("events") or []]
        },
    }
    if graph.get("start_id"):
        ast["Mission"] = {
            "Start": graph["start_id"],
            "Blocks": [{"Action": s, "Rules": r} for s, r in blocks.items()],
        }
    return ast


def _decl(index: TypeIndex, section: str, instance: dict) -> dict:
    qualified = index.qualify(section, instance["type_name"]) or instance["type_name"]
    attrs = []
    for key, raw in (instance.get("params") or {}).items():
        value = _value(index, index.field_type(qualified, key), raw)
        if value is not None:
            attrs.append({"Key": key, "Value": value})
    return {"Type": qualified, "Name": instance["instance_id"], "Attrs": attrs}


def _value(index: TypeIndex, go_type: str | None, value) -> dict | None:
    """One plain-JSON param value as an AST Value, shaped by the field's Go
    type when it's known. None for an unset value (null or "")."""
    if value is None or value == "":
        return None
    kind = index.kind(go_type) if go_type else "unknown"
    if kind == "feature":
        return {"Ident": f"{go_type}_{value}"}
    if kind == "enum" and isinstance(value, str):
        return {"Ident": value if "." in value else f"{qualifier(go_type)}.{value}"}
    if isinstance(value, dict):
        if kind != "object":
            raise ValueError(
                f"an object was given for a field of type {go_type or 'unknown'}"
            )
        args = []
        for key, raw in value.items():
            nested = _value(index, index.field_type(go_type, key), raw)
            if nested is not None:
                args.append({"Key": key, "Value": nested})
        return {"Inline": {"Type": go_type, "Args": args}}
    if isinstance(value, bool):
        return {"Ident": "true" if value else "false"}
    if isinstance(value, (int, float)):
        if kind == "number":
            return {"Float": float(value)}
        if kind == "integer" and float(value).is_integer():
            return {"Int": int(value)}
        return {"Int": value} if isinstance(value, int) else {"Float": value}
    if isinstance(value, list):
        elem_type = go_type[2:] if kind == "array" else None
        elems = [_value(index, elem_type, e) for e in value]
        return {"Array": {"Elems": [e for e in elems if e is not None]}}
    return {"String": str(value)}


def prepare_geojson(text: str) -> tuple[bytes | None, list[str]]:
    """The Map tab's GeoJSON as eaglec takes it -- None when there are no
    features, since eaglec rejects an empty file -- and an error per
    feature eaglec would reject, naming the feature. Mirrors the SDK's
    geo.parse rules plus the Go-identifier rule for the generated
    params.<Geometry>_<name> constants."""
    if not text or not text.strip():
        return None, []
    try:
        collection = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"Map features are not valid GeoJSON: {e}"]
    features = collection.get("features") if isinstance(collection, dict) else None
    if features is None:
        return None, []
    if not isinstance(features, list):
        return None, ["Map features are not valid GeoJSON: features must be a list"]
    if not features:
        return None, []
    errors = []
    seen = set()
    for i, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            errors.append(f"Map feature {i} is not a valid GeoJSON feature")
            continue
        properties = feature.get("properties")
        geometry_obj = feature.get("geometry")
        name = (properties if isinstance(properties, dict) else {}).get("name")
        geometry = (geometry_obj if isinstance(geometry_obj, dict) else {}).get("type")
        if not isinstance(name, str) or not name:
            errors.append(f"Map feature {i} has no name")
            continue
        if name in seen:
            errors.append(f"Map feature name '{name}' is used more than once")
            continue
        seen.add(name)
        if geometry not in _GEOMETRIES:
            errors.append(
                f"Map feature '{name}' is a {geometry}, but only Point, LineString, "
                "MultiLineString and Polygon features are supported"
            )
            continue
        if not f"{geometry}_{name}".isidentifier():
            errors.append(
                f"Map feature '{name}' can only contain letters, digits and underscores"
            )
    return text.encode(), errors


# The DSL header the Plan page wrote before the SDK renamed it to Imports:
_LEGACY_IMPORT_HEADER = re.compile(r"^(\s*)Import(\s*):", re.MULTILINE)


def upgrade_legacy_dsl(dsl: str) -> tuple[str, list[str]]:
    """DSL text with the pre-rename `Import:` header rewritten to
    `Imports:`, so files exported before the SDK grammar change still load,
    and a warning saying so (none if nothing changed). Everything else the
    old exports wrote -- bare type names and enum values, string map-feature
    names -- the current grammar already accepts."""
    upgraded, count = _LEGACY_IMPORT_HEADER.subn(r"\1Imports\2:", dsl)
    if not count:
        return dsl, []
    return upgraded, ["Converted the old Import: header to Imports:"]


def ast_to_graph(ast: dict, index: TypeIndex) -> dict:
    """eaglec AST JSON (from `eaglec parse`) as the frontend's graph, plus
    the mission's own modules/imports and warnings about anything the
    canvas can't represent. Data decls referenced by an ident are inlined
    into the params that reference them."""
    warnings: list[str] = []
    data = {d["Name"]: d for d in _decls(ast, "Data")}
    used: set[str] = set()

    def instances(stanza: str, section: str) -> list[dict]:
        out = []
        for d in _decls(ast, stanza):
            key = _type_key(index, section, d["Type"], warnings)
            owner = index.qualify(section, key) or d["Type"]
            params = {
                a["Key"]: _from_value(
                    index, index.field_type(owner, a["Key"]), a["Value"], data, used
                )
                for a in d.get("Attrs") or []
            }
            out.append({"instance_id": d["Name"], "type_name": key, "params": params})
        return out

    nodes = instances("Actions", "actions")
    events = instances("Events", "events")
    mission = ast.get("Mission") or {}
    edges = [
        {"source": block["Action"], "event_id": rule["Event"], "target": rule["Next"]}
        for block in mission.get("Blocks") or []
        for rule in block.get("Rules") or []
    ]
    role = (ast.get("Role") or {}).get("Name")
    if role:
        warnings.append(
            f"Role {role} is ignored: the GCS compiles missions without a role"
        )
    for name in data:
        if name not in used:
            warnings.append(
                f"Data {name} is not used by any action or event and was dropped"
            )
    return {
        "nodes": nodes,
        "events": events,
        "edges": edges,
        "start_id": mission.get("Start") or None,
        "modules": [
            {
                "path": m["Path"],
                "version": m.get("Version", ""),
                "override": m.get("Override", ""),
            }
            for m in (ast.get("Modules") or {}).get("Modules") or []
        ],
        "imports": [
            {"path": i["Path"], "alias": i.get("Alias", "")}
            for i in (ast.get("Imports") or {}).get("Imports") or []
        ],
        "warnings": warnings,
    }


def _decls(ast: dict, stanza: str) -> list[dict]:
    return (ast.get(stanza) or {}).get("Decls") or []


def _type_key(
    index: TypeIndex, section: str, type_name: str, warnings: list[str]
) -> str:
    """The frontend key for a decl's type. A bare name the palette knows
    ("Land") is accepted as-is; anything else unknown is warned about and
    shown by its bare name."""
    key = index.key(section, type_name)
    if key is not None:
        return key
    if index.qualify(section, type_name) is not None:
        return type_name
    warnings.append(f"{type_name} is not a known {section[:-1]} type")
    return bare(type_name)


def _from_value(
    index: TypeIndex, go_type: str | None, value: dict, data: dict, used: set
):
    """One AST Value as the plain-JSON param the frontend holds."""
    if "Float" in value:
        return float(value["Float"])
    if "Int" in value:
        return int(value["Int"])
    if "String" in value:
        return value["String"]
    if "Array" in value:
        elem_type = go_type[2:] if go_type and go_type.startswith("[]") else None
        return [
            _from_value(index, elem_type, e, data, used)
            for e in value["Array"].get("Elems") or []
        ]
    if "Inline" in value:
        return _from_attrs(
            index,
            go_type or value["Inline"]["Type"],
            value["Inline"].get("Args"),
            data,
            used,
        )
    ident = value["Ident"]
    if ident in ("true", "false"):
        return ident == "true"
    if ident in data:
        used.add(ident)
        return _from_attrs(
            index, go_type or data[ident]["Type"], data[ident].get("Attrs"), data, used
        )
    if go_type and index.kind(go_type) == "feature":
        prefix = bare(go_type) + "_"
        name = bare(ident)
        return name[len(prefix) :] if name.startswith(prefix) else name
    return bare(ident)


def _from_attrs(index: TypeIndex, owner: str, attrs, data: dict, used: set) -> dict:
    return {
        a["Key"]: _from_value(
            index, index.field_type(owner, a["Key"]), a["Value"], data, used
        )
        for a in attrs or []
    }


def ast_to_dsl(ast: dict) -> str:
    """eaglec AST JSON as DSL text, in the grammar of
    sdk/dsl/compiler/parser/ast.go."""
    parts = []
    role = (ast.get("Role") or {}).get("Name")
    if role:
        parts.append(f"Role {role}:")
    modules = (ast.get("Modules") or {}).get("Modules") or []
    if modules:
        parts.append(
            "Modules:\n" + "\n".join(f"    {_module_line(m)}" for m in modules)
        )
    imports = (ast.get("Imports") or {}).get("Imports") or []
    if imports:
        lines = []
        for i in imports:
            alias = f"{i['Alias']} " if i.get("Alias") else ""
            lines.append(f"    {alias}{_quote(i['Path'])}")
        parts.append("Imports:\n" + "\n".join(lines))
    for stanza in ("Data", "Actions", "Events"):
        decls = _decls(ast, stanza)
        if decls:
            parts.append(
                f"{stanza}:\n"
                + "\n".join(
                    f"    {d['Type']} {d['Name']}({_render_attrs(d.get('Attrs'))})"
                    for d in decls
                )
            )
    mission = ast.get("Mission") or {}
    if mission.get("Start"):
        lines = ["Mission:", f"    Start {mission['Start']}"]
        for block in mission.get("Blocks") or []:
            lines.append(f"    During {block['Action']}:")
            lines += [
                f"        {r['Event']} -> {r['Next']}" for r in block.get("Rules") or []
            ]
        parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n"


def _module_line(module: dict) -> str:
    line = _quote(module["Path"])
    if module.get("Version"):
        line += f" {module['Version']}"
    if module.get("Override"):
        line += f" => {_quote(module['Override'])}"
    return line


def _quote(s: str) -> str:
    """The DSL has no escapes: a string is quoted with whichever quote
    character it doesn't contain."""
    if '"' not in s:
        return f'"{s}"'
    if "'" not in s:
        return f"'{s}'"
    raise ValueError(f"can't write a DSL string containing both quote characters: {s}")


def _render_attrs(attrs) -> str:
    return ", ".join(f"{a['Key']}={_render_value(a['Value'])}" for a in attrs or [])


def _render_value(value: dict) -> str:
    if "Float" in value:
        return _render_float(float(value["Float"]))
    if "Int" in value:
        return str(int(value["Int"]))
    if "String" in value:
        return _quote(value["String"])
    if "Array" in value:
        return (
            "["
            + ", ".join(_render_value(e) for e in value["Array"].get("Elems") or [])
            + "]"
        )
    if "Inline" in value:
        return (
            f"{value['Inline']['Type']}({_render_attrs(value['Inline'].get('Args'))})"
        )
    return value["Ident"]


def _render_float(f: float) -> str:
    """A float in the DSL's Float token form (-?digits.digits): always a
    decimal point, never an exponent."""
    if not math.isfinite(f):
        raise ValueError(f"can't write a non-finite float in the DSL: {f}")
    s = repr(f)
    if "e" in s or "E" in s:
        s = f"{f:.20f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    if "." not in s:
        s += ".0"
    return s
