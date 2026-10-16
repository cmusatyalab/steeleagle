import pytest

from app import daemon_config as dc
from app.daemon_config import ConfigError

SAMPLE = """\
# daemon-wide
hostname = "eagled"
vehicle-port-base = 9000
headless = true

[[vehicles]]
# the real drone
name = "harpy"
[vehicles.plugin]
plugin = "parrot_anafi"
runtime = "container"
url = "https://example.com/plugins.git"
tag = "main"
override = ""
[vehicles.plugin.args]
confidence = 1.0
modes = ["a", "b"]
[vehicles.sim]
default = false
[vehicles.args]
ip = "10.202.0.1"

[[engines]]
name = "detector"
[engines.plugin]
id = "yolo_qnn"
runtime = "container"
image = "docker.io/org/yolo"
tag = "v2"
[engines.plugin.args]
model = "yolov8n"

[[extras]]

[swarm-controller]
[swarm-controller.plugin]
id = "steeleagle_swarm_controller"
[swarm-controller.plugin.args]
"""

HARPY = {
    "name": "harpy",
    "plugin": {
        "id": "parrot_anafi",
        "runtime": "container",
        "source": {
            "kind": "repo",
            "url": "https://example.com/plugins.git",
            "tag": "main",
        },
        "args": {"confidence": 1.0, "modes": ["a", "b"]},
        "extra": {"override": ""},
    },
    "instance_fields": {"sim": {"default": False}, "args": {"ip": "10.202.0.1"}},
}


def _doc():
    return dc.parse(SAMPLE)


def _harpy(form):
    return form["instances"]["vehicle"][0]


def _apply(doc, form) -> str:
    dc.apply_form(doc, form)
    return dc.dumps(doc)


def test_list_sections_skips_nameless_entries_and_reads_both_id_spellings():
    got = [(c, s["name"], s["plugin"]["id"]) for c, s in dc.list_sections(_doc())]
    assert got == [
        ("vehicle", "harpy", "parrot_anafi"),
        ("engine", "detector", "yolo_qnn"),
    ]


def test_to_form_has_settings_and_every_category():
    form = dc.to_form(_doc())
    assert form["settings"] == {
        "hostname": "eagled",
        "vehicle_port_base": 9000,
        "headless": True,
    }
    assert set(form["instances"]) == {"vehicle", "engine", "monitor", "extra"}
    assert _harpy(form) == HARPY
    assert form["instances"]["engine"][0]["plugin"]["source"] == {
        "kind": "image",
        "url": "docker.io/org/yolo",
        "tag": "v2",
    }
    assert form["instances"]["monitor"] == []


def test_unchanged_form_round_trips_byte_for_byte():
    doc = _doc()
    assert _apply(doc, dc.to_form(_doc())) == SAMPLE


def test_a_changed_entry_is_rewritten_with_id_spelling():
    doc = _doc()
    form = dc.to_form(doc)
    _harpy(form)["plugin"]["args"]["new"] = 1
    table = dc.parse(_apply(doc, form))["vehicles"][0]["plugin"].unwrap()
    assert table["id"] == "parrot_anafi" and "plugin" not in table


def test_edit_preserves_comments_unknown_keys_and_untouched_entries():
    doc = _doc()
    form = dc.to_form(doc)
    _harpy(form)["plugin"]["args"] = {"confidence": 2, "modes": ["a", "b"], "new": "x"}

    out = _apply(doc, form)

    assert "# daemon-wide" in out and "# the real drone" in out
    assert "[swarm-controller.plugin]" in out
    assert 'override = ""' in out
    reparsed = dc.to_form(dc.parse(out))
    assert _harpy(reparsed)["plugin"]["args"] == {
        "confidence": 2.0,
        "modes": ["a", "b"],
        "new": "x",
    }
    assert reparsed["instances"]["engine"] == dc.to_form(_doc())["instances"]["engine"]


def test_integral_numbers_replacing_floats_stay_floats():
    doc = dc.parse(
        SAMPLE
        + '\n[[monitors]]\nname = "m"\n[monitors.plugin]\nid = "p"\n[monitors.plugin.args]\nthresholds = [1.0, 2.0]\n'
    )
    form = dc.to_form(doc)
    _harpy(form)["plugin"]["args"]["confidence"] = 1  # what JSON delivers for 1.0
    form["instances"]["monitor"][0]["plugin"]["args"]["thresholds"] = [1, 2]

    out = _apply(doc, form)

    assert "confidence = 1.0" in out
    assert "thresholds = [1.0, 2.0]" in out


def test_settings_are_set_added_and_removed():
    doc = _doc()
    form = dc.to_form(doc)
    form["settings"] = {"hostname": "renamed", "gabriel_port": 9099, "headless": None}

    out = _apply(doc, form)

    assert dc.daemon_settings(dc.parse(out)) == {
        "hostname": "renamed",
        "gabriel_port": 9099,
    }
    assert out.index("gabriel-port") < out.index("[[vehicles]]")


def test_instances_are_added_removed_and_renamed():
    doc = _doc()
    form = dc.to_form(doc)
    monitor = {
        "name": "battery",
        "plugin": {
            "id": "battery_monitor",
            "runtime": "sandbox",
            "source": None,
            "args": {"threshold": 20},
            "extra": {},
        },
        "instance_fields": {},
    }
    form["instances"]["monitor"] = [monitor]
    form["instances"]["engine"] = []
    _harpy(form)["name"] = "eagle"

    out = _apply(doc, form)

    got = dc.to_form(dc.parse(out))
    assert got["instances"]["monitor"] == [monitor]
    assert got["instances"]["engine"] == []
    assert [s["name"] for s in got["instances"]["vehicle"]] == ["eagle"]
    assert "[[engines]]" not in out


def test_nameless_entries_survive_when_their_category_is_emptied():
    doc = _doc()
    form = dc.to_form(doc)
    form["instances"]["extra"] = []
    assert "[[extras]]" in _apply(doc, form)


@pytest.mark.parametrize(
    "names, fragment",
    [
        (["a", "a"], "duplicate vehicle names: a"),
        (["a", ""], "every vehicle needs a name"),
    ],
)
def test_apply_form_rejects_bad_names(names, fragment):
    form = {
        "settings": {},
        "instances": {"vehicle": [{**HARPY, "name": n} for n in names]},
    }
    with pytest.raises(ConfigError, match=fragment):
        dc.apply_form(_doc(), form)


def test_parse_error_carries_line_and_column():
    with pytest.raises(ConfigError) as e:
        dc.parse("a = \n")
    assert e.value.line == 1 and e.value.column is not None


def test_config_hash_is_stable_and_content_sensitive():
    assert dc.config_hash(SAMPLE) == dc.config_hash(SAMPLE)
    assert dc.config_hash(SAMPLE) != dc.config_hash(SAMPLE + "\n")


def test_section_to_table_name_and_managed_keys_cannot_be_overridden():
    section = {
        "name": "d",
        "plugin": {
            "id": "p",
            "runtime": "process",
            "source": {"kind": "repo", "url": "https://x", "tag": "t"},
            "args": {"a": 1},
            "extra": {"id": "evil", "url": "evil", "args": {"z": 1}, "keep": 1},
        },
        "instance_fields": {"name": "../../etc"},
    }
    table = dc.section_to_table("engine", section)
    assert table["name"] == "d"
    assert table["plugin"]["id"] == "p"
    assert table["plugin"]["url"] == "https://x"
    assert table["plugin"]["args"] == {"a": 1}
    assert table["plugin"]["keep"] == 1


@pytest.mark.parametrize(
    "text, fragment",
    [
        ('[vehicles]\nname = "x"\n', "array of tables"),
        ('vehicles = "x"\n', "array of tables"),
        ('[[engines]]\nname = "e"\nplugin = "p"\n', "plugin must be a table"),
        (
            '[[engines]]\nname = "e"\n[engines.plugin]\nargs = "s"\n',
            "args must be a table",
        ),
    ],
)
def test_wrong_shape_documents_fail_validation(text, fragment):
    with pytest.raises(ConfigError) as e:
        dc.validate(dc.parse(text))
    assert fragment in e.value.message


def test_validate_accepts_a_well_formed_document():
    dc.validate(_doc())
