from __future__ import annotations
import importlib, pkgutil, sys
from types import ModuleType

_LOADED = False

def _safe_import(name: str):
    try:
        if name not in sys.modules:
            importlib.import_module(name)
    except ModuleNotFoundError:
        # optional modules may not exist; ignore
        pass
    except Exception as e:
        # consider logging
        raise

def load_all(base_pkg: str = "tasks"):
    global _LOADED
    if _LOADED:
        return
    try:
        tasks_pkg: ModuleType = importlib.import_module(base_pkg)
    except ModuleNotFoundError:
        # tolerate missing tasks package (useful for tests)
        return

    for m in pkgutil.walk_packages(tasks_pkg.__path__, tasks_pkg.__name__ + "."):
        _safe_import(m.name)
    _LOADED = True