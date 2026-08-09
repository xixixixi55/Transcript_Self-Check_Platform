"""Synthetic persistence and HTTP tests for workbench image assets."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import zlib

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import CaseDraftRepository, CaseShellRepository, WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.services.workbench_factory_service import build_workbench_services  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_export_service import _resolve_photo_paths  # noqa: E402

CASE_ID = "SYNTHETIC-ASSET-CASE"
IDENTITY = {
    "identity_kind": "local_session", "client_instance_id": "SYNTHETIC-ASSET-CLIENT",
    "session_id": "SYNTHETIC-ASSET-SESSION", "deployment_instance_id": "SYNTHETIC-ASSET-DEPLOYMENT",
}
REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport", "document_number": "SYNTHETIC-ASSET-DOC",
    "introduction": {"entrust_unit": "SYNTHETIC", "entrust_persons": [], "entrust_time": "", "case_summary": "SYNTHETIC", "evidence_list": [], "inspection_requirement": "", "inspection_time_range": "", "inspectors": [], "inspection_place": ""},
    "inspection": {"method": "", "hardware_device": "", "software_tools": [], "process_steps": [], "result": {"evidence_number": "", "software_name": "", "software_version": "", "data_summary": "", "rar_filename": "", "md5_hash": "", "file_size": ""}},
    "attachments": {"extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": ""},
}


def png_bytes(color: tuple[int, int, int] = (20, 40, 60)) -> bytes:
    raw = b"\x00" + bytes(color) + b"\xff"
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture()
def asset_context(tmp_path: Path):
    database = WorkbenchDatabase(database_path_for_deployment(tmp_path, IDENTITY["deployment_instance_id"]), IDENTITY["deployment_instance_id"])
    CaseShellRepository(database).create({"case_id": CASE_ID, "case_name": "SYNTHETIC", "case_summary": "SYNTHETIC", "source_id": "SYNTHETIC-ASSET-SOURCE", "parse_task_id": "SYNTHETIC-ASSET-TASK"})
    CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    CaseDraftRepository(database).save({"case_id": CASE_ID, "report": copy.deepcopy(REPORT), "asset_refs": [], "field_states": {}})
    services = build_workbench_services(database)
    lease = services.leases.acquire(CASE_ID, IDENTITY)
    return database, services, lease


def test_upload_refresh_restart_and_opaque_http_contract(asset_context):
    database, services, lease = asset_context
    content = png_bytes()
    asset = services.assets.upload_image(CASE_ID, "SYNTHETIC-front.png", content, lease["lease_id"], lease["lease_token"])
    assert asset["asset_id"].startswith("asset-")
    assert "case_id" not in asset and "path" not in json.dumps(asset)
    assert asset["content_status"] == "available"
    assert services.assets.read_image(CASE_ID, asset["asset_id"])[0] == content

    restarted = build_workbench_services(WorkbenchDatabase(database.database_path, database.deployment_instance_id))
    listed = restarted.assets.list_images(CASE_ID)
    assert listed["items"][0]["asset_id"] == asset["asset_id"]
    assert listed["items"][0]["content_status"] == "available"
    assert restarted.assets.read_image(CASE_ID, asset["asset_id"])[0] == content

    from app.main import app
    from app.controllers import case_asset_controller
    with patch.object(case_asset_controller, "get_workbench_services", return_value=services):
        client = TestClient(app)
        response = client.post(
            f"/api/v1/workbench/cases/{CASE_ID}/assets",
            files={"photo": ("SYNTHETIC-api.png", content, "image/png")},
            data={"lease_id": lease["lease_id"], "lease_token": lease["lease_token"]},
        )
        assert response.status_code == 200
        assert "case_id" not in response.text and "assets" not in response.text
        binary = client.get(f"/api/v1/workbench/cases/{CASE_ID}/assets/{response.json()['data']['asset_id']}")
        assert binary.status_code == 200 and binary.content == content


def test_signature_extension_and_size_limits_are_enforced(asset_context):
    _, services, lease = asset_context
    args = (CASE_ID, lease["lease_id"], lease["lease_token"])
    with pytest.raises(WorkbenchPersistenceError) as extension:
        services.assets.upload_image(args[0], "SYNTHETIC-fake.jpg", png_bytes(), args[1], args[2])
    assert extension.value.code == "ASSET_IMAGE_INVALID"
    with pytest.raises(WorkbenchPersistenceError) as format_error:
        services.assets.upload_image(args[0], "SYNTHETIC-file.txt", b"SYNTHETIC", args[1], args[2])
    assert format_error.value.code == "ASSET_IMAGE_FORMAT_INVALID"
    with pytest.raises(WorkbenchPersistenceError) as too_large:
        services.assets.upload_image(args[0], "SYNTHETIC-large.png", b"0" * (10 * 1024 * 1024 + 1), args[1], args[2])
    assert too_large.value.code == "ASSET_IMAGE_TOO_LARGE"


def test_asset_missing_or_corrupt_is_not_silently_read(asset_context):
    _, services, lease = asset_context
    asset = services.assets.upload_image(CASE_ID, "SYNTHETIC-photo.png", png_bytes(), lease["lease_id"], lease["lease_token"])
    suffix = asset["metadata"]["extension"]
    path = services.assets.storage.path_for(CASE_ID, asset["asset_id"], suffix)
    path.write_bytes(b"SYNTHETIC-corrupt")
    assert services.assets.list_images(CASE_ID)["items"][0]["content_status"] == "corrupt"
    with pytest.raises(WorkbenchPersistenceError) as error:
        services.assets.read_image(CASE_ID, asset["asset_id"])
    assert error.value.code == "ASSET_CONTENT_CORRUPT"
    path.unlink()
    assert services.assets.list_images(CASE_ID)["items"][0]["content_status"] == "missing"


def test_asset_refs_require_lease_revision_and_release_content(asset_context):
    _, services, lease = asset_context
    first = services.assets.upload_image(CASE_ID, "SYNTHETIC-first.png", png_bytes(), lease["lease_id"], lease["lease_token"])
    draft = CaseDraftRepository(services.database).get(CASE_ID)
    draft["asset_refs"] = [{key: first[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")}]
    draft["report"]["attachments"]["photo_ids"] = [first["asset_id"]]
    saved = services.lifecycle.save_draft(draft, draft["revision"], None, None, IDENTITY, lease["lease_id"], lease["lease_token"])
    assert saved["draft_save_status"]["status"] == "saved"

    stale = copy.deepcopy(saved["draft"])
    current = CaseDraftRepository(services.database).get(CASE_ID)
    second = services.assets.upload_image(CASE_ID, "SYNTHETIC-second.png", png_bytes((80, 90, 100)), lease["lease_id"], lease["lease_token"])
    current["asset_refs"].append({key: second[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")})
    current["report"]["attachments"]["photo_ids"].append(second["asset_id"])
    expanded = services.lifecycle.save_draft(current, current["revision"], None, None, IDENTITY, lease["lease_id"], lease["lease_token"])
    assert expanded["draft_save_status"]["status"] == "saved"

    stale["asset_refs"] = stale["asset_refs"][:1]
    stale["report"]["attachments"]["photo_ids"] = [first["asset_id"]]
    stale_result = services.lifecycle.save_draft(stale, stale["revision"], None, None, IDENTITY, lease["lease_id"], lease["lease_token"])
    assert stale_result["draft_save_status"] == {"status": "conflict", "error_code": "REVISION_CONFLICT"}
    assert {item["asset_id"] for item in services.assets.list_images(CASE_ID)["items"]} == {first["asset_id"], second["asset_id"]}

    current = CaseDraftRepository(services.database).get(CASE_ID)
    current["asset_refs"] = []
    current["report"]["attachments"]["photo_ids"] = []
    services.lifecycle.save_draft(current, current["revision"], None, None, IDENTITY, lease["lease_id"], lease["lease_token"])
    assert services.assets.list_images(CASE_ID)["items"] == []
    with pytest.raises(WorkbenchPersistenceError) as inactive:
        services.assets.upload_image(CASE_ID, "SYNTHETIC-no-lease.png", png_bytes(), lease["lease_id"], "SYNTHETIC-WRONG-TOKEN")
    assert inactive.value.code == "LEASE_NOT_ACTIVE"
    assert stale["asset_refs"][0]["asset_id"] == first["asset_id"]


def test_archived_case_asset_save_without_lifecycle_preserves_archive_state(asset_context):
    database, services, lease = asset_context
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET lifecycle = 'archive_verified' WHERE case_id = ?",
            (CASE_ID,),
        )
        connection.execute(
            "UPDATE case_drafts SET lifecycle = 'archive_verified' WHERE case_id = ?",
            (CASE_ID,),
        )

    asset = services.assets.upload_image(
        CASE_ID, "SYNTHETIC-archived-photo.png", png_bytes(), lease["lease_id"], lease["lease_token"],
    )
    draft = CaseDraftRepository(services.database).get(CASE_ID)
    draft.pop("lifecycle")
    draft["asset_refs"] = [{key: asset[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")}]
    draft["report"]["attachments"]["photo_ids"] = [asset["asset_id"]]

    saved = services.lifecycle.save_draft(
        draft, draft["revision"], None, None, IDENTITY, lease["lease_id"], lease["lease_token"],
    )

    assert saved["draft_save_status"]["status"] == "saved"
    assert saved["draft"]["lifecycle"] == "archive_verified"
    assert saved["draft"]["asset_refs"][0]["asset_id"] == asset["asset_id"]


def test_orphan_asset_cleanup_is_graceful(asset_context):
    _, services, lease = asset_context
    asset = services.assets.upload_image(CASE_ID, "SYNTHETIC-orphan.png", png_bytes(), lease["lease_id"], lease["lease_token"])
    with services.database.transaction() as connection:
        connection.execute("UPDATE asset_references SET created_at = '2020-01-01T00:00:00+00:00' WHERE asset_id = ?", (asset["asset_id"],))
    assert services.assets.list_images(CASE_ID)["items"] == []
    api = SimpleNamespace(database=services.database, drafts=CaseDraftRepository(services.database))
    assert _resolve_photo_paths(api, CASE_ID) == []
    assert services.assets.cleanup_orphans() >= 1
    assert services.assets.list_images(CASE_ID)["items"] == []


def test_bound_asset_remains_visible_after_orphan_retention_window(asset_context):
    _, services, lease = asset_context
    asset = services.assets.upload_image(
        CASE_ID, "SYNTHETIC-bound-old.png", png_bytes(),
        lease["lease_id"], lease["lease_token"],
    )
    draft = CaseDraftRepository(services.database).get(CASE_ID)
    draft["asset_refs"] = [
        {key: asset[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")}
    ]
    draft["report"]["attachments"]["photo_ids"] = [asset["asset_id"]]
    saved = services.lifecycle.save_draft(
        draft, draft["revision"], None, None, IDENTITY,
        lease["lease_id"], lease["lease_token"],
    )
    assert saved["draft_save_status"]["status"] == "saved"
    with services.database.transaction() as connection:
        connection.execute(
            "UPDATE asset_references SET created_at = '2020-01-01T00:00:00+00:00' WHERE asset_id = ?",
            (asset["asset_id"],),
        )

    assert [item["asset_id"] for item in services.assets.list_images(CASE_ID)["items"]] == [asset["asset_id"]]


def test_unbound_uploaded_image_blocks_unified_export_resolution(asset_context):
    _, services, lease = asset_context
    services.assets.upload_image(
        CASE_ID, "SYNTHETIC-unbound.png", png_bytes(),
        lease["lease_id"], lease["lease_token"],
    )
    api = SimpleNamespace(
        database=services.database,
        drafts=CaseDraftRepository(services.database),
    )

    with pytest.raises(WorkbenchPersistenceError) as error:
        _resolve_photo_paths(api, CASE_ID)

    assert error.value.code == "PHOTO_ASSETS_NOT_SAVED"


def test_unified_export_photo_resolution_uses_only_asset_ref_order(asset_context):
    _, services, lease = asset_context
    first = services.assets.upload_image(
        CASE_ID, "SYNTHETIC-first.png", png_bytes(),
        lease["lease_id"], lease["lease_token"],
    )
    second = services.assets.upload_image(
        CASE_ID, "SYNTHETIC-second.png", png_bytes((80, 90, 100)),
        lease["lease_id"], lease["lease_token"],
    )
    ordered = [second, first]
    draft = CaseDraftRepository(services.database).get(CASE_ID)
    draft["asset_refs"] = [
        {key: asset[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")}
        for asset in ordered
    ]
    draft["report"]["attachments"]["photo_ids"] = [asset["asset_id"] for asset in ordered]
    saved = services.lifecycle.save_draft(
        draft, draft["revision"], None, None, IDENTITY,
        lease["lease_id"], lease["lease_token"],
    )
    assert saved["draft_save_status"]["status"] == "saved"
    api = SimpleNamespace(
        database=services.database,
        drafts=CaseDraftRepository(services.database),
    )

    paths = _resolve_photo_paths(api, CASE_ID)

    assert [path.stem for path in paths] == [asset["asset_id"] for asset in ordered]
