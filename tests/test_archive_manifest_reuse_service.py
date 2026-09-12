"""SYNTHETIC/TEST：持久 Manifest 复用的发布位置恢复。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive import archive_manifest_reuse_service  # noqa: E402


def test_sqlite_publication_locator_restores_direct_manifest_without_legacy_json(
    tmp_path: Path, monkeypatch,
) -> None:
    logical = tmp_path / "workspace" / "compressed" / "context" / "manifest"
    direct = tmp_path / "SYNTHETIC-report-parent"
    direct.mkdir()
    persisted = SimpleNamespace(
        manifest_id="SYNTHETIC-manifest",
        workbench_attempt_id="SYNTHETIC-attempt",
        source_key="a" * 64,
        input_fingerprint="b" * 64,
        archive_fingerprint="c" * 64,
        relative_final_dir="context/manifest",
        public_manifest={"manifest_id": "SYNTHETIC-manifest", "parts": []},
        publication_id="SYNTHETIC-publication",
        publication_digest="d" * 64,
        created_at=1.0,
    )
    intent = {
        "phase": "verified", "publication_status": "verified",
        "task_id": "SYNTHETIC-task", "deployment_instance_id": "SYNTHETIC-instance",
        "publication_relative_dir": str(direct.resolve()),
        **{key: getattr(persisted, key) for key in (
            "manifest_id", "source_key", "input_fingerprint", "archive_fingerprint",
            "relative_final_dir", "public_manifest", "publication_id", "publication_digest",
        )},
    }
    database = SimpleNamespace(
        database_path=tmp_path / "data" / "workbench.sqlite3",
        deployment_instance_id="SYNTHETIC-instance",
    )
    attempt_service = SimpleNamespace(
        database=database,
        repository=SimpleNamespace(get_internal=lambda _attempt_id: {"task_id": "SYNTHETIC-task"}),
    )
    registry = SimpleNamespace(
        find_reusable=lambda *_args: [persisted],
        resolve_final_dir=lambda _record: logical,
        touch=lambda _manifest_id: None,
        mark_invalid=lambda _manifest_id: None,
    )
    captured = []
    monkeypatch.setattr(
        archive_manifest_reuse_service, "ArchivePublishIntentRepository",
        lambda _database: SimpleNamespace(get_for_attempt=lambda _attempt_id: intent),
    )
    monkeypatch.setattr(
        archive_manifest_reuse_service, "validate_manifest_files",
        lambda record: captured.append(record),
    )
    monkeypatch.setattr(
        archive_manifest_reuse_service.ARCHIVE_RUNTIME_STORE, "attach_manifest",
        lambda _context_id, record: record,
    )
    context = SimpleNamespace(
        context_id="SYNTHETIC-context",
        source_key=persisted.source_key,
        input_fingerprint=persisted.input_fingerprint,
    )

    restored = archive_manifest_reuse_service.restore_persisted_manifest(
        context, persisted.archive_fingerprint, registry,
        attempt_service=attempt_service, attempt_id="SYNTHETIC-attempt",
    )

    assert restored is captured[0]
    assert restored.logical_final_dir == logical
    assert restored.final_dir == direct
    assert restored.external_export is True
    assert not (database.database_path.parent / "archive-export-locations.json").exists()
