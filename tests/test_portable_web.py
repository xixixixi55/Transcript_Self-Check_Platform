"""便携式同源托管与身份验证的 SYNTHETIC 集成测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.main import create_app  # noqa: E402

SECRET = "SYNTHETIC-DESKTOP-SECRET-0123456789ABCDEF"


def portable_app(tmp_path: Path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>SYNTHETIC/INDEX</html>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("SYNTHETIC/JS", encoding="utf-8")
    app = create_app(
        enable_archive_runtime=False,
        portable_web_root=web,
        desktop_secret=SECRET,
    )

    return app


def test_portable_serves_index_assets_and_spa_fallback(tmp_path: Path) -> None:
    client = TestClient(portable_app(tmp_path))
    assert client.get("/").text == "<html>SYNTHETIC/INDEX</html>"
    assert client.get("/assets/app.js").text == "SYNTHETIC/JS"
    assert client.get("/cases/SYNTHETIC").text == "<html>SYNTHETIC/INDEX</html>"
    assert client.get("/api/v1/not-found").status_code == 401


def test_portable_api_requires_one_use_desktop_bootstrap(tmp_path: Path) -> None:
    client = TestClient(portable_app(tmp_path), follow_redirects=False)
    denied = client.get("/api/v1/SYNTHETIC-not-found")
    assert denied.status_code == 401
    assert denied.json()["detail"]["code"] == "DESKTOP_SESSION_REQUIRED"

    page = client.get("/desktop/bootstrap")
    assert SECRET not in page.text
    assert "bootstrap.js" in page.text
    script = client.get("/desktop/bootstrap.js")
    assert "history.replaceState" in script.text
    invalid = client.post("/desktop/bootstrap/session", json={"token": "SYNTHETIC-WRONG"})
    assert invalid.status_code == 401
    accepted = client.post("/desktop/bootstrap/session", json={"token": SECRET})
    assert accepted.status_code == 200
    assert "HttpOnly" in accepted.headers["set-cookie"]
    assert "SameSite=strict" in accepted.headers["set-cookie"]
    assert client.get("/api/v1/SYNTHETIC-not-found").status_code == 404
    replay = client.post("/desktop/bootstrap/session", json={"token": SECRET})
    assert replay.status_code == 401


def test_portable_responses_set_security_headers(tmp_path: Path) -> None:
    response = TestClient(portable_app(tmp_path)).get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "object-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"


def test_portable_rejects_missing_web_resources(tmp_path: Path) -> None:
    try:
        create_app(
            enable_archive_runtime=False,
            portable_web_root=tmp_path / "missing",
            desktop_secret=SECRET,
        )
    except RuntimeError as error:
        assert str(error) == "PORTABLE_WEB_RESOURCES_UNAVAILABLE"
    else:
        raise AssertionError("missing web resources were accepted")
