"""定向测试：HashMyFiles 校验截图生成接口与可用性门控。"""

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
from app.services.hashmyfiles_service import (  # noqa: E402
    _hash_timeout_seconds,
    generate_verification_image,
)


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


def test_generate_verification_image_unavailable_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "missing.exe"))
    with patch.object(hashmyfiles_repository, "_DEFAULT_TOOL_PATH", tmp_path / "missing-default.exe"):
        rar = tmp_path / "case.part1.rar"
        rar.write_bytes(b"SYNTHETIC/RAR")
        with pytest.raises(HashMyFilesError) as error:
            generate_verification_image([rar], tmp_path / "out")
        assert error.value.code == "HASHMYFILES_UNAVAILABLE"


def test_generate_verification_image_invokes_runner_and_returns_filename(monkeypatch, tmp_path):
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
        (output_dir / "hash.png").write_bytes(b"SYNTHETIC/PNG")
        return "hash.png"

    result = generate_verification_image([rar], out, runner=fake_runner)
    assert result == "hash.png"
    assert captured["rar_paths"] == [rar]
    assert captured["out"] == out
    assert captured["timeout"] == 121
    assert (out / "hash.png").exists()


def test_generate_verification_image_no_parts_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BIJI_HASHMYFILES_PATH", str(tmp_path / "HashMyFiles.exe"))
    with pytest.raises(HashMyFilesError) as error:
        generate_verification_image([], tmp_path / "out")
    assert error.value.code == "HASHMYFILES_NO_PARTS"


def test_hash_timeout_scales_for_three_maximum_size_parts(monkeypatch):
    class SizedPart:
        def stat(self):
            return type("Stat", (), {"st_size": 45 * 1024**3})()

    monkeypatch.delenv("BIJI_HASHMYFILES_TIMEOUT_SECONDS", raising=False)
    timeout = _hash_timeout_seconds([SizedPart(), SizedPart(), SizedPart()])
    assert timeout >= 8 * 60 * 60
    assert timeout <= 10 * 60 * 60


@pytest.mark.parametrize(
    ("total_bytes", "expected"),
    [
        (23_000_000_000, 4_720),
        (135_000_000_000, 27_120),
        (500_000_000_000, 36_000),
    ],
)
def test_hash_timeout_uses_exact_hdd_budget(monkeypatch, total_bytes, expected):
    class SizedPart:
        def stat(self):
            return type("Stat", (), {"st_size": total_bytes})()

    monkeypatch.delenv("BIJI_HASHMYFILES_TIMEOUT_SECONDS", raising=False)
    assert _hash_timeout_seconds([SizedPart()]) == expected


def test_hash_timeout_allows_bounded_deployment_override(monkeypatch, tmp_path):
    part = tmp_path / "SYNTHETIC.part1.rar"
    part.write_bytes(b"SYNTHETIC/RAR")
    monkeypatch.setenv("BIJI_HASHMYFILES_TIMEOUT_SECONDS", "900")
    assert _hash_timeout_seconds([part]) == 900


def test_hash_timeout_caps_deployment_override_for_hdd_budget(monkeypatch, tmp_path):
    part = tmp_path / "SYNTHETIC.part1.rar"
    part.write_bytes(b"SYNTHETIC/RAR")
    monkeypatch.setenv("BIJI_HASHMYFILES_TIMEOUT_SECONDS", "999999")
    assert _hash_timeout_seconds([part]) == 10 * 60 * 60


def test_run_hashmyfiles_publishes_real_window_capture_and_removes_legacy_html(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar1 = tmp_path / "case.part1.rar"
    rar2 = tmp_path / "case.part2.rar"
    rar1.write_bytes(b"SYNTHETIC/RAR-1")
    rar2.write_bytes(b"SYNTHETIC/RAR-2")
    out = tmp_path / "out"
    out.mkdir()
    (out / "hash-verification.html").write_text("SYNTHETIC/LEGACY")
    captured = {}

    def fake_capture(executable, rar_paths, output_path, timeout_seconds):
        captured.update({
            "executable": executable, "rar_paths": rar_paths,
            "timeout": timeout_seconds,
        })
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC")

    with patch.object(
        hashmyfiles_repository, "_capture_hashmyfiles_window", side_effect=fake_capture,
    ):
        name = run_hashmyfiles(exe, [rar1, rar2], out, 60)

    assert name == "hash-verification.png"
    assert captured == {
        "executable": exe, "rar_paths": [rar1, rar2], "timeout": 60,
    }
    assert (out / name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not list(out.glob("*.html"))


def test_failed_screenshot_preserves_previous_artifacts_and_cleans_temporary_files(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    out = tmp_path / "out"
    out.mkdir()
    previous_png = b"\x89PNG\r\n\x1a\nPREVIOUS"
    (out / "hash-verification.png").write_bytes(previous_png)
    (out / "hash-verification.html").write_text("SYNTHETIC/LEGACY")

    def failed_capture(executable, rar_paths, output_path, timeout_seconds):
        output_path.write_bytes(b"PARTIAL")
        raise HashMyFilesError(
            "HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验截图生成失败。",
        )

    with (
        patch.object(
            hashmyfiles_repository, "_capture_hashmyfiles_window", side_effect=failed_capture,
        ),
        pytest.raises(HashMyFilesError) as error,
    ):
        run_hashmyfiles(exe, [rar], out)

    assert error.value.code == "HASHMYFILES_SCREENSHOT_FAILED"
    assert (out / "hash-verification.png").read_bytes() == previous_png
    assert (out / "hash-verification.html").is_file()
    assert not list(out.glob(".biji-hashmyfiles-*"))


def test_missing_screenshot_does_not_replace_previous_png(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    out = tmp_path / "out"
    out.mkdir()
    previous_png = b"\x89PNG\r\n\x1a\nPREVIOUS"
    (out / "hash-verification.png").write_bytes(previous_png)

    with (
        patch.object(hashmyfiles_repository, "_capture_hashmyfiles_window", return_value=None),
        pytest.raises(HashMyFilesError) as error,
    ):
        run_hashmyfiles(exe, [rar], out)

    assert error.value.code == "HASHMYFILES_SCREENSHOT_MISSING"
    assert (out / "hash-verification.png").read_bytes() == previous_png


def test_capture_passes_real_executable_files_and_md5_only_configuration(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "case.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")
    output = tmp_path / "hash-verification.png"
    captured = {}

    def fake_run(args, **kwargs):
        payload_path, output_path, result_path = map(Path, args[-3:])
        captured.update(hashmyfiles_repository.json.loads(payload_path.read_text(encoding="utf-8")))
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC")
        result_path.write_text(
            '{"item_count": 1, "rows": [{"filename": "case.part1.rar", '
            '"md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "size_bytes": "13"}]}',
            encoding="utf-8-sig",
        )
        return type("Completed", (), {"returncode": 0})()

    with patch.object(hashmyfiles_repository.subprocess, "run", side_effect=fake_run):
        hashmyfiles_repository._capture_hashmyfiles_window(exe, [rar], output, 30)

    assert captured["executable"] == str(exe)
    assert captured["files"] == [str(rar)]
    assert captured["hash_arguments"] == [
        "/MD5", "1", "/SHA1", "0", "/CRC32", "0",
        "/SHA256", "0", "/SHA512", "0", "/SHA384", "0",
    ]
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_capture_script_uses_native_window_and_only_three_visible_columns():
    script = hashmyfiles_repository._CAPTURE_SCRIPT
    assert "PrintWindow" in script
    assert "SysListView32" in script
    assert "ClearSelection" in script
    assert "ReadListText" in script
    assert "CreateKillOnCloseJob" in script
    assert "WaitForExit(3000)" in script
    assert "[IntPtr]0, [IntPtr]300" in script
    assert "[IntPtr]1, [IntPtr]300" in script
    assert "[IntPtr]11, [IntPtr]145" in script
    assert "DrawString" not in script
