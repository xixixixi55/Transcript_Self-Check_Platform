"""冻结后端入口契约的 SYNTHETIC 子进程冒烟测试。"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "packages" / "backend"
PRODUCTION_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "word_templates"


def _environment(tmp_path: Path, resource_root: Path, *, secret: bool = True) -> dict[str, str]:
    values = os.environ.copy()
    values.update({
        "PYTHONPATH": str(BACKEND_ROOT),
        "BIJI_PORTABLE_MODE": "1",
        "BIJI_RESOURCE_ROOT": str(resource_root),
        "BIJI_APP_DATA_ROOT": str(tmp_path / "SYNTHETIC-appdata"),
    })
    if secret:
        values["BIJI_DESKTOP_SECRET"] = "SYNTHETIC-PORTABLE-SECRET-1234567890"
    else:
        values.pop("BIJI_DESKTOP_SECRET", None)
    return values


def _command(port: int, ready_file: Path) -> list[str]:
    return [
        sys.executable, "-m", "app.portable_entry",
        "--port", str(port), "--ready-file", str(ready_file),
    ]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _resource_root(tmp_path: Path) -> Path:
    root = tmp_path / "SYNTHETIC-program"
    (root / "web" / "assets").mkdir(parents=True)
    (root / "web" / "index.html").write_text(
        "<!doctype html><title>SYNTHETIC portable</title>", encoding="utf-8",
    )
    (root / "web" / "assets" / "SYNTHETIC.js").write_text(
        "// SYNTHETIC fixture", encoding="utf-8",
    )
    shutil.copytree(PRODUCTION_TEMPLATE_ROOT, root / "resources" / "word_templates")
    return root


def test_portable_entry_writes_ready_handshake_and_serves_health(tmp_path: Path) -> None:
    resource_root = _resource_root(tmp_path)
    ready_file = tmp_path / "ready.json"
    port = _free_port()
    process = subprocess.Popen(
        _command(port, ready_file), cwd=BACKEND_ROOT,
        env=_environment(tmp_path, resource_root),
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while not ready_file.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert process.poll() is None, process.stderr.read() if process.stderr else ""
        assert json.loads(ready_file.read_text(encoding="utf-8"))["port"] == port
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            assert json.load(response)["status"] == "ok"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_portable_entry_rejects_missing_secret(tmp_path: Path) -> None:
    result = subprocess.run(
        _command(_free_port(), tmp_path / "ready.json"), cwd=BACKEND_ROOT,
        env=_environment(tmp_path, _resource_root(tmp_path), secret=False),
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert result.stderr.strip() == "RuntimeError"


def test_portable_entry_rejects_missing_web_resources(tmp_path: Path) -> None:
    resource_root = tmp_path / "SYNTHETIC-incomplete-program"
    resource_root.mkdir()
    result = subprocess.run(
        _command(_free_port(), tmp_path / "ready.json"), cwd=BACKEND_ROOT,
        env=_environment(tmp_path, resource_root),
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert not (tmp_path / "ready.json").exists()


def test_portable_entry_rejects_occupied_port(tmp_path: Path) -> None:
    resource_root = _resource_root(tmp_path)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = int(listener.getsockname()[1])
        result = subprocess.run(
            _command(port, tmp_path / "ready.json"), cwd=BACKEND_ROOT,
            env=_environment(tmp_path, resource_root),
            capture_output=True, text=True, timeout=10,
        )
    assert result.returncode == 1
    assert not (tmp_path / "ready.json").exists()
