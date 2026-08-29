"""删除明确确认案件的平台自有文件。"""

from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...repository.archive.archive_manifest_repository import ArchiveManifestRepository
from ...repository.workbench.workbench_database import WorkbenchDatabase
from ...repository.workbench.workbench_errors import WorkbenchPersistenceError
from ...repository.workbench.workbench_serialization import validate_opaque_id
from ..archive.archive_input_snapshot_files_service import marker_path
from ..archive.archive_input_snapshot_layout_service import private_snapshot_root

_INDEX_NAMES = {".archive-manifest-index.json", ".archive-manifest-index.lock"}


@dataclass(frozen=True)
class CaseArtifactDeletionPlan:
    case_id: str
    attempt_ids: frozenset[str]
    relative_final_dirs: frozenset[str]
    paths: tuple[Path, ...]
    asset_directory: Path


class CaseArtifactDeletionService:
    """删除前仅解析持久的平台自有工件位置。"""

    def __init__(
        self,
        database: WorkbenchDatabase,
        output_root: str | Path,
        *,
        archive_output_roots: tuple[str | Path, ...] = (),
    ) -> None:
        self.database = database
        self.output_root = Path(output_root).resolve(strict=False)
        configured_roots = archive_output_roots or (self.output_root,)
        self.archive_output_roots = tuple(dict.fromkeys(
            Path(root).resolve(strict=False) for root in configured_roots
        ))
        self.compressed_roots = tuple(
            (root / "compressed").resolve(strict=False)
            for root in self.archive_output_roots
        )
        self.compressed_root = self.compressed_roots[0]
        self.staging_root = (self.compressed_root / ".staging").resolve(strict=False)
        self.snapshot_root = (self.compressed_root / ".inputs").resolve(strict=False)
        self.short_snapshot_root = (self.output_root / ".i").resolve(strict=False)
        self.external_snapshot_root = private_snapshot_root().resolve(strict=False)
        self.exports_root = (self.output_root / "exports").resolve(strict=False)
        self.assets_root = (database.database_path.parent / "assets").resolve(strict=False)

    def prepare(self, case_id: str) -> CaseArtifactDeletionPlan:
        case_id = validate_opaque_id(case_id)
        with self.database.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM case_shells WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchone() is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            attempts = connection.execute(
                "SELECT attempt_id,staging_locator,input_snapshot_locator FROM archive_attempts "
                "WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchall()
            snapshots = connection.execute(
                "SELECT snapshot_locator FROM archive_input_snapshots "
                "WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchall()
            snapshot_locators = {
                str(row["input_snapshot_locator"])
                for row in attempts
                if row["input_snapshot_locator"]
            } | {
                str(row["snapshot_locator"])
                for row in snapshots
                if row["snapshot_locator"]
            }
            shared_snapshot_locators: set[str] = set()
            if snapshot_locators:
                placeholders = ",".join("?" for _ in snapshot_locators)
                shared_snapshot_locators.update(
                    str(row[0]) for row in connection.execute(
                        "SELECT DISTINCT input_snapshot_locator FROM archive_attempts "
                        "WHERE case_id<>? AND deployment_instance_id=? AND input_snapshot_locator IN ("
                        + placeholders + ")",
                        (case_id, self.database.deployment_instance_id, *snapshot_locators),
                    ).fetchall() if row[0]
                )
                shared_snapshot_locators.update(
                    str(row[0]) for row in connection.execute(
                        "SELECT DISTINCT snapshot_locator FROM archive_input_snapshots "
                        "WHERE case_id<>? AND deployment_instance_id=? AND snapshot_locator IN ("
                        + placeholders + ")",
                        (case_id, self.database.deployment_instance_id, *snapshot_locators),
                    ).fetchall() if row[0]
                )
            intents = connection.execute(
                "SELECT attempt_id,relative_final_dir,publication_relative_dir FROM archive_publish_intents "
                "WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchall()
            words = connection.execute(
                "SELECT internal_relative_path FROM formal_word_artifacts "
                "WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchall()
            archive_assets = connection.execute(
                "SELECT internal_locator FROM archive_assets WHERE case_id=?",
                (case_id,),
            ).fetchall()
            final_dirs = {
                str(value)
                for row in intents
                for value in (row["relative_final_dir"], row["publication_relative_dir"])
                if value
            }
            shared_dirs = {
                str(value) for row in connection.execute(
                    "SELECT relative_final_dir,publication_relative_dir FROM archive_publish_intents "
                    "WHERE case_id<>? AND (relative_final_dir IN ("
                    + ",".join("?" for _ in final_dirs) + ") OR publication_relative_dir IN ("
                    + ",".join("?" for _ in final_dirs) + "))",
                    (case_id, *final_dirs, *final_dirs),
                ).fetchall() for value in row if value in final_dirs
            } if final_dirs else set()
            asset_locators = {str(row[0]) for row in archive_assets if row[0]}
            shared_asset_locators = {
                str(row[0]) for row in connection.execute(
                    "SELECT DISTINCT internal_locator FROM archive_assets WHERE case_id<>? "
                    "AND internal_locator IN (" + ",".join("?" for _ in asset_locators) + ")",
                    (case_id, *asset_locators),
                ).fetchall()
            } if asset_locators else set()
            word_paths = {str(row[0]) for row in words if row[0]}
            shared_words = {
                str(row[0]) for row in connection.execute(
                    "SELECT DISTINCT internal_relative_path FROM formal_word_artifacts "
                    "WHERE case_id<>? AND internal_relative_path IN ("
                    + ",".join("?" for _ in word_paths) + ")",
                    (case_id, *word_paths),
                ).fetchall()
            } if word_paths else set()

        owned_dirs = final_dirs - shared_dirs
        paths = [
            self._controlled_path(root, value, reject_names=_INDEX_NAMES | {".staging", ".inputs"})
            for root in self.compressed_roots
            for value in owned_dirs
        ]
        paths.extend(
            path
            for row in attempts if row["staging_locator"]
            for path in self._controlled_staging_paths(row["staging_locator"])
        )
        paths.extend(
            path
            for locator in (
                [row["input_snapshot_locator"] for row in attempts if row["input_snapshot_locator"]]
                + [row["snapshot_locator"] for row in snapshots if row["snapshot_locator"]]
            )
            if locator not in shared_snapshot_locators
            for path in self._snapshot_paths(locator)
        )
        paths.extend(
            path
            for row in archive_assets
            if row["internal_locator"] and str(row["internal_locator"]) not in shared_asset_locators
            for path in self._controlled_archive_paths(row["internal_locator"])
        )
        paths.extend(
            self._controlled_path(self.exports_root, value)
            for value in word_paths - shared_words
        )
        return CaseArtifactDeletionPlan(
            case_id=case_id,
            attempt_ids=frozenset(str(row["attempt_id"]) for row in attempts),
            relative_final_dirs=frozenset(owned_dirs),
            paths=_unique_paths(paths),
            asset_directory=self._controlled_path(self.assets_root, case_id),
        )

    def cleanup(self, plan: CaseArtifactDeletionPlan) -> None:
        try:
            for path in sorted(plan.paths, key=lambda value: len(value.parts), reverse=True):
                _remove_path(path)
            for relative_dir in sorted(plan.relative_final_dirs, key=_path_depth, reverse=True):
                self._remove_empty_archive_parents(relative_dir)
            _remove_path(plan.asset_directory)
        except OSError as error:
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED") from error

    def _remove_empty_archive_parents(self, relative_dir: str) -> None:
        for compressed_root in self.compressed_roots:
            archive_dir = self._controlled_path(
                compressed_root, relative_dir,
                reject_names=_INDEX_NAMES | {".staging", ".inputs"},
            )
            parent = archive_dir.parent
            while parent != compressed_root:
                if parent.is_symlink():
                    break
                if not _remove_empty_directory(parent):
                    break
                parent = parent.parent

    def remove_manifest_index(self, plan: CaseArtifactDeletionPlan) -> None:
        try:
            for output_root in self.archive_output_roots:
                ArchiveManifestRepository(output_root).remove_for_case(
                    attempt_ids=set(plan.attempt_ids),
                    relative_final_dirs=set(plan.relative_final_dirs),
                )
        except (OSError, RuntimeError, ValueError) as error:
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED") from error

    def _controlled_path(
        self, root: Path, value: Any, *, reject_names: set[str] | None = None,
    ) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve(strict=False)
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED") from error
        if not relative.parts or (reject_names and any(part in reject_names for part in relative.parts)):
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        return candidate.absolute() if candidate.is_symlink() else resolved

    def _snapshot_paths(self, locator: Any) -> tuple[Path, ...]:
        paths = []
        for snapshot in self._snapshot_path_candidates(locator):
            temporary = snapshot.parent / f".{snapshot.name}.copying"
            paths.extend((snapshot, temporary, marker_path(snapshot)))
        return tuple(paths)

    def _snapshot_path_candidates(self, locator: Any) -> tuple[Path, ...]:
        if not isinstance(locator, str) or not locator.strip():
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        normalized = locator.replace("\\", "/")
        roots = tuple(
            (".inputs/", compressed_root / ".inputs")
            for compressed_root in self.compressed_roots
        ) + tuple(
            (".i/", output_root / ".i")
            for output_root in self.archive_output_roots
        ) + ((".t/", self.external_snapshot_root),)
        if not Path(locator).is_absolute():
            candidates = tuple(
                self._controlled_path(root, normalized.removeprefix(prefix))
                for prefix, root in roots
                if normalized.startswith(prefix)
            )
            if candidates:
                return _unique_paths(list(candidates))
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        candidates = []
        for _prefix, root in roots:
            try:
                candidates.append(self._controlled_path(root, locator))
            except WorkbenchPersistenceError:
                continue
        if not candidates:
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        return _unique_paths(candidates)

    def _controlled_archive_paths(self, locator: Any) -> tuple[Path, ...]:
        candidates = []
        for output_root in self.archive_output_roots:
            try:
                candidates.append(self._controlled_path(output_root, locator))
            except WorkbenchPersistenceError:
                continue
        if not candidates:
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        return _unique_paths(candidates)

    def _controlled_staging_paths(self, locator: Any) -> tuple[Path, ...]:
        candidates = []
        for compressed_root in self.compressed_roots:
            try:
                candidates.append(self._controlled_path(compressed_root / ".staging", locator))
            except WorkbenchPersistenceError:
                continue
        if not candidates:
            raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        return _unique_paths(candidates)


def _unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path)] = path
    return tuple(unique.values())


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path, onerror=_remove_readonly)
    else:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        path.unlink()


def _remove_empty_directory(path: Path) -> bool:
    """仅移除空目录；仍有所有者时返回 false。"""
    if not path.exists():
        return True
    if path.is_symlink() or not path.is_dir():
        return False
    try:
        path.rmdir()
    except OSError:
        try:
            next(path.iterdir())
        except StopIteration:
            raise
        except FileNotFoundError:
            return True
        return False
    return True


def _path_depth(value: str) -> int:
    return len(Path(value).parts)


def _remove_readonly(function: Any, path: str, _error: Any) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    function(path)
