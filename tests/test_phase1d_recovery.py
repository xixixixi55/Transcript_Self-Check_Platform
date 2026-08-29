"""使用合成记录的 Phase 1D 恢复与归档所有权测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Event

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    CaseShellRepository,
    CaseDraftRepository,
    EditLeaseRepository,
    SourceRecordRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.case.case_workflow_repository import CaseWorkflowRepository  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive.archive_attempt_service import ArchiveAttemptService  # noqa: E402
from app.services.archive.archive_staging_security_service import cleanup_owned_staging  # noqa: E402
from app.services.case_parse_dispatcher_service import CaseParseDispatcher  # noqa: E402

from test_workbench_persistence import IDENTITY, REPORT  # noqa: E402


CASE_ID = "SYNTHETIC-1D-CASE-001"
SOURCE_ID = "SYNTHETIC-1D-SOURCE-001"
TASK_ID = "SYNTHETIC-1D-TASK-001"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-1D-DEPLOYMENT"),
        "SYNTHETIC-1D-DEPLOYMENT",
    )


def ready_case(database: WorkbenchDatabase) -> dict:
    workflow = CaseWorkflowRepository(database)
    workflow.create_submission(
        {
            "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/Case",
            "case_summary": "SYNTHETIC/TEST/Recovery",
            "source_id": SOURCE_ID, "parse_task_id": TASK_ID,
        },
        {"task_id": TASK_ID, "case_id": CASE_ID},
        {
            "source_id": SOURCE_ID, "case_id": CASE_ID, "task_id": TASK_ID,
            "source_type": "report_directory", "internal_path": "locator://SYNTHETIC-1D",
            "allowed_root": "root://SYNTHETIC-1D", "allowed_root_id": "SYNTHETIC-1D-ROOT",
            "metadata": {}, "fingerprint": "pending:SYNTHETIC-1D", "access_status": "pending",
        },
        IDENTITY,
    )
    workflow.start_parse(CASE_ID, TASK_ID)
    workflow.complete_parse(CASE_ID, TASK_ID, REPORT, {})
    return CaseShellRepository(database).get(CASE_ID)


def mark_source_available(database: WorkbenchDatabase) -> None:
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET access_status = 'available', fingerprint_json = ?, revalidation_error_code = NULL WHERE source_id = ?",
            (json.dumps({"value": "SYNTHETIC-1D-VERIFIED"}), SOURCE_ID),
        )


def _start_owned_process() -> subprocess.Popen[bytes]:
    flags = 0
    start_new_session = os.name != "nt"
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=flags,
        start_new_session=start_new_session,
    )


def _stop_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None and process.stdin is not None:
        process.stdin.close()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_unfinished_archive_attempt_restarts_once_and_keeps_draft_editable(database, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    accepted = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-001", shell["revision"])
    assert service.context_matches(accepted["attempt_id"], "SYNTHETIC-CONTEXT-001")
    assert accepted["status"] == "accepted"
    recovered = service.recover_after_restart()
    assert recovered == [accepted["attempt_id"]]
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "archive_interrupted"
    assert CaseDraftRepository(database).get(CASE_ID)["lifecycle"] == "archive_interrupted"
    assert service.recover_after_restart() == []
    assert not service.context_matches(accepted["attempt_id"], "SYNTHETIC-CONTEXT-001")
    assert service.repository.get_public(accepted["attempt_id"])["status"] == "interrupted"
    assert service.repository.get_public(accepted["attempt_id"])["error_code"] == "ARCHIVE_RESTART_PENDING_VERIFICATION"


def test_archive_interrupted_allows_deferred_or_new_attempt_only(database: WorkbenchDatabase, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    old = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-002", shell["revision"])
    service.recover_after_restart()
    deferred_shell = CaseWorkflowRepository(database)
    deferred_shell.decide_archive(CASE_ID, "deferred", CaseShellRepository(database).get(CASE_ID)["revision"])
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "archive_deferred"
    next_shell = CaseShellRepository(database).get(CASE_ID)
    new = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-003", next_shell["revision"])
    assert new["attempt_id"] != old["attempt_id"]
    assert service.context_matches(new["attempt_id"], "SYNTHETIC-CONTEXT-003")
    assert not service.context_matches(new["attempt_id"], "SYNTHETIC-CONTEXT-002")
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "archive_queued"
    with pytest.raises(WorkbenchPersistenceError):
        service.repository.mark_succeeded(old["attempt_id"], "SYNTHETIC-MANIFEST-OLD")


def test_refresh_reissues_context_without_creating_a_second_queued_attempt(database: WorkbenchDatabase, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    old = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-REFRESH-1", shell["revision"])
    refreshed = service.reissue_context(
        CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-REFRESH-2",
        CaseShellRepository(database).get(CASE_ID)["revision"],
    )
    assert refreshed["attempt_id"] == old["attempt_id"]
    assert service.context_matches(refreshed["attempt_id"], "SYNTHETIC-CONTEXT-REFRESH-2")
    assert len(service.repository.list_public(CASE_ID)) == 1


def test_succeeded_archive_attempt_is_not_recovered_or_rolled_back(database: WorkbenchDatabase, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-004", shell["revision"])
    service.start(attempt["attempt_id"])
    with pytest.raises(WorkbenchPersistenceError) as error:
        service.succeed(attempt["attempt_id"], "SYNTHETIC-MANIFEST-004")
    assert error.value.code == "ARCHIVE_COMPLETION_EVIDENCE_REQUIRED"
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"
    assert service.recover_after_restart() == [attempt["attempt_id"]]
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "interrupted"


def test_owned_staging_cleans_only_with_marker_and_record_match(database: WorkbenchDatabase, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-005", shell["revision"])
    staging = service.staging_root / "archive-owned-synthetic"
    staging.mkdir(parents=True)
    service.staging_initializer(attempt["attempt_id"])(staging)
    formal = service.staging_root.parent / "SYNTHETIC-FORMAL" / "SYNTHETIC-TEST.rar"
    formal.parent.mkdir(parents=True)
    formal.write_bytes(b"SYNTHETIC/TEST/FORMAL")
    service.recover_after_restart()
    assert not staging.exists()
    assert service.repository.get_public(attempt["attempt_id"])["cleanup_status"] == "succeeded"
    assert cleanup_owned_staging(
        service.repository.get_internal(attempt["attempt_id"]),
        service.staging_root, database.deployment_instance_id,
    ) == "succeeded"
    assert formal.exists()


def test_mismatched_marker_is_unknown_and_formal_records_are_untouched(database: WorkbenchDatabase, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-006", shell["revision"])
    staging = service.staging_root / "archive-unknown-synthetic"
    staging.mkdir(parents=True)
    service.staging_initializer(attempt["attempt_id"])(staging)
    marker = staging / ".workbench-staging-owner.json"
    marker.write_text(marker.read_text(encoding="utf-8").replace(attempt["attempt_id"], "SYNTHETIC-OTHER"), encoding="utf-8")
    service.recover_after_restart()
    assert staging.exists()
    assert service.repository.get_public(attempt["attempt_id"])["cleanup_status"] == "unknown"


def test_active_unknown_process_is_never_terminated_or_cleaned(database: WorkbenchDatabase, tmp_path: Path) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT")
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, "SYNTHETIC-CONTEXT-007", shell["revision"])
    staging = service.staging_root / "archive-active-synthetic"
    staging.mkdir(parents=True)
    service.staging_initializer(attempt["attempt_id"])(staging)
    service.start(attempt["attempt_id"])
    sentinel = _start_owned_process()
    try:
        assert sentinel.poll() is None
        service.repository.bind_process(attempt["attempt_id"], sentinel.pid, "SYNTHETIC-STARTED-AT")
        service.recover_after_restart()
        assert staging.exists()
        assert service.repository.get_public(attempt["attempt_id"])["cleanup_status"] == "unknown"
    finally:
        _stop_owned_process(sentinel)
    assert sentinel.poll() is not None


def test_restart_expires_old_lease_and_allows_new_session(database: WorkbenchDatabase) -> None:
    ready_case(database)
    repository = EditLeaseRepository(database)
    identity = {**IDENTITY, "deployment_instance_id": database.deployment_instance_id}
    old = repository.acquire(
        case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-OLD", lease_token="SYNTHETIC-TOKEN-OLD",
        identity=identity,
    )
    assert repository.expire_active_after_restart() == [old["lease_id"]]
    assert repository.get(old["lease_id"])["status"] == "expired"
    new_identity = {**identity, "session_id": "SYNTHETIC-SESSION-NEW"}
    new = repository.acquire(
        case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-NEW", lease_token="SYNTHETIC-TOKEN-NEW",
        identity=new_identity,
    )
    assert new["status"] == "active"


def test_pending_source_is_rescheduled_and_dispatch_failure_stays_pending(database: WorkbenchDatabase) -> None:
    ready_case(database)
    service = __import__("app.services.source_record_service", fromlist=["SourceRecordService"]).SourceRecordService(database)

    class Dispatcher:
        def __init__(self, fail: bool = False) -> None:
            self.calls: list[tuple[str, int]] = []
            self.fail = fail

        def dispatch_source_verification(self, _sources: object, source_id: str, revision: int) -> None:
            if self.fail:
                raise RuntimeError("SYNTHETIC-DISPATCH-FAILURE")
            self.calls.append((source_id, revision))

    success = Dispatcher()
    assert service.recover_pending_after_startup(success) == [SOURCE_ID]
    assert success.calls == [(SOURCE_ID, 0)]
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET access_status = 'available', revalidation_error_code = NULL, revision = revision + 1 WHERE source_id = ?",
            (SOURCE_ID,),
        )
    assert service.recover_pending_after_startup(Dispatcher()) == []
    failed = Dispatcher(fail=True)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET access_status = 'pending', revision = revision + 1 WHERE source_id = ?",
            (SOURCE_ID,),
        )
    service.recover_pending_after_startup(failed)
    source = SourceRecordRepository(database).get(SOURCE_ID)
    assert source["access_status"] == "pending"
    assert source["revalidation_error_code"] == "SOURCE_REVALIDATION_PENDING"


def test_source_verification_transient_pending_is_retried_until_available() -> None:
    completed = Event()

    class Sources:
        def __init__(self) -> None:
            self.calls: list[int | None] = []

        def verify_after_parse(
            self, _source_id: str, expected_revision: int | None = None,
            cancellation_event=None,
        ) -> dict:
            self.calls.append(expected_revision)
            if len(self.calls) == 1:
                return {"access_status": "pending", "revision": 1}
            completed.set()
            return {"access_status": "available", "revision": 2}

        def mark_verification_pending(
            self, _source_id: str, _error_code: str, _expected_revision: int,
        ) -> dict:
            raise AssertionError("successful retry must not persist a worker failure")

    sources = Sources()
    dispatcher = CaseParseDispatcher(source_verification_retry_delay_seconds=0)
    dispatcher.dispatch_source_verification(sources, SOURCE_ID, 0)

    assert completed.wait(2)
    dispatcher.shutdown(wait=True)
    assert sources.calls == [0, 1]


def test_source_verification_worker_failure_is_bounded_and_diagnosed() -> None:
    exhausted = Event()

    class Sources:
        def __init__(self) -> None:
            self.verify_calls = 0
            self.revision = 0
            self.error_codes: list[str] = []

        def verify_after_parse(
            self, _source_id: str, expected_revision: int | None = None,
            cancellation_event=None,
        ) -> dict:
            self.verify_calls += 1
            raise RuntimeError(f"SYNTHETIC/TEST/WORKER/{expected_revision}")

        def get(self, _source_id: str) -> dict:
            return {"access_status": "pending", "revision": self.revision}

        def mark_verification_pending(
            self, _source_id: str, error_code: str, expected_revision: int,
        ) -> dict:
            assert expected_revision == self.revision
            self.revision += 1
            self.error_codes.append(error_code)
            if error_code == "SOURCE_REVALIDATION_RETRY_EXHAUSTED":
                exhausted.set()
            return {"access_status": "pending", "revision": self.revision}

    sources = Sources()
    dispatcher = CaseParseDispatcher(
        source_verification_max_attempts=3,
        source_verification_retry_delay_seconds=0,
    )
    dispatcher.dispatch_source_verification(sources, SOURCE_ID, 0)

    assert exhausted.wait(2)
    dispatcher.shutdown(wait=True)
    assert sources.verify_calls == 3
    assert sources.error_codes == [
        "SOURCE_REVALIDATION_WORKER_FAILED",
        "SOURCE_REVALIDATION_WORKER_FAILED",
        "SOURCE_REVALIDATION_WORKER_FAILED",
        "SOURCE_REVALIDATION_RETRY_EXHAUSTED",
    ]


def test_source_verification_does_not_block_the_parse_executor() -> None:
    verification_started = Event()
    release_verification = Event()
    parse_completed = Event()

    class Sources:
        def verify_after_parse(
            self, _source_id: str, expected_revision: int | None = None,
            cancellation_event=None,
        ) -> dict:
            verification_started.set()
            assert release_verification.wait(2)
            return {"access_status": "available", "revision": expected_revision or 0}

    class Tasks:
        @staticmethod
        def get(_task_id: str) -> dict:
            return {"status": "queued", "attempt": 0}

    class Cases:
        tasks = Tasks()

        @staticmethod
        def run_parse_task(_case_id: str, _task_id: str) -> None:
            parse_completed.set()

    dispatcher = CaseParseDispatcher(max_workers=1, source_verification_max_attempts=1)
    dispatcher.dispatch_source_verification(Sources(), SOURCE_ID, 0)
    assert verification_started.wait(2)
    dispatcher.dispatch(Cases(), CASE_ID, TASK_ID)

    assert parse_completed.wait(2)
    release_verification.set()
    dispatcher.shutdown(wait=True)


def test_dispatcher_shutdown_cancels_running_source_verification() -> None:
    verification_started = Event()
    verification_finished = Event()

    class Sources:
        @staticmethod
        def verify_after_parse(
            _source_id: str,
            expected_revision: int | None = None,
            cancellation_event=None,
        ) -> dict:
            verification_started.set()
            assert cancellation_event is not None
            assert cancellation_event.wait(2)
            verification_finished.set()
            return {"access_status": "pending", "revision": expected_revision or 0}

    dispatcher = CaseParseDispatcher()
    dispatcher.dispatch_source_verification(Sources(), SOURCE_ID, 0)
    assert verification_started.wait(2)

    dispatcher.shutdown(wait=True)

    assert verification_finished.is_set()


def test_stale_verification_diagnostic_cannot_revert_an_available_source(
    database: WorkbenchDatabase,
) -> None:
    ready_case(database)
    repository = SourceRecordRepository(database)
    stale_revision = repository.get(SOURCE_ID)["revision"]
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET access_status = 'available', revision = revision + 1 "
            "WHERE source_id = ?",
            (SOURCE_ID,),
        )

    with pytest.raises(WorkbenchPersistenceError) as error:
        repository.mark_pending_revalidation(
            SOURCE_ID,
            "SOURCE_REVALIDATION_RETRY_EXHAUSTED",
            expected_revision=stale_revision,
        )

    assert error.value.code == "SOURCE_REVISION_CONFLICT"
    assert repository.get(SOURCE_ID)["access_status"] == "available"


def test_temporary_source_failure_stays_pending_but_changed_fingerprint_requires_reselection(
    database: WorkbenchDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "SYNTHETIC-source.txt"
    path.write_text("SYNTHETIC/TEST/source", encoding="utf-8")
    ready_case(database)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET source_type = 'other', internal_path = ?, allowed_root = ?, metadata_json = ?, fingerprint_json = ?, access_status = 'available' WHERE source_id = ?",
            (str(path), str(tmp_path), json.dumps({}), json.dumps({"value": "SYNTHETIC-ORIGINAL"}), SOURCE_ID),
        )
    from app.services import source_record_service as source_module

    def unavailable(_path: Path, _should_cancel=None) -> str:
        raise PermissionError("SYNTHETIC-TEMPORARY")

    monkeypatch.setattr(source_module, "_fingerprint", unavailable)
    service = source_module.SourceRecordService(database)
    assert service.revalidate(SOURCE_ID)["access_status"] == "pending"
    monkeypatch.setattr(
        source_module, "_fingerprint", lambda _path, _should_cancel=None: "SYNTHETIC-CHANGED",
    )
    assert service.revalidate(SOURCE_ID)["access_status"] == "requires_reselection"


def test_shutdown_cancellation_preserves_the_current_source_state(
    database: WorkbenchDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "SYNTHETIC-source-cancelled.txt"
    path.write_text("SYNTHETIC/TEST/source", encoding="utf-8")
    ready_case(database)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE source_records SET source_type = 'other', internal_path = ?, "
            "allowed_root = ?, metadata_json = ?, fingerprint_json = ?, "
            "access_status = 'available' WHERE source_id = ?",
            (
                str(path), str(tmp_path), json.dumps({}),
                json.dumps({"value": "SYNTHETIC-ORIGINAL"}), SOURCE_ID,
            ),
        )
    from app.services import source_record_service as source_module
    from app.services.source_record_fingerprint_service import SourceFingerprintCancelledError

    def cancelled(_path: Path, _should_cancel=None) -> str:
        raise SourceFingerprintCancelledError("SYNTHETIC/TEST/CANCELLED")

    monkeypatch.setattr(source_module, "_fingerprint", cancelled)
    service = source_module.SourceRecordService(database)
    before = service.get(SOURCE_ID)

    result = service.revalidate(SOURCE_ID)

    assert result["access_status"] == "available"
    assert result["revision"] == before["revision"]
