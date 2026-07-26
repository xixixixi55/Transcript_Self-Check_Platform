"""Safe persistence errors without local paths or report content."""

from __future__ import annotations


class WorkbenchPersistenceError(RuntimeError):
    """Base error whose text is safe to expose through a controller later."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class RevisionConflictError(WorkbenchPersistenceError):
    def __init__(self, resource: str, expected: int, actual: int) -> None:
        self.resource = resource
        self.expected_revision = expected
        self.actual_revision = actual
        super().__init__("REVISION_CONFLICT")


class SchemaIncompatibleError(WorkbenchPersistenceError):
    def __init__(self) -> None:
        super().__init__("SQLITE_SCHEMA_INCOMPATIBLE")


class ForbiddenPayloadError(WorkbenchPersistenceError):
    def __init__(self, code: str = "FORBIDDEN_LARGE_OBJECT") -> None:
        super().__init__(code)


class LeaseConflictError(WorkbenchPersistenceError):
    def __init__(self) -> None:
        super().__init__("LEASE_CONFLICT")
