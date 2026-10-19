"""Resolves the optional [compiler] section of config.toml -- see
docs/superpowers/specs/2026-10-14-gcs-eaglec-compiler-integration-design.md.
Every key is optional, so a repo checkout needs no [compiler] section at
all: eaglec is rebuilt in-repo at every startup and missions compile against the
checkout's own SDK and protocol (api/go)."""

import asyncio
import logging
import os
import re
import signal
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("rich")

# gcs/react/backend/app/compiler_config.py -> the repo root
REPO_ROOT = Path(__file__).resolve().parents[4]

SDK_MODULE = "github.com/cmusatyalab/steeleagle/sdk"
# The checkout's SDK is generated against the checkout's protocol, which can
# be ahead of the api/go release sdk/go.mod requires.
API_MODULE = "github.com/cmusatyalab/steeleagle/api/go"

# Packages every mission imports; [compiler] imports are added after these.
DEFAULT_IMPORTS = tuple(
    f"{SDK_MODULE}/{pkg}"
    for pkg in ("dsl/actions", "dsl/events", "dsl/datatypes", "params", "enums")
)


@dataclass(frozen=True)
class Module:
    path: str
    version: str = ""
    override: str = ""


@dataclass(frozen=True)
class Import:
    path: str
    alias: str = ""


@dataclass(frozen=True)
class CompilerConfig:
    eaglec: Path
    eaglec_configured: bool  # False when eaglec is the in-repo default
    sdk_dir: Path
    api_dir: Path
    modules: tuple[Module, ...]
    imports: tuple[Import, ...]
    timeout_s: float

    def header(self) -> dict:
        """The Modules: and Imports: stanzas every mission is compiled
        with, as eaglec's AST JSON."""
        modules = []
        for m in self.modules:
            entry = {"Path": m.path}
            if m.version:
                entry["Version"] = m.version
            if m.override:
                entry["Override"] = m.override
            modules.append(entry)
        imports = []
        for i in self.imports:
            entry = {"Path": i.path}
            if i.alias:
                entry["Alias"] = i.alias
            imports.append(entry)
        return {"Modules": {"Modules": modules}, "Imports": {"Imports": imports}}


def load_compiler_config(
    section: dict | None, repo_root: Path = REPO_ROOT
) -> CompilerConfig:
    """Applies the [compiler] section (None or {} when absent) over the
    in-repo defaults. Relative paths are resolved against the working
    directory, where config.toml is read from; overrides must be absolute
    anyway, since eaglec compiles in a temporary directory."""
    section = section or {}
    sdk_dir = repo_root / "sdk"
    api_dir = repo_root / "api" / "go"

    configured = section.get("eaglec")
    eaglec = (
        Path(configured).resolve()
        if configured
        else sdk_dir / "cmd" / "eaglec" / "eaglec"
    )

    sdk_version = section.get("sdk_version", "")
    modules = (
        [Module(SDK_MODULE, version=sdk_version)]
        if sdk_version
        else [
            Module(SDK_MODULE, override=str(sdk_dir)),
            Module(API_MODULE, override=str(api_dir)),
        ]
    )
    for entry in section.get("modules", []):
        path = entry["path"]
        if path == SDK_MODULE:
            logger.warning(
                "[compiler] modules: ignoring the SDK module; set sdk_version to change its version"
            )
            continue
        if any(m.path == path for m in modules):
            continue
        override = entry.get("override", "")
        modules.append(
            Module(
                path,
                entry.get("version", ""),
                str(Path(override).resolve()) if override else "",
            )
        )

    imports = [Import(path) for path in DEFAULT_IMPORTS]
    for entry in section.get("imports", []):
        if any(i.path == entry["path"] for i in imports):
            continue
        imports.append(Import(entry["path"], entry.get("alias", "")))

    return CompilerConfig(
        eaglec=eaglec,
        eaglec_configured=bool(configured),
        sdk_dir=sdk_dir,
        api_dir=api_dir,
        modules=tuple(modules),
        imports=tuple(imports),
        timeout_s=float(section.get("timeout_s", 300)),
    )


def _go_version(gomod: Path) -> tuple[int, ...]:
    m = re.search(r"^go\s+(\d+(?:\.\d+)*)\s*$", gomod.read_text(), re.MULTILINE)
    return tuple(int(p) for p in m.group(1).split(".")) if m else (1,)


def _write_go_work(directory: Path, modules: list[Path]) -> Path:
    """A go.work using modules, at the highest go version any requires."""
    version = max(_go_version(m / "go.mod") for m in modules)
    work = directory / "go.work"
    uses = "".join(f"\t{m}\n" for m in modules)
    work.write_text(f"go {'.'.join(map(str, version))}\n\nuse (\n{uses})\n")
    return work


async def ensure_eaglec(config: CompilerConfig) -> None:
    """Builds the in-repo eaglec with go build on every startup, even if the
    binary exists: the build is incremental, and a binary left over from an
    older sdk/cmd/eaglec or sdk/dsl/compiler would otherwise be used stale.
    A configured eaglec is used as-is; a missing one is an error, since
    building it wherever the config points would hide a typo. The build is
    bounded by config.timeout_s. The in-repo build uses a temporary workspace
    with the checkout's api/go, for the same reason missions compile against
    it (see API_MODULE)."""
    if config.eaglec_configured:
        if not config.eaglec.exists():
            raise FileNotFoundError(
                f"[compiler] eaglec = {config.eaglec} does not exist"
            )
        return
    if not config.sdk_dir.is_dir():
        raise FileNotFoundError(
            f"no SDK checkout at {config.sdk_dir} to build eaglec from"
        )
    logger.info(f"building eaglec at {config.eaglec} with go build")
    with tempfile.TemporaryDirectory() as tmp:
        env = None
        if (config.api_dir / "go.mod").is_file():
            work = _write_go_work(Path(tmp), [config.sdk_dir, config.api_dir])
            env = {**os.environ, "GOWORK": str(work)}
        await _go_build(config, env)


async def _go_build(config: CompilerConfig, env: dict | None) -> None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "go",
            "build",
            "-o",
            str(config.eaglec),
            "./cmd/eaglec",
            cwd=config.sdk_dir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            # own process group, so a timeout also kills go's compile children
            start_new_session=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError("building eaglec needs the go toolchain on PATH") from e
    try:
        output, _ = await asyncio.wait_for(proc.communicate(), config.timeout_s)
    except BaseException as e:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
        if isinstance(e, TimeoutError):
            raise RuntimeError(
                f"building eaglec timed out after {config.timeout_s:g} s"
            ) from None
        raise
    if proc.returncode != 0:
        raise RuntimeError(
            f"building eaglec failed:\n{output.decode(errors='replace')}"
        )
