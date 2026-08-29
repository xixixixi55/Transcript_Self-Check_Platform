"""Windows 便携发行版的冻结后端入口。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import uvicorn


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ready-file", required=True)
    return parser


async def _serve(port: int, ready_file: Path) -> int:
    from app.repository.runtime.runtime_paths import get_runtime_paths

    if os.environ.get("BIJI_PORTABLE_MODE") != "1":
        raise RuntimeError("PORTABLE_MODE_REQUIRED")
    secret = os.environ.get("BIJI_DESKTOP_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("DESKTOP_SECRET_REQUIRED")
    paths = get_runtime_paths()
    paths.ensure_user_directories()
    from app.main import create_app

    app = create_app(portable_web_root=paths.web_root, desktop_secret=secret)
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, access_log=False, log_level="warning",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    serve_task = asyncio.create_task(server.serve())
    while not server.started and not serve_task.done():
        await asyncio.sleep(0.02)
    if serve_task.done():
        return 1
    actual_port = int(server.servers[0].sockets[0].getsockname()[1])
    identity = f"{os.getpid()}:{actual_port}".encode("ascii")
    proof = hmac.new(secret.encode("utf-8"), identity, hashlib.sha256).hexdigest()
    payload = json.dumps({
        "status": "ready", "port": actual_port, "pid": os.getpid(), "proof": proof,
    })
    temporary = ready_file.with_suffix(ready_file.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, ready_file)
    await serve_task
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_serve(args.port, Path(args.ready_file)))
    except Exception as error:
        print(type(error).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
