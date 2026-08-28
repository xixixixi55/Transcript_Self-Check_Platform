"""路径规范化与内容标识的合成数据测试。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.filesystem_identity_repository import (  # noqa: E402
    directory_content_fingerprint,
    normalized_directory_key,
    selected_files_content_fingerprint,
)


def test_directory_key_ignores_trailing_separator_and_dot_segment(tmp_path):
    report = tmp_path / "SYNTHETIC-REPORT"
    report.mkdir()
    (report / "data.json").write_text("fixture", encoding="utf-8")

    assert normalized_directory_key(str(report)) == normalized_directory_key(
        os.path.join(str(report), ".", "")
    )


def test_directory_key_uses_windows_case_semantics(tmp_path):
    report = tmp_path / "Synthetic-Report"
    report.mkdir()
    lower = str(report)
    upper = lower.upper()
    if os.name == "nt":
        assert normalized_directory_key(lower) == normalized_directory_key(upper)
    else:
        pytest.skip("大小写等价只适用于 Windows 文件系统。")


def test_content_fingerprint_changes_with_report_content(tmp_path):
    report = tmp_path / "report"
    report.mkdir()
    source = report / "data.json"
    source.write_text("SYNTHETIC-ONE", encoding="utf-8")
    first = directory_content_fingerprint(report)
    source.write_text("SYNTHETIC-TWO", encoding="utf-8")

    assert directory_content_fingerprint(report) != first


def test_content_fingerprint_rejects_same_size_same_timestamp_byte_change(tmp_path):
    report = tmp_path / "report"
    report.mkdir()
    source = report / "data.json"
    source.write_bytes(b"SYNTHETIC-A")
    first_stat = source.stat()
    first = directory_content_fingerprint(report)
    source.write_bytes(b"SYNTHETIC-B")
    os.utime(source, ns=(first_stat.st_atime_ns, first_stat.st_mtime_ns))

    assert directory_content_fingerprint(report) != first


def test_selected_content_fingerprint_reuses_unchanged_bytes_and_tracks_paths(tmp_path):
    report = tmp_path / "report"
    report.mkdir()
    selected = report / "parser.json"
    unrelated = report / "unrelated.json"
    selected.write_text("SYNTHETIC-ONE", encoding="utf-8")
    unrelated.write_text("SYNTHETIC-ONE", encoding="utf-8")

    first = selected_files_content_fingerprint(str(report), ["parser.json"])
    unrelated.write_text("SYNTHETIC-TWO", encoding="utf-8")
    assert selected_files_content_fingerprint(str(report), ["parser.json"]) == first

    selected.write_text("SYNTHETIC-TWO", encoding="utf-8")
    assert selected_files_content_fingerprint(str(report), ["parser.json"]) != first
    assert selected_files_content_fingerprint(
        str(report), ["parser.json", "unrelated.json"],
    ) != first
