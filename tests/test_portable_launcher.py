"""SYNTHETIC tests for the portable launcher lifecycle."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "launcher"))

from portable_launcher import (  # noqa: E402
    LauncherError,
    LauncherPaths,
    SingleInstance,
    attach_kill_on_close_job,
    build_backend_environment,
    open_desktop_browser,
    resolve_launcher_paths,
    validate_program_integrity,
    wait_until_ready,
)


class FakeProcess:
    def __init__(self, returncode=None, pid=43210):
        self.returncode = returncode
        self.pid = pid

    def poll(self):
        return self.returncode


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_resolve_launcher_paths_separates_program_and_data(tmp_path: Path) -> None:
    executable = tmp_path / "程序" / "文枢.exe"
    paths = resolve_launcher_paths(
        {"LOCALAPPDATA": str(tmp_path / "local")}, executable=executable,
    )
    assert paths.resource_root == tmp_path / "程序"
    assert paths.backend_executable == tmp_path / "程序" / "runtime" / "backend" / "backend.exe"
    assert paths.app_data_root == tmp_path / "local" / "文枢"


def test_single_instance_rejects_concurrent_lock(tmp_path: Path) -> None:
    first = SingleInstance(tmp_path / "data" / "launcher.lock")
    second = SingleInstance(tmp_path / "data" / "launcher.lock")
    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()
    assert second.acquire() is True
    second.release()


def test_backend_environment_contains_private_roots_and_secret(tmp_path: Path) -> None:
    paths = LauncherPaths(
        resource_root=tmp_path / "program",
        app_data_root=tmp_path / "data",
        backend_executable=tmp_path / "program" / "runtime" / "backend" / "backend.exe",
        log_root=tmp_path / "data" / "logs",
        lock_file=tmp_path / "data" / "launcher.lock",
    )
    values = build_backend_environment(paths, "SYNTHETIC-SECRET")
    assert values["BIJI_PORTABLE_MODE"] == "1"
    assert values["BIJI_RESOURCE_ROOT"] == str(paths.resource_root)
    assert values["BIJI_APP_DATA_ROOT"] == str(paths.app_data_root)
    assert values["BIJI_DESKTOP_SECRET"] == "SYNTHETIC-SECRET"


def test_backend_environment_removes_development_runtime_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIJI_NODE_PATH", "SYNTHETIC-untrusted-node")
    monkeypatch.setenv("BIJI_OFFICECLI_ENTRY", "SYNTHETIC-untrusted-officecli")
    paths = resolve_launcher_paths(
        {"LOCALAPPDATA": str(tmp_path / "local")},
        executable=tmp_path / "program" / "文枢.exe",
    )
    values = build_backend_environment(paths, "SYNTHETIC-SECRET")
    assert "BIJI_NODE_PATH" not in values
    assert "BIJI_OFFICECLI_ENTRY" not in values


def test_wait_until_ready_requires_matching_handshake(tmp_path: Path) -> None:
    ready = tmp_path / "ready.json"
    secret = "SYNTHETIC-SECRET"
    proof = hmac.new(secret.encode(), b"43210:32123", hashlib.sha256).hexdigest()
    ready.write_text(json.dumps({
        "status": "ready", "port": 32123, "pid": 43210, "proof": proof,
    }), encoding="utf-8")
    assert wait_until_ready(
        FakeProcess(), ready, secret, expected_port=32123, timeout_seconds=0.2,
        opener=lambda *_args, **_kwargs: FakeResponse(),
    ) == 32123


def test_wait_until_ready_rejects_forged_handshake(tmp_path: Path) -> None:
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({
        "status": "ready", "port": 32123, "pid": 43210, "proof": "0" * 64,
    }), encoding="utf-8")
    with pytest.raises(LauncherError, match="启动超时"):
        wait_until_ready(
            FakeProcess(), ready, "SYNTHETIC-SECRET", timeout_seconds=0.15,
            opener=lambda *_args, **_kwargs: FakeResponse(),
        )


def test_wait_until_ready_reports_early_backend_exit(tmp_path: Path) -> None:
    with pytest.raises(LauncherError, match="后端启动失败"):
        wait_until_ready(
            FakeProcess(1), tmp_path / "missing", "SYNTHETIC-SECRET",
            timeout_seconds=0.1,
        )


def test_browser_bootstrap_url_contains_encoded_one_time_secret() -> None:
    captured = []
    open_desktop_browser(32123, "SYNTHETIC secret/+", browser_open=lambda url: captured.append(url))
    assert captured == [
        "http://127.0.0.1:32123/desktop/bootstrap#token=SYNTHETIC%20secret%2F%2B",
    ]


def test_program_integrity_rejects_missing_modified_and_unknown_files(tmp_path: Path) -> None:
    program = tmp_path / "program"
    trusted = program / "runtime" / "backend" / "backend.exe"
    trusted.parent.mkdir(parents=True)
    trusted.write_bytes(b"SYNTHETIC/TRUSTED")
    paths = resolve_launcher_paths(
        {"LOCALAPPDATA": str(tmp_path / "local")}, executable=program / "文枢.exe",
    )
    expected = {"runtime/backend/backend.exe": hashlib.sha256(trusted.read_bytes()).hexdigest()}
    validate_program_integrity(paths, expected_files=expected)
    trusted.write_bytes(b"SYNTHETIC/MODIFIED")
    with pytest.raises(LauncherError, match="校验失败"):
        validate_program_integrity(paths, expected_files=expected)
    trusted.write_bytes(b"SYNTHETIC/TRUSTED")
    (program / "SYNTHETIC-unknown.txt").write_text("SYNTHETIC", encoding="utf-8")
    with pytest.raises(LauncherError, match="未知文件"):
        validate_program_integrity(paths, expected_files=expected)


def test_launcher_rejects_overlapping_program_and_data_roots(tmp_path: Path) -> None:
    program = tmp_path / "program"
    with pytest.raises(LauncherError, match="不能重叠"):
        resolve_launcher_paths(
            {"BIJI_APP_DATA_ROOT": str(program / "data")},
            executable=program / "文枢.exe",
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object contract")
def test_kill_on_close_job_terminates_owned_process() -> None:
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    job = attach_kill_on_close_job(process)
    assert job is not None
    assert process.poll() is None
    job.close()
    process.wait(timeout=5)
