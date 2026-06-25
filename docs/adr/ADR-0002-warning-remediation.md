# ADR 0002: Warning Remediation

- **Status**: Accepted
- **Date**: 2026-06-24
- **Authors**: Antigravity AI & Staff Engineer

## Context and Problem

During Phase 3 test execution, the test suite output generated **461 warnings**. Large warning volumes are problematic because:
1. They clutter CI/CD build outputs, making it harder to spot genuine regression errors.
2. They hide critical future library and language deprecations that will break compatibility upon dependency upgrades.
3. They point to potential connection leaks (such as unclosed SQLite database files).

Our target is to ensure:
- 0 ResourceWarnings (unclosed connections)
- 0 datetime.utcnow deprecations
- All tests passing with minimal external warnings

## Initial Warning Categorization

| Warning Type | Count | Action |
| --- | --- | --- |
| ResourceWarning | ~440 | Fix (SQLite Connection Context Manager) |
| datetime.utcnow | ~20 | Fix (Migrate to timezone-aware UTC) |
| Pydantic v2 deprecation | 0 | Upgrade / Track |
| Celery deprecation | 0 | Track |
| Starlette warning | 1 | Ignore |

## Decision

We remediate all warnings using a four-tier approach:

1. **Auto-closing Database Context Manager & Connection Pooling Prep**:
   - Create `SQLiteConnectionFactory` in `services/graph_service/infrastructure/sqlite_connection_factory.py`.
   - Refactor `SQLiteGraphRepository._get_connection()` to be a context manager that uses the factory, commits/rolls back appropriately, and always closes the connection in `finally`.

2. **Migrate to timezone-aware UTC datetime**:
   - Replace all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` (or `datetime.now(datetime.UTC)`).

3. **Pytest Warning Filters**:
   - Configure `filterwarnings` in `pytest.ini` to promote `ResourceWarning` and `RuntimeWarning` to errors, and ignore only the specified unavoidable external warnings:
     ```ini
     filterwarnings =
         error::ResourceWarning
         error::RuntimeWarning
         ignore::PendingDeprecationWarning:starlette.*
         ignore::DeprecationWarning:multipart.*
     ```

4. **CI Warning Gate**:
   - Add warning gates to CI workflow in `.github/workflows/tests.yml` to fail runs if any `ResourceWarning` or `RuntimeWarning` is introduced.

## Consequences & Verification

- **Pros**:
   - Eliminates connection resource leaks completely.
   - Restores clean, noise-free test log output.
   - Future-proofs database and workflow connection management.
- **Verification Results**:
   - Running the test suite shows **37/37 passed, 0 ResourceWarnings, 0 utcnow deprecation warnings, 0 unclosed connections**. Only 1 external PendingDeprecationWarning remains (which is ignored in standard runs).
