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
from app.controllers.workbench_error_messages_controller import (  # noqa: E402
    message_for_workbench_error,
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

    def fake_runner(executable, rar_paths, output_dir, timeout_seconds, hash_algorithm):
        captured["exe"] = executable
        captured["rar_paths"] = list(rar_paths)
        captured["out"] = output_dir
        captured["timeout"] = timeout_seconds
        captured["hash_algorithm"] = hash_algorithm
        (output_dir / "hash.png").write_bytes(b"SYNTHETIC/PNG")
        return "hash.png"

    result = generate_verification_image([rar], out, runner=fake_runner)
    assert result == "hash.png"
    assert captured["rar_paths"] == [rar]
    assert captured["out"] == out
    assert captured["timeout"] == 121
    assert captured["hash_algorithm"] == "md5"
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
    assert timeout >= 16 * 24 * 60 * 60
    assert timeout <= 30 * 24 * 60 * 60


@pytest.mark.parametrize(
    ("total_bytes", "expected"),
    [
        (23_000_000_000, 230_120),
        (135_000_000_000, 1_350_120),
        (500_000_000_000, 2_592_000),
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
    monkeypatch.setenv("BIJI_HASHMYFILES_TIMEOUT_SECONDS", "9999999")
    assert _hash_timeout_seconds([part]) == 30 * 24 * 60 * 60


def test_hash_timeout_invalid_override_falls_back_to_size_budget(monkeypatch):
    class SizedPart:
        def stat(self):
            return type("Stat", (), {"st_size": 23_000_000_000})()

    monkeypatch.setenv("BIJI_HASHMYFILES_TIMEOUT_SECONDS", "invalid")
    assert _hash_timeout_seconds([SizedPart()]) == 230_120


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

    def fake_capture(executable, rar_paths, output_path, timeout_seconds, hash_algorithm):
        captured.update({
            "executable": executable, "rar_paths": rar_paths,
            "timeout": timeout_seconds,
            "hash_algorithm": hash_algorithm,
        })
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC")

    with patch.object(
        hashmyfiles_repository, "_capture_hashmyfiles_window", side_effect=fake_capture,
    ):
        name = run_hashmyfiles(exe, [rar1, rar2], out, 60)

    assert name == "hash-verification.png"
    assert captured == {
        "executable": exe, "rar_paths": [rar1, rar2], "timeout": 60,
        "hash_algorithm": "md5",
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

    def failed_capture(executable, rar_paths, output_path, timeout_seconds, hash_algorithm):
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


@pytest.mark.parametrize(
    (
        "algorithm", "column", "length", "column_width", "window_width",
        "md5_enabled", "sha1_enabled", "sha256_enabled",
    ),
    [
        ("md5", 1, 32, 312, 787, "1", "0", "0"),
        ("sha1", 2, 40, 384, 859, "0", "1", "0"),
        ("sha256", 4, 64, 600, 1075, "0", "0", "1"),
    ],
)
def test_capture_passes_selected_hash_configuration(
    tmp_path, algorithm, column, length, column_width, window_width,
    md5_enabled, sha1_enabled, sha256_enabled,
):
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
            '{"status": "succeeded", "item_count": 1, "rows": [{"filename": "case.part1.rar", '
            f'"hash_value": "{"a" * length}", "size_bytes": "13"}}]}}',
            encoding="utf-8-sig",
        )
        return type("Completed", (), {"returncode": 0})()

    with patch.object(hashmyfiles_repository.subprocess, "run", side_effect=fake_run):
        hashmyfiles_repository._capture_hashmyfiles_window(
            exe, [rar], output, 30, algorithm,
        )

    assert captured["executable"] == str(exe)
    assert captured["files"] == [str(rar)]
    assert captured["hash_arguments"] == [
        "/MD5", md5_enabled, "/SHA1", sha1_enabled, "/CRC32", "0",
        "/SHA256", sha256_enabled, "/SHA512", "0", "/SHA384", "0",
    ]
    assert captured["hash_column_index"] == column
    assert captured["hash_digest_length"] == length
    assert captured["hash_column_width"] == column_width
    assert captured["window_width"] == window_width
    assert captured["capture_grace_seconds"] == 30
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    ("error_code", "expected_message"),
    [
        ("HASHMYFILES_LAUNCH_FAILED", "HashMyFiles 无法启动。"),
        ("HASHMYFILES_TIMEOUT", "HashMyFiles 校验未在规定时间内完成。"),
        ("HASHMYFILES_WINDOW_UNRESPONSIVE", "HashMyFiles 窗口持续无响应。"),
        ("HASHMYFILES_RUN_FAILED", "HashMyFiles 校验执行失败。"),
        ("HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验已完成，但截图生成失败。"),
    ],
)
def test_capture_preserves_structured_failure_code(
    tmp_path, error_code, expected_message,
):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "SYNTHETIC.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")

    def fake_run(args, **kwargs):
        result_path = Path(args[-1])
        result_path.write_text(
            hashmyfiles_repository.json.dumps({
                "status": "failed", "stage": "synthetic", "error_code": error_code,
            }),
            encoding="utf-8-sig",
        )
        return type("Completed", (), {"returncode": 1})()

    with (
        patch.object(hashmyfiles_repository.subprocess, "run", side_effect=fake_run),
        pytest.raises(HashMyFilesError) as error,
    ):
        hashmyfiles_repository._capture_hashmyfiles_window(
            exe, [rar], tmp_path / "hash-verification.png", 30, "md5",
        )

    assert error.value.code == error_code
    assert error.value.args[0] == expected_message


def test_capture_maps_outer_process_timeout_to_hash_timeout(tmp_path):
    exe = tmp_path / "HashMyFiles.exe"
    rar = tmp_path / "SYNTHETIC.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")

    with (
        patch.object(
            hashmyfiles_repository.subprocess,
            "run",
            side_effect=hashmyfiles_repository.subprocess.TimeoutExpired("powershell", 75),
        ),
        pytest.raises(HashMyFilesError) as error,
    ):
        hashmyfiles_repository._capture_hashmyfiles_window(
            exe, [rar], tmp_path / "hash-verification.png", 30, "md5",
        )

    assert error.value.code == "HASHMYFILES_TIMEOUT"
    assert error.value.args[0] == "HashMyFiles 校验未在规定时间内完成。"


@pytest.mark.skipif(sys.platform != "win32", reason="Native HashMyFiles capture is Windows-only")
def test_real_capture_script_returns_structured_launch_failure(tmp_path):
    rar = tmp_path / "SYNTHETIC.part1.rar"
    rar.write_bytes(b"SYNTHETIC/RAR")

    with pytest.raises(HashMyFilesError) as error:
        hashmyfiles_repository._capture_hashmyfiles_window(
            tmp_path / "missing-HashMyFiles.exe",
            [rar],
            tmp_path / "hash-verification.png",
            30,
            "md5",
        )

    assert error.value.code == "HASHMYFILES_LAUNCH_FAILED"
    assert error.value.args[0] == "HashMyFiles 无法启动。"


@pytest.mark.parametrize(
    ("error_code", "expected_message"),
    [
        (
            "HASHMYFILES_TIMEOUT",
            "HashMyFiles 校验未在规定时间内完成，目标磁盘可能繁忙，请稍后重试或选择其他磁盘。",
        ),
        (
            "HASHMYFILES_WINDOW_UNRESPONSIVE",
            "HashMyFiles 校验已完成，但窗口持续无响应，无法读取和截图。",
        ),
        (
            "HASHMYFILES_RESULT_INVALID",
            "HashMyFiles 已结束，但校验结果缺失或不完整，请重试。",
        ),
        (
            "HASHMYFILES_SCREENSHOT_FAILED",
            "HashMyFiles 校验已完成，但窗口截图生成失败，请重试。",
        ),
    ],
)
def test_hashmyfiles_public_messages_distinguish_failure_stage(
    error_code, expected_message,
):
    assert message_for_workbench_error(error_code) == expected_message


def test_capture_script_uses_native_window_and_only_three_visible_columns():
    script = hashmyfiles_repository._CAPTURE_SCRIPT
    assert "PrintWindow" in script
    assert "SysListView32" in script
    assert "ClearSelection" in script
    assert "ReadListText" in script
    assert "CreateKillOnCloseJob" in script
    assert "WaitForExit(3000)" in script
    assert "@{ column = 0; width = 300 }" in script
    assert "[int]$payload.hash_column_index" in script
    assert "[int]$payload.hash_column_width" in script
    assert "@{ column = 11; width = 145 }" in script
    assert "[int]$payload.window_width" in script
    assert "DrawString" not in script
    assert "LiveHashes=0" in script
    assert "LiveHashes=1" not in script
    assert "SendMessageTimeout(window, message, wParam, lParam, 2, 5000" in script
    assert "Start-Sleep -Milliseconds 500" in script
    assert "TryGetItemCount" in script
    assert "HASHMYFILES_WINDOW_UNRESPONSIVE" in script
    assert "status = 'failed'" in script
