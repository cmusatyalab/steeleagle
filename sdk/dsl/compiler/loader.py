# compiler/loader.py
from __future__ import annotations
import importlib
import pkgutil
import sys
import traceback
import logging
from types import ModuleType
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LOADED_BASES: set[str] = set()
_DEFAULT_BASES = ("api.actions", "api.events", "api.messages")


def _walk_package(base: str) -> Tuple[Optional[ModuleType], List[str]]:
    """Try to import a base package and list its submodules, skipping internals."""
    try:
        pkg: ModuleType = importlib.import_module(base)
    except ModuleNotFoundError:
        return None, []
    names: List[str] = []
    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        mod_name = m.name.rsplit(".", 1)[-1]
        # Skip files starting with "_" or exactly "native"
        if mod_name.startswith("_") or mod_name == "native":
            logger.debug("   -> skipping %s (ignored)", m.name)
            continue
        names.append(m.name)
    return pkg, names


def load_all(
    *base_pkgs: str,
    force: bool = False,
    strict: bool = False,
    show_trace: bool = False,
) -> List[Dict[str, object]]:
    """
    Import every submodule under each base package and REPORT failures.

    Returns a per-base summary list. Each summary dict has:
      {
        'base': str,
        'imported': [str, ...],
        'failed': [{'module': str, 'exc_type': str, 'message': str, 'traceback': Optional[str]}],
        'skipped': bool,
        'missing_base': bool,
      }
    """
    if not base_pkgs:
        base_pkgs = _DEFAULT_BASES

    all_summaries: List[Dict[str, object]] = []
    any_failures = False

    for base in base_pkgs:
        summary: Dict[str, object] = {
            "base": base,
            "imported": [],
            "failed": [],
            "skipped": False,
            "missing_base": False,
        }

        if not force and base in _LOADED_BASES:
            summary["skipped"] = True
            logger.info("Skipping already scanned base: %s", base)
            all_summaries.append(summary)
            continue

        pkg, submods = _walk_package(base)
        if pkg is None:
            summary["missing_base"] = True
            logger.warning("Base package not found: %s", base)
            all_summaries.append(summary)
            continue

        logger.info("Scanning '%s' (%d submodules discovered)", base, len(submods))

        imported: List[str] = []
        failed: List[Dict[str, str]] = []

        for mod_name in submods:
            try:
                logger.debug(" importing %s ...", mod_name)
                importlib.import_module(mod_name)
                imported.append(mod_name)
                logger.debug("   -> OK")
            except Exception as e:
                any_failures = True
                tb = traceback.format_exc() if show_trace else ""
                fail_rec = {
                    "module": mod_name,
                    "exc_type": type(e).__name__,
                    "message": str(e),
                    "traceback": tb,
                }
                failed.append(fail_rec)
                logger.error("   -> FAIL importing %s: %s: %s", mod_name, type(e).__name__, e)
                if show_trace:
                    logger.error(
                        "---------- traceback begin ----------\n%s----------- traceback end -----------",
                        tb.rstrip()
                    )

        summary["imported"] = imported
        summary["failed"] = failed
        _LOADED_BASES.add(base)
        all_summaries.append(summary)

        if not imported and not failed:
            logger.info(
                "No importable submodules under '%s'. "
                "Is the package empty or missing __init__.py files?",
                base,
            )

    if strict and any_failures:
        lines = ["One or more task modules failed to import:"]
        for s in all_summaries:
            for f in s["failed"]:  # type: ignore[index]
                lines.append(f"  - {s['base']}: {f['module']} → {f['exc_type']}: {f['message']}")  # type: ignore[index]
        lines.extend(
            [
                "Hints:",
                "  • Check sys.path includes your repo root.",
                "  • Fix bad imports inside the failing modules.",
                "  • Ensure packages have __init__.py (unless using namespace pkgs).",
            ]
        )
        msg = "\n".join(lines)
        logger.error(msg)
        raise ImportError(msg)

    if not any(s["imported"] for s in all_summaries):
        logger.info("Imported 0 modules from all bases.")
        logger.info("        sys.path:")
        for p in sys.path:
            logger.info("          - %s", p)

    return all_summaries


def print_report(summaries: List[Dict[str, object]]) -> None:
    """Pretty-print the summaries returned by load_all()."""
    for s in summaries:
        base = s["base"]
        if s.get("skipped"):
            logger.info("%s: skipped (already scanned)", base)
            continue
        if s.get("missing_base"):
            logger.warning("%s: MISSING base package", base)
            continue

        imported = s.get("imported", [])
        failed = s.get("failed", [])
        logger.info("%s: %d imported, %d failed", base, len(imported), len(failed))

        if imported:
            for name in imported[:10]:
                logger.info("   ✓ %s", name)
            if len(imported) > 10:
                logger.info("   … (+%d more)", len(imported) - 10)

        if failed:
            for f in failed:
                logger.error("   ✗ %s — %s: %s", f["module"], f["exc_type"], f["message"])
