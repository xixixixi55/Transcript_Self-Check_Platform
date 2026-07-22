"""Synthetic tests for path normalization and content identities."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.filesystem_identity_repository import (  # noqa: E402
    directory_content_fingerprint,
    normalized_directory_key,
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
