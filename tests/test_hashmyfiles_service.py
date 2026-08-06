"""定向测试：HashMyFiles 校验 HTML 生成接口与可用性门控。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.hashmyfiles_repository import (  # noqa: E402
    HashMyFilesError,
    resolve_hashmyfiles,
)
from app.services.hashmyfiles_service import generate_verification_html  # noqa: E402


def test_resolve_hashmyfiles_uses_override(monkeypatch, tmp_path):
    fake = tmp_path / "HashMyFiles.exe"
    fake.write_bytes(b"SYNTHETIC-EXE")
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(fake))
    assert resolve_hashmyfiles() == fake


def test_resolve_hashmyfiles_missing_override_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "missing.exe"))
    assert resolve_hashmyfiles() is None
    monkeypatch.delenv("BIJI_HASHMYFILES_PATH", raising=False)
    assert resolve_hashmyfiles() is None


def test_generate_verification_html_unavailable_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "missing.exe"))
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    with pytest.raises(HashMyFilesError) as error:
        generate_verification_html([rar], tmp_path / "out")
    assert error.value.code == "HASHMYFILES_UNAVAILABLE"


def test_generate_verification_html_invokes_runner_and_returns_filename(monkeypatch, tmp_path):
    fake = tmp_path / "HashMyFiles.exe"
    fake.write_bytes(b"SYNTHETIC-EXE")
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(fake))
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    out = tmp_path / "out"
    captured = {}

    def fake_runner(executable, rar_paths, output_dir, timeout_seconds):
        captured["exe"] = executable
        captured["rar_paths"] = list(rar_paths)
        captured["out"] = output_dir
        captured["timeout"] = timeout_seconds
        (output_dir / "hash.html").write_text("<html/>")
        return "hash.html"

    result = generate_verification_html([rar], out, runner=fake_runner)
    assert result == "hash.html"
    assert captured["rar_paths"] == [rar]
    assert captured["out"] == out
    assert captured["timeout"] == 120
    assert (out / "hash.html").exists()


def test_generate_verification_html_no_parts_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "HashMyFiles.exe"))
    with pytest.raises(HashMyFilesError) as error:
        generate_verification_html([], tmp_path / "out")
    assert error.value.code == "HASHMYFILES_NO_PARTS"
