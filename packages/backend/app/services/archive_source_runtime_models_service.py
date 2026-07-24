"""Internal records for authorized preview-source lifecycle state."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..repository.archive_authorization_repository import AuthorizedInputRoot


@dataclass
class PreviewSourceRecord:
    source_id: str
    authorized_input: AuthorizedInputRoot
    source_key: str
    created_at: float
    expires_at: float
    cleanup_root: Path | None = None
    prepared_context_id: str | None = None
    preparation_status: str = "not_prepared"
    prepare_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def preview_source_summary(record: PreviewSourceRecord) -> dict[str, object]:
    def iso(value: float) -> str:
        return datetime.fromtimestamp(value, timezone.utc).isoformat()

    return {
        "archive_context_id": record.source_id,
        "file_count": None,
        "total_input_bytes": None,
        "status": record.preparation_status,
        "context_kind": "preview_source",
        "inventory_ready": False,
        "created_at": iso(record.created_at),
        "expires_at": iso(record.expires_at),
    }


__all__ = ["PreviewSourceRecord", "preview_source_summary"]
