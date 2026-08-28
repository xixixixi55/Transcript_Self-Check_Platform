"""第 23 层：生产环境 SPA 托管和本地桌面会话边界。"""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

_COOKIE_NAME = "wenshu_desktop_session"
_RESERVED_PREFIXES = ("api/", "desktop/", "health")


def configure_portable_web(app: FastAPI, web_root: Path, secret: str) -> None:
    """挂载一次性浏览器引导、API 认证和 SPA 文件服务。"""
    if len(secret) < 32:
        raise ValueError("desktop secret must contain at least 32 characters")
    index_path = web_root / "index.html"
    assets_root = web_root / "assets"
    if not index_path.is_file() or not assets_root.is_dir():
        raise RuntimeError("PORTABLE_WEB_RESOURCES_UNAVAILABLE")
    bootstrap_available = True

    @app.middleware("http")
    async def portable_session_boundary(request: Request, call_next) -> Response:
        if request.url.path.startswith("/api/"):
            session = request.cookies.get(_COOKIE_NAME, "")
            if not secrets.compare_digest(session, secret):
                return JSONResponse(
                    status_code=401,
                    content={"detail": {"code": "DESKTOP_SESSION_REQUIRED"}},
                )
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/desktop/bootstrap", include_in_schema=False)
    async def bootstrap_page() -> HTMLResponse:
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>文枢启动中</title>"
            "<p>正在建立安全会话……</p><script src='/desktop/bootstrap.js'></script>",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/desktop/bootstrap.js", include_in_schema=False)
    async def bootstrap_script() -> Response:
        script = """
const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
history.replaceState(null, '', '/desktop/bootstrap');
fetch('/desktop/bootstrap/session', {
  method: 'POST', credentials: 'same-origin',
  headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token})
}).then((response) => {
  if (!response.ok) throw new Error('bootstrap rejected');
  location.replace('/');
}).catch(() => { document.body.textContent = '文枢安全会话建立失败，请关闭后重试。'; });
""".strip()
        return Response(
            content=script, media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/desktop/bootstrap/session", include_in_schema=False)
    async def bootstrap_session(request: Request) -> JSONResponse:
        nonlocal bootstrap_available
        try:
            body = await request.json()
            token = body.get("token", "") if isinstance(body, dict) else ""
        except (ValueError, TypeError):
            token = ""
        if (
            not bootstrap_available or not isinstance(token, str)
            or not secrets.compare_digest(token, secret)
        ):
            raise HTTPException(status_code=401, detail="DESKTOP_BOOTSTRAP_INVALID")
        bootstrap_available = False
        response = JSONResponse({"status": "ok"})
        response.set_cookie(
            _COOKIE_NAME, secret, httponly=True, samesite="strict", path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/assets", StaticFiles(directory=assets_root), name="portable-assets")

    @app.get("/", include_in_schema=False)
    async def portable_index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{requested_path:path}", include_in_schema=False)
    async def portable_spa_fallback(requested_path: str) -> FileResponse:
        normalized = requested_path.replace("\\", "/").lstrip("/")
        if normalized.startswith(_RESERVED_PREFIXES):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (web_root / normalized).resolve()
        try:
            candidate.relative_to(web_root.resolve())
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Not Found") from error
        return FileResponse(candidate if candidate.is_file() else index_path)


__all__ = ["configure_portable_web"]
