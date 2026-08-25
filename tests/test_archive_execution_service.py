import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import (  # noqa: E402
    ArchiveExecutionError,
    WinRarExecutionResult,
)
from app.repository.archive_authorization_repository import AuthorizedInputRoot  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_execution_service import (  # noqa: E402
    ArchiveGateError,
    create_archive_context,
    execute_archive,
    get_valid_manifest,
)
from app.services.archive_runtime_service import ARCHIVE_RUNTIME_STORE  # noqa: E402
from app.services.archive_runtime_service import ArchiveRuntimeError  # noqa: E402
from app.services.archive_attempt_validation_service import ArchivePublicationSnapshot  # noqa: E402
from app.services.archive_manifest_access_service import get_manifest_part_download  # noqa: E402
from app.services.report_parsing_cache_service import ReportParsingCacheService  # noqa: E402
from app.services.archive_planner_service import ArchivePolicy, ArchiveTier  # noqa: E402


def valid_report():
    return {
        "introduction": {
            "case_summary": "合成案件",
            "evidence_list": [{
                "id": "material-1", "device_type": "手机", "device_type_source": "report_field",
                "material_type": "phone", "material_type_status": "confirmed_by_report",
                "material_type_source": "report",
            }],
        },
        "inspection": {"primary_software": {
            "name": "合成取证软件", "version": "1.0", "confirmation_status": "confirmed_by_report",
        }},
        "attachments": {"disc_number": "GP2026071802-01", "photo_ids": []},
    }


class FakeExecutor:
    def __init__(self, root, count_for_tier):
        self.root = Path(root)
        self.count_for_tier = count_for_tier
        self.calls = []

    def execute(self, plan, inventory_files, source_root, capability):
        self.calls.append(plan.volume_tier_gb)
        staging = self.root / f"attempt-{len(self.calls)}"
        staging.mkdir(parents=True)
        count = self.count_for_tier(plan.volume_tier_gb)
        for number in range(1, count + 1):
            filename = (
                f"{plan.archive_base_name}.rar"
                if count == 1
                else f"{plan.archive_base_name}.part{number}.rar"
            )
            (staging / filename).write_bytes(b"x")
        return WinRarExecutionResult(plan.plan_id, staging, 0, False)

    @staticmethod
    def cleanup(result):
        for path in result.staging_dir.glob("*"):
            path.unlink()
        result.staging_dir.rmdir()


def integrity_ok(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, "", "")


def policy(forced=None):
    return ArchivePolicy(
        (ArchiveTier(4, 4, 2), ArchiveTier(22, 22, 2), ArchiveTier(45, 45, 3)),
        forced_tier_gb=forced,
    )


def make_context(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    (source / "input.bin").write_bytes(b"12345678")
    output = tmp_path / "output"
    authorized = AuthorizedInputRoot(source.resolve(), "exact_directory_grant", "test-root")
    context_id = create_archive_context(authorized, valid_report(), output_root=str(output))
    return source, output, context_id


def test_replans_upward_and_manifest_uses_final_plan(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 3 if tier == 4 else 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    outcome = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )
    assert outcome.manifest_id
    assert fake.calls == [4, 22]
    manifest_dir = output / "compressed" / context_id / outcome.manifest_id
    assert manifest_dir.is_dir()


def test_archive_executes_without_first_disc_number(tmp_path):
    """REQ-030: compression must not fail when the first disc number is empty."""
    _, output, context_id = make_context(tmp_path)
    no_disc = valid_report()
    no_disc["attachments"]["disc_number"] = ""
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 2)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    outcome = execute_archive(
        context_id, no_disc, output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )
    assert outcome.status == "completed"
    assert outcome.manifest_id
    manifest = get_valid_manifest(context_id, outcome.manifest_id, no_disc)
    parts = manifest["parts"]
    assert len(parts) == 2
    assert all(part["disc_number"] == "" for part in parts)
    assert all(part["disc_date"] == "" for part in parts)


def test_archive_publishes_two_parts_with_three_character_disc_prefix(
    tmp_path, monkeypatch,
):
    _, output, context_id = make_context(tmp_path)
    report = valid_report()
    report["attachments"]["disc_number"] = "检验盘20260809-01"
    fake = FakeExecutor(tmp_path / "fake-staging", lambda _tier: 2)
    projected_parts: list[dict] = []
    monkeypatch.setattr(
        "app.services.archive_execution_service.persist_archive_plan_for_attempt",
        lambda _service, _attempt_id, _plan, manifest: projected_parts.extend(
            manifest["parts"],
        ),
    )

    outcome = execute_archive(
        context_id, report, output_root=str(output), policy=policy(4),
        capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
        executor=fake, integrity_runner=integrity_ok,
    )

    assert outcome.status == "completed"
    assert outcome.manifest_id
    manifest = get_valid_manifest(context_id, outcome.manifest_id, report)
    assert [part["disc_number"] for part in manifest["parts"]] == [
        "检验盘20260809-01", "检验盘20260809-02",
    ]
    assert [part["disc_date"] for part in manifest["parts"]] == [
        "2026-08-09", "2026-08-09",
    ]
    assert [part["disc_number"] for part in projected_parts] == [
        "检验盘20260809-01", "检验盘20260809-02",
    ]
    assert len(list((output / "compressed" / context_id).glob("**/*.rar"))) == 2


@pytest.mark.parametrize(
    ("disc_number", "error_code"),
    [
        ("GP20260230-01", "FIRST_DISC_DATE_INVALID"),
        ("GP20260809-0", "FIRST_DISC_SEQUENCE_INVALID"),
        ("ABCDEFGHIJKLMNOPQRSTU20260809-01", "FIRST_DISC_NUMBER_INVALID"),
    ],
)
def test_archive_rejects_invalid_disc_sequence_with_stable_error(
    tmp_path, disc_number, error_code,
):
    _, output, context_id = make_context(tmp_path)
    report = valid_report()
    report["attachments"]["disc_number"] = disc_number
    fake = FakeExecutor(tmp_path / "fake-staging", lambda _tier: 2)

    with pytest.raises(ArchiveGateError) as error:
        execute_archive(
            context_id, report, output_root=str(output), policy=policy(4),
            capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
            executor=fake, integrity_runner=integrity_ok,
        )

    assert {str(item.code) for item in error.value.blockers} == {error_code}
    assert fake.calls == []


def test_new_archive_hashes_each_generated_part_once(tmp_path, monkeypatch):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 2)
    calls: list[str] = []

    def counted_md5(path, _root):
        calls.append(path.name)
        return __import__("hashlib").md5(path.read_bytes()).hexdigest()

    monkeypatch.setattr(
        "app.services.archive_manifest_service.compute_md5_streaming", counted_md5,
    )
    outcome = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
        executor=fake, integrity_runner=integrity_ok,
    )

    assert outcome.status == "completed"
    assert len(calls) == 2
    assert sorted(calls) == ["合成案件.part1.rar", "合成案件.part2.rar"]


def test_direct_source_execution_does_not_repeat_inventory_scan(tmp_path, monkeypatch):
    source, output, context_id = make_context(tmp_path)

    class MutatingExecutor(FakeExecutor):
        def execute(self, plan, inventory_files, source_root, capability):
            assert Path(source_root) == source.resolve()
            changed = source / "input.bin"
            changed.write_bytes(b"SYNTHETIC-CHANGED")
            return super().execute(plan, inventory_files, source_root, capability)

    fake = MutatingExecutor(tmp_path / "fake-staging", lambda tier: 1)
    monkeypatch.setattr(
        "app.repository.archive_input_repository.verify_input_inventory",
        lambda *_args, **_kwargs: pytest.fail("archive execution repeated the input scan"),
    )
    outcome = execute_archive(
            context_id, valid_report(), output_root=str(output), policy=policy(4),
            capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
            executor=fake, integrity_runner=integrity_ok,
    )
    assert outcome.status == "completed"
    assert list((output / "compressed").glob("**/*.rar"))
    assert source.is_dir()
    assert (source / "input.bin").read_bytes() == b"SYNTHETIC-CHANGED"


def test_winrar_failure_is_reported_without_a_second_source_scan(tmp_path):
    source, output, context_id = make_context(tmp_path)

    class MutatingFailedExecutor(FakeExecutor):
        def execute(self, plan, inventory_files, source_root, capability):
            (source / "input.bin").write_bytes(b"SYNTHETIC-CHANGED")
            raise ArchiveExecutionError("ARCHIVE_EXECUTION_FAILED", "synthetic failure")

    fake = MutatingFailedExecutor(tmp_path / "fake-staging", lambda tier: 1)
    with pytest.raises(ArchiveGateError) as error:
        execute_archive(
            context_id, valid_report(), output_root=str(output), policy=policy(4),
            capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
            executor=fake, integrity_runner=integrity_ok,
        )
    assert {str(item.code) for item in error.value.blockers} == {"ARCHIVE_EXECUTION_FAILED"}
    assert source.is_dir()
    assert not list((output / "compressed").glob("**/*.rar"))


def test_equal_size_equal_mtime_change_documents_metadata_gate_limit(tmp_path):
    source, output, context_id = make_context(tmp_path)
    original_stat = (source / "input.bin").stat()

    class DirectSourceExecutor(FakeExecutor):
        seen_source_root = None

        def execute(self, plan, inventory_files, source_root, capability):
            self.seen_source_root = Path(source_root)
            assert self.seen_source_root == source.resolve()
            changed = source / "input.bin"
            changed.write_bytes(b"ABCDEFGH")
            os.utime(changed, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            return super().execute(plan, inventory_files, source_root, capability)

    fake = DirectSourceExecutor(tmp_path / "fake-staging", lambda tier: 1)
    outcome = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
        executor=fake,
        integrity_runner=integrity_ok,
    )
    assert outcome.manifest_id
    assert fake.seen_source_root == source.resolve()
    assert (source / "input.bin").read_bytes() == b"ABCDEFGH"
    assert not (output / ".i").exists()
    assert not (output / "compressed" / ".inputs").exists()


def test_workbench_publish_removes_staging_marker_exactly_once(
    tmp_path, monkeypatch,
):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)

    class AttemptService:
        remove_calls = 0
        latest_report = valid_report()
        latest_report["attachments"]["disc_number"] = "GP2026080802-08"

        @staticmethod
        def staging_initializer(_attempt_id):
            return lambda _staging: None

        @staticmethod
        def process_started_callback(_attempt_id):
            return lambda _pid: None

        @staticmethod
        def revalidate_before_publish(_attempt_id, report):
            return ArchivePublicationSnapshot(
                AttemptService.latest_report, 7 + publish_calls, chr(97 + publish_calls) * 64,
            )

        def remove_marker(self, _staging):
            self.remove_calls += 1

    attempts = AttemptService()
    hash_calls: list[str] = []
    completion_kwargs: dict[str, object] = {}

    def counted_md5(path, _root):
        hash_calls.append(path.name)
        return __import__("hashlib").md5(path.read_bytes()).hexdigest()

    monkeypatch.setattr(
        "app.services.archive_manifest_service.compute_md5_streaming", counted_md5,
    )
    monkeypatch.setattr(
        "app.services.archive_execution_service.WinRarExecutor",
        lambda *_args, **_kwargs: fake,
    )
    monkeypatch.setattr(
        "app.services.archive_execution_service.record_attempt_completion",
        lambda *_args, **kwargs: completion_kwargs.update(kwargs),
    )

    publish_calls = 0

    def publish(staging_dir, final_dir, *_args, attempt_service=None, **_kwargs):
        nonlocal publish_calls
        assert attempt_service is attempts
        assert attempts.remove_calls == 0
        publish_calls += 1
        if publish_calls == 1:
            AttemptService.latest_report = valid_report()
            AttemptService.latest_report["attachments"]["disc_number"] = "GP2026080802-09"
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
        attempt_service.remove_marker(staging_dir)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging_dir), str(final_dir))
        return {"合成案件.rar": (1, 2, 3, 4, 5)}

    monkeypatch.setattr(
        "app.services.archive_execution_service.publish_staged_archive", publish,
    )

    outcome = execute_archive(
        context_id,
        valid_report(),
        output_root=str(output),
        policy=policy(4),
        capability=capability,
        integrity_runner=integrity_ok,
        attempt_id="SYNTHETIC-ATTEMPT",
        attempt_service=attempts,
        workbench_context_id="SYNTHETIC-WORKBENCH-CONTEXT",
    )

    assert outcome.manifest_id
    assert publish_calls == 2
    assert hash_calls == ["合成案件.rar"]
    assert completion_kwargs["verified_md5s"]
    assert completion_kwargs["verified_file_identities"] == {
        "合成案件.rar": (1, 2, 3, 4, 5),
    }
    assert attempts.remove_calls == 1
    manifest = get_valid_manifest(
        context_id, outcome.manifest_id, AttemptService.latest_report,
    )
    assert manifest["parts"][0]["disc_number"] == "GP2026080802-09"


@pytest.mark.parametrize(
    ("disc_number", "error_code"),
    [
        ("GP20260230-01", "FIRST_DISC_DATE_INVALID"),
        ("GP20260809-0", "FIRST_DISC_SEQUENCE_INVALID"),
        ("ABCDEFGHIJKLMNOPQRSTU20260809-01", "FIRST_DISC_NUMBER_INVALID"),
    ],
)
def test_publish_revalidation_rejects_latest_invalid_disc_sequence(
    tmp_path, monkeypatch, disc_number, error_code,
):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda _tier: 2)

    class AttemptService:
        @staticmethod
        def staging_initializer(_attempt_id):
            return lambda _staging: None

        @staticmethod
        def process_started_callback(_attempt_id):
            return lambda _pid: None

        @staticmethod
        def revalidate_before_publish(_attempt_id, _report):
            latest = valid_report()
            latest["attachments"]["disc_number"] = disc_number
            return ArchivePublicationSnapshot(latest, 8, "a" * 64)

    monkeypatch.setattr(
        "app.services.archive_execution_service.WinRarExecutor",
        lambda *_args, **_kwargs: fake,
    )

    with pytest.raises(ArchiveGateError) as error:
        execute_archive(
            context_id, valid_report(), output_root=str(output), policy=policy(4),
            capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
            integrity_runner=integrity_ok, attempt_id="SYNTHETIC-ATTEMPT-INVALID-DISC",
            attempt_service=AttemptService(),
            workbench_context_id="SYNTHETIC-WORKBENCH-INVALID-DISC",
        )

    assert {str(item.code) for item in error.value.blockers} == {error_code}
    assert not list((output / "compressed").glob("**/*.rar"))


def test_publish_binding_error_is_not_misreported_as_invalid_rar(tmp_path, monkeypatch):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)

    class StaleAttemptService:
        @staticmethod
        def staging_initializer(_attempt_id):
            return lambda _staging: None

        @staticmethod
        def process_started_callback(_attempt_id):
            return lambda _pid: None

        @staticmethod
        def revalidate_before_publish(_attempt_id, _report):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")

    monkeypatch.setattr(
        "app.services.archive_execution_service.WinRarExecutor",
        lambda *_args, **_kwargs: fake,
    )
    with pytest.raises(ArchiveGateError) as error:
        execute_archive(
            context_id, valid_report(), output_root=str(output), policy=policy(4),
            capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
            integrity_runner=integrity_ok, attempt_id="SYNTHETIC-ATTEMPT-STALE",
            attempt_service=StaleAttemptService(),
            workbench_context_id="SYNTHETIC-WORKBENCH-CONTEXT-STALE",
        )
    assert {str(item.code) for item in error.value.blockers} == {
        "ARCHIVE_ATTEMPT_BINDING_STALE",
    }
    assert not list((output / "compressed").glob("**/*.rar"))


def test_successful_manifest_is_reused_only_for_same_snapshot_and_review(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    first = execute_archive(context_id, valid_report(), output_root=str(output), policy=policy(4), capability=capability, executor=fake, integrity_runner=integrity_ok)
    second = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=WinRarCapability(False, None, None, None, False),
        executor=fake, integrity_runner=integrity_ok,
    )
    assert first.manifest_id == second.manifest_id
    assert second.reused
    assert fake.calls == [4]
    corrected_photos = valid_report()
    corrected_photos["attachments"]["photo_ids"] = ["photo-1", "photo-2"]
    assert get_valid_manifest(context_id, first.manifest_id, corrected_photos)


def test_manifest_reuse_validates_output_without_rescanning_direct_source(tmp_path):
    source, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    first = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )

    # Disc numbers are mapped after compression and intentionally decoupled
    # from the reuse fingerprint: changing them must not invalidate the manifest.
    changed_disc = valid_report()
    changed_disc["attachments"]["disc_number"] = "GP2026071802-02"
    assert get_valid_manifest(context_id, first.manifest_id, changed_disc)

    (source / "input.bin").write_bytes(b"changed-input")
    assert get_valid_manifest(context_id, first.manifest_id, valid_report())


def test_replan_exhaustion_does_not_publish_manifest(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 4)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    with pytest.raises(ArchiveGateError) as error:
        execute_archive(context_id, valid_report(), output_root=str(output), policy=policy(4), capability=capability, executor=fake, integrity_runner=integrity_ok)
    assert error.value.blockers[0].code == "ARCHIVE_REPLAN_EXHAUSTED"
    assert list((output / "compressed").glob("**/*.part*.rar")) == []
    assert ARCHIVE_RUNTIME_STORE.get_context_summary(context_id)["status"] == "failed"


def test_unconfirmed_review_data_does_not_block_preview_archive(tmp_path):
    _, output, context_id = make_context(tmp_path)
    report = valid_report()
    report["inspection"]["primary_software"]["confirmation_status"] = "unconfirmed"
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    result = execute_archive(
        context_id, report, output_root=str(output), policy=policy(4),
        capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
        executor=fake, integrity_runner=integrity_ok,
    )
    assert result.manifest_id
    assert fake.calls == [4]


@pytest.mark.parametrize("photo_count", [1, 3, 5])
def test_odd_attachment2_photo_count_does_not_block_preview_archive(tmp_path, photo_count):
    _, output, context_id = make_context(tmp_path)
    report = valid_report()
    report["attachments"]["photo_ids"] = [
        f"photo-{index}" for index in range(photo_count)
    ]
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    result = execute_archive(
        context_id, report, output_root=str(output), policy=policy(4),
        capability=WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True),
        executor=fake, integrity_runner=integrity_ok,
    )
    assert result.manifest_id
    assert fake.calls == [4]


def test_unavailable_winrar_blocks_before_execution_without_manifest(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    unavailable = WinRarCapability(False, None, None, None, False)
    with pytest.raises(ArchiveGateError) as error:
        execute_archive(
            context_id, valid_report(), output_root=str(output), policy=policy(4),
            capability=unavailable, executor=fake, integrity_runner=integrity_ok,
        )
    assert error.value.blockers[0].code == "WINRAR_UNAVAILABLE"
    assert fake.calls == []


def test_manifest_context_mismatch_is_a_stable_authority_error(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    result = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )
    with pytest.raises(ArchiveGateError) as error:
        get_valid_manifest("other-context", result.manifest_id, valid_report())
    assert error.value.blockers[0].code == "ARCHIVE_MANIFEST_CONTEXT_MISMATCH"


def test_manifest_part_missing_and_changed_are_distinguished(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    result = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )
    part = next((output / "compressed" / context_id / result.manifest_id).glob("*.rar"))
    part.write_bytes(b"changed")
    with pytest.raises(ArchiveGateError) as error:
        get_valid_manifest(context_id, result.manifest_id, valid_report())
    assert error.value.blockers[0].code == "ARCHIVE_MANIFEST_PART_CHANGED"
    part.unlink()
    with pytest.raises(ArchiveGateError) as error:
        get_valid_manifest(context_id, result.manifest_id, valid_report())
    assert error.value.blockers[0].code == "ARCHIVE_MANIFEST_PART_MISSING"


def test_download_resolves_only_current_opaque_part_and_revalidates_file(tmp_path):
    _, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    result = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )
    manifest = ARCHIVE_RUNTIME_STORE.get_manifest(result.manifest_id).public_manifest
    part = manifest["parts"][0]
    download = get_manifest_part_download(context_id, result.manifest_id, part["part_id"])
    assert download.filename == part["filename"]
    assert download.size_bytes == part["size_bytes"]
    with pytest.raises(ArchiveRuntimeError) as missing:
        get_manifest_part_download(context_id, result.manifest_id, "../server-path")
    assert missing.value.code == "ARCHIVE_PART_NOT_FOUND"
    download.path.write_bytes(b"changed")
    with pytest.raises(ArchiveGateError) as changed:
        get_manifest_part_download(context_id, result.manifest_id, part["part_id"])
    assert changed.value.blockers[0].code == "ARCHIVE_MANIFEST_PART_CHANGED"


def test_reparse_same_input_reuses_persisted_manifest_after_cache_clear(tmp_path):
    source, output, context_id = make_context(tmp_path)
    first_fake = FakeExecutor(tmp_path / "fake-staging-first", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    first = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=first_fake, integrity_runner=integrity_ok,
    )
    parsed = output / "parsed"
    parsed.mkdir()
    (parsed / "cache.json").write_text("{}", encoding="utf-8")
    part = ARCHIVE_RUNTIME_STORE.get_manifest(first.manifest_id).public_manifest["parts"][0]

    assert ReportParsingCacheService().clear_all(str(parsed)) == 1
    second_context = create_archive_context(
        AuthorizedInputRoot(source.resolve(), "exact_directory_grant", "test-root"),
        valid_report(), output_root=str(output),
    )
    second_fake = FakeExecutor(tmp_path / "fake-staging-second", lambda tier: 1)
    second = execute_archive(
        second_context, valid_report(), output_root=str(output), policy=policy(4),
        capability=WinRarCapability(False, None, None, None, False), executor=second_fake,
        integrity_runner=integrity_ok,
    )

    assert second.reused is True
    assert second.manifest_id == first.manifest_id
    download = get_manifest_part_download(second_context, second.manifest_id, part["part_id"])
    assert download.path.is_file()
    assert get_valid_manifest(second_context, second.manifest_id, valid_report())
    assert (output / "compressed" / ".archive-manifest-index.json").is_file()


def test_reparse_reuses_manifest_within_confirmed_immutable_input_window(tmp_path):
    source, output, context_id = make_context(tmp_path)
    first_fake = FakeExecutor(tmp_path / "fake-staging-first", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=first_fake, integrity_runner=integrity_ok,
    )
    (source / "input.bin").write_bytes(b"changed!")
    changed_context = create_archive_context(
        AuthorizedInputRoot(source.resolve(), "exact_directory_grant", "test-root"),
        valid_report(), output_root=str(output),
    )
    second_fake = FakeExecutor(tmp_path / "fake-staging-second", lambda tier: 1)
    outcome = execute_archive(
        changed_context, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=second_fake, integrity_runner=integrity_ok,
    )

    # Deep input mutation is deliberately outside the confirmed immutable-input
    # contract; a repeated source scan must not be reintroduced here.
    assert outcome.reused is True
    assert second_fake.calls == []


@pytest.mark.parametrize("tamper", ["missing", "size", "md5"])
def test_reparse_does_not_reuse_tampered_rar(tmp_path, tamper):
    source, output, context_id = make_context(tmp_path)
    first_fake = FakeExecutor(tmp_path / "fake-staging-first", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    first = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=first_fake, integrity_runner=integrity_ok,
    )
    record = ARCHIVE_RUNTIME_STORE.get_manifest(first.manifest_id)
    part_path = next(record.final_dir.glob("*.rar"))
    if tamper == "missing":
        part_path.unlink()
    elif tamper == "size":
        part_path.write_bytes(b"changed-size")
    else:
        part_path.write_bytes(b"y")

    second_context = create_archive_context(
        AuthorizedInputRoot(source.resolve(), "exact_directory_grant", "test-root"),
        valid_report(), output_root=str(output),
    )
    second_fake = FakeExecutor(tmp_path / "fake-staging-second", lambda tier: 1)
    outcome = execute_archive(
        second_context, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=second_fake, integrity_runner=integrity_ok,
    )

    assert outcome.reused is False
    assert second_fake.calls == [4]
