"""确定性的第二轮归档安全与故障注入证据。"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_input_repository import (  # noqa: E402
    ArchiveInputError, build_input_inventory,
)
from app.repository.archive.archive_input_snapshot_repository import (  # noqa: E402
    ArchiveInputSnapshotRepository,
)
from app.repository.case_workbench_repository import CaseDraftRepository  # noqa: E402
from app.repository.archive.archive_manifest_repository import (  # noqa: E402
    ArchiveManifestRepository, ArchiveManifestRepositoryError,
)
from app.repository.archive.archive_publish_intent_repository import (  # noqa: E402
    ArchivePublishIntentRepository,
)
from app.repository.archive.archive_task_repository import ArchiveTaskRepository  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive.archive_attempt_service import ArchiveAttemptService  # noqa: E402
from app.services.archive.archive_input_snapshot_service import (  # noqa: E402
    assert_sealed_input, cleanup_ephemeral_input_snapshot,
    create_ephemeral_sealed_input_snapshot,
)
from app.services.archive.archive_input_snapshot_files_service import (  # noqa: E402
    resolve_snapshot_dir,
)
from app.services.archive.archive_input_snapshot_layout_service import (  # noqa: E402
    EXTERNAL_SNAPSHOT_ROOT, choose_snapshot_layout,
)
from app.services.archive.archive_manifest_service import validate_manifest_files  # noqa: E402
from app.services.archive.archive_publish_service import publish_staged_archive  # noqa: E402
from app.services.archive.archive_publication_identity_service import publication_digest  # noqa: E402
from app.services.archive.archive_runtime_service import ArchiveManifestRecord  # noqa: E402
from app.services.archive.archive_task_api_service import ArchiveTaskApiService  # noqa: E402
from app.repository.archive.archive_attempt_restart_repository import interrupt_owned_claim  # noqa: E402

from test_phase1d_recovery import (  # noqa: E402
    CASE_ID, SOURCE_ID, database, mark_source_available, ready_case,
)
from test_phase1d_review_remediation import _trusted_completion  # noqa: E402


def _manifest(manifest_id: str, filename: str, payload: bytes) -> dict[str, object]:
    return {
        "manifest_id": manifest_id, "archive_base_name": filename.removesuffix(".rar"),
        "volume_size_bytes": 4_000_000_000, "max_part_count": 2,
        "actual_archive_bytes": len(payload), "validation_status": "validated",
        "parts": [{
            "part_id": "SYNTHETIC-PART-1", "part_number": 1, "filename": filename,
            "size_bytes": len(payload), "md5": hashlib.md5(payload).hexdigest(),  # noqa: S324
            "disc_number": "SYNTHETIC-DISC-1", "disc_date": "2026-07-28",
            "disc_capacity_bytes": 4_000_000_000, "volume_size_bytes": 4_000_000_000,
        }],
    }


def _bound_task(database, tmp_path: Path, task_id: str):
    shell = ready_case(database)
    mark_source_available(database)
    attempts = ArchiveAttemptService(database, tmp_path / f"SYNTHETIC-OUTPUT-{task_id}")
    attempt = attempts.accept(
        CASE_ID, SOURCE_ID, 0, f"SYNTHETIC-CONTEXT-{task_id}", shell["revision"], task_id=task_id,
    )
    tasks = ArchiveTaskRepository(database)
    task = tasks.create({
        "task_id": task_id, "case_id": CASE_ID, "input_revision": 1,
        "attempt": 1, "created_at": "2026-07-28T00:00:00+00:00",
    })
    task = tasks.bind_attempt(task_id, attempt["attempt_id"])
    return attempts, tasks, task, attempt


def test_task_b_cannot_bind_or_reuse_task_a_identity(database, tmp_path: Path) -> None:
    attempts, tasks, task_a, attempt = _bound_task(database, tmp_path, "SYNTHETIC-TASK-A")
    task_b = tasks.create({
        "task_id": "SYNTHETIC-TASK-B", "case_id": CASE_ID, "input_revision": 1,
        "attempt": 2, "created_at": "2026-07-28T00:00:01+00:00",
    })
    with pytest.raises(WorkbenchPersistenceError) as binding:
        tasks.bind_attempt(task_b["task_id"], attempt["attempt_id"])
    assert binding.value.code in {"ARCHIVE_ATTEMPT_ALREADY_BOUND", "ARCHIVE_ATTEMPT_BINDING_MISMATCH"}
    assert tasks.get(task_a["task_id"])["process_binding"]["staging_asset_id"] == attempt["attempt_id"]

    attempts.start(attempt["attempt_id"])
    task_a = tasks.claim(
        task_a["task_id"], owner_token="SYNTHETIC-OWNER-M1",
        attempt_id=attempt["attempt_id"], expected_revision=task_a["revision"],
        max_running=6,
    )
    context_id = "SYNTHETIC-CONTEXT-SYNTHETIC-TASK-A"
    final_dir = attempts.output_root / "compressed" / context_id / "SYNTHETIC-MANIFEST-M1"
    manifest = _manifest("SYNTHETIC-MANIFEST-M1", "SYNTHETIC-CASE.rar", b"SYNTHETIC/M1")
    identity = attempts.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, source_key="1" * 64,
        input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id=manifest["manifest_id"], final_dir=final_dir, public_manifest=manifest,
    )
    with pytest.raises(WorkbenchPersistenceError) as conflict:
        ArchivePublishIntentRepository(database).create(
            attempt_id=attempt["attempt_id"], task_id=task_b["task_id"],
            deployment_instance_id=database.deployment_instance_id,
            case_id=CASE_ID, source_id=SOURCE_ID, context_id=context_id,
            target_context_id=context_id, source_revision=0, draft_revision=1,
            report_fingerprint=identity["report_fingerprint"], source_key=identity["source_key"],
            input_fingerprint=identity["input_fingerprint"], archive_fingerprint=identity["archive_fingerprint"],
            manifest_id=identity["manifest_id"], relative_final_dir=identity["relative_final_dir"],
            public_manifest=identity["public_manifest"], publication_id=identity["publication_id"],
        )
    assert conflict.value.code == "ARCHIVE_PUBLISH_INTENT_CONFLICT"


def test_missing_task_identity_in_old_intent_is_not_a_match(database, tmp_path: Path) -> None:
    attempts, tasks, task, attempt = _bound_task(database, tmp_path, "SYNTHETIC-TASK-M1-OLD")
    attempts.start(attempt["attempt_id"])
    tasks.claim(
        task["task_id"], owner_token="SYNTHETIC-OWNER-M1-OLD",
        attempt_id=attempt["attempt_id"], expected_revision=task["revision"],
        max_running=6,
    )
    context_id = "SYNTHETIC-CONTEXT-SYNTHETIC-TASK-M1-OLD"
    manifest = _manifest("SYNTHETIC-MANIFEST-M1-OLD", "SYNTHETIC-CASE.rar", b"SYNTHETIC/OLD")
    identity = attempts.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, source_key="4" * 64,
        input_fingerprint="5" * 64, archive_fingerprint="6" * 64,
        manifest_id=manifest["manifest_id"],
        final_dir=attempts.output_root / "compressed" / context_id / manifest["manifest_id"],
        public_manifest=manifest,
    )
    with database.transaction() as connection:
        connection.execute(
            "UPDATE archive_publish_intents SET task_id=NULL WHERE attempt_id=?",
            (attempt["attempt_id"],),
        )
    from app.repository.workbench_database import WorkbenchDatabase
    WorkbenchDatabase(database.database_path, database.deployment_instance_id)
    migrated = ArchivePublishIntentRepository(database).get_for_attempt(
        attempt["attempt_id"],
    )
    assert migrated["task_id"] == f"legacy-task-{attempt['attempt_id']}"
    assert migrated["phase"] == "conflict"
    with pytest.raises(WorkbenchPersistenceError) as conflict:
        ArchivePublishIntentRepository(database).create(
            attempt_id=attempt["attempt_id"], task_id="SYNTHETIC-TASK-M1-OLD",
            deployment_instance_id=database.deployment_instance_id,
            case_id=CASE_ID, source_id=SOURCE_ID, context_id=context_id,
            target_context_id=context_id, source_revision=0, draft_revision=1,
            report_fingerprint=identity["report_fingerprint"], source_key=identity["source_key"],
            input_fingerprint=identity["input_fingerprint"], archive_fingerprint=identity["archive_fingerprint"],
            manifest_id=identity["manifest_id"], relative_final_dir=identity["relative_final_dir"],
            public_manifest=identity["public_manifest"], publication_id=identity["publication_id"],
        )
    assert conflict.value.code == "ARCHIVE_PUBLISH_INTENT_CONFLICT"


def test_public_enqueue_does_not_accept_internal_binding_fields() -> None:
    parameters = inspect.signature(ArchiveTaskApiService.enqueue).parameters
    assert "task_id" not in parameters
    assert "attempt_id" not in parameters
    assert "fence_id" not in parameters


def test_shutdown_rereads_revision_after_worker_activity(database, tmp_path: Path) -> None:
    attempts, tasks, task, attempt = _bound_task(database, tmp_path, "SYNTHETIC-TASK-M2-REVISION")
    claimed = tasks.claim(
        task["task_id"], owner_token="SYNTHETIC-OWNER-M2", attempt_id=attempt["attempt_id"],
        expected_revision=task["revision"], max_running=6,
    )
    stale_revision = claimed["revision"]
    advanced = tasks.update_state(
        task["task_id"], {"stage": "inventory", "worker_state": "owned_running"}, stale_revision,
    )
    result = interrupt_owned_claim(
        database, task_id=task["task_id"], owner_token="SYNTHETIC-OWNER-M2",
        attempt_id=attempt["attempt_id"], task_revision=stale_revision,
    )
    assert result == "interrupted"
    current = tasks.get(task["task_id"])
    assert current["revision"] > advanced["revision"]
    assert current["status"] == "interrupted"
    assert current["percent"] == 10 and current["percent"] != 100
    assert attempts.repository.get_internal(attempt["attempt_id"])["status"] == "interrupted"
    assert interrupt_owned_claim(
        database, task_id=task["task_id"], owner_token="SYNTHETIC-OWNER-M2",
        attempt_id=attempt["attempt_id"], task_revision=stale_revision,
    ) == "not_interruptible"


def test_shutdown_does_not_touch_transferred_owner_or_unverified_success(
    database, tmp_path: Path,
) -> None:
    _attempts, tasks, task, attempt = _bound_task(database, tmp_path, "SYNTHETIC-TASK-M2-OWNER")
    claimed = tasks.claim(
        task["task_id"], owner_token="SYNTHETIC-OWNER-OLD", attempt_id=attempt["attempt_id"],
        expected_revision=task["revision"], max_running=6,
    )
    with database.transaction() as connection:
        connection.execute(
            "UPDATE task_records SET process_binding_json=?, revision=revision+1 WHERE task_id=?",
            (json.dumps({"process_tree_id": "SYNTHETIC-OWNER-NEW", "staging_asset_id": attempt["attempt_id"]}), task["task_id"]),
        )
    assert interrupt_owned_claim(
        database, task_id=task["task_id"], owner_token="SYNTHETIC-OWNER-OLD",
        attempt_id=attempt["attempt_id"], task_revision=claimed["revision"],
    ) == "ownership_lost"
    assert tasks.get(task["task_id"])["status"] == "running"

    with database.transaction() as connection:
        connection.execute(
            "UPDATE task_records SET status='succeeded', stage='completed', percent=100 "
            "WHERE task_id=?",
            (task["task_id"],),
        )
    assert interrupt_owned_claim(
        database, task_id=task["task_id"], owner_token="SYNTHETIC-OWNER-NEW",
        attempt_id=attempt["attempt_id"], task_revision=claimed["revision"],
    ) == "unresolved"
    assert tasks.get(task["task_id"])["status"] == "succeeded"


def test_snapshot_change_before_seal_invalidates_input_and_never_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "SYNTHETIC-SOURCE-M3"
    source.mkdir()
    source_file = source / "SYNTHETIC-REPORT.bin"
    source_file.write_bytes(b"SYNTHETIC/ORIGINAL")
    output = tmp_path / "SYNTHETIC-OUTPUT-M3"
    inventory = build_input_inventory(source, output_root=output)

    import app.services.archive.archive_input_snapshot_service as snapshot_module

    original_assert = snapshot_module._assert_source_matches
    mutated = False

    def mutate_before_seal(current, evidence):
        nonlocal mutated
        if not mutated:
            mutated = True
            source_file.write_bytes(b"SYNTHETIC/REPLACED-SAME-NAME")
        return original_assert(current, evidence)

    monkeypatch.setattr(snapshot_module, "_assert_source_matches", mutate_before_seal)
    with pytest.raises(ArchiveInputError) as error:
        create_ephemeral_sealed_input_snapshot(output, inventory)
    assert error.value.code == "ARCHIVE_INPUT_CHANGED"
    assert not list((output / "compressed" / ".inputs").glob("snapshot-*"))
    assert not list((output / "compressed" / ".inputs").glob(".snapshot-*"))


def test_snapshot_is_read_only_and_executor_input_is_not_mutable_source(tmp_path: Path) -> None:
    source = tmp_path / "SYNTHETIC-SOURCE-M3-SEALED"
    source.mkdir()
    (source / "data.bin").write_bytes(b"SYNTHETIC/SEALED")
    output = tmp_path / "SYNTHETIC-OUTPUT-M3-SEALED"
    snapshot = create_ephemeral_sealed_input_snapshot(
        output, build_input_inventory(source, output_root=output),
    )
    assert snapshot.snapshot_dir != source
    assert not (snapshot.snapshot_dir / "data.bin").stat().st_mode & 0o200
    assert_sealed_input(snapshot)
    (source / "data.bin").write_bytes(b"SYNTHETIC/SOURCE-CHANGED")
    assert (snapshot.snapshot_dir / "data.bin").read_bytes() == b"SYNTHETIC/SEALED"


def test_long_snapshot_paths_use_short_private_root_without_changing_source_tree(tmp_path: Path) -> None:
    output = tmp_path / "o"
    source = tmp_path / "s"
    snapshot_id = "snapshot-" + "a" * 48
    standard_temp = output / "compressed" / ".inputs" / f".{snapshot_id}.copying"
    short_temp = output / ".i" / f".s{'a' * 16}.copying"
    relative_length = 250 - len(str(short_temp)) - 1
    middle_length = relative_length - len("folder/") - 80 - len("/fixture.bin") - 1
    assert middle_length >= 16
    relative = f"folder/{'x' * 80}/{'y' * middle_length}/fixture.bin"
    directories = ["folder", f"folder/{'x' * 80}"]

    layout = choose_snapshot_layout(output, snapshot_id, [relative], directories)
    assert layout.locator.startswith(".i/")
    assert len(str(layout.root / f".{layout.snapshot_name}.copying" / relative)) < 260
    assert len(str(standard_temp / relative)) >= 260

    source_file = source / relative
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"SYNTHETIC/LONG-PATH")
    snapshot = create_ephemeral_sealed_input_snapshot(
        output, build_input_inventory(source, output_root=output),
    )
    try:
        assert snapshot.snapshot_dir.parent == output / ".i"
        assert resolve_snapshot_dir(
            output, f".i/{snapshot.snapshot_dir.name}",
        ) == snapshot.snapshot_dir.resolve()
        assert snapshot.snapshot_dir.joinpath(relative).read_bytes() == b"SYNTHETIC/LONG-PATH"
    finally:
        cleanup_ephemeral_input_snapshot(snapshot)


def test_very_long_output_root_uses_external_private_snapshot_root(tmp_path: Path) -> None:
    output = tmp_path / ("output-" + "x" * 130)
    source = tmp_path / "source"
    output.mkdir()
    snapshot_id = "snapshot-" + "b" * 48
    relative = f"folder/{'x' * 50}/fixture.bin"
    source_file = source / relative
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"SYNTHETIC/EXTERNAL-LONG-PATH")

    layout = choose_snapshot_layout(
        output, snapshot_id, [relative], ["folder", f"folder/{'x' * 50}"],
    )
    assert layout.locator.startswith(f"{EXTERNAL_SNAPSHOT_ROOT}/")
    snapshot = create_ephemeral_sealed_input_snapshot(
        output, build_input_inventory(source, output_root=output),
    )
    try:
        assert snapshot.snapshot_dir.parent == layout.root
        assert snapshot.snapshot_dir.joinpath(relative).read_bytes() == b"SYNTHETIC/EXTERNAL-LONG-PATH"
        assert resolve_snapshot_dir(
            output, f"{EXTERNAL_SNAPSHOT_ROOT}/{snapshot.snapshot_dir.name}",
        ) == snapshot.snapshot_dir.resolve()
    finally:
        cleanup_ephemeral_input_snapshot(snapshot)


def test_restart_cleans_unsealed_snapshot_without_reusing_old_attempt(
    database, tmp_path: Path,
) -> None:
    attempts, _tasks, task, attempt = _bound_task(
        database, tmp_path, "SYNTHETIC-TASK-M3-CRASH",
    )
    attempts.start(attempt["attempt_id"])
    internal_attempt = attempts.repository.get_internal(attempt["attempt_id"])
    snapshot_id = "SYNTHETIC-SNAPSHOT-M3-CRASH"
    snapshot_root = attempts.output_root / "compressed" / ".inputs"
    copying = snapshot_root / f".{snapshot_id}.copying"
    copying.mkdir(parents=True)
    (copying / "SYNTHETIC-PARTIAL.bin").write_bytes(b"SYNTHETIC/PARTIAL")
    ArchiveInputSnapshotRepository(database).create_copying({
        "snapshot_id": snapshot_id, "task_id": task["task_id"],
        "attempt_id": attempt["attempt_id"], "case_id": CASE_ID,
        "source_id": SOURCE_ID, "source_revision": internal_attempt["source_revision"],
        "draft_revision": internal_attempt["draft_revision"],
        "source_root_id": "SYNTHETIC-SOURCE-ROOT-M3",
        "snapshot_root_id": "SYNTHETIC-SNAPSHOT-ROOT-M3",
        "snapshot_locator": f".inputs/{snapshot_id}",
        "marker_token": "SYNTHETIC-SNAPSHOT-TOKEN-M3",
    })

    assert attempt["attempt_id"] in attempts.recover_after_restart()
    row = ArchiveInputSnapshotRepository(database).get(snapshot_id)
    assert row["status"] == "cleaned"
    assert not copying.exists()
    assert not (snapshot_root / snapshot_id).exists()


def test_publication_cutpoint_tamper_never_becomes_durable_success(
    database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT-M4A")
    context_id = "SYNTHETIC-CONTEXT-M4A-CUT"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    staging = service.staging_root / "SYNTHETIC-STAGING-M4A"
    staging.mkdir(parents=True)
    service.staging_initializer(attempt["attempt_id"])(staging)
    payload = b"SYNTHETIC/M4A-ORIGINAL"
    (staging / "SYNTHETIC-CASE.rar").write_bytes(payload)
    final_dir = service.output_root / "compressed" / context_id / "SYNTHETIC-MANIFEST-M4A"
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    manifest = _manifest("SYNTHETIC-MANIFEST-M4A", "SYNTHETIC-CASE.rar", payload)
    record = ArchiveManifestRecord(
        manifest["manifest_id"], context_id, "7" * 64, manifest, final_dir, 0.0, 9_999_999_999.0,
    )
    context = SimpleNamespace(
        context_id=context_id, source_key="8" * 64, input_fingerprint="9" * 64,
    )
    import app.services.archive.archive_publish_service as publish_module

    original_validate = publish_module.validate_published_manifest
    tampered = False

    def validate_then_tamper(candidate, **kwargs):
        nonlocal tampered
        valid = original_validate(candidate, **kwargs)
        if valid and not tampered and Path(candidate.final_dir).resolve() == final_dir.resolve():
            tampered = True
            part = final_dir / "SYNTHETIC-CASE.rar"
            part.chmod(0o600)
            part.write_bytes(b"SYNTHETIC/M4A-TAMPERED")
        return valid

    monkeypatch.setattr(publish_module, "validate_published_manifest", validate_then_tamper)
    with pytest.raises(ValueError, match="ARCHIVE_PARTS_INVALID"):
        publish_staged_archive(
            staging, final_dir, record, CaseDraftRepository(database).get(CASE_ID)["report"], context=context,
            attempt_id=attempt["attempt_id"], attempt_service=service,
            workbench_context_id=context_id,
            verified_md5s={"SYNTHETIC-CASE.rar": manifest["parts"][0]["md5"]},
        )
    assert tampered
    assert service.repository.get_public(attempt["attempt_id"])["status"] == "running"
    intent = ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])
    assert intent["phase"] == "intent_persisted"
    assert intent["publication_status"] == "sealed"


def test_manifest_index_is_fail_closed_and_cross_instance_append_is_lossless(
    tmp_path: Path,
) -> None:
    output = tmp_path / "SYNTHETIC-OUTPUT-M4B"
    repository_a = ArchiveManifestRepository(output)
    repository_b = ArchiveManifestRepository(output)

    def save(index: int) -> None:
        repository = repository_a if index == 1 else repository_b
        repository.save(
            source_key=f"{index}" * 64, input_fingerprint=f"{index + 1}" * 64,
            archive_fingerprint=f"{index + 2}" * 64,
            manifest_id=f"SYNTHETIC-MANIFEST-M4B-{index}",
            final_dir=output / "compressed" / f"SYNTHETIC-CONTEXT-{index}" / f"SYNTHETIC-MANIFEST-M4B-{index}",
            public_manifest=_manifest(
                f"SYNTHETIC-MANIFEST-M4B-{index}", "SYNTHETIC-CASE.rar", b"SYNTHETIC/M4B",
            ),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(save, (1, 2)))
    assert len(repository_a.find_by_manifest_id("SYNTHETIC-MANIFEST-M4B-1")) == 1
    assert len(repository_b.find_by_manifest_id("SYNTHETIC-MANIFEST-M4B-2")) == 1

    repository_a.index_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ArchiveManifestRepositoryError, match="ARCHIVE_INDEX_CORRUPT"):
        repository_a.find_by_manifest_id("SYNTHETIC-MANIFEST-M4B-1")


def test_sqlite_authority_repairs_corrupt_derived_index(database, tmp_path: Path) -> None:
    service, attempt, _registry, record = _trusted_completion(
        database, tmp_path, "SYNTHETIC-CONTEXT-M4B-AUTHORITY", "SYNTHETIC-MANIFEST-M4B-AUTHORITY",
    )
    repository = ArchiveManifestRepository(service.output_root, database=database)
    expected_digest = ArchivePublishIntentRepository(database).get_for_attempt(
        attempt["attempt_id"],
    )["publication_digest"]
    payload = json.loads(repository.index_path.read_text(encoding="utf-8"))
    payload["records"][0]["publication_digest"] = "0" * 64
    repository.index_path.write_text(json.dumps(payload), encoding="utf-8")
    found = repository.find_for_attempt(attempt["attempt_id"])
    assert len(found) == 1
    assert found[0].publication_digest == expected_digest
    repository.save(
        source_key=found[0].source_key, input_fingerprint=found[0].input_fingerprint,
        archive_fingerprint=found[0].archive_fingerprint, manifest_id=found[0].manifest_id,
        final_dir=repository.resolve_final_dir(found[0]), public_manifest=found[0].public_manifest,
        workbench_attempt_id=attempt["attempt_id"], publication_id=found[0].publication_id,
        publication_digest=found[0].publication_digest,
    )
    assert json.loads(repository.index_path.read_text(encoding="utf-8"))["records"][0]["publication_digest"] == expected_digest


def _prepared_marker_publish(database, tmp_path: Path):
    shell = ready_case(database)
    mark_source_available(database)
    service = ArchiveAttemptService(database, tmp_path / "SYNTHETIC-OUTPUT-L1")
    context_id = "SYNTHETIC-CONTEXT-L1-OWNER"
    attempt = service.accept(CASE_ID, SOURCE_ID, 0, context_id, shell["revision"])
    service.start(attempt["attempt_id"])
    staging = service.staging_root / "SYNTHETIC-STAGING-L1-OWNER"
    staging.mkdir(parents=True)
    service.staging_initializer(attempt["attempt_id"])(staging)
    payload = b"SYNTHETIC/L1-OWNER"
    (staging / "SYNTHETIC-CASE.rar").write_bytes(payload)
    final_dir = service.output_root / "compressed" / context_id / "SYNTHETIC-MANIFEST-L1-OWNER"
    manifest = _manifest("SYNTHETIC-MANIFEST-L1-OWNER", "SYNTHETIC-CASE.rar", payload)
    service.persist_publish_intent(
        attempt["attempt_id"], context_id=context_id, source_key="a" * 64,
        input_fingerprint="b" * 64, archive_fingerprint="c" * 64,
        manifest_id=manifest["manifest_id"], final_dir=final_dir, public_manifest=manifest,
    )
    intent = ArchivePublishIntentRepository(database).get_for_attempt(attempt["attempt_id"])
    digest, file_set = publication_digest(intent, manifest)
    ArchivePublishIntentRepository(database).seal_publication(attempt["attempt_id"], digest, file_set)
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final_dir)
    return service, attempt, final_dir, manifest


def test_marker_owner_mismatch_rejected_and_concurrent_legal_delete_is_idempotent(
    database, tmp_path: Path,
) -> None:
    service, attempt, final_dir, _manifest_value = _prepared_marker_publish(database, tmp_path)
    marker = final_dir / ".workbench-staging-owner.json"
    original = json.loads(marker.read_text(encoding="utf-8"))
    marker.write_text(json.dumps({**original, "task_id": "SYNTHETIC-OTHER-TASK"}), encoding="utf-8")
    with pytest.raises(WorkbenchPersistenceError) as mismatch:
        service.remove_marker(final_dir, attempt["attempt_id"])
    assert mismatch.value.code == "ARCHIVE_PUBLISH_OWNER_REQUIRED"
    marker.write_text(json.dumps(original), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _value: service.remove_marker(final_dir, attempt["attempt_id"]), (1, 2),
        ))
    assert results == [None, None]
    assert not marker.exists()
    assert validate_manifest_files(SimpleNamespace(
        manifest_id="SYNTHETIC-MANIFEST-L1-OWNER", public_manifest=_manifest_value,
        final_dir=final_dir,
    )) is None
