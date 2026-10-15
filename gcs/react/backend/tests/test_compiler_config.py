import os
from pathlib import Path

import pytest

from app.compiler_config import (
    DEFAULT_IMPORTS,
    REPO_ROOT,
    SDK_MODULE,
    Import,
    Module,
    ensure_eaglec,
    load_compiler_config,
)


def test_defaults_point_into_the_repo(tmp_path):
    cfg = load_compiler_config(None, repo_root=tmp_path)

    assert cfg.eaglec == tmp_path / "sdk" / "cmd" / "eaglec" / "eaglec"
    assert not cfg.eaglec_configured
    assert cfg.sdk_dir == tmp_path / "sdk"
    assert cfg.modules == (Module(SDK_MODULE, override=str(tmp_path / "sdk")),)
    assert [i.path for i in cfg.imports] == list(DEFAULT_IMPORTS)
    assert cfg.timeout_s == 300.0


def test_real_repo_root_contains_the_sdk():
    assert (REPO_ROOT / "sdk" / "go.mod").is_file()
    assert (REPO_ROOT / "sdk" / "cmd" / "eaglec" / "main.go").is_file()


def test_empty_section_is_the_same_as_none(tmp_path):
    assert load_compiler_config({}, repo_root=tmp_path) == load_compiler_config(
        None, repo_root=tmp_path
    )


def test_sdk_version_replaces_the_local_override(tmp_path):
    cfg = load_compiler_config({"sdk_version": "v4.0-beta"}, repo_root=tmp_path)

    assert cfg.modules == (Module(SDK_MODULE, version="v4.0-beta"),)


def test_imports_are_additive_and_deduplicated(tmp_path):
    cfg = load_compiler_config(
        {
            "imports": [
                {"path": DEFAULT_IMPORTS[0]},
                {"path": "example.com/x/actions", "alias": "xa"},
                {"path": "example.com/x/actions"},
            ]
        },
        repo_root=tmp_path,
    )

    assert [i.path for i in cfg.imports] == [*DEFAULT_IMPORTS, "example.com/x/actions"]
    assert cfg.imports[-1] == Import("example.com/x/actions", "xa")


def test_modules_are_additive_and_always_keep_the_sdk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg = load_compiler_config(
        {
            "modules": [
                {"path": SDK_MODULE, "version": "v9.9.9"},
                {"path": "example.com/x", "override": "plugins/x"},
                {"path": "example.com/x", "version": "v1.0.0"},
                {"path": "example.com/y", "version": "v1.2.0"},
            ]
        },
        repo_root=tmp_path,
    )

    assert cfg.modules == (
        Module(SDK_MODULE, override=str(tmp_path / "sdk")),
        Module("example.com/x", override=str((tmp_path / "plugins" / "x").resolve())),
        Module("example.com/y", version="v1.2.0"),
    )


def test_configured_eaglec_is_resolved_and_marked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg = load_compiler_config({"eaglec": "bin/eaglec"}, repo_root=tmp_path)

    assert cfg.eaglec == (tmp_path / "bin" / "eaglec").resolve()
    assert cfg.eaglec_configured


def test_timeout_is_configurable(tmp_path):
    assert load_compiler_config({"timeout_s": 30}, repo_root=tmp_path).timeout_s == 30.0


def test_header_is_eaglec_ast_json(tmp_path):
    cfg = load_compiler_config(
        {"imports": [{"path": "example.com/x", "alias": "x"}]}, repo_root=tmp_path
    )

    header = cfg.header()

    assert header["Modules"] == {
        "Modules": [{"Path": SDK_MODULE, "Override": str(tmp_path / "sdk")}]
    }
    assert header["Imports"]["Imports"][0] == {"Path": DEFAULT_IMPORTS[0]}
    assert header["Imports"]["Imports"][-1] == {"Path": "example.com/x", "Alias": "x"}
    assert set(header) == {"Modules", "Imports"}


async def test_ensure_eaglec_rejects_a_missing_configured_path(tmp_path):
    cfg = load_compiler_config({"eaglec": str(tmp_path / "nope")}, repo_root=tmp_path)

    with pytest.raises(FileNotFoundError, match="does not exist"):
        await ensure_eaglec(cfg)


def _fake_go(tmp_path, monkeypatch, script: str) -> None:
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    go = bin_dir / "go"
    go.write_text(script)
    go.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


async def test_ensure_eaglec_builds_the_default(tmp_path, monkeypatch):
    # invoked as: go build -o <path> ./cmd/eaglec
    _fake_go(
        tmp_path,
        monkeypatch,
        '#!/bin/sh\nmkdir -p "$(dirname "$3")" && echo "$PWD $4" > "$3"\n',
    )
    (tmp_path / "sdk").mkdir()
    cfg = load_compiler_config(None, repo_root=tmp_path)

    await ensure_eaglec(cfg)

    cwd, target = cfg.eaglec.read_text().split()
    assert Path(cwd).resolve() == (tmp_path / "sdk").resolve()
    assert target == "./cmd/eaglec"


async def test_ensure_eaglec_reports_build_output(tmp_path, monkeypatch):
    _fake_go(
        tmp_path, monkeypatch, '#!/bin/sh\necho "cannot find module" >&2\nexit 1\n'
    )
    (tmp_path / "sdk").mkdir()
    cfg = load_compiler_config(None, repo_root=tmp_path)

    with pytest.raises(RuntimeError, match="cannot find module"):
        await ensure_eaglec(cfg)


async def test_ensure_eaglec_without_go_on_path(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    (tmp_path / "sdk").mkdir()
    cfg = load_compiler_config(None, repo_root=tmp_path)

    with pytest.raises(RuntimeError, match="go toolchain on PATH"):
        await ensure_eaglec(cfg)


async def test_ensure_eaglec_without_an_sdk_checkout(tmp_path):
    cfg = load_compiler_config(None, repo_root=tmp_path)

    with pytest.raises(FileNotFoundError, match="SDK checkout"):
        await ensure_eaglec(cfg)


def _marker_go(tmp_path, monkeypatch):
    marker = tmp_path / "go-ran"
    _fake_go(tmp_path, monkeypatch, f'#!/bin/sh\ntouch "{marker}"\n')
    return marker


async def test_ensure_eaglec_rebuilds_the_default_even_when_present(
    tmp_path, monkeypatch
):
    marker = _marker_go(tmp_path, monkeypatch)
    (tmp_path / "sdk").mkdir()
    cfg = load_compiler_config(None, repo_root=tmp_path)
    cfg.eaglec.parent.mkdir(parents=True)
    cfg.eaglec.write_text("stale")

    await ensure_eaglec(cfg)

    assert marker.exists()


async def test_ensure_eaglec_uses_a_configured_binary_as_is(tmp_path, monkeypatch):
    marker = _marker_go(tmp_path, monkeypatch)
    binary = tmp_path / "my-eaglec"
    binary.write_text("")
    cfg = load_compiler_config({"eaglec": str(binary)}, repo_root=tmp_path)

    await ensure_eaglec(cfg)

    assert not marker.exists()


async def test_ensure_eaglec_build_timeout(tmp_path, monkeypatch):
    _fake_go(tmp_path, monkeypatch, "#!/bin/sh\nsleep 5\n")
    (tmp_path / "sdk").mkdir()
    cfg = load_compiler_config({"timeout_s": 0.3}, repo_root=tmp_path)

    with pytest.raises(RuntimeError, match="timed out after 0.3 s"):
        await ensure_eaglec(cfg)
