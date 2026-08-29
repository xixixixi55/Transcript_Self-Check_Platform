"""通过工作台证据边界发布已验证的暂存目录。"""

from __future__ import annotations

import os
import copy
import stat
from pathlib import Path
from typing import Any

from .archive_attempt_service import ArchiveAttemptService
from .archive_manifest_service import (
    ArchiveFileIdentity,
    archive_file_identities_match,
    capture_archive_file_identities,
    validate_published_manifest,
)
from ...repository.archive.archive_manifest_repository import ArchiveManifestRepository
from ...repository.archive.archive_publish_fence_repository import assert_publishable
from ...repository.archive.archive_publish_intent_repository import ArchivePublishIntentRepository
from ...repository.workbench_errors import WorkbenchPersistenceError
from .archive_publication_identity_service import publication_digest


def publish_staged_archive(
    staging_dir: Path, final_dir: Path, record: Any, report: dict[str, Any],
    *, context: Any, attempt_id: str | None, attempt_service: ArchiveAttemptService | None,
    workbench_context_id: str | None,
    expected_draft_revision: int | None = None,
    expected_report_fingerprint: str | None = None,
    verified_md5s: dict[str, str] | None = None,
) -> dict[str, ArchiveFileIdentity] | None:
    verified_file_identities: dict[str, ArchiveFileIdentity] | None = None

    def validate(candidate: Any) -> bool:
        if verified_md5s is None:
            return validate_published_manifest(candidate)
        if not validate_published_manifest(candidate, verified_md5s=verified_md5s):
            return False
        return (
            verified_file_identities is None
            or archive_file_identities_match(
                Path(candidate.final_dir), verified_file_identities,
            )
        )

    if attempt_id is not None and attempt_service is not None:
        attempt_service.persist_publish_intent(
            attempt_id,
            source_key=context.source_key,
            input_fingerprint=context.input_fingerprint,
            archive_fingerprint=record.fingerprint,
            manifest_id=record.manifest_id,
            final_dir=final_dir,
            public_manifest=record.public_manifest,
            context_id=workbench_context_id or context.context_id,
            target_context_id=context.context_id,
            expected_draft_revision=expected_draft_revision,
            expected_report_fingerprint=expected_report_fingerprint,
        )
        # 持久围栏由 persist_publish_intent 在最终服务器事实验证的同一事务中建立。
        # 再进行一次普通读取无法关闭 TOCTOU 窗口。
        assert_publishable(attempt_service.database, attempt_id)
        if final_dir.exists():
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_CONFLICT")
        staging_record = copy.copy(record)
        staging_record.final_dir = staging_dir
        if not validate(staging_record):
            raise WorkbenchPersistenceError("ARCHIVE_PARTS_INVALID")
        intent = ArchivePublishIntentRepository(attempt_service.database).get_for_attempt(attempt_id)
        if intent is None:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
        digest, file_set = publication_digest(intent, record.public_manifest)
        record.publication_id = intent["publication_id"]
        record.publication_digest = digest
        ArchivePublishIntentRepository(attempt_service.database).seal_publication(
            attempt_id, digest, file_set,
        )
        _seal_publication_directory(staging_dir)
    if verified_md5s is not None:
        try:
            verified_file_identities = capture_archive_file_identities(
                staging_dir, set(verified_md5s),
            )
        except (OSError, ValueError) as error:
            raise WorkbenchPersistenceError("ARCHIVE_PARTS_INVALID") from error
    registry = ArchiveManifestRepository(
        attempt_service.output_root if attempt_service is not None else final_dir.parents[2],
        database=attempt_service.database if attempt_service is not None else None,
    )
    if attempt_service is not None:
        try:
            staging_dir.resolve(strict=False).relative_to(
                attempt_service.staging_root.resolve(strict=False),
            )
        except ValueError as error:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_STAGING_INVALID") from error
    registry.atomic_publish_generation(staging_dir, final_dir)
    if not validate(record):
        raise ValueError("ARCHIVE_PARTS_INVALID")
    if attempt_id is not None and attempt_service is not None:
        attempt_service.remove_marker(final_dir)
        ArchivePublishIntentRepository(attempt_service.database).mark_publication_state(
            attempt_id, "published",
        )
        attempt_service.mark_publish_phase(attempt_id, "published")
    if not validate(record):
        raise ValueError("ARCHIVE_PARTS_INVALID")
    return verified_file_identities


def _seal_publication_directory(root: Path) -> None:
    """移动前使密封代次对普通写入者不可变。"""
    try:
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_file():
                path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            elif path.is_dir():
                path.chmod(
                    stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
                    | stat.S_IROTH | stat.S_IXOTH,
                )
        root.chmod(
            stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IXOTH,
        )
    except OSError as error:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_SEAL_FAILED") from error
