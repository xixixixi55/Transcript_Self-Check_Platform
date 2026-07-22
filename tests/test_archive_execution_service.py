import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import WinRarExecutionResult  # noqa: E402
from app.repository.archive_authorization_repository import AuthorizedInputRoot  # noqa: E402
from app.services.archive_execution_service import (  # noqa: E402
    ArchiveGateError,
    create_archive_context,
    execute_archive,
    get_valid_manifest,
)
from app.services.archive_runtime_service import ARCHIVE_RUNTIME_STORE  # noqa: E402
from app.services.archive_runtime_service import ArchiveRuntimeError  # noqa: E402
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
        "attachments": {"disc_number": "GP20260718-01", "photo_ids": []},
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


def test_manifest_reuse_rechecks_disc_review_and_input_snapshot(tmp_path):
    source, output, context_id = make_context(tmp_path)
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    capability = WinRarCapability(True, "fake", "WinRAR.exe", "6.24", True)
    first = execute_archive(
        context_id, valid_report(), output_root=str(output), policy=policy(4),
        capability=capability, executor=fake, integrity_runner=integrity_ok,
    )

    changed_disc = valid_report()
    changed_disc["attachments"]["disc_number"] = "GP20260718-02"
    with pytest.raises(ArchiveGateError) as disc_error:
        get_valid_manifest(context_id, first.manifest_id, changed_disc)
    assert disc_error.value.blockers[0].code == "ARCHIVE_MANIFEST_MISSING"

    (source / "input.bin").write_bytes(b"changed-input")
    with pytest.raises(ArchiveGateError) as input_error:
        get_valid_manifest(context_id, first.manifest_id, valid_report())
    assert input_error.value.blockers[0].code == "ARCHIVE_INPUT_CHANGED"


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


def test_reparse_after_input_change_does_not_reuse_old_manifest(tmp_path):
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

    assert outcome.reused is False
    assert second_fake.calls == [4]


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
