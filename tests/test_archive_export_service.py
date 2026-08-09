"""定向测试：export_bundle 的 picker 授权门控与 exported 持久化（MF-4/MF-9）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive_export_service import export_bundle  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402


def _api(consume_ok: bool) -> MagicMock:
    api = MagicMock()
    api.shells.get.return_value = {"revision": 3}
    api.sources.authorization.consume_exact_directory_grant.return_value = consume_ok
    api.tasks.get_current_or_recent.return_value = {
        "task_id": "task-synthetic", "status": "succeeded",
    }
    api.results.manifest_bundle.return_value = {
        "public_manifest": {"parts": [{"filename": "case.part1.rar", "disc_number": "GP20260730-01"}]},
        "final_dir": "D:\\synthetic\\final",
    }
    api.drafts.get.return_value = {"report": {
        "inspection": {"software_tools": [
            {"name": "Python hashlib", "version": "3.11.0"},
        ]},
        "attachments": {"disc_number": "GP20260730-01"},
    }}
    api.plans.get_latest_for_case.return_value = {
        "volume_slots": [{"status": "active", "disc_mapping": {"disc_number": "GP20260730-01"}}],
    }
    return api


@pytest.fixture(autouse=True)
def _no_photo_side_effects():
    with patch("app.services.archive_export_service._resolve_photo_paths", return_value=[]):
        yield


def test_export_bundle_rejects_unauthorized_path(tmp_path: Path) -> None:
    api = _api(consume_ok=False)
    with pytest.raises(WorkbenchPersistenceError) as error:
        export_bundle(
            api, "case-synthetic", 3, "D:\\unauthorized\\out",
            directory_token="token-synthetic", template_context={},
        )
    assert error.value.code == "EXPORT_PATH_NOT_AUTHORIZED"


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
