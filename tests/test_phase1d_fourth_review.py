"""第四次独立 Level 3 审查的合成数据回归测试。"""

from __future__ import annotations

from concurrent.futures import Future
import os
from pathlib import Path
from threading import Event, Thread
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import CaseDraftRepository
from app.repository import CaseShellRepository, SourceRecordRepository
from app.repository.archive_manifest_repository import ArchiveManifestRepository
from app.repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from app.repository.workbench_errors import WorkbenchPersistenceError
from app.services.archive.archive_attempt_service import ArchiveAttemptService
from app.services.report_parse_inflight_service import ReportParseInFlightRegistry
from app.services.source_record_fingerprint_service import fingerprint, fingerprint_with_metadata

from test_phase1d_recovery import (  # noqa: E402
    CASE_ID,
    SOURCE_ID,
    database,
    mark_source_available,
    ready_case,
)
from test_phase1d_review_remediation import _valid_manifest  # noqa: E402


def _core_source(tmp_path: Path, name: str) -> tuple[Path, Path]:
    source = tmp_path / name
    data = source / "data"
    data.mkdir(parents=True)
    for filename in (
        "data_case_info.json", "data_device_lists.json", "data_report_info.json",
    ):
        (data / filename).write_bytes(b"SYNTHETIC/TEST/CORE")
    return source, data


def _publish_intent(service: ArchiveAttemptService, attempt_id: str, context_id: str) -> None:
    service.persist_publish_intent(
        attempt_id,
        context_id=context_id,
        source_key="1" * 64,
        input_fingerprint="2" * 64,
        archive_fingerprint="3" * 64,
        manifest_id="SYNTHETIC-MANIFEST-FENCE",
        final_dir=service.output_root / "compressed" / "SYNTHETIC-RUNTIME" / "SYNTHETIC-MANIFEST-FENCE",
        target_context_id="SYNTHETIC-RUNTIME",
        public_manifest={
            "manifest_id": "SYNTHETIC-MANIFEST-FENCE",
            "parts": [],
        },
    )


def test_active_publish_fence_allows_draft_write_without_rebinding_evidence(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    context_id = "SYNTHETIC-CONTEXT-FENCE"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    _publish_intent(service, attempt["attempt_id"], context_id)
    original_attempt = service.repository.get_internal(attempt["attempt_id"])
    original_binding = service.context_binding(context_id)

    draft = CaseDraftRepository(database).get(CASE_ID)
    edited = {**draft, "report": {**draft["report"], "title": "SYNTHETIC/TEST/FENCE"}}
    edited.pop("lifecycle", None)
    saved = CaseDraftRepository(database).save(edited, draft["revision"])

    assert saved["report"]["title"] == "SYNTHETIC/TEST/FENCE"
    assert service.repository.get_internal(attempt["attempt_id"])["draft_revision"] == original_attempt["draft_revision"]
    assert service.context_binding(context_id)["draft_revision"] == original_binding["draft_revision"]


def test_active_publish_fence_blocks_source_write(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-SOURCE-FENCE", shell["revision"])
    service.start(attempt["attempt_id"])
    _publish_intent(service, attempt["attempt_id"], "SYNTHETIC-CONTEXT-SOURCE-FENCE")

    with pytest.raises(WorkbenchPersistenceError) as error:
        SourceRecordRepository(database).mark_pending_revalidation(SOURCE_ID)
    assert error.value.code == "ARCHIVE_PUBLISH_FENCE_ACTIVE"


def test_pending_verification_edit_invalidates_old_fence(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    context_id = "SYNTHETIC-CONTEXT-PENDING-FENCE"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    _publish_intent(service, attempt["attempt_id"], context_id)
    assert service.recover_after_restart() == [attempt["attempt_id"]]

    current = CaseDraftRepository(database).get(CASE_ID)
    editable = {**current, "lifecycle": "archive_deferred"}
    CaseDraftRepository(database).save(editable, current["revision"])
    intent = ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])
    assert intent is not None
    with database.connect() as connection:
        fence = connection.execute(
            "SELECT status FROM archive_publish_fences WHERE fence_id = ?", (intent["fence_id"],),
        ).fetchone()
    assert fence["status"] == "invalidated"
    assert not service.context_matches(attempt["attempt_id"], context_id)


def test_failed_attempt_with_publish_intent_is_reconciled_without_republish(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    output = tmp_path / "SYNTHETIC-OUTPUT"
    service = ArchiveAttemptService(database, output)
    context_id = "SYNTHETIC-CONTEXT-FAILED-INTENT"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    manifest_id = "SYNTHETIC-MANIFEST-FAILED-INTENT"
    final_dir = output / "compressed" / context_id / manifest_id
    final_dir.mkdir(parents=True)
    payload = b"SYNTHETIC/FAILED-INTENT-RAR"
    part = final_dir / "SYNTHETIC-CASE.rar"
    part.write_bytes(payload)
    manifest = _valid_manifest(manifest_id, part.name, payload)
    identity = {"source_key": "4" * 64, "input_fingerprint": "5" * 64, "archive_fingerprint": "6" * 64}
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, manifest_id=manifest_id,
        final_dir=final_dir, public_manifest=manifest, **identity,
    )
    ArchiveManifestRepository(output).save(
        manifest_id=manifest_id, final_dir=final_dir, public_manifest=manifest,
        workbench_attempt_id=attempt["attempt_id"], **identity,
    )
    service.mark_publish_phase(attempt["attempt_id"], "published")
    service.repository.mark_failed(attempt["attempt_id"], "SYNTHETIC-TEMPORARY-FAILURE")

    assert service.recover_after_restart() == []
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "succeeded"
    assert len(ArchiveManifestRepository(output).find_for_attempt(attempt["attempt_id"])) == 1


def test_source_fingerprint_is_bounded_and_detects_core_metadata_changes(tmp_path: Path) -> None:
    source, data = _core_source(tmp_path, "SYNTHETIC-SOURCE")
    item = data / "data_case_info.json"
    item.write_bytes(b"SYNTHETIC-ONE")
    original = item.stat()
    first = fingerprint(source)

    # 保持大小和时间戳不变的原地重写按设计不在
    # 仅元数据门禁的保证范围内。
    item.write_bytes(b"SYNTHETIC-TWO")
    os.utime(item, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert fingerprint(source) == first

    # 可检测到大小变化。
    item.write_bytes(b"SYNTHETIC-THREE-LONGER")
    assert fingerprint(source) != first

    # 可检测到时间戳变化。
    item.write_bytes(b"SYNTHETIC-TWO")
    os.utime(item, ns=(original.st_atime_ns, original.st_mtime_ns + 1_000_000))
    assert fingerprint(source) != first


def test_source_fingerprint_returns_transient_failure_for_snapshot_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source, data = _core_source(tmp_path, "SYNTHETIC-SOURCE-CHANGE")
    item = data / "data_case_info.json"
    item.write_bytes(b"SYNTHETIC-ORIGINAL")
    from app.services import source_record_fingerprint_service as fingerprint_module

    original_snapshot = fingerprint_module._snapshot
    calls = 0

    def mutate_between_snapshots(path: Path, _should_cancel=None):
        nonlocal calls
        result = original_snapshot(path)
        calls += 1
        if calls == 1:
            item.write_bytes(b"SYNTHETIC-REPLACED-LONGER")
        return result

    monkeypatch.setattr(fingerprint_module, "_snapshot", mutate_between_snapshots)
    with pytest.raises(fingerprint_module.SourceFingerprintTransientError):
        fingerprint(source)


def test_initial_source_fingerprint_reuses_the_stable_snapshot_for_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source, _ = _core_source(tmp_path, "SYNTHETIC-SOURCE-METADATA")
    (source / "deep" / "media").mkdir(parents=True)
    (source / "deep" / "media" / "item.bin").write_bytes(b"SYNTHETIC")
    from app.services import source_record_fingerprint_service as fingerprint_module

    original_snapshot = fingerprint_module._snapshot
    calls = 0

    def counted_snapshot(path: Path, _should_cancel=None):
        nonlocal calls
        calls += 1
        return original_snapshot(path)

    monkeypatch.setattr(fingerprint_module, "_snapshot", counted_snapshot)
    metadata, value = fingerprint_with_metadata(source)

    assert calls == 2
    assert metadata["identity_entry_count"] == 5
    assert value == fingerprint_module._fingerprint_entries(original_snapshot(source))
    assert all("deep" not in relative for relative, *_ in original_snapshot(source))


def test_source_fingerprint_traversal_honors_shutdown_cancellation(tmp_path: Path) -> None:
    source, _ = _core_source(tmp_path, "SYNTHETIC-SOURCE-CANCEL")
    from app.services.source_record_fingerprint_service import SourceFingerprintCancelledError

    checks = 0

    def should_cancel() -> bool:
        nonlocal checks
        checks += 1
        return checks > 4

    with pytest.raises(SourceFingerprintCancelledError):
        fingerprint(source, should_cancel)


def test_future_callback_can_reenter_registry_without_lock_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ReportParseInFlightRegistry(max_entries=2)
    callback_blocked = Event()
    callback_finished = Event()
    original_set_result = Future.set_result

    def patched_set_result(future: Future[object], value: object) -> None:
        def callback(_: Future[object]) -> None:
            query_finished = Event()

            def query_registry() -> None:
                _ = registry.active_count
                registry.run("SYNTHETIC-CALLBACK-KEY", lambda: "SYNTHETIC-RESULT")
                query_finished.set()

            worker = Thread(target=query_registry, daemon=True)
            worker.start()
            if not query_finished.wait(timeout=0.2):
                callback_blocked.set()
            callback_finished.set()

        future.add_done_callback(callback)
        original_set_result(future, value)

    monkeypatch.setattr(Future, "set_result", patched_set_result)
    assert registry.run("SYNTHETIC-CALLBACK-KEY", lambda: "SYNTHETIC-RESULT") == "SYNTHETIC-RESULT"
    assert callback_finished.wait(timeout=1)
    assert not callback_blocked.is_set()


def test_future_exception_callback_reenters_and_completing_entry_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ReportParseInFlightRegistry(max_entries=2)
    callback_finished = Event()
    original_set_exception = Future.set_exception

    def patched_set_exception(future: Future[object], error: BaseException) -> None:
        def callback(_: Future[object]) -> None:
            _ = registry.active_count
            with pytest.raises(RuntimeError):
                registry.run("SYNTHETIC-EXCEPTION-KEY", lambda: "unused")
            registry.run("SYNTHETIC-OTHER-KEY", lambda: "SYNTHETIC-OTHER")
            callback_finished.set()

        future.add_done_callback(callback)
        original_set_exception(future, error)

    monkeypatch.setattr(Future, "set_exception", patched_set_exception)
    with pytest.raises(RuntimeError):
        registry.run("SYNTHETIC-EXCEPTION-KEY", lambda: (_ for _ in ()).throw(RuntimeError("SYNTHETIC-ERROR")))
    assert callback_finished.wait(timeout=1)
    assert registry.active_count == 0
    assert not registry._completing
