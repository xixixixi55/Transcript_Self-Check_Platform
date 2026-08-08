"""Phase 1D archive-attempt boundary around the existing Legacy executor."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..repository.archive_attempt_repository import ArchiveAttemptRepository
from ..repository.archive_preparation_repository import ArchivePreparationRepository
from ..repository.archive_context_binding_repository import find_binding, report_fingerprint
from ..repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ..repository.source_record_repository import SourceRecordRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_staging_security_service import (
    controlled_staging_root_id,
    remove_ownership_marker,
    write_ownership_marker,
)
from .archive_input_snapshot_service import (
    SealedInputSnapshot, assert_sealed_input, cleanup_sealed_input_snapshot,
    create_sealed_input_snapshot, load_sealed_input_snapshot,
)
from ..repository.workbench_serialization import validate_opaque_id
from .archive_attempt_failure_service import fail_attempt
from .archive_attempt_marker_service import remove_owned_marker
from .archive_attempt_validation_service import expired as _expired
from .archive_attempt_validation_service import revalidate_before_publish as _revalidate_before_publish


class ArchiveAttemptService:
    def __init__(self, database: WorkbenchDatabase, output_root: str | Path) -> None:
        self.database = database
        self.output_root = Path(output_root)
        self.repository = ArchiveAttemptRepository(database)
        self.preparation = ArchivePreparationRepository(database)
        self.sources = SourceRecordRepository(database)
        self.staging_root = self.output_root / "compressed" / ".staging"
        self.staging_root_id = controlled_staging_root_id(
            self.staging_root, database.deployment_instance_id,
        )

    def accept(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int, task_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_archive_source(source_id)
        context_id = validate_opaque_id(context_id)
        draft = CaseDraftRepository(self.database).get(case_id)
        result = self.preparation.prepare(
            case_id, source_id, source_revision, context_id, expected_case_revision,
            int(draft["revision"]), report_fingerprint(draft["report"]),
            task_id=task_id,
        )
        if task_id is not None:
            bound = self.repository.get_internal(result["attempt_id"]).get("task_id")
            if bound != task_id:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        return result

    def start(self, attempt_id: str) -> dict[str, Any]:
        return self.repository.mark_running(attempt_id)

    def reissue_context(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int,
    ) -> dict[str, Any]:
        self._require_archive_source(source_id)
        context_id = validate_opaque_id(context_id)
        draft = CaseDraftRepository(self.database).get(case_id)
        return self.preparation.reissue(
            case_id, source_id, source_revision, context_id, expected_case_revision,
            int(draft["revision"]), report_fingerprint(draft["report"]),
        )

    def context_matches(self, attempt_id: str, context_id: str) -> bool:
        try:
            attempt_id = validate_opaque_id(attempt_id)
            context_id = validate_opaque_id(context_id)
        except WorkbenchPersistenceError:
            return False
        binding = find_binding(self.database, context_id)
        return bool(
            binding and binding["active"]
            and binding["context_kind"] == "workbench"
            and not _expired(binding.get("expires_at"))
            and binding["attempt_id"] == attempt_id
            and binding["attempt_status"] in {"accepted", "running"}
        )

    def context_binding(self, context_id: str) -> dict[str, Any] | None:
        return find_binding(self.database, context_id)

    def succeed(self, attempt_id: str, manifest_id: str) -> dict[str, Any]:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")

    def workbench_report(
        self, attempt_id: str, context_id: str, client_report: object | None = None,
    ) -> dict[str, Any]:
        binding = find_binding(self.database, context_id)
        if not binding or not binding["active"] or binding["context_kind"] != "workbench":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_CONTEXT_MISMATCH")
        if binding["attempt_id"] != validate_opaque_id(attempt_id) or _expired(binding.get("expires_at")):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_CONTEXT_MISMATCH")
        shell = CaseShellRepository(self.database).get(binding["case_id"])
        source = self.sources.get(binding["source_id"])
        draft = CaseDraftRepository(self.database).get(binding["case_id"])
        if (
            shell["source_id"] != binding["source_id"]
            or int(source["revision"]) != binding["source_revision"]
            or source["access_status"] != "available"
            or int(draft["revision"]) != binding["draft_revision"]
            or report_fingerprint(draft["report"]) != binding["report_fingerprint"]
            or shell["lifecycle"] not in {"archive_queued", "archiving"}
        ):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
        if client_report is not None and report_fingerprint(client_report) != binding["report_fingerprint"]:
            raise WorkbenchPersistenceError("ARCHIVE_REPORT_MISMATCH")
        return draft["report"]

    def persist_publish_intent(self, attempt_id: str, **kwargs: Any) -> dict[str, Any]:
        from .archive_attempt_completion_service import persist_publish_intent
        return persist_publish_intent(self, attempt_id, **kwargs)

    def revalidate_before_publish(self, attempt_id: str, report: object) -> Any:
        return _revalidate_before_publish(self, attempt_id, report)

    def mark_publish_phase(self, attempt_id: str, phase: str) -> dict[str, Any]:
        from .archive_attempt_completion_service import mark_publish_phase
        return mark_publish_phase(self, attempt_id, phase)

    def complete_verified(
        self, attempt_id: str, registry: Any, manifest_record: Any, *, recovery: bool = False,
    ) -> dict[str, Any]:
        from .archive_attempt_completion_service import complete_verified
        return complete_verified(self, attempt_id, registry, manifest_record, recovery=recovery)

    def fail(self, attempt_id: str, error_code: str) -> dict[str, Any]:
        return fail_attempt(self, attempt_id, error_code)

    def _cleanup_execution_input_best_effort(self, attempt_id: str) -> None:
        try:
            self.cleanup_execution_input(attempt_id)
        except Exception:
            # The durable snapshot row remains non-sealed/diagnosable for
            # recovery; never turn a failed archive into a false success.
            pass

    def staging_initializer(self, attempt_id: str) -> Callable[[Path], None]:
        root_id = self.staging_root_id
        deployment_id = self.database.deployment_instance_id
        task_id = self.repository.get_internal(attempt_id).get("task_id")

        def initialize(staging_dir: Path) -> None:
            token = write_ownership_marker(
                staging_dir, attempt_id, deployment_id, root_id, task_id,
            )
            try:
                self.repository.bind_staging(attempt_id, str(staging_dir), root_id, token)
            except Exception:
                remove_ownership_marker(staging_dir)
                raise

        return initialize

    def process_started_callback(self, attempt_id: str) -> Callable[[int], None]:
        return lambda pid: self.repository.bind_process(attempt_id, pid, utc_now())

    def seal_execution_input(self, attempt_id: str, inventory: Any) -> SealedInputSnapshot:
        return create_sealed_input_snapshot(
            self.database, self.output_root, self.repository.get_internal(attempt_id), inventory,
        )

    def load_execution_input(self, attempt_id: str) -> SealedInputSnapshot:
        return load_sealed_input_snapshot(self.database, self.output_root, attempt_id)

    @staticmethod
    def assert_execution_input(snapshot: SealedInputSnapshot) -> None:
        assert_sealed_input(snapshot)

    def cleanup_execution_input(self, attempt_id: str) -> str:
        return cleanup_sealed_input_snapshot(self.database, self.output_root, attempt_id)

    def remove_marker(self, staging_dir: Path, attempt_id: str | None = None) -> None:
        remove_owned_marker(self, staging_dir, attempt_id)

    def _publish_intent(self, attempt_id: str) -> dict[str, Any] | None:
        from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
        return ArchivePublishIntentRepository(self.database).get_for_attempt(attempt_id)

    def _attempt_for_final_dir(self, final_dir: Path) -> str | None:
        try:
            relative = final_dir.resolve(strict=False).relative_to(
                (self.output_root / "compressed").resolve(strict=False),
            ).as_posix()
        except ValueError:
            return None
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT attempt_id FROM archive_publish_intents WHERE relative_final_dir=? "
                "AND deployment_instance_id=? ORDER BY created_at DESC LIMIT 1",
                (relative, self.database.deployment_instance_id),
            ).fetchone()
        return None if row is None else str(row[0])

    def recover_after_restart(self) -> list[str]:
        from .archive_attempt_recovery_reconciliation_service import recover_after_restart
        return recover_after_restart(self)

    def _require_archive_source(self, source_id: str) -> None:
        status = self.sources.get(source_id)["access_status"]
        if status == "pending":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING")
        if status != "available":
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
