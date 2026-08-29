"""Phase 1D 独立审查发现项的回归测试。"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import AssetReferenceRepository, CaseDraftRepository, CaseShellRepository  # noqa: E402
from app.repository.case.case_archive_decision_repository import CaseArchiveDecisionRepository  # noqa: E402
from app.repository.archive.archive_manifest_repository import ArchiveManifestRepository  # noqa: E402
from app.repository.archive.archive_manifest_repository import ArchiveManifestRepositoryError  # noqa: E402
from app.repository.archive.archive_publish_intent_repository import ArchivePublishIntentRepository  # noqa: E402
from app.repository.source_record_repository import SourceRecordRepository  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive.archive_attempt_service import ArchiveAttemptService  # noqa: E402
from app.services.archive import archive_attempt_completion_service as completion_module  # noqa: E402
from app.services.archive.archive_staging_security_service import cleanup_owned_staging  # noqa: E402
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.source_record_service import SourceRecordService  # noqa: E402
from app.services.archive.archive_runtime_service import ArchiveManifestRecord  # noqa: E402
from app.services.archive.archive_publish_service import publish_staged_archive  # noqa: E402
from app.services.workbench_factory_service import build_workbench_services  # noqa: E402

from test_phase1d_recovery import (  # noqa: E402
    CASE_ID,
    SOURCE_ID,
    database,
    mark_source_available,
    ready_case,
)


def test_generic_lifecycle_cannot_bypass_interrupted_archive_gate(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    attempts = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    accepted = attempts.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H1", shell["revision"],
    )
    attempts.recover_after_restart()
    before_shell = CaseShellRepository(database).get(CASE_ID)
    before_draft = CaseDraftRepository(database).get(CASE_ID)

    with pytest.raises(WorkbenchPersistenceError) as captured:
        CaseLifecycleService(database).transition(
            CASE_ID, "archive_queued", before_shell["revision"],
        )

    assert captured.value.code == "ARCHIVE_ATTEMPT_REQUIRED"
    assert CaseShellRepository(database).get(CASE_ID) == before_shell
    assert CaseDraftRepository(database).get(CASE_ID) == before_draft
    assert attempts.repository.get_public(accepted["attempt_id"])["status"] == "interrupted"


def test_generic_archive_decision_cannot_write_queued(database) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    with pytest.raises(WorkbenchPersistenceError) as captured:
        CaseLifecycleService(database).decide_archive(
            CASE_ID, "immediate", shell["revision"],
        )
    assert captured.value.code == "ARCHIVE_ATTEMPT_REQUIRED"
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "review_ready"


def test_draft_and_plain_shell_repositories_cannot_write_queued(database) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    draft = CaseDraftRepository(database).get(CASE_ID)
    with pytest.raises(WorkbenchPersistenceError) as draft_error:
        CaseDraftRepository(database).save(
            {**draft, "lifecycle": "archive_queued"}, draft["revision"],
        )
    assert draft_error.value.code == "ARCHIVE_ATTEMPT_REQUIRED"
    with pytest.raises(WorkbenchPersistenceError) as shell_error:
        CaseShellRepository(database).update_lifecycle(
            CASE_ID, "archive_queued", shell["revision"],
        )
    assert shell_error.value.code == "ARCHIVE_ATTEMPT_REQUIRED"
    with pytest.raises(WorkbenchPersistenceError) as decision_error:
        CaseArchiveDecisionRepository(database).decide(
            CASE_ID, "immediate", shell["revision"],
        )
    assert decision_error.value.code == "ARCHIVE_ATTEMPT_REQUIRED"


def test_archive_attempt_carries_server_draft_binding(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H4-BINDING", shell["revision"],
    )
    internal = service.repository.get_internal(attempt["attempt_id"])
    assert internal["source_revision"] == 0
    assert internal["draft_revision"] == 1
    assert internal["report_fingerprint"]
    binding = service.context_binding("SYNTHETIC-CONTEXT-H4-BINDING")
    assert binding is not None
    assert binding["context_kind"] == "workbench"
    assert binding["draft_revision"] == 1


def test_workbench_attempt_refreshes_for_a_new_server_draft_revision(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H4-STALE-DRAFT", shell["revision"],
    )
    draft = CaseDraftRepository(database).get(CASE_ID)
    editable = {**draft, "report": {**draft["report"], "title": "SYNTHETIC/TEST/NEW-DRAFT"}}
    editable.pop("lifecycle", None)
    saved = CaseDraftRepository(database).save(editable, draft["revision"])
    internal = service.repository.get_internal(attempt["attempt_id"])
    binding = service.context_binding("SYNTHETIC-CONTEXT-H4-STALE-DRAFT")

    assert saved["report"]["title"] == "SYNTHETIC/TEST/NEW-DRAFT"
    assert internal["draft_revision"] == saved["revision"]
    assert binding is not None and binding["draft_revision"] == saved["revision"]
    assert service.context_matches(
        attempt["attempt_id"], "SYNTHETIC-CONTEXT-H4-STALE-DRAFT",
    )
    publication = service.revalidate_before_publish(
        attempt["attempt_id"], draft["report"],
    )
    assert publication.report["title"] == "SYNTHETIC/TEST/NEW-DRAFT"
    assert publication.draft_revision == saved["revision"]


def test_disc_number_save_refreshes_running_attempt_binding(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    context_id = "SYNTHETIC-CONTEXT-H4-DISC-UPDATE"
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    original = CaseDraftRepository(database).get(CASE_ID)
    edited = {**original, "report": copy.deepcopy(original["report"])}
    edited.pop("lifecycle", None)
    edited["report"].setdefault("attachments", {})["disc_number"] = "GP20260808-01"

    saved = CaseDraftRepository(database).save(edited, original["revision"])
    internal = service.repository.get_internal(attempt["attempt_id"])
    binding = service.context_binding(context_id)

    assert internal["draft_revision"] == saved["revision"]
    assert binding is not None and binding["draft_revision"] == saved["revision"]
    assert internal["report_fingerprint"] == binding["report_fingerprint"]
    latest = service.revalidate_before_publish(
        attempt["attempt_id"], original["report"],
    )
    assert latest.report["attachments"]["disc_number"] == "GP20260808-01"
    assert latest.draft_revision == saved["revision"]
    assert latest.report_fingerprint == internal["report_fingerprint"]


def test_publish_intent_rechecks_server_draft_before_formal_move(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    context_id = "SYNTHETIC-CONTEXT-H4-PUBLISH-RECHECK"
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    internal = service.repository.get_internal(attempt["attempt_id"])
    draft = CaseDraftRepository(database).get(CASE_ID)
    edited = {**draft, "report": {**draft["report"], "title": "SYNTHETIC/TEST/EDITED"}}
    # 绕过受保护的保存 API，以证明发布边界仍会拒绝
    # 带外的持久化报告变更。
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_drafts SET report_json=?, revision=revision+1 WHERE case_id=?",
            (json.dumps(edited["report"], ensure_ascii=False), CASE_ID),
        )
    with pytest.raises(WorkbenchPersistenceError) as stale:
        service.persist_publish_intent(
            attempt["attempt_id"], context_id=context_id, source_key="1" * 64,
            input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
            manifest_id="SYNTHETIC-MANIFEST-H4-RECHECK",
            final_dir=service.output_root / "compressed" / context_id / "SYNTHETIC-MANIFEST-H4-RECHECK",
            public_manifest=_valid_manifest(
                "SYNTHETIC-MANIFEST-H4-RECHECK", "SYNTHETIC-CASE.rar", b"SYNTHETIC/TEST/RECHECK",
            ),
        )
    assert stale.value.code == "ARCHIVE_ATTEMPT_BINDING_STALE"
    assert service.repository.get_internal(attempt["attempt_id"])["status"] == "running"
    assert ArchiveManifestRepository(service.output_root).find_for_attempt(attempt["attempt_id"]) == []


def test_publish_intent_rechecks_server_source_before_formal_move(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    context_id = "SYNTHETIC-CONTEXT-H4-SOURCE-RECHECK"
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET revision = revision + 1 WHERE source_id = ?",
            (SOURCE_ID,),
        )
    with pytest.raises(WorkbenchPersistenceError) as stale:
        service.persist_publish_intent(
            attempt["attempt_id"], context_id=context_id, source_key="a" * 64,
            input_fingerprint="b" * 64, archive_fingerprint="c" * 64,
            manifest_id="SYNTHETIC-MANIFEST-H4-SOURCE-RECHECK",
            final_dir=service.output_root / "compressed" / context_id / "SYNTHETIC-MANIFEST-H4-SOURCE-RECHECK",
            public_manifest=_valid_manifest(
                "SYNTHETIC-MANIFEST-H4-SOURCE-RECHECK", "SYNTHETIC-CASE.rar", b"SYNTHETIC/TEST/SOURCE-RECHECK",
            ),
        )
    assert stale.value.code == "ARCHIVE_ATTEMPT_BINDING_STALE"
    assert service.repository.get_internal(attempt["attempt_id"])["status"] == "running"
    assert ArchiveManifestRepository(service.output_root).find_for_attempt(attempt["attempt_id"]) == []


def test_publish_intent_reentry_requires_complete_immutable_identity(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    context_id = "SYNTHETIC-CONTEXT-M1-IDENTITY"
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    internal = service.repository.get_internal(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-M1-IDENTITY"
    final_dir = service.output_root / "compressed" / context_id / manifest_id
    manifest = _valid_manifest(manifest_id, "SYNTHETIC-CASE.rar", b"SYNTHETIC/TEST/M1")
    identity = {
        "attempt_id": attempt["attempt_id"], "case_id": CASE_ID, "source_id": SOURCE_ID,
        "context_id": context_id, "target_context_id": context_id,
        "source_revision": 0, "draft_revision": 1,
        "report_fingerprint": internal["report_fingerprint"], "source_key": "1" * 64,
        "input_fingerprint": "2" * 64, "archive_fingerprint": "3" * 64,
        "manifest_id": manifest_id, "relative_final_dir": f"{context_id}/{manifest_id}",
        "public_manifest": manifest,
    }
    repository = ArchivePublishIntentRepository(database)
    original = repository.create(**identity)
    assert repository.create(**identity) == original

    variants = (
        {"case_id": "SYNTHETIC-OTHER-CASE-001"},
        {"source_id": "SYNTHETIC-OTHER-SOURCE-001"},
        {"source_revision": 1},
        {"draft_revision": 2},
        {"report_fingerprint": "4" * 64},
        {"source_key": "5" * 64},
        {"input_fingerprint": "6" * 64},
        {"archive_fingerprint": "7" * 64},
        {"manifest_id": "SYNTHETIC-MANIFEST-M1-OTHER", "relative_final_dir": f"{context_id}/SYNTHETIC-MANIFEST-M1-OTHER"},
        {"public_manifest": {**manifest, "manifest_id": "SYNTHETIC-MANIFEST-M1-OTHER"}},
        {"context_id": "SYNTHETIC-CONTEXT-M1-OTHER"},
    )
    for variant in variants:
        candidate = {**identity, **variant}
        with pytest.raises(WorkbenchPersistenceError) as conflict:
            repository.create(**candidate)
        assert conflict.value.code == "ARCHIVE_PUBLISH_INTENT_CONFLICT"

    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM archive_publish_fences WHERE fence_id = ?", (original["fence_id"],),
        )
    with pytest.raises(WorkbenchPersistenceError) as missing_fence:
        repository.create(**identity)
    assert missing_fence.value.code == "ARCHIVE_PUBLISH_INTENT_CONFLICT"


def test_concurrent_exact_publish_intent_creation_is_idempotent(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    context_id = "SYNTHETIC-CONTEXT-M1-CONCURRENT"
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    internal = service.repository.get_internal(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-M1-CONCURRENT"
    identity = {
        "attempt_id": attempt["attempt_id"], "case_id": CASE_ID, "source_id": SOURCE_ID,
        "context_id": context_id, "target_context_id": context_id,
        "source_revision": 0, "draft_revision": 1,
        "report_fingerprint": internal["report_fingerprint"], "source_key": "8" * 64,
        "input_fingerprint": "9" * 64, "archive_fingerprint": "a" * 64,
        "manifest_id": manifest_id, "relative_final_dir": f"{context_id}/{manifest_id}",
        "public_manifest": _valid_manifest(manifest_id, "SYNTHETIC-CASE.rar", b"SYNTHETIC/TEST/M1-CONCURRENT"),
    }
    repository = ArchivePublishIntentRepository(database)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _value: repository.create(**identity), (1, 2)))
    assert results[0]["intent_id"] == results[1]["intent_id"]
    connection = database.connect()
    try:
        assert connection.execute(
            "SELECT COUNT(*) AS count FROM archive_publish_intents WHERE attempt_id = ?",
            (attempt["attempt_id"],),
        ).fetchone()["count"] == 1
    finally:
        connection.close()


def test_completion_transaction_rechecks_source_after_external_validation(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    context_id = "SYNTHETIC-CONTEXT-H4-SOURCE-RACE"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-H4-SOURCE-RACE"
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/SOURCE-RACE"
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(payload)
    manifest = _valid_manifest(manifest_id, part.name, payload)
    identity = {"source_key": "4" * 64, "input_fingerprint": "5" * 64, "archive_fingerprint": "6" * 64}
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, **identity,
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")
    service.mark_publish_phase(attempt["attempt_id"], "indexed")
    registry = ArchiveManifestRepository(output)
    registry.save(**identity, manifest_id=manifest_id, final_dir=final_dir,
                  public_manifest=manifest, workbench_attempt_id=attempt["attempt_id"])
    original_get = CaseDraftRepository.get
    changed = False

    def read_then_change(draft_repository, case_id):
        nonlocal changed
        result = original_get(draft_repository, case_id)
        if not changed:
            changed = True
            with database.transaction() as connection:
                connection.execute(
                    "UPDATE source_records SET revision = revision + 1 WHERE source_id = ?",
                    (SOURCE_ID,),
                )
        return result

    monkeypatch.setattr(CaseDraftRepository, "get", read_then_change)
    record = ArchiveManifestRecord(
        manifest_id, context_id, identity["archive_fingerprint"], manifest,
        final_dir, 0.0, 9999999999.0,
    )
    with pytest.raises(WorkbenchPersistenceError) as raced:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert raced.value.code == "ARCHIVE_COMPLETION_EVIDENCE_CONFLICT"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "archive_queued"
    assert CaseDraftRepository(database).get(CASE_ID)["lifecycle"] == "archive_queued"


def test_succeed_rejects_untrusted_manifest_id(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H3-FAKE", shell["revision"],
    )
    service.start(attempt["attempt_id"])
    with pytest.raises(WorkbenchPersistenceError) as captured:
        service.succeed(attempt["attempt_id"], "SYNTHETIC-MANIFEST-NOT-INDEXED")
    assert captured.value.code == "ARCHIVE_COMPLETION_EVIDENCE_REQUIRED"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"


def test_completion_service_rejects_wrong_index_missing_rar_and_source_revision(
    database, tmp_path: Path,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H3-EVIDENCE", shell["revision"])
    service.start(attempt["attempt_id"])
    registry = ArchiveManifestRepository(output)
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-H3-EVIDENCE" / "SYNTHETIC-MANIFEST-EVIDENCE"
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/EVIDENCE"
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(payload)
    manifest = _valid_manifest("SYNTHETIC-MANIFEST-EVIDENCE", part.name, payload)
    record = ArchiveManifestRecord(
        "SYNTHETIC-MANIFEST-EVIDENCE", "SYNTHETIC-CONTEXT-H3-EVIDENCE", "3" * 64,
        manifest, final_dir, 0.0, 9999999999.0,
    )
    service.persist_publish_intent(
        attempt["attempt_id"], context_id="SYNTHETIC-CONTEXT-H3-EVIDENCE",
        source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id=record.manifest_id, final_dir=final_dir, public_manifest=manifest,
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")
    service.mark_publish_phase(attempt["attempt_id"], "indexed")
    registry.save(
        source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id=record.manifest_id, final_dir=final_dir, public_manifest=manifest,
        workbench_attempt_id="attempt-SYNTHETIC-OTHER",
    )
    with pytest.raises(WorkbenchPersistenceError) as wrong_attempt:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert wrong_attempt.value.code == "ARCHIVE_COMPLETION_EVIDENCE_REQUIRED"

    with pytest.raises(ArchiveManifestRepositoryError):
        registry.save(
            source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
            manifest_id=record.manifest_id, final_dir=final_dir, public_manifest=manifest,
            workbench_attempt_id=attempt["attempt_id"],
        )
    registry.index_path.unlink()
    registry = ArchiveManifestRepository(output)
    registry.save(
        source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id=record.manifest_id, final_dir=final_dir, public_manifest=manifest,
        workbench_attempt_id=attempt["attempt_id"],
    )
    part.unlink()
    with pytest.raises(WorkbenchPersistenceError) as missing_rar:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert missing_rar.value.code == "ARCHIVE_COMPLETION_EVIDENCE_INVALID"
    part.write_bytes(payload)
    with database.transaction() as connection:
        connection.execute("UPDATE source_records SET revision = revision + 1 WHERE source_id = ?", (SOURCE_ID,))
    with pytest.raises(WorkbenchPersistenceError) as stale_source:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert stale_source.value.code == "ARCHIVE_COMPLETION_EVIDENCE_CONFLICT"


def test_completion_requires_publish_intent_even_when_index_and_rar_are_valid(
    database, tmp_path: Path,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H3-NO-INTENT", shell["revision"])
    service.start(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-H3-NO-INTENT"
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-H3-NO-INTENT" / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/NO-INTENT"
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(payload)
    manifest = _valid_manifest(manifest_id, part.name, payload)
    record = ArchiveManifestRecord(
        manifest_id, attempt["attempt_id"], "3" * 64, manifest, final_dir, 0.0, 9999999999.0,
    )
    registry = ArchiveManifestRepository(output)
    registry.save(
        source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
        workbench_attempt_id=attempt["attempt_id"],
    )
    with pytest.raises(WorkbenchPersistenceError) as missing_intent:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert missing_intent.value.code == "ARCHIVE_COMPLETION_EVIDENCE_REQUIRED"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"


def test_conflict_after_real_source_change_requires_reselection(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "SYNTHETIC-source-conflict"
    source_path.mkdir()
    source_file = source_path / "report.txt"
    source_file.write_bytes(b"SYNTHETIC/TEST/ORIGINAL")
    ready_case(database)
    from app.services import source_record_service as source_module
    fingerprint = source_module._fingerprint(source_path)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET source_type = 'report_directory', internal_path = ?, allowed_root = ?, "
            "metadata_json = ?, fingerprint_json = ?, access_status = 'available' WHERE source_id = ?",
            (str(source_path), str(tmp_path), json.dumps({}), json.dumps({"value": fingerprint}), SOURCE_ID),
        )
    service = SourceRecordService(database)
    monkeypatch.setattr(service, "_validate_report_structure", lambda _path: None)
    original = service.repository.revalidate
    raced = False

    def revision_race(source_id: str, *, current_fingerprint: str | None = None):
        nonlocal raced
        if not raced:
            raced = True
            result = original(source_id, current_fingerprint=current_fingerprint)
            source_file.write_bytes(b"SYNTHETIC/TEST/CHANGED")
            raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
        return original(source_id, current_fingerprint=current_fingerprint)

    monkeypatch.setattr(service.repository, "revalidate", revision_race)
    result = service.verify_after_parse(SOURCE_ID, SourceRecordRepository(database).get(SOURCE_ID)["revision"])
    assert result["access_status"] == "requires_reselection"


def test_source_conflict_retry_exhaustion_is_pending_and_bounded(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "SYNTHETIC-source-conflict-exhausted"
    source_path.mkdir()
    (source_path / "report.txt").write_bytes(b"SYNTHETIC/TEST/STABLE")
    ready_case(database)
    from app.services import source_record_service as source_module
    fingerprint = source_module._fingerprint(source_path)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET source_type = 'report_directory', internal_path = ?, allowed_root = ?, "
            "metadata_json = ?, fingerprint_json = ?, access_status = 'available' WHERE source_id = ?",
            (str(source_path), str(tmp_path), json.dumps({}), json.dumps({"value": fingerprint}), SOURCE_ID),
        )
    service = SourceRecordService(database)
    calls = 0

    def always_conflicts(source_id: str, *, current_fingerprint: str | None = None):
        nonlocal calls
        calls += 1
        raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")

    monkeypatch.setattr(service.repository, "revalidate", always_conflicts)
    monkeypatch.setattr(
        service,
        "_compute_current_fingerprint",
        lambda _source_id, _should_cancel=None: fingerprint,
    )
    result = service.verify_after_parse(SOURCE_ID, SourceRecordRepository(database).get(SOURCE_ID)["revision"])
    assert calls == service._MAX_REVISION_CONFLICT_RETRIES * 2
    assert result["access_status"] == "pending"
    assert result["revalidation_error_code"] == "SOURCE_REVISION_CONFLICT_RETRY_EXHAUSTED"


def test_verified_manifest_is_reconciled_before_restart_interruption(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    attempts = ArchiveAttemptService(database, output)
    attempt = attempts.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H3", shell["revision"],
    )
    attempts.start(attempt["attempt_id"])
    identity = {
        "source_key": "1" * 64,
        "input_fingerprint": "2" * 64,
        "archive_fingerprint": "3" * 64,
    }
    manifest_id = "SYNTHETIC-MANIFEST-H3"
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-H3" / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/VERIFIED-RAR"
    filename = "SYNTHETIC-CASE.rar"
    (final_dir / filename).write_bytes(payload)
    manifest = _valid_manifest(manifest_id, filename, payload)
    attempts.persist_publish_intent(
        attempt["attempt_id"], source_key=identity["source_key"],
        input_fingerprint=identity["input_fingerprint"],
        archive_fingerprint=identity["archive_fingerprint"], manifest_id=manifest_id,
        final_dir=final_dir, public_manifest=manifest, context_id="SYNTHETIC-CONTEXT-H3",
    )
    attempts.mark_publish_phase(attempt["attempt_id"], "published")
    ArchiveManifestRepository(output).save(
        **identity, manifest_id=manifest_id, final_dir=final_dir,
        public_manifest=manifest, workbench_attempt_id=attempt["attempt_id"],
    )

    restarted = ArchiveAttemptService(database, output)
    assert restarted.recover_after_restart() == []
    assert restarted.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "archive_verified"
    draft = CaseDraftRepository(database).get(CASE_ID)
    assert draft["lifecycle"] == "archive_verified"
    attachment_rows = draft["report"]["attachments"]["extract_list"]["rows"]
    assert [row["electronic_data"] for row in attachment_rows] == [filename]
    assert draft["report"]["inspection"]["result"]["md5_hash"] == (
        hashlib.md5(payload).hexdigest().upper()
    )
    assert [row["md5_hash"] for row in attachment_rows] == [
        hashlib.md5(payload).hexdigest().upper()
    ]
    assert all("file_size" not in row for row in attachment_rows)
    assert (final_dir / filename).read_bytes() == payload
    assert len(ArchiveManifestRepository(output).find_reusable(**identity)) == 1
    recovered = restarted.repository.get_internal(attempt["attempt_id"])
    assert recovered["manifest_source_key"] == identity["source_key"]


def test_move_before_sealed_publication_cannot_become_succeeded(
    database, tmp_path: Path,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    context_id = "SYNTHETIC-CONTEXT-H3-PUBLISHED-CRASH"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    identity = {
        "source_key": "a" * 64,
        "input_fingerprint": "b" * 64,
        "archive_fingerprint": "c" * 64,
    }
    manifest_id = "SYNTHETIC-MANIFEST-H3-PUBLISHED-CRASH"
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/PUBLISHED-CRASH"
    filename = "SYNTHETIC-CASE.rar"
    (final_dir / filename).write_bytes(payload)
    manifest = _valid_manifest(manifest_id, filename, payload)
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, **identity,
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
    )
    # 发布代次密封前的移动无法恢复为成功。
    # 意图仍是唯一权威来源，必须拒绝清理。
    assert service.context_binding(context_id)["attempt_id"] == attempt["attempt_id"]
    with pytest.raises(ArchiveManifestRepositoryError, match="ARCHIVE_INDEX_MISSING"):
        ArchiveManifestRepository(output).find_for_attempt(attempt["attempt_id"])
    restarted = ArchiveAttemptService(database, output)
    assert restarted.recover_after_restart() == [attempt["attempt_id"]]
    assert restarted.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"
    intent = restarted._publish_intent(attempt["attempt_id"])
    assert intent["phase"] == "conflict"
    assert not final_dir.exists()
    assert restarted.recover_after_restart() == []


def test_damaged_manifest_evidence_remains_interrupted(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    attempts = ArchiveAttemptService(database, output)
    attempt = attempts.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H3-BAD", shell["revision"],
    )
    attempts.start(attempt["attempt_id"])
    identity = {
        "source_key": "4" * 64,
        "input_fingerprint": "5" * 64,
        "archive_fingerprint": "6" * 64,
    }
    manifest_id = "SYNTHETIC-MANIFEST-H3-BAD"
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-H3-BAD" / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/ORIGINAL"
    filename = "SYNTHETIC-CASE.rar"
    part = final_dir / filename
    part.write_bytes(payload)
    ArchiveManifestRepository(output).save(
        **identity, manifest_id=manifest_id, final_dir=final_dir,
        public_manifest=_valid_manifest(manifest_id, filename, payload),
        workbench_attempt_id=attempt["attempt_id"],
    )
    part.write_bytes(b"SYNTHETIC/TEST/TAMPERED")

    assert ArchiveAttemptService(database, output).recover_after_restart() == [attempt["attempt_id"]]
    assert attempts.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"
    assert attempts.repository.get_internal(attempt["attempt_id"])["manifest_source_key"] is None
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "archive_interrupted"


def test_publish_intent_before_move_waits_for_explicit_retry(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-PUBLISH-BEFORE", shell["revision"])
    service.start(attempt["attempt_id"])
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-PUBLISH-BEFORE" / "SYNTHETIC-MANIFEST-BEFORE"
    manifest = _valid_manifest("SYNTHETIC-MANIFEST-BEFORE", "SYNTHETIC-CASE.rar", b"SYNTHETIC/TEST/BEFORE")
    service.persist_publish_intent(
        attempt["attempt_id"], source_key="7" * 64, input_fingerprint="8" * 64,
        archive_fingerprint="9" * 64, manifest_id="SYNTHETIC-MANIFEST-BEFORE",
        final_dir=final_dir, public_manifest=manifest, context_id="SYNTHETIC-CONTEXT-PUBLISH-BEFORE",
    )
    assert service.recover_after_restart() == [attempt["attempt_id"]]
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"
    assert not final_dir.exists()


def test_published_intent_without_index_is_registered_and_completed(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-PUBLISH-AFTER", shell["revision"])
    service.start(attempt["attempt_id"])
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-PUBLISH-AFTER" / "SYNTHETIC-MANIFEST-AFTER"
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/AFTER-MOVE"
    (final_dir / "SYNTHETIC-CASE.rar").write_bytes(payload)
    manifest = _valid_manifest("SYNTHETIC-MANIFEST-AFTER", "SYNTHETIC-CASE.rar", payload)
    service.persist_publish_intent(
        attempt["attempt_id"], source_key="a" * 64, input_fingerprint="b" * 64,
        archive_fingerprint="c" * 64, manifest_id="SYNTHETIC-MANIFEST-AFTER",
        final_dir=final_dir, public_manifest=manifest, context_id="SYNTHETIC-CONTEXT-PUBLISH-AFTER",
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")
    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"
    assert service.recover_after_restart() == []
    assert len(ArchiveManifestRepository(output).find_for_attempt(attempt["attempt_id"])) == 1


def test_tampered_published_intent_is_interrupted_and_preserved(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-PUBLISH-TAMPER", shell["revision"])
    service.start(attempt["attempt_id"])
    final_dir = output / "compressed" / "SYNTHETIC-CONTEXT-PUBLISH-TAMPER" / "SYNTHETIC-MANIFEST-TAMPER"
    final_dir.mkdir(parents=True)
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(b"SYNTHETIC/TEST/ORIGINAL")
    manifest = _valid_manifest("SYNTHETIC-MANIFEST-TAMPER", part.name, part.read_bytes())
    service.persist_publish_intent(
        attempt["attempt_id"], source_key="d" * 64, input_fingerprint="e" * 64,
        archive_fingerprint="f" * 64, manifest_id="SYNTHETIC-MANIFEST-TAMPER",
        final_dir=final_dir, public_manifest=manifest, context_id="SYNTHETIC-CONTEXT-PUBLISH-TAMPER",
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")
    part.write_bytes(b"SYNTHETIC/TEST/TAMPERED")
    assert service.recover_after_restart() == [attempt["attempt_id"]]
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"
    assert part.exists()


def test_transient_manifest_index_failure_keeps_intent_retryable(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    context_id = "SYNTHETIC-CONTEXT-H3-TRANSIENT-INDEX"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-H3-TRANSIENT-INDEX"
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/TRANSIENT-INDEX"
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(payload)
    manifest = _valid_manifest(manifest_id, part.name, payload)
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, source_key="d" * 64,
        input_fingerprint="e" * 64, archive_fingerprint="f" * 64,
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")

    def fail_index(*_args, **_kwargs):
        raise ArchiveManifestRepositoryError("SYNTHETIC/TEST/INDEX-TEMPORARY")

    monkeypatch.setattr(ArchiveManifestRepository, "save", fail_index)
    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"
    intent = service.context_binding(context_id)
    assert intent is not None
    monkeypatch.undo()
    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"


def test_transient_publish_phase_database_lock_keeps_intent_retryable(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    context_id = "SYNTHETIC-CONTEXT-H3-TRANSIENT-SQLITE"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-H3-TRANSIENT-SQLITE"
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/TRANSIENT-SQLITE"
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(payload)
    manifest = _valid_manifest(manifest_id, part.name, payload)
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, source_key="7" * 64,
        input_fingerprint="8" * 64, archive_fingerprint="9" * 64,
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")

    def fail_phase(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ArchivePublishIntentRepository, "mark_phase", fail_phase)
    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"
    assert ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])["phase"] == "published"
    monkeypatch.undo()
    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"


def test_reissued_workbench_context_keeps_old_origin_but_only_new_binding_is_active(
    database, tmp_path: Path,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    attempts = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = attempts.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H4-OLD", shell["revision"],
    )
    attempts.reissue_context(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-H4-NEW",
        CaseShellRepository(database).get(CASE_ID)["revision"],
    )

    old_binding = attempts.context_binding("SYNTHETIC-CONTEXT-H4-OLD")
    new_binding = attempts.context_binding("SYNTHETIC-CONTEXT-H4-NEW")
    assert {key: old_binding[key] for key in ("attempt_id", "case_id", "active", "attempt_status")} == {
        "attempt_id": attempt["attempt_id"], "case_id": CASE_ID,
        "active": False, "attempt_status": "accepted",
    }
    assert {key: new_binding[key] for key in ("attempt_id", "case_id", "active", "attempt_status")} == {
        "attempt_id": attempt["attempt_id"], "case_id": CASE_ID,
        "active": True, "attempt_status": "accepted",
    }
    assert not attempts.context_matches(attempt["attempt_id"], "SYNTHETIC-CONTEXT-H4-OLD")
    assert attempts.context_matches(attempt["attempt_id"], "SYNTHETIC-CONTEXT-H4-NEW")


def test_revision_conflict_reuses_latest_source_without_false_reselection(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "SYNTHETIC-source"
    source_path.mkdir()
    (source_path / "report.txt").write_bytes(b"SYNTHETIC/TEST/SOURCE")
    ready_case(database)
    from app.services import source_record_service as source_module
    fingerprint = source_module._fingerprint(source_path)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET source_type = 'report_directory', internal_path = ?, allowed_root = ?, "
            "metadata_json = ?, fingerprint_json = ?, access_status = 'available' WHERE source_id = ?",
            (
                str(source_path), str(tmp_path), json.dumps({}),
                json.dumps({"value": fingerprint}), SOURCE_ID,
            ),
        )
    service = SourceRecordService(database)
    monkeypatch.setattr(service, "_validate_report_structure", lambda _path: None)
    original = service.repository.revalidate
    raced = False

    def revision_race(source_id: str, *, current_fingerprint: str | None = None):
        nonlocal raced
        if not raced:
            raced = True
            original(source_id, current_fingerprint=current_fingerprint)
            raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
        return original(source_id, current_fingerprint=current_fingerprint)

    monkeypatch.setattr(service.repository, "revalidate", revision_race)
    expected_revision = SourceRecordRepository(database).get(SOURCE_ID)["revision"]

    result = service.verify_after_parse(SOURCE_ID, expected_revision)

    assert result["access_status"] == "available"
    assert SourceRecordRepository(database).get(SOURCE_ID)["requires_reselection"] is False


def test_staging_root_and_other_attempt_directory_are_never_deleted(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-L1", shell["revision"],
    )
    service.staging_root.mkdir(parents=True)
    other = service.staging_root / "archive-SYNTHETIC-OTHER"
    other.mkdir()
    (other / "keep.txt").write_text("SYNTHETIC/TEST/KEEP", encoding="utf-8")
    service.staging_initializer(attempt["attempt_id"])(service.staging_root)
    record = service.repository.get_internal(attempt["attempt_id"])

    assert cleanup_owned_staging(
        record, service.staging_root, database.deployment_instance_id,
    ) == "unknown"
    assert service.staging_root.is_dir()
    assert (other / "keep.txt").read_text(encoding="utf-8") == "SYNTHETIC/TEST/KEEP"


def test_completion_transaction_rejects_shell_zero_row_race(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-H4-SHELL-RACE", "SYNTHETIC-MANIFEST-H4-SHELL-RACE",
    )
    original_get = CaseDraftRepository.get
    changed = False

    def read_then_interrupt(draft_repository, case_id):
        nonlocal changed
        result = original_get(draft_repository, case_id)
        if not changed:
            changed = True
            with database.transaction() as connection:
                connection.execute(
                    "UPDATE case_shells SET lifecycle = 'archive_interrupted' WHERE case_id = ?",
                    (CASE_ID,),
                )
        return result

    monkeypatch.setattr(CaseDraftRepository, "get", read_then_interrupt)
    with pytest.raises(WorkbenchPersistenceError) as raced:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert raced.value.code == "ARCHIVE_COMPLETION_EVIDENCE_CONFLICT"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"
    with database.connect() as connection:
        assert connection.execute("SELECT lifecycle FROM case_shells WHERE case_id = ?", (CASE_ID,)).fetchone()[0] == "archive_interrupted"


def test_completion_transaction_rejects_draft_zero_row_race(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-H4-DRAFT-RACE", "SYNTHETIC-MANIFEST-H4-DRAFT-RACE",
    )
    original_get = CaseDraftRepository.get
    changed = False

    def read_then_edit(draft_repository, case_id):
        nonlocal changed
        result = original_get(draft_repository, case_id)
        if not changed:
            changed = True
            with database.transaction() as connection:
                connection.execute(
                    "UPDATE case_drafts SET lifecycle = 'review_ready' WHERE case_id = ?",
                    (CASE_ID,),
                )
        return result

    monkeypatch.setattr(CaseDraftRepository, "get", read_then_edit)
    with pytest.raises(WorkbenchPersistenceError) as raced:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert raced.value.code == "ARCHIVE_COMPLETION_EVIDENCE_CONFLICT"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"
    with database.connect() as connection:
        assert connection.execute("SELECT lifecycle FROM case_drafts WHERE case_id = ?", (CASE_ID,)).fetchone()[0] == "review_ready"


def test_completion_merges_manifest_into_latest_photo_draft_during_active_fence(
    database, tmp_path: Path,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-T026-PHOTO",
        "SYNTHETIC-MANIFEST-T026-PHOTO",
    )
    references = []
    repository = AssetReferenceRepository(database)
    for index in (1, 2):
        references.append(repository.create({
            "asset_id": f"asset-synthetic-t026-{index}",
            "case_id": CASE_ID,
            "asset_kind": "image",
            "fingerprint": f"{index}" * 64,
            "metadata": {
                "file_name": f"SYNTHETIC-t026-{index}.png",
                "extension": ".png",
                "media_type": "image/png",
                "size_bytes": index,
            },
        }))
    current = CaseDraftRepository(database).get(CASE_ID)
    edited = {**current, "report": copy.deepcopy(current["report"])}
    edited.pop("lifecycle", None)
    edited["asset_refs"] = [
        {key: reference[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")}
        for reference in references
    ]
    edited["report"]["introduction"]["evidence_list"] = [{
        "id": "SYNTHETIC-MATERIAL-T026",
        "device_type": "SYNTHETIC-DEVICE",
        "evidence_number": "SYNTHETIC-T026-1",
    }]
    photo_ids = [reference["asset_id"] for reference in references]
    edited["report"]["attachments"].update({
        "photo_ids": photo_ids,
        "photo_groups": [{
            "material_id": "SYNTHETIC-MATERIAL-T026",
            "material_number": "SYNTHETIC-T026-1",
            "display_text": "检材SYNTHETIC-T026-1照片",
            "ordered_image_ids": photo_ids,
            "source_order": 1,
        }],
    })

    saved = CaseDraftRepository(database).save(edited, current["revision"])
    assert service.repository.get_internal(attempt["attempt_id"])["draft_revision"] != saved["revision"]

    service.complete_verified(attempt["attempt_id"], registry, record)

    completed = CaseDraftRepository(database).get(CASE_ID)
    assert completed["lifecycle"] == "archive_verified"
    assert [item["asset_id"] for item in completed["asset_refs"]] == photo_ids
    assert completed["report"]["attachments"]["photo_ids"] == photo_ids
    assert completed["report"]["attachments"]["photo_groups"][0]["ordered_image_ids"] == photo_ids
    assert completed["report"]["inspection"]["result"]["rar_filename"] == "SYNTHETIC-CASE.rar"


def test_draft_save_rebases_once_when_verified_completion_wins_the_revision_race(
    database, tmp_path: Path,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-T027-SAVE-RACE",
        "SYNTHETIC-MANIFEST-T027-SAVE-RACE",
    )
    stale = CaseDraftRepository(database).get(CASE_ID)
    service.complete_verified(attempt["attempt_id"], registry, record)

    services = build_workbench_services(database)
    identity = {
        "identity_kind": "local_session",
        "client_instance_id": "SYNTHETIC-T027-CLIENT",
        "session_id": "SYNTHETIC-T027-SESSION",
        "deployment_instance_id": database.deployment_instance_id,
    }
    lease = services.leases.acquire(CASE_ID, identity)
    reference = AssetReferenceRepository(database).create({
        "asset_id": "asset-synthetic-t027",
        "case_id": CASE_ID,
        "asset_kind": "image",
        "fingerprint": "7" * 64,
        "metadata": {
            "file_name": "SYNTHETIC-t027.png", "extension": ".png",
            "media_type": "image/png", "size_bytes": 1,
        },
    })
    stale.pop("lifecycle", None)
    stale["asset_refs"] = [{
        key: reference[key]
        for key in ("asset_id", "asset_kind", "fingerprint", "metadata")
    }]
    stale["report"]["attachments"]["photo_ids"] = [reference["asset_id"]]

    result = services.lifecycle.save_draft(
        stale, stale["revision"], None, None, identity,
        lease["lease_id"], lease["lease_token"],
    )

    assert result["draft_save_status"]["status"] == "saved"
    saved = result["draft"]
    assert saved["asset_refs"][0]["asset_id"] == reference["asset_id"]
    assert saved["report"]["attachments"]["photo_ids"] == [reference["asset_id"]]
    assert saved["report"]["inspection"]["result"]["rar_filename"] == "SYNTHETIC-CASE.rar"
    assert saved["report"]["inspection"]["result"]["md5_hash"]


def test_completion_retries_a_bounded_latest_draft_merge_conflict(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-T026-RETRY",
        "SYNTHETIC-MANIFEST-T026-RETRY",
    )
    original_complete = completion_module.complete_verified_attempt
    calls = 0

    def conflict_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            current = CaseDraftRepository(database).get(CASE_ID)
            edited = {**current, "report": copy.deepcopy(current["report"])}
            edited.pop("lifecycle", None)
            edited["report"]["title"] = "SYNTHETIC/TEST/T026-RETRY-LATEST"
            CaseDraftRepository(database).save(edited, current["revision"])
        return original_complete(*args, **kwargs)

    monkeypatch.setattr(completion_module, "complete_verified_attempt", conflict_once)

    service.complete_verified(attempt["attempt_id"], registry, record)

    assert calls == 2
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"
    assert CaseDraftRepository(database).get(CASE_ID)["report"]["title"] == "SYNTHETIC/TEST/T026-RETRY-LATEST"


def test_success_commit_and_verified_phase_share_one_transaction(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-H3-VERIFIED-PHASE", "SYNTHETIC-MANIFEST-H3-VERIFIED-PHASE",
    )
    original_mark_phase = ArchivePublishIntentRepository.mark_phase

    def fail_verified(repository, attempt_id, phase):
        if phase == "verified":
            raise sqlite3.OperationalError("database is locked")
        return original_mark_phase(repository, attempt_id, phase)

    monkeypatch.setattr(ArchivePublishIntentRepository, "mark_phase", fail_verified)
    # 完成流程不再有提交后的 mark_phase 调用。
    # 在此注入失败不得产生虚假的中间成功窗口。
    service.complete_verified(attempt["attempt_id"], registry, record)
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"
    assert ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])["phase"] == "verified"
    monkeypatch.undo()
    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"
    assert ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])["phase"] == "verified"


def test_completion_rejects_formal_part_changed_after_index_and_invalidates_index(
    database, tmp_path: Path,
) -> None:
    service, attempt, registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-M4-FORMAL", "SYNTHETIC-MANIFEST-M4-FORMAL",
    )
    filename = str(record.public_manifest["parts"][0]["filename"])
    (record.final_dir / filename).write_bytes(b"SYNTHETIC/TEST/M4-TAMPERED")

    with pytest.raises(WorkbenchPersistenceError) as changed:
        service.complete_verified(attempt["attempt_id"], registry, record)
    assert changed.value.code == "ARCHIVE_COMPLETION_EVIDENCE_INVALID"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"
    assert registry.find_for_attempt(attempt["attempt_id"]) == []
    assert (record.final_dir / filename).is_file()


def test_publish_moves_before_single_marker_removal(database, tmp_path: Path, monkeypatch) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    context_id = "SYNTHETIC-CONTEXT-L1-ORDER"
    manifest_id = "SYNTHETIC-MANIFEST-L1-ORDER"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    staging_dir = service.staging_root / "SYNTHETIC-STAGING-L1"
    staging_dir.mkdir(parents=True)
    service.staging_initializer(attempt["attempt_id"])(staging_dir)
    payload = b"SYNTHETIC/TEST/L1-MARKER"
    (staging_dir / "SYNTHETIC-CASE.rar").write_bytes(payload)
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.parent.mkdir(parents=True)
    manifest = _valid_manifest(manifest_id, "SYNTHETIC-CASE.rar", payload)
    record = ArchiveManifestRecord(
        manifest_id, context_id, "3" * 64, manifest, final_dir, 0.0, 9999999999.0,
    )
    context = SimpleNamespace(
        context_id=context_id, source_key="1" * 64, input_fingerprint="2" * 64,
    )
    report = CaseDraftRepository(database).get(CASE_ID)["report"]
    calls: list[Path] = []
    original_remove = service.remove_marker

    def record_remove(path: Path) -> None:
        calls.append(path)
        original_remove(path)

    monkeypatch.setattr(service, "remove_marker", record_remove)
    publish_staged_archive(
        staging_dir, final_dir, record, report, context=context,
        attempt_id=attempt["attempt_id"], attempt_service=service,
        workbench_context_id=context_id,
    )

    assert calls == [final_dir]
    assert not (final_dir / ".workbench-staging-owner.json").exists()
    assert ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])["phase"] == "published"


def _trusted_completion(database, tmp_path: Path, context_id: str, manifest_id: str):
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/TEST/TRUSTED-COMPLETION"
    filename = "SYNTHETIC-CASE.rar"
    (final_dir / filename).write_bytes(payload)
    manifest = _valid_manifest(manifest_id, filename, payload)
    identity = {
        "source_key": "1" * 64, "input_fingerprint": "2" * 64,
        "archive_fingerprint": "3" * 64,
    }
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, **identity,
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")
    service.mark_publish_phase(attempt["attempt_id"], "indexed")
    registry = ArchiveManifestRepository(output)
    registry.save(
        **identity, manifest_id=manifest_id, final_dir=final_dir,
        public_manifest=manifest, workbench_attempt_id=attempt["attempt_id"],
    )
    return service, attempt, registry, ArchiveManifestRecord(
        manifest_id, context_id, identity["archive_fingerprint"], manifest,
        final_dir, 0.0, 9999999999.0,
    )


def _valid_manifest(manifest_id: str, filename: str, payload: bytes) -> dict[str, object]:
    return {
        "manifest_id": manifest_id,
        "archive_base_name": filename.removesuffix(".rar"),
        "volume_size_bytes": 4_000_000_000,
        "max_part_count": 2,
        "actual_archive_bytes": len(payload),
        "validation_status": "validated",
        "parts": [{
            "part_id": "SYNTHETIC-PART-1",
            "part_number": 1,
            "filename": filename,
            "size_bytes": len(payload),
            "md5": hashlib.md5(payload).hexdigest(),  # noqa: S324 - required Legacy contract
            "disc_number": "SYNTHETIC-DISC-1",
            "disc_date": "2026-07-28",
            "disc_capacity_bytes": 4_000_000_000,
            "volume_size_bytes": 4_000_000_000,
        }],
    }
