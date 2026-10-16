"""Pure helpers over an eagled config TOML document (the shape of
cmd/eagled/defaults/new_config.toml) -- see
docs/superpowers/specs/2026-10-15-gcs-generic-plugins-design.md.

Everything that knows the config's TOML layout lives here, so the mock
daemon and the routes agree on it and a layout change in the eagled rework
is a change to this one file. tomlkit (not the `toml` package api.py uses)
because config edits are written back to the daemon: comments and
formatting outside the edited section must survive.

The GCS edits the whole document at once (eagled's Configure replaces it
whole): `to_form` turns it into a form model, and `apply_form` merges an
edited form back into the original document, so comments, unknown keys,
nameless entries, and top-level tables the form doesn't show (such as
[swarm-controller]) survive. A form is

    {"settings": {<api name>: value},           # see _SETTINGS_KEYS
     "instances": {<category>: [section, ...]}}

and a "section" is the JSON shape of one plugin instance:

    {"name": str,
     "plugin": {"id": str,
                "runtime": str | None,
                "source": {"kind": "repo" | "image", "url": str, "tag": str} | None,
                "args": dict,
                "extra": dict},     # unrecognized [*.plugin] keys, passed through
     "instance_fields": dict}       # every instance key but name/plugin
"""

import hashlib
from typing import Any

import tomlkit
from tomlkit.exceptions import ParseError
from tomlkit.toml_document import TOMLDocument

CATEGORY_TABLES = {
    "vehicle": "vehicles",
    "engine": "engines",
    "monitor": "monitors",
    "extra": "extras",
}
CATEGORIES = list(CATEGORY_TABLES)
RUNTIMES = ["process", "sandbox", "container"]

# new_config.toml spells the plugin identifier both `id` and `plugin`; both
# are read, `id` is written.
_PLUGIN_KEYS = {"id", "plugin", "runtime", "url", "image", "tag", "args"}

_SETTINGS_KEYS = {
    "hostname": "hostname",
    "vehicle-port-base": "vehicle_port_base",
    "gabriel-port": "gabriel_port",
    "swarm-controller-port": "swarm_controller_port",
    "headless": "headless",
    "auto-run": "auto_run",
    "auto-install": "auto_install",
}


class ConfigError(ValueError):
    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def parse(text: str) -> TOMLDocument:
    try:
        return tomlkit.parse(text)
    except ParseError as e:
        raise ConfigError(str(e), e.line, e.col) from e


def dumps(doc) -> str:
    return tomlkit.dumps(doc)


def config_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plain(value):
    return value.unwrap() if hasattr(value, "unwrap") else value


def _scalars_first(table: dict) -> dict:
    """TOML needs a table's plain keys before its sub-tables."""
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    tables = {k: v for k, v in table.items() if isinstance(v, dict)}
    return {**scalars, **tables}


def _plugin_from_table(table) -> dict:
    if not isinstance(table, dict):
        raise ConfigError("plugin must be a table")
    if not isinstance(table.get("args", {}), dict):
        raise ConfigError("plugin.args must be a table")
    extra = {k: v for k, v in table.items() if k not in _PLUGIN_KEYS}
    source = None
    if table.get("image"):
        source = {"kind": "image", "url": table["image"], "tag": table.get("tag", "")}
        if table.get("url"):
            extra["url"] = table["url"]
    elif table.get("url"):
        source = {"kind": "repo", "url": table["url"], "tag": table.get("tag", "")}
    elif table.get("tag"):
        extra["tag"] = table["tag"]
    return {
        "id": table.get("id") or table.get("plugin") or "",
        "runtime": table.get("runtime") or None,
        "source": source,
        "args": dict(table.get("args", {})),
        "extra": extra,
    }


def _plugin_to_table(plugin: dict) -> dict:
    table: dict[str, Any] = {"id": plugin.get("id", "")}
    if plugin.get("runtime"):
        table["runtime"] = plugin["runtime"]
    source = plugin.get("source")
    if source:
        table["image" if source["kind"] == "image" else "url"] = source["url"]
        if source.get("tag"):
            table["tag"] = source["tag"]
    # Extras first, so a pass-through key can never displace a managed one.
    table = {**(plugin.get("extra") or {}), **table}
    table["args"] = dict(plugin.get("args") or {})
    return _scalars_first(table)


def table_to_section(category: str, table) -> dict:
    t = _plain(table)
    if not isinstance(t, dict):
        raise ConfigError("a config entry must be a table")
    return {
        "name": t.get("name"),
        "plugin": _plugin_from_table(t.get("plugin", {})),
        "instance_fields": {k: v for k, v in t.items() if k not in ("name", "plugin")},
    }


def section_to_table(category: str, section: dict) -> dict:
    table: dict[str, Any] = {"name": section["name"]}
    table.update(section.get("instance_fields") or {})
    # Reassigned after instance_fields (keeping its first position) so they
    # can't rename the instance.
    table["name"] = section["name"]
    table["plugin"] = _plugin_to_table(section["plugin"])
    return _scalars_first(table)


def _keep_floats(old, new):
    """JSON can't tell 1 from 1.0, so an integral number replacing an
    existing float is written back as a float."""
    if isinstance(new, dict) and isinstance(old, dict):
        return {k: _keep_floats(old.get(k), v) for k, v in new.items()}
    if isinstance(new, list) and isinstance(old, list) and len(new) == len(old):
        return [_keep_floats(o, n) for o, n in zip(old, new)]
    if isinstance(old, float) and isinstance(new, int) and not isinstance(new, bool):
        return float(new)
    return new


def _replace_table(table, new: dict) -> None:
    """Swaps a table's contents in place: keys that stay are reassigned
    where they are, so the table's position, key order, and comments are
    untouched."""
    for key in [k for k in table.keys() if k not in new]:
        del table[key]
    for key, value in new.items():
        table[key] = value


def _aot(doc, category: str, create: bool = False):
    if category not in CATEGORY_TABLES:
        raise ConfigError(f"unknown category {category!r}")
    key = CATEGORY_TABLES[category]
    if key not in doc:
        if not create:
            return None
        doc[key] = tomlkit.aot()
    value = doc[key]
    if not isinstance(value, list) or not all(isinstance(t, dict) for t in value):
        raise ConfigError(f"[{key}] must be an array of tables ([[{key}]])")
    return value


def _find(doc, category: str, name: str):
    for table in _aot(doc, category) or []:
        if table.get("name") == name:
            return table
    return None


def list_sections(doc) -> list[tuple[str, dict]]:
    sections = []
    for category in CATEGORIES:
        for table in _aot(doc, category) or []:
            if table.get("name"):
                sections.append((category, table_to_section(category, table)))
    return sections


def validate(doc) -> None:
    """Raises ConfigError unless every instance has the shape the helpers
    above expect. Valid TOML can still be the wrong
    shape (`[vehicles]` for `[[vehicles]]`); checking up front turns what
    would be a crash mid-edit into a message."""
    list_sections(doc)


def daemon_settings(doc) -> dict:
    return {api: _plain(doc[key]) for key, api in _SETTINGS_KEYS.items() if key in doc}


def to_form(doc) -> dict:
    instances = {category: [] for category in CATEGORIES}
    for category, section in list_sections(doc):
        instances[category].append(section)
    return {"settings": daemon_settings(doc), "instances": instances}


def apply_form(doc, form: dict) -> None:
    """Merges `form` into `doc` in place. A setting that is None or missing
    is removed. Each category's instances are matched to existing entries
    by name: matches are rewritten in place (keeping their position and
    comments), new names are appended, and named entries the form leaves
    out are removed. A renamed instance is therefore a remove plus an add."""
    settings = form.get("settings") or {}
    for key, api in _SETTINGS_KEYS.items():
        value = settings.get(api)
        if value is None:
            if key in doc:
                del doc[key]
        else:
            doc[key] = _keep_floats(_plain(doc.get(key)), value)
    for category in CATEGORIES:
        sections = (form.get("instances") or {}).get(category) or []
        names = [s.get("name") for s in sections]
        if not all(names):
            raise ConfigError(f"every {category} needs a name")
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ConfigError(f"duplicate {category} names: {', '.join(duplicates)}")
        aot = _aot(doc, category, create=bool(sections))
        if aot is None:
            continue
        wanted = set(names)
        for index in reversed(range(len(aot))):
            name = aot[index].get("name")
            if name and name not in wanted:
                del aot[index]
        for section in sections:
            table = _find(doc, category, section["name"])
            if table is None:
                aot.append(section_to_table(category, section))
            elif table_to_section(category, table) != section:
                # Unchanged entries are left alone, keeping their exact text.
                _replace_table(
                    table,
                    _keep_floats(_plain(table), section_to_table(category, section)),
                )
        if len(aot) == 0:
            del doc[CATEGORY_TABLES[category]]
