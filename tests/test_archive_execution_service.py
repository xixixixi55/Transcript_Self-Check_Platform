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
        for number in range(1, self.count_for_tier(plan.volume_tier_gb) + 1):
            (staging / f"{plan.archive_base_name}.part{number}.rar").write_bytes(b"x")
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


def test_unconfirmed_review_data_blocks_before_executor(tmp_path):
    _, output, context_id = make_context(tmp_path)
    report = valid_report()
    report["inspection"]["primary_software"]["confirmation_status"] = "unconfirmed"
    fake = FakeExecutor(tmp_path / "fake-staging", lambda tier: 1)
    with pytest.raises(ArchiveGateError) as error:
        execute_archive(context_id, report, output_root=str(output), policy=policy(4), capability=None, executor=fake, integrity_runner=integrity_ok)
    assert error.value.blockers[0].code == "PRIMARY_SOFTWARE_UNCONFIRMED"
    assert fake.calls == []


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
