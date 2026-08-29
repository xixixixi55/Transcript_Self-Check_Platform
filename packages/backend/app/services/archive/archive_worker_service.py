"""基于现有正式执行链的持久归档工作进程。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ...repository.archive_manifest_index_repository import (
    ArchiveManifestRepositoryError,
)
from ...repository.archive_task_repository import ArchiveTaskRepository
from ...repository.workbench_database import utc_now
from ...repository.workbench_errors import WorkbenchPersistenceError
from .archive_attempt_service import ArchiveAttemptService
from .archive_execution_service import ArchiveGateError, execute_archive
from .archive_planner_service import safe_archive_base_name
from .archive_progress_service import ArchiveProgressService
from .archive_scheduler_service import ArchiveTaskClaim


@dataclass(frozen=True)
class ArchiveWorkItem:
    formal_context_id: str
    report: dict[str, Any]
    output_root: str
    attempt_service: ArchiveAttemptService
    workbench_context_id: str | None = None
    configured_winrar_path: str | None = None


class ArchiveWorkerService:
    def __init__(
        self,
        tasks: ArchiveTaskRepository,
        progress: ArchiveProgressService,
    ) -> None:
        self.tasks = tasks
        self.progress = progress

    def run(
        self,
        claim: ArchiveTaskClaim,
        item: ArchiveWorkItem,
        *,
        interruption_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        self._assert_claim(claim)
        attempt = item.attempt_service.repository.get_internal(claim.attempt_id)
        if self.progress.cancellation_requested(
            claim.task_id, claim.owner_token,
        ):
            return self._finish_cancelled(claim, item.attempt_service)
        if attempt["status"] == "accepted":
            item.attempt_service.start(claim.attempt_id)
        elif attempt["status"] != "running":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        base_name = safe_archive_base_name(str(
            (item.report.get("introduction") or {}).get("case_summary") or ""
        ))
        try:
            outcome = execute_archive(
                item.formal_context_id,
                item.report,
                output_root=item.output_root,
                configured_winrar_path=item.configured_winrar_path,
                attempt_id=claim.attempt_id,
                attempt_service=item.attempt_service,
                workbench_context_id=item.workbench_context_id,
                stage_observer=lambda stage: self.progress.advance(
                    claim.task_id, claim.owner_token, stage,
                ),
                activity_observer=lambda root: self._record_activity(
                    claim, root, base_name,
                ),
                cancellation_check=lambda: self.progress.cancellation_requested(
                    claim.task_id, claim.owner_token,
                ) or bool(interruption_check and interruption_check()),
            )
        except Exception as error:
            if interruption_check and interruption_check():
                return self._finish_interrupted(claim, item.attempt_service)
            return self._finish_error(claim, item.attempt_service, error)
        if interruption_check and interruption_check():
            attempt_state = item.attempt_service.repository.get_internal(
                claim.attempt_id,
            )
            if attempt_state["status"] != "succeeded":
                return self._finish_interrupted(claim, item.attempt_service)
        if self.progress.cancellation_requested(claim.task_id, claim.owner_token):
            attempt_state = item.attempt_service.repository.get_internal(
                claim.attempt_id,
            )
            if attempt_state["status"] == "succeeded":
                return self._complete_succeeded(claim)
            return self.progress.cancel(claim.task_id, claim.owner_token)
        if outcome.reused:
            return self._complete_reused(claim)
        current = self.tasks.get(claim.task_id)
        if current["status"] == "succeeded":
            return current
        return self.progress.complete(claim.task_id, claim.owner_token)

    def _finish_interrupted(
        self,
        claim: ArchiveTaskClaim,
        attempt_service: ArchiveAttemptService,
    ) -> dict[str, Any]:
        from ...repository.archive_attempt_restart_repository import interrupt_owned_claim

        try:
            result = interrupt_owned_claim(
                attempt_service.database,
                task_id=claim.task_id,
                owner_token=claim.owner_token,
                attempt_id=claim.attempt_id,
                task_revision=claim.revision,
            )
        except WorkbenchPersistenceError as error:
            raise WorkbenchPersistenceError(
                "ARCHIVE_RUNTIME_INTERRUPTION_UNRESOLVED",
            ) from error
        if result in {"ownership_lost", "unresolved"}:
            raise WorkbenchPersistenceError(
                "ARCHIVE_RUNTIME_INTERRUPTION_UNRESOLVED",
            )
        return self.tasks.get(claim.task_id)

    def _complete_succeeded(self, claim: ArchiveTaskClaim) -> dict[str, Any]:
        current = self.tasks.get(claim.task_id)
        if current["status"] == "succeeded":
            return current
        if not self.tasks.is_owned_by(claim.task_id, claim.owner_token):
            raise WorkbenchPersistenceError("ARCHIVE_TASK_OWNERSHIP_LOST")
        return self.tasks.update_state(claim.task_id, {
            "status": "succeeded", "stage": "completed",
            "worker_state": "released", "cancel_requested": False,
        }, current["revision"])

    def recover_after_restart(
        self, attempt_service: ArchiveAttemptService,
    ) -> list[dict[str, Any]]:
        attempt_service.recover_after_restart()
        results = []
        for task in self.tasks.list_inflight():
            attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
            succeeded = False
            if attempt_id:
                try:
                    succeeded = (
                        attempt_service.repository.get_internal(attempt_id)["status"]
                        == "succeeded"
                    )
                except WorkbenchPersistenceError:
                    pass
            if succeeded and task["status"] in {"running", "cancelling"}:
                results.append(self.tasks.update_state(task["task_id"], {
                    "status": "succeeded", "stage": "completed",
                    "worker_state": "released",
                }, task["revision"]))
            elif task["status"] == "cancelling":
                results.append(self.tasks.update_state(task["task_id"], {
                    "status": "cancelled", "cancel_requested": True,
                    "worker_state": "released",
                }, task["revision"]))
            else:
                results.append(self.tasks.update_state(task["task_id"], {
                    "status": "interrupted", "worker_state": "waiting_reclaim",
                    "error_code": "ARCHIVE_WAITING_RECLAIM",
                    "error_summary": "Archive task is waiting for safe reclaim.",
                }, task["revision"]))
        return results

    def _record_activity(
        self, claim: ArchiveTaskClaim, root: Path, base_name: str,
    ) -> None:
        pattern = re.compile(
            rf"^{re.escape(base_name)}(?:\.part[1-9][0-9]*)?\.rar$"
        )
        outputs = [
            path for path in root.iterdir()
            if path.is_file() and pattern.fullmatch(path.name)
        ]
        total = 0
        for path in outputs:
            try:
                total += path.stat().st_size
            except OSError:
                continue
        self.progress.activity(claim.task_id, claim.owner_token, {
            "observed_at": utc_now(),
            "output_bytes": total if outputs else None,
            "output_volume_count": len(outputs) if outputs else None,
        })

    def _finish_error(
        self,
        claim: ArchiveTaskClaim,
        attempt_service: ArchiveAttemptService,
        error: Exception,
    ) -> dict[str, Any]:
        if self.progress.cancellation_requested(claim.task_id, claim.owner_token):
            return self._finish_cancelled(claim, attempt_service)
        code, summary = _safe_failure(error)
        try:
            attempt_service.fail(claim.attempt_id, code)
        except WorkbenchPersistenceError:
            pass
        return self.progress.fail(
            claim.task_id, claim.owner_token,
            error_code=code, error_summary=summary,
            retryable=code != "ARCHIVE_INPUT_CHANGED",
        )

    def _finish_cancelled(
        self,
        claim: ArchiveTaskClaim,
        attempt_service: ArchiveAttemptService,
    ) -> dict[str, Any]:
        attempt = attempt_service.repository.get_internal(claim.attempt_id)
        if attempt["status"] == "succeeded":
            return self._complete_succeeded(claim)
        if attempt["status"] in {"accepted", "running"}:
            try:
                attempt_service.fail(claim.attempt_id, "ARCHIVE_CANCELLED")
            except WorkbenchPersistenceError:
                pass
        return self.progress.cancel(claim.task_id, claim.owner_token)

    def _complete_reused(self, claim: ArchiveTaskClaim) -> dict[str, Any]:
        current = self.tasks.get(claim.task_id)
        if current["status"] == "succeeded":
            return current
        if not self.tasks.is_owned_by(claim.task_id, claim.owner_token):
            raise WorkbenchPersistenceError("ARCHIVE_TASK_OWNERSHIP_LOST")
        return self.tasks.update_state(claim.task_id, {
            "status": "succeeded", "stage": "completed",
            "worker_state": "released",
        }, current["revision"])

    def _assert_claim(self, claim: ArchiveTaskClaim) -> None:
        task = self.tasks.get(claim.task_id)
        binding = task.get("process_binding") or {}
        if (
            task["status"] not in {"running", "cancelling"}
            or binding.get("process_tree_id") != claim.owner_token
            or binding.get("staging_asset_id") != claim.attempt_id
        ):
            raise WorkbenchPersistenceError("ARCHIVE_TASK_OWNERSHIP_LOST")


def _safe_failure(error: Exception) -> tuple[str, str]:
    if isinstance(error, ArchiveGateError) and error.blockers:
        blocker = error.blockers[0]
        raw_code = blocker.code.value if hasattr(blocker.code, "value") else blocker.code
        return str(raw_code), str(blocker.message)
    if isinstance(error, ArchiveManifestRepositoryError):
        code = str(error)
        if code == "ARCHIVE_INDEX_UNTRUSTED":
            return code, (
                "归档目录包含当前案件库无法确认的历史 RAR。请在归档存储设置中选择 "
                "D 盘上的新空白目录，重启文枢后重试；现有文件不会被修改。"
            )
        if code.startswith("ARCHIVE_INDEX_"):
            return code, "归档目录登记无法安全确认，请更换新的空白归档目录并重启后重试。"
        return "ARCHIVE_INDEX_INVALID", "归档目录登记无法安全确认，请更换新的空白归档目录并重启后重试。"
    code = getattr(error, "code", "ARCHIVE_EXECUTION_FAILED")
    return str(code), "Archive execution failed safely."
