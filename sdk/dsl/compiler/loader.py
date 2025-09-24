# compiler/loader.py
from __future__ import annotations
import importlib
import pkgutil
import logging
from types import ModuleType
from typing import Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)

_DEFAULT_BASES = ("steeleagle_sdk.api.actions", "steeleagle_sdk.api.events", "steeleagle_sdk.api.datatypes")
_SKIP_RULES = [
    lambda short: short.startswith("_"),
    lambda short: short == "native",
]

def _walk_package(base: str) -> Tuple[Optional[ModuleType], List[str]]:
    try:
        pkg: ModuleType = importlib.import_module(base)
    except ModuleNotFoundError:
        return None, []
    modules: List[str] = []
    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        mod_name = m.name.rsplit(".", 1)[-1]
        if any(rule(mod_name) for rule in _SKIP_RULES):
            logger.debug("   -> skipping %s (ignored)", m.name)
            continue
        modules.append(m.name)
    return pkg, modules


def load_all(
    *base_pkgs: str,
    show_trace: bool = False,
) -> List[Dict[str, object]]:
    """
    Import every submodule under each base package and REPORT failures.
    """
    if not base_pkgs: base_pkgs = _DEFAULT_BASES
    all_summaries: List[Dict[str, object]] = []

    for base in base_pkgs:

        # init summary
        summary: Dict[str, object] = {
            "base": base,
            "imported": [],
            "failed": [],
            "skipped": False,
            "missing_base": False,
        }

        # walk package
        pkg, modules = _walk_package(base)
        if pkg is None:
            summary["missing_base"] = True
            logger.warning("Base package not found: %s", base)
            all_summaries.append(summary)
            continue
        logger.info("Scanning '%s' (%d submodules discovered)", base, len(modules))

        # import submodules
        imported: List[str] = []
        failed: List[Dict[str, str]] = []
        for module in modules:
            try:
                logger.debug(" importing %s ...", module)
                importlib.import_module(module)
                imported.append(module)
                logger.debug("   -> OK")
            except Exception as e:
                fail_rec = {
                    "module": module,
                    "exc_type": type(e).__name__,
                    "message": str(e),
                }
                failed.append(fail_rec)
                logger.error("   -> FAIL importing %s: %s: %s", module, type(e).__name__, e)
        summary["imported"] = imported
        summary["failed"] = failed
        all_summaries.append(summary)
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
