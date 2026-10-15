"""Runs eaglec (sdk/cmd/eaglec) as a subprocess -- see
docs/superpowers/specs/2026-10-14-gcs-eaglec-compiler-integration-design.md.
Every call works in its own temporary directory, so calls may run
concurrently."""

import asyncio
import json
import os
import signal
import tempfile
from asyncio.subprocess import PIPE
from pathlib import Path


class EaglecError(Exception):
    """Base class for everything EaglecClient raises."""


class EaglecCompileErrors(EaglecError):
    """eaglec rejected the mission. errors are its -errors=json objects:
    {"file": str, "decl": str, "line": int, "message": str}."""

    def __init__(self, errors: list[dict]) -> None:
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


class EaglecFailure(EaglecError):
    """eaglec couldn't run, timed out, or failed some way other than
    rejecting the mission. stderr is whatever it printed."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class EaglecClient:
    def __init__(self, eaglec: Path, timeout_s: float = 300.0) -> None:
        self._eaglec = eaglec
        self._timeout_s = timeout_s

    async def schema(self, header: dict) -> dict:
        """The type registry for a mission with header's Modules: and
        Imports: stanzas."""
        with tempfile.TemporaryDirectory(prefix="eaglec-") as tmp:
            # file names are relative to cwd=tmp, so eaglec's messages read
            # "mission.dsl:3:1: ..." rather than naming the temporary directory
            (Path(tmp) / "header.json").write_text(json.dumps(header))
            out = await self._run(["schema", "-json", "header.json"], tmp)
        return _decode(out, "schema")

    async def parse(self, dsl: str) -> dict:
        """The AST JSON of DSL mission text."""
        with tempfile.TemporaryDirectory(prefix="eaglec-") as tmp:
            (Path(tmp) / "mission.dsl").write_text(dsl)
            out = await self._run(["parse", "mission.dsl"], tmp)
        return _decode(out, "parse")

    async def compile(self, ast: dict, geojson: bytes | None, arch: str) -> bytes:
        """Compiles an AST JSON mission for arch and returns the binary.
        geojson is left out of the compile when None."""
        with tempfile.TemporaryDirectory(prefix="eaglec-") as tmp:
            (Path(tmp) / "mission.json").write_text(json.dumps(ast))
            output = Path(tmp) / "mission.bin"
            args = ["dsl", "-json", "-o", "mission.bin"]
            if geojson is not None:
                (Path(tmp) / "map.geojson").write_bytes(geojson)
                args += ["-geojson", "map.geojson"]
            args.append("mission.json")
            await self._run(args, tmp, {"GOARCH": arch})
            return output.read_bytes()

    async def _run(
        self, args: list[str], cwd: str, env: dict[str, str] | None = None
    ) -> bytes:
        mode = args[0]
        # each mode parses its own flags, so -errors=json follows the mode
        argv = [mode, "-errors=json", *args[1:]]
        try:
            proc = await asyncio.create_subprocess_exec(
                str(self._eaglec),
                *argv,
                cwd=cwd,
                env={**os.environ, **(env or {})},
                stdout=PIPE,
                stderr=PIPE,
                # own process group, so killing it also takes eaglec's go build children
                start_new_session=True,
            )
        except OSError as e:
            raise EaglecFailure(f"running {self._eaglec} failed: {e}") from e
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), self._timeout_s)
        except BaseException as e:
            # timeout or cancellation: nothing may outlive this call, since the
            # temporary directory is about to be deleted
            await _kill_group(proc)
            if isinstance(e, TimeoutError):
                raise EaglecFailure(
                    f"eaglec {mode} timed out after {self._timeout_s:g} s"
                ) from None
            raise
        text = stderr.decode(errors="replace")
        if proc.returncode == 0:
            return stdout
        errors = _error_lines(text) if proc.returncode == 1 else None
        if errors:
            raise EaglecCompileErrors(errors)
        raise EaglecFailure(f"eaglec {mode} exited with status {proc.returncode}", text)


async def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """SIGKILLs proc's process group (proc leads it: start_new_session) and
    reaps proc. Safe if the group is already gone."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await proc.wait()


def _error_lines(stderr: str) -> list[dict] | None:
    """Parses eaglec's -errors=json output, or returns None if any line
    isn't one of its error objects (e.g. a panic)."""
    errors = []
    for line in stderr.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict) or "message" not in obj:
            return None
        errors.append(
            {
                "file": obj.get("file", ""),
                "decl": obj.get("decl", ""),
                "line": obj.get("line", 0),
                "message": obj["message"],
            }
        )
    return errors or None


def _decode(out: bytes, mode: str) -> dict:
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise EaglecFailure(
            f"eaglec {mode} printed invalid JSON: {e}",
            out.decode(errors="replace")[:2000],
        ) from e
