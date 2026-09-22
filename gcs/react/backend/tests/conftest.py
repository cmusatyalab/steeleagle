import pytest
from steeleagle_sdk.dsl.compiler.loader import load_all as _dsl_load_all


@pytest.fixture(scope="session", autouse=True)
def load_dsl_registry():
    """Populate the DSL registry once per test session (mirrors app startup)."""
    _dsl_load_all()
