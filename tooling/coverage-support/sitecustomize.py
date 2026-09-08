"""Start coverage in Python subprocesses when the parent requests it."""

try:
    import coverage
except ImportError:  # pragma: no cover - coverage is optional outside CI
    pass
else:
    coverage.process_startup()
