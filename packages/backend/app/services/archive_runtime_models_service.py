"""Data records used by the in-process archive lifecycle store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..repository.archive_input_repository import InputInventory


@dataclass
class ArchiveContextRecord:
    context_id: str
    case_display_name: str
    inventory: InputInventory
    authorization_type: str
    authorized_root_id: str
    authorized_scope: Path | None
    source_key: str
    input_fingerprint: str
    created_at: float
    expires_at: float
    cleanup_root: Path | None = None
    execution_state: str = "idle"
    active_execution_id: str | None = None
    successful_manifest_id: str | None = None

    @property
    def executing(self) -> bool:
        return self.active_execution_id is not None

    def public_summary(self) -> dict[str, object]:
        def iso(value: float) -> str:
            return datetime.fromtimestamp(value, timezone.utc).isoformat()

        return {
            "archive_context_id": self.context_id,
            "file_count": len(self.inventory.files),
            "total_input_bytes": self.inventory.total_input_bytes,
            "status": self.execution_state,
            "context_kind": "formal",
            "inventory_ready": True,
            "created_at": iso(self.created_at),
            "expires_at": iso(self.expires_at),
        }


@dataclass(frozen=True)
class ArchiveContextSnapshot:
    """Immutable read view used outside the archive lifecycle lock."""

    context_id: str
    case_display_name: str
    inventory: InputInventory
    input_fingerprint: str
    successful_manifest_id: str | None


@dataclass
class ArchiveManifestRecord:
    manifest_id: str
    context_id: str
    fingerprint: str
    public_manifest: dict[str, object]
    final_dir: Path
    created_at: float
    expires_at: float
    context_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.context_ids.add(self.context_id)

    def belongs_to(self, context_id: str) -> bool:
        return context_id in self.context_ids
