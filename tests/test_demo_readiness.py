"""Safe Demo readiness projections using only SYNTHETIC/TEST fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1] / "packages" / "backend"))

from app.main import app  # noqa: E402
from app.repository.demo_readiness_repository import probe_archive_output  # noqa: E402
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.services.demo_readiness_service import build_demo_readiness  # noqa: E402


class SyntheticAuthorizationStore:
    def __init__(self, roots=(), warnings=()):
        self.configured_roots = roots
        self.configuration_warnings = warnings


def _capability(available: bool) -> WinRarCapability:
    return WinRarCapability(
        available=available,
        executable_path=r"C:\SYNTHETIC\SECRET\rar.exe" if available else None,
        executable_name="rar.exe" if available else None,
        version="SYNTHETIC/TEST",
        supports_rar_volumes=available,
        diagnostic_code=None if available else "WINRAR_UNAVAILABLE",
    )


def test_ready_snapshot_does_not_expose_internal_capability_details():
    result = build_demo_readiness(
        SyntheticAuthorizationStore((Path("SYNTHETIC-ROOT"),)),
        r"C:\SYNTHETIC\SECRET\output",
        winrar_probe=lambda: _capability(True),
        output_probe=lambda _root: "ready",
    )

    assert [item["status"] for item in result["items"]] == ["ready"] * 4
    serialized = json.dumps(result, ensure_ascii=False)
    assert "SYNTHETIC-ROOT" not in serialized
    assert "SECRET" not in serialized
    assert "rar.exe" not in serialized
    assert "version" not in serialized


def test_snapshot_uses_stable_safe_fallbacks_for_each_failure():
    result = build_demo_readiness(
        SyntheticAuthorizationStore(),
        r"C:\SYNTHETIC\SECRET\output",
        winrar_probe=lambda: _capability(False),
        output_probe=lambda _root: "unavailable",
    )
    by_key = {item["key"]: item for item in result["items"]}

    assert by_key["source_authorization"]["status"] == "not_configured"
    assert by_key["source_authorization"]["code"] == "DEMO_SOURCE_AUTH_NOT_CONFIGURED"
    assert by_key["winrar"]["code"] == "WINRAR_UNAVAILABLE"
    assert by_key["archive_output"]["code"] == "DEMO_ARCHIVE_OUTPUT_UNAVAILABLE"


def test_snapshot_converts_probe_exceptions_to_unknown_without_exception_text():
    def fail():
        raise RuntimeError(r"SYNTHETIC\SECRET\stack")

    result = build_demo_readiness(
        None, r"C:\SYNTHETIC\SECRET\output",
        winrar_probe=fail,
        output_probe=lambda _root: (_ for _ in ()).throw(PermissionError("SYNTHETIC SECRET")),
    )

    assert [item["status"] for item in result["items"]] == [
        "ready", "unknown", "unknown", "unknown",
    ]
    assert "SECRET" not in json.dumps(result, ensure_ascii=False)


def test_output_probe_is_read_only_and_reports_existing_directory(tmp_path):
    output = tmp_path / "SYNTHETIC-OUTPUT"
    output.mkdir()

    assert probe_archive_output(str(output)) == "ready"
    assert list(output.iterdir()) == []
    assert probe_archive_output(str(output / "missing")) == "unavailable"


def test_readiness_endpoint_uses_versioned_envelope():
    safe = build_demo_readiness(
        SyntheticAuthorizationStore(), "SYNTHETIC",
        winrar_probe=lambda: _capability(False),
        output_probe=lambda _root: "unavailable",
    )
    services = SimpleNamespace(
        sources=SimpleNamespace(
            authorization=SimpleNamespace(store=SyntheticAuthorizationStore()),
        ),
    )
    with patch(
        "app.controllers.demo_readiness_controller.get_workbench_services",
        return_value=services,
    ), patch(
        "app.controllers.demo_readiness_controller.build_demo_readiness",
        return_value=safe,
    ):
        response = TestClient(app).get("/api/v1/demo/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "api_version": "v1", "schema_version": 1, "data": safe,
    }
