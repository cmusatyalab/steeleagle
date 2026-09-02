"""No fixtures needed: api.py no longer depends on steeleagle_sdk (see
docs/superpowers/plans/2026-09-02-gcs-dslcompiler-api-proxy.md Task 7) --
its DSL type-checking now lives entirely in the dslcompiler Go service,
which tests reach through FakeDslCompilerClient, not a real registry
load."""
