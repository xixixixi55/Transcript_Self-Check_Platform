"""定向测试：export_bundle 的 picker 授权门控与 exported 持久化（MF-4/MF-9）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive_export_service import (  # noqa: E402
    export_bundle,
    resolve_case_word_manifest,
    validate_export_directory,
)
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_manifest_projection_service import (  # noqa: E402
    project_manifest_to_legacy_report_with_plan,
)
from app.services.unified_export_service import with_disc_mapping  # noqa: E402


def _api(consume_ok: bool) -> MagicMock:
    api = MagicMock()
    api.shells.get.return_value = {"revision": 3}
    api.sources.authorization.consume_exact_directory_grant.return_value = consume_ok
    api.tasks.get_current_or_recent.return_value = {
        "task_id": "task-synthetic", "status": "succeeded",
    }
    api.tasks.get_history.return_value = [{
        "task_id": "task-synthetic", "status": "succeeded",
    }]
    api.results.manifest_bundle.return_value = {
        "public_manifest": {
            "manifest_id": "manifest-synthetic", "plan_id": "plan-synthetic",
            "validation_status": "validated", "volume_size_bytes": 1024,
            "parts": [{
                "part_id": "part-synthetic", "part_number": 1,
                "filename": "case.part1.rar", "size_bytes": 1024,
                "md5": "a" * 32, "disc_number": "GP20260730-01",
                "disc_date": "2026-07-30", "disc_capacity_bytes": 4_700_000_000,
            }],
        },
        "final_dir": "D:\\synthetic\\final",
    }
    api.drafts.get.return_value = {"report": {
        "inspection": {"software_tools": [
            {"name": "Python hashlib", "version": "3.11.0"},
        ]},
        "attachments": {"disc_number": "GP20260730-01"},
    }}
    plan = {
        "plan_id": "plan-synthetic", "case_id": "case-synthetic",
        "volume_slots": [{
            "status": "active", "ordinal": 1,
            "disc_mapping": {
                "confirmation": "confirmed", "disc_number": "GP20260730-01",
                "disc_date": "2026-07-30",
            },
        }],
    }
    api.plans.get.return_value = plan
    api.plans.get_latest_for_case.return_value = plan
    return api


@pytest.fixture(autouse=True)
def _no_photo_side_effects():
    with patch("app.services.archive_export_service._resolve_photo_paths", return_value=[]):
        yield


def test_export_bundle_rejects_unauthorized_path(tmp_path: Path) -> None:
    api = _api(consume_ok=False)
    with pytest.raises(WorkbenchPersistenceError) as error:
        export_bundle(
            api, "case-synthetic", 3, str(tmp_path),
            directory_token="token-synthetic", template_context={},
        )
    assert error.value.code == "EXPORT_PATH_NOT_AUTHORIZED"


def test_export_directory_rejects_program_and_user_data_roots(tmp_path: Path) -> None:
    program_root = tmp_path / "SYNTHETIC-PROGRAM"
    user_data_root = tmp_path / "SYNTHETIC-USER-DATA"
    safe_root = tmp_path / "SYNTHETIC-EXPORT"
    for path in (program_root, user_data_root, safe_root, program_root / "nested"):
        path.mkdir(parents=True, exist_ok=True)

    for unsafe in (program_root, program_root / "nested", user_data_root):
        with pytest.raises(WorkbenchPersistenceError) as error:
            validate_export_directory(
                unsafe, protected_roots=(program_root, user_data_root),
            )
        assert error.value.code == "EXPORT_DIRECTORY_UNSAFE"

    assert validate_export_directory(
        safe_root, protected_roots=(program_root, user_data_root),
    ) == safe_root.resolve()


def test_standalone_word_manifest_matches_unified_export_projection() -> None:
    api = _api(consume_ok=True)
    api.results.manifest_bundle.return_value["public_manifest"]["parts"][0].update({
        "disc_number": "",
        "disc_date": "",
    })
    api.plans.get.return_value = {
        "plan_id": "plan-synthetic", "case_id": "case-synthetic",
        "volume_slots": [{
            "status": "active",
            "ordinal": 1,
            "disc_mapping": {
                "confirmation": "confirmed",
                "disc_number": "GP20260730-01",
                "disc_date": "2026-07-30",
            },
        }],
    }

    resolved = resolve_case_word_manifest(api, "case-synthetic")

    assert resolved is not None
    assert resolved["parts"][0]["disc_number"] == "GP20260730-01"
    assert resolved["parts"][0]["disc_date"] == "2026-07-30"
    assert api.results.manifest_bundle.return_value["public_manifest"]["parts"][0]["disc_number"] == ""


def test_newer_active_task_does_not_hide_last_successful_archive() -> None:
    api = _api(consume_ok=True)
    api.tasks.get_current_or_recent.return_value = {
        "task_id": "task-running", "status": "running",
    }
    api.tasks.get_history.return_value = [
        {"task_id": "task-running", "status": "running"},
        {"task_id": "task-synthetic", "status": "succeeded"},
    ]

    resolved = resolve_case_word_manifest(api, "case-synthetic")

    assert resolved is not None
    api.results.manifest_bundle.assert_called_once_with("task-synthetic")


def test_standalone_word_rejects_plan_from_another_publication() -> None:
    api = _api(consume_ok=True)
    api.plans.get.return_value = {
        "plan_id": "plan-synthetic", "case_id": "case-other", "volume_slots": [],
    }

    with pytest.raises(WorkbenchPersistenceError) as error:
        resolve_case_word_manifest(api, "case-synthetic")

    assert error.value.code == "ARCHIVE_RESULT_NOT_AVAILABLE"


def test_standalone_word_does_not_fallback_when_verified_manifest_is_invalid() -> None:
    api = _api(consume_ok=True)
    api.results.manifest_bundle.side_effect = WorkbenchPersistenceError(
        "ARCHIVE_RESULT_NOT_AVAILABLE",
    )

    with pytest.raises(WorkbenchPersistenceError) as error:
        resolve_case_word_manifest(api, "case-synthetic")

    assert error.value.code == "ARCHIVE_RESULT_NOT_AVAILABLE"


def test_standalone_and_unified_inputs_build_the_same_real_attachment_plan() -> None:
    api = _api(consume_ok=True)
    report = {
        "introduction": {"evidence_list": [{"evidence_number": "SYNTHETIC-JC-1"}]},
        "inspection": {
            "hardware_device": "SYNTHETIC-DEVICE",
            "primary_software": {
                "name": "SYNTHETIC-FORENSIC", "version": "1.0",
                "confirmation_status": "confirmed_by_user",
            },
            "software_tools": [
                {"name": "WinRAR", "version": "7.0"},
                {"name": "HashMyFiles", "version": "2.51"},
            ],
        },
        "attachments": {"photo_ids": [], "photo_groups": []},
    }
    standalone_manifest = resolve_case_word_manifest(api, "case-synthetic")
    raw_manifest = api.results.manifest_bundle.return_value["public_manifest"]
    unified_manifest = with_disc_mapping(raw_manifest, api.plans.get("plan-synthetic"))

    _, standalone_plan = project_manifest_to_legacy_report_with_plan(
        report, standalone_manifest,
    )
    _, unified_plan = project_manifest_to_legacy_report_with_plan(report, unified_manifest)

    assert standalone_plan == unified_plan
    assert standalone_plan.attachment1_pages[0].serial_rows[0].filename == "case.part1.rar"


def test_standalone_word_without_successful_archive_keeps_report_only_path() -> None:
    api = _api(consume_ok=True)
    api.tasks.get_history.return_value = [{
        "task_id": "task-synthetic", "status": "failed",
    }]

    assert resolve_case_word_manifest(api, "case-synthetic") is None
    api.results.manifest_bundle.assert_not_called()


def test_export_bundle_marks_shell_exported_after_success(tmp_path: Path) -> None:
    api = _api(consume_ok=True)
    export_dir = tmp_path / "export-out"
    export_dir.mkdir(parents=True)
    api.sources.authorization.consume_exact_directory_grant.return_value = True

    with patch("app.services.archive_export_service.unified_export") as unified:
        unified.return_value = {
            "export_path": str(export_dir), "word_filename": "用户命名.docx",
            "rar_filenames": ["case.part1.rar"],
            "hash_verification_image": "hash.png", "exported_at": "2026-01-01T00:00:00Z",
        }
        result = export_bundle(
            api, "case-synthetic", 3, str(export_dir),
            directory_token="token-synthetic", word_filename="用户命名.docx",
            template_context={},
        )

    assert result["lifecycle"] == "exported"
    api.sources.authorization.consume_exact_directory_grant.assert_called_once_with(
        "token-synthetic", str(export_dir),
    )
    api.shells.update_lifecycle.assert_called_once_with(
        "case-synthetic", "exported", 3,
    )
    assert unified.call_args.kwargs["word_filename"] == "用户命名.docx"
    assert unified.call_args.kwargs["report"]["inspection"]["software_tools"] == [
        {
            "category": "hashmyfiles", "name": "HashMyFiles", "version": "2.51",
            "display_name": "HashMyFiles 2.51",
        },
    ]


def test_export_bundle_uses_asset_ref_order_and_rebuilds_missing_photo_groups(
    tmp_path: Path,
) -> None:
    api = _api(consume_ok=True)
    export_dir = tmp_path / "export-with-photos"
    export_dir.mkdir()
    photo_ids = ["asset-synthetic-front", "asset-synthetic-back"]
    api.drafts.get.return_value = {
        "asset_refs": [
            {"asset_id": asset_id, "asset_kind": "image"}
            for asset_id in photo_ids
        ],
        "report": {
            "introduction": {
                "evidence_list": [{
                    "id": "SYNTHETIC-MATERIAL-1",
                    "evidence_number": "SYNTHETIC-1",
                }],
            },
            "inspection": {"software_tools": []},
            "attachments": {"photo_ids": [], "disc_number": "GP20260730-01"},
        },
    }

    with patch("app.services.archive_export_service.unified_export") as unified:
        unified.return_value = {
            "export_path": str(export_dir), "word_filename": "SYNTHETIC.docx",
            "rar_filenames": ["case.part1.rar"], "hash_verification_image": "hash.png",
            "exported_at": "2026-01-01T00:00:00Z",
        }
        export_bundle(
            api, "case-synthetic", 3, str(export_dir),
            directory_token="token-synthetic", word_filename="SYNTHETIC.docx",
            template_context={},
        )

    report = unified.call_args.kwargs["report"]
    assert report["attachments"]["photo_ids"] == photo_ids
    assert report["attachments"]["photo_groups"] == [{
        "material_id": "SYNTHETIC-MATERIAL-1",
        "material_number": "SYNTHETIC-1",
        "display_text": "检材SYNTHETIC-1照片",
        "ordered_image_ids": photo_ids,
        "source_order": 1,
    }]


def test_export_bundle_fails_when_disc_mapping_incomplete(tmp_path: Path) -> None:
    api = _api(consume_ok=True)
    export_dir = tmp_path / "export-out"
    export_dir.mkdir(parents=True)
    # Plan still has an unmapped slot.
    api.plans.get_latest_for_case.return_value = {
        "volume_slots": [{"status": "active", "disc_mapping": None}],
    }
    from app.services.unified_export_service import UnifiedExportError

    with patch("app.services.archive_export_service.unified_export", side_effect=UnifiedExportError(
        "DISC_MAPPING_INCOMPLETE", "光盘编号尚未全部补齐，无法导出。",
    )):
        with pytest.raises(WorkbenchPersistenceError) as error:
            export_bundle(
                api, "case-synthetic", 3, str(export_dir),
                directory_token="token-synthetic", template_context={},
            )
    assert error.value.code == "DISC_MAPPING_INCOMPLETE"
    api.shells.update_lifecycle.assert_not_called()


def test_export_bundle_projects_hash_screenshot_failure_without_marking_exported(tmp_path: Path) -> None:
    api = _api(consume_ok=True)
    export_dir = tmp_path / "export-out"
    export_dir.mkdir(parents=True)
    from app.services.unified_export_service import UnifiedExportError

    with patch("app.services.archive_export_service.unified_export", side_effect=UnifiedExportError(
        "HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验截图生成失败。",
    )):
        with pytest.raises(WorkbenchPersistenceError) as error:
            export_bundle(
                api, "case-synthetic", 3, str(export_dir),
                directory_token="token-synthetic", template_context={},
            )

    assert error.value.code == "HASHMYFILES_SCREENSHOT_FAILED"
    assert error.value.args[0] == "HashMyFiles 校验截图生成失败。"
    api.shells.update_lifecycle.assert_not_called()
