"""T014 工作流里程碑与正式执行器的集成测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_authorization_repository import AuthorizedInputRoot  # noqa: E402
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import WinRarExecutionResult  # noqa: E402
from app.services.archive.archive_execution_service import create_archive_context, execute_archive  # noqa: E402
from app.services.archive.archive_planner_service import ArchivePolicy, ArchiveTier  # noqa: E402


def report() -> dict:
    return {
        "introduction": {
            "case_summary": "SYNTHETIC-T014-ARCHIVE",
            "evidence_list": [{
                "id": "SYNTHETIC-MATERIAL", "device_type": "SYNTHETIC",
                "device_type_source": "report_field", "material_type": "phone",
                "material_type_status": "confirmed_by_report",
                "material_type_source": "report",
            }],
        },
        "inspection": {"primary_software": {
            "name": "SYNTHETIC TOOL", "version": "1.0",
            "confirmation_status": "confirmed_by_report",
        }},
        "attachments": {"disc_number": "GP2026073002-01", "photo_ids": []},
    }


class ReplanningExecutor:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def execute(self, plan, _files, _source, _capability):
        self.calls += 1
        staging = self.root / f"attempt-{self.calls}"
        staging.mkdir(parents=True)
        count = 3 if self.calls == 1 else 1
        for number in range(1, count + 1):
            name = (
                f"{plan.archive_base_name}.rar"
                if count == 1 else f"{plan.archive_base_name}.part{number}.rar"
            )
            (staging / name).write_bytes(b"x")
        return WinRarExecutionResult(plan.plan_id, staging, 0, False)

    @staticmethod
    def cleanup(result):
        for path in result.staging_dir.iterdir():
            path.unlink()
        result.staging_dir.rmdir()


def test_formal_executor_observes_only_real_safe_boundaries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SYNTHETIC.txt").write_bytes(b"TESTDATA")
    output = tmp_path / "output"
    context_id = create_archive_context(
        AuthorizedInputRoot(source.resolve(), "exact_directory_grant", "SYNTHETIC-ROOT"),
        report(), output_root=str(output),
    )
    stages = []
    outcome = execute_archive(
        context_id, report(), output_root=str(output),
        policy=ArchivePolicy((
            ArchiveTier(4, 4, 2), ArchiveTier(22, 22, 2),
            ArchiveTier(45, 45, 3),
        ), forced_tier_gb=4),
        capability=WinRarCapability(
            True, "configured", "WinRAR.exe", "7.23", True,
        ),
        executor=ReplanningExecutor(tmp_path / "staging"),
        integrity_runner=lambda args, **kwargs: subprocess.CompletedProcess(
            args, 0, "", "",
        ),
        stage_observer=stages.append,
    )
    assert outcome.status == "completed"
    assert stages == [
        "inventory", "preflight_verified", "winrar", "winrar", "integrity",
        "integrity_verified", "md5", "manifest",
    ]
    assert not any(isinstance(stage, int) for stage in stages)
