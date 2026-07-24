import pytest

try:
    from steeleagle_sdk.dsl.compiler.loader import load_all as _dsl_load_all
except ImportError:
    _dsl_load_all = None


@pytest.fixture(scope="session", autouse=True)
def load_dsl_registry():
    """Populate the DSL registry once per test session (mirrors app startup).

    steeleagle_sdk is not currently an installed dependency (see
    docs/superpowers/specs/2026-07-24-gcs-swarm-service-migration-design.md);
    skip silently so unrelated tests can still run.
    """
    if _dsl_load_all is not None:
        _dsl_load_all()
