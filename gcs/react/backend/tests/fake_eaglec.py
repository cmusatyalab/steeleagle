"""Stand-ins for eaglec: make_fake_eaglec writes an executable script that
behaves like the real CLI's I/O contract, for testing EaglecClient's
subprocess handling; FakeEaglecClient replaces EaglecClient itself, for
testing routes without any subprocess."""

import json
import sys
from pathlib import Path


def make_fake_eaglec(
    tmp_path: Path,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    binary: bytes = b"",
    sleep: float = 0.0,
    spawn_child: bool = False,
) -> Path:
    """Writes tmp_path/eaglec. Each run appends {args, cwd, goarch, files}
    to tmp_path/calls.jsonl (files holds the mission file's and any
    -geojson file's contents), writes `binary` to the -o path if one is
    given, prints stdout/stderr, and exits with exit_code.

    Each run first writes its own pid to tmp_path/eaglec.pid. With
    spawn_child, it also starts a long-lived child (like go build would)
    and writes that child's pid to tmp_path/child.pid."""
    spec = {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "binary": binary.hex(),
        "sleep": sleep,
        "spawn_child": spawn_child,
        "pid_dir": str(tmp_path),
        "log": str(tmp_path / "calls.jsonl"),
    }
    script = tmp_path / "eaglec"
    script.write_text(
        f"""#!{sys.executable}
import json, os, subprocess, sys, time
spec = {spec!r}
with open(os.path.join(spec["pid_dir"], "eaglec.pid"), "w") as f:
    f.write(str(os.getpid()))
if spec["spawn_child"]:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    with open(os.path.join(spec["pid_dir"], "child.pid"), "w") as f:
        f.write(str(child.pid))
args = sys.argv[1:]
files = {{"mission": open(args[-1]).read()}}
if "-geojson" in args:
    files["geojson"] = open(args[args.index("-geojson") + 1]).read()
with open(spec["log"], "a") as log:
    log.write(json.dumps({{"args": args, "cwd": os.getcwd(), "goarch": os.environ.get("GOARCH"), "files": files}}) + "\\n")
time.sleep(spec["sleep"])
if "-o" in args:
    with open(args[args.index("-o") + 1], "wb") as out:
        out.write(bytes.fromhex(spec["binary"]))
sys.stdout.write(spec["stdout"])
sys.stderr.write(spec["stderr"])
sys.exit(spec["exit_code"])
"""
    )
    script.chmod(0o755)
    return script


def fake_calls(tmp_path: Path) -> list[dict]:
    log = tmp_path / "calls.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


class FakeEaglecClient:
    """In-process EaglecClient double. Pass canned results; calls are
    recorded. compile_error, if set, is raised by every compile; otherwise
    compile returns binaries[arch] (default b"bin-<arch>")."""

    def __init__(
        self,
        registry: dict | None = None,
        parse_result: dict | None = None,
        parse_error: Exception | None = None,
        binaries: dict[str, bytes] | None = None,
        compile_error: Exception | None = None,
    ) -> None:
        self._registry = registry
        self._parse_result = parse_result
        self._parse_error = parse_error
        self._binaries = binaries or {}
        self._compile_error = compile_error
        self.schema_calls: list[dict] = []
        self.parse_calls: list[str] = []
        self.compile_calls: list[tuple[dict, bytes | None, str]] = []

    async def schema(self, header: dict) -> dict:
        self.schema_calls.append(header)
        assert self._registry is not None, "schema() called without a canned registry"
        return self._registry

    async def parse(self, dsl: str) -> dict:
        self.parse_calls.append(dsl)
        if self._parse_error is not None:
            raise self._parse_error
        assert self._parse_result is not None, "parse() called without a canned result"
        return self._parse_result

    async def compile(self, ast: dict, geojson: bytes | None, arch: str) -> bytes:
        self.compile_calls.append((ast, geojson, arch))
        if self._compile_error is not None:
            raise self._compile_error
        return self._binaries.get(arch, f"bin-{arch}".encode())
