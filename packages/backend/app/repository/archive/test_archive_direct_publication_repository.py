"""SYNTHETIC/TEST：同卷无复制发布、排他冲突与崩溃续传。"""

import os
from types import SimpleNamespace

import pytest

from .archive_direct_publication_repository import ArchiveDirectPublicationRepository, file_identity
from ..workbench.workbench_errors import WorkbenchPersistenceError


@pytest.fixture
def publication(tmp_path):
    target = tmp_path / "SYNTHETIC-report-parent"
    staging = target / "archive-SYNTHETIC"
    staging.mkdir(parents=True)
    names = ["SYNTHETIC.part1.rar", "SYNTHETIC.part2.rar"]
    for name in names:
        (staging / name).write_bytes(b"SYNTHETIC/TEST")
    origin = tmp_path / "internal" / "SYNTHETIC-manifest"
    repo = ArchiveDirectPublicationRepository(SimpleNamespace(database_path=tmp_path / "db.sqlite3"))
    return repo, origin, staging, target, names


def test_publish_preserves_file_identity_without_copy(publication):
    repo, origin, staging, target, names = publication
    identities = {name: file_identity(staging / name) for name in names}
    repo.prepare(origin, staging, target, "SYNTHETIC-manifest", names)
    repo.publish(origin, target, "SYNTHETIC-manifest")
    assert all(file_identity(target / name) == identities[name] for name in names)
    assert not list(staging.glob("*.rar"))
    assert not list(origin.rglob("*.rar"))
    assert repo.resolve(origin, "SYNTHETIC-manifest") == target


def test_existing_target_is_never_overwritten(publication):
    repo, origin, staging, target, names = publication
    repo.prepare(origin, staging, target, "SYNTHETIC-manifest", names)
    (target / names[1]).write_bytes(b"SYNTHETIC unrelated")
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_PUBLISH_TARGET_CONFLICT"):
        repo.publish(origin, target, "SYNTHETIC-manifest")
    assert (target / names[1]).read_bytes() == b"SYNTHETIC unrelated"
    assert all((staging / name).exists() for name in names)
    assert not (target / names[0]).exists()


def test_resume_after_process_stops_between_renames(publication):
    repo, origin, staging, target, names = publication
    repo.prepare(origin, staging, target, "SYNTHETIC-manifest", names)
    os.rename(staging / names[0], target / names[0])
    repo.publish(origin, target, "SYNTHETIC-manifest")
    repo.publish(origin, target, "SYNTHETIC-manifest")
    assert all((target / name).read_bytes() == b"SYNTHETIC/TEST" for name in names)


def test_registration_failure_restores_staged_files(publication, monkeypatch):
    repo, origin, staging, target, names = publication
    repo.prepare(origin, staging, target, "SYNTHETIC-manifest", names)
    def fail(*args, **kwargs):
        raise OSError("SYNTHETIC disk failure")
    monkeypatch.setattr(repo.locations, "remember", fail)
    with pytest.raises(OSError):
        repo.publish(origin, target, "SYNTHETIC-manifest")
    assert all((staging / name).exists() for name in names)
    assert not list(target.glob("*.rar"))


def test_unfinished_publication_metadata_is_not_an_untrusted_rar(tmp_path):
    from .archive_manifest_repository import ArchiveManifestRepository
    from .archive_direct_publication_repository import JOURNAL_NAME
    origin = tmp_path / "compressed" / "SYNTHETIC-context" / "SYNTHETIC-manifest"
    origin.mkdir(parents=True)
    (origin / JOURNAL_NAME).write_text('{"SYNTHETIC": true}')
    registry = ArchiveManifestRepository(tmp_path)
    assert registry.find_by_manifest_id("SYNTHETIC-manifest") == []
    (origin / "SYNTHETIC.rar").write_bytes(b"SYNTHETIC/TEST")
    from .archive_manifest_index_repository import ArchiveManifestRepositoryError
    with pytest.raises(ArchiveManifestRepositoryError, match="ARCHIVE_INDEX_MISSING"):
        registry.find_by_manifest_id("SYNTHETIC-manifest")
