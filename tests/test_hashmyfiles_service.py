"""定向测试：HashMyFiles 校验 HTML 生成接口与可用性门控。"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import hashmyfiles_repository  # noqa: E402
from app.repository.hashmyfiles_repository import (  # noqa: E402
    HashMyFilesError,
    resolve_hashmyfiles,
    run_hashmyfiles,
)
from app.services.hashmyfiles_service import generate_verification_html  # noqa: E402


def test_resolve_hashmyfiles_uses_override(monkeypatch, tmp_path):
    fake = tmp_path / "HashMyFiles.exe"
    fake.write_bytes(b"SYNTHETIC-EXE")
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(fake))
    assert resolve_hashmyfiles() == fake


def test_resolve_hashmyfiles_missing_override_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "missing.exe"))
    with patch.object(hashmyfiles_repository, "_DEFAULT_TOOL_PATH", tmp_path / "missing-default.exe"):
        assert resolve_hashmyfiles() is None


def test_resolve_hashmyfiles_falls_back_to_bundled_default(monkeypatch, tmp_path):
    default = tmp_path / "HashMyFiles.exe"
    default.write_bytes(b"SYNTHETIC-EXE")
    monkeypatch.delenv("BIJI_HASHMYFILES_PATH", raising=False)
    with patch.object(hashmyfiles_repository, "_DEFAULT_TOOL_PATH", default):
        assert resolve_hashmyfiles() == default


def test_generate_verification_html_unavailable_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "missing.exe"))
    with patch.object(hashmyfiles_repository, "_DEFAULT_TOOL_PATH", tmp_path / "missing-default.exe"):
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


class _FakeCompleted:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_run_hashmyfiles_builds_files_and_shtml_arguments(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar1 = tmp_path / "case.part1.rar"
    rar2 = tmp_path / "case.part2.rar"
    for rar in (rar1, rar2):
        rar.write_bytes(b"SYNTHETIC/RAR")
    out = tmp_path / "out"

    captured = {}

    def fake_invoke(executable, args, timeout_seconds):
        captured["exe"] = executable
        captured["args"] = args
        captured["timeout"] = timeout_seconds
        out.mkdir(parents=True, exist_ok=True)
        (out / "hash-verification.html").write_text("<html/>")
        return _FakeCompleted(0)

    with patch.object(hashmyfiles_repository, "_invoke", side_effect=fake_invoke):
        name = run_hashmyfiles(exe, [rar1, rar2], out, 60)

    assert name == "hash-verification.html"
    assert captured["exe"] == exe
    assert captured["timeout"] == 60
    args = captured["args"]
    assert args[0] == "/files"
    assert str(rar1) in args and str(rar2) in args
    assert "/MD5" in args and "1" in args
    assert "/SHA1" in args and "0" in args
    assert "/shtml" in args
    assert str(out / "hash-verification.html") in args


def test_run_hashmyfiles_raises_on_nonzero_returncode(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    out = tmp_path / "out"
    with patch.object(hashmyfiles_repository, "_invoke", return_value=_FakeCompleted(1)):
        with pytest.raises(HashMyFilesError) as error:
            run_hashmyfiles(exe, [rar], out)
    assert error.value.code == "HASHMYFILES_RUN_FAILED"


def test_run_hashmyfiles_raises_when_html_missing(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    out = tmp_path / "out"
    with patch.object(hashmyfiles_repository, "_invoke", return_value=_FakeCompleted(0)):
        with pytest.raises(HashMyFilesError) as error:
            run_hashmyfiles(exe, [rar], out)
    assert error.value.code == "HASHMYFILES_OUTPUT_MISSING"
