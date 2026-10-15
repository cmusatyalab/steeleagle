import asyncio
import json
import os
from pathlib import Path

import pytest

from app.eaglec_client import (
    EaglecClient,
    EaglecCompileErrors,
    EaglecFailure,
)
from tests.fake_eaglec import fake_calls, make_fake_eaglec


async def test_schema_writes_the_header_and_decodes_stdout(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, stdout='{"actions": {}}\n'))

    assert await client.schema({"Imports": {"Imports": []}}) == {"actions": {}}

    [call] = fake_calls(tmp_path)
    assert call["args"][:3] == ["schema", "-errors=json", "-json"]
    assert json.loads(call["files"]["mission"]) == {"Imports": {"Imports": []}}


async def test_parse_passes_the_dsl_text(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, stdout='{"Mission": {}}'))

    assert await client.parse("Actions:\n") == {"Mission": {}}

    [call] = fake_calls(tmp_path)
    assert call["args"][:2] == ["parse", "-errors=json"]
    assert call["files"]["mission"] == "Actions:\n"


async def test_compile_returns_the_binary_built_for_arch(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, binary=b"\x7fELFdata"))

    out = await client.compile(
        {"Actions": {}}, b'{"type":"FeatureCollection"}', "arm64"
    )

    assert out == b"\x7fELFdata"
    [call] = fake_calls(tmp_path)
    assert call["args"][:3] == ["dsl", "-errors=json", "-json"]
    assert call["goarch"] == "arm64"
    assert json.loads(call["files"]["mission"]) == {"Actions": {}}
    assert call["files"]["geojson"] == '{"type":"FeatureCollection"}'


async def test_compile_omits_geojson_when_none(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, binary=b"x"))

    await client.compile({}, None, "amd64")

    [call] = fake_calls(tmp_path)
    assert "-geojson" not in call["args"]
    assert "geojson" not in call["files"]


async def test_concurrent_compiles_use_separate_directories(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, binary=b"x", sleep=0.2))

    results = await asyncio.gather(
        client.compile({"n": 1}, None, "amd64"),
        client.compile({"n": 2}, None, "arm64"),
    )

    assert results == [b"x", b"x"]
    calls = fake_calls(tmp_path)
    assert len({c["cwd"] for c in calls}) == 2
    assert sorted(json.loads(c["files"]["mission"])["n"] for c in calls) == [1, 2]


async def test_exit_1_with_json_lines_is_compile_errors(tmp_path):
    stderr = (
        json.dumps(
            {"file": "", "decl": "patrol", "line": 0, "message": "no field Altitud"}
        )
        + "\n"
        + json.dumps({"file": "m.json", "decl": "", "line": 2, "message": "other"})
        + "\n"
    )
    client = EaglecClient(make_fake_eaglec(tmp_path, stderr=stderr, exit_code=1))

    with pytest.raises(EaglecCompileErrors) as exc:
        await client.compile({}, None, "amd64")

    assert exc.value.errors == [
        {"file": "", "decl": "patrol", "line": 0, "message": "no field Altitud"},
        {"file": "m.json", "decl": "", "line": 2, "message": "other"},
    ]


async def test_exit_1_with_unparseable_stderr_is_a_failure(tmp_path):
    client = EaglecClient(
        make_fake_eaglec(tmp_path, stderr="panic: runtime error\n", exit_code=1)
    )

    with pytest.raises(EaglecFailure) as exc:
        await client.compile({}, None, "amd64")

    assert "exited with status 1" in str(exc.value)
    assert "panic: runtime error" in exc.value.stderr


async def test_usage_exit_2_is_a_failure(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, stderr="usage: ...", exit_code=2))

    with pytest.raises(EaglecFailure, match="status 2"):
        await client.parse("x")


async def _assert_gone(pid: int) -> None:
    """Polls briefly: a killed process is reparented to init, which reaps it."""
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"pid {pid} is still alive")


async def _wait_for_file(path: Path) -> None:
    for _ in range(100):
        if path.exists() and path.read_text():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"{path} was never written")


async def test_timeout_kills_eaglec_and_its_children(tmp_path):
    client = EaglecClient(
        make_fake_eaglec(tmp_path, sleep=5, spawn_child=True), timeout_s=1.0
    )

    start = asyncio.get_running_loop().time()
    with pytest.raises(EaglecFailure, match="timed out after 1 s"):
        await client.compile({}, None, "amd64")
    # the child sleeps 30 s and holds the pipes open; a call that waits for
    # it to exit has not killed the group
    assert asyncio.get_running_loop().time() - start < 10

    await _assert_gone(int((tmp_path / "eaglec.pid").read_text()))
    await _assert_gone(int((tmp_path / "child.pid").read_text()))


async def test_cancellation_kills_eaglec_and_its_children(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, sleep=5, spawn_child=True))
    task = asyncio.create_task(client.compile({}, None, "amd64"))
    await _wait_for_file(tmp_path / "child.pid")

    task.cancel()
    await asyncio.wait({task}, timeout=10)
    assert task.done(), "cancelled compile did not return promptly"

    with pytest.raises(asyncio.CancelledError):
        await task
    await _assert_gone(int((tmp_path / "eaglec.pid").read_text()))
    await _assert_gone(int((tmp_path / "child.pid").read_text()))


async def test_invalid_json_on_stdout_is_a_failure(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, stdout="not json"))

    with pytest.raises(EaglecFailure, match="invalid JSON"):
        await client.schema({})


async def test_missing_binary_is_a_failure(tmp_path):
    client = EaglecClient(tmp_path / "does-not-exist")

    with pytest.raises(EaglecFailure, match="does-not-exist"):
        await client.parse("x")


async def test_files_are_passed_relative_to_the_working_directory(tmp_path):
    client = EaglecClient(make_fake_eaglec(tmp_path, binary=b"x"))

    await client.compile({"Actions": {}}, b"{}", "amd64")

    [call] = fake_calls(tmp_path)
    assert call["args"][-1] == "mission.json"
    assert call["args"][call["args"].index("-o") + 1] == "mission.bin"
    assert call["args"][call["args"].index("-geojson") + 1] == "map.geojson"
