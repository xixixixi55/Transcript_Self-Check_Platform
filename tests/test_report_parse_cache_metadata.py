"""SYNTHETIC tests for metadata-first Parser cache validation."""

import os
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.report_parser_service import _build_report, parse_report  # noqa: E402
from synthetic_report_builders import (  # noqa: E402
    build_parse_cache_report_tree,
    write_synthetic_json,
)


def _open_counter(data_root: Path):
    original_open = Path.open
    calls: Counter[str] = Counter()

    def counted_open(path: Path, *args, **kwargs):
        try:
            key = path.relative_to(data_root).as_posix()
        except ValueError:
            key = "outside-data"
        calls[key] += 1
        return original_open(path, *args, **kwargs)

    return calls, counted_open


def _parse_twice(root: Path, counted_open):
    output = root / "output"
    with patch("pathlib.Path.open", new=counted_open), \
         patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        first = parse_report(str(root), str(output), compress=False)
        second = parse_report(str(root), str(output), compress=False)
    return first, second


def test_unchanged_cache_hit_does_not_open_dependency_content(tmp_path):
    data_root, candidate, _ = build_parse_cache_report_tree(tmp_path)
    calls, counted_open = _open_counter(data_root)

    first, second = _parse_twice(tmp_path, counted_open)

    assert first["report"] == second["report"]
    assert calls["data_case_info.json"] == 1
    assert calls["data_device_lists.json"] == 1
    assert calls["data_report_info.json"] == 1
    assert calls["JC-SYN-01/Base/device_table.json"] == 1
    assert calls["JC-SYN-01/Base/unrelated.json"] == 0
    assert calls["JC-SYN-01/Base/attachment.html"] == 0


def test_mtime_change_with_same_content_reads_only_changed_dependency(tmp_path):
    data_root, candidate, _ = build_parse_cache_report_tree(tmp_path)
    calls, counted_open = _open_counter(data_root)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    before = candidate.stat()
    os.utime(candidate, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))

    with patch("pathlib.Path.open", new=counted_open), \
         patch("app.services.report_parser_service.detect_winrar_version", return_value=None), \
         patch("app.services.report_parser_service._build_report", wraps=_build_report) as build:
        parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)

    assert build.call_count == 0
    assert calls["data_case_info.json"] == 0
    assert calls["data_device_lists.json"] == 0
    assert calls["data_report_info.json"] == 0
    assert calls["JC-SYN-01/Base/device_table.json"] == 1


def test_changed_dependency_invalidates_and_rebuilds_parser(tmp_path):
    data_root, candidate, _ = build_parse_cache_report_tree(tmp_path)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    candidate.write_text(
        candidate.read_text(encoding="utf-8").replace("SYNTHETIC-MODEL", "SYNTHETIC-MODEL-CHANGED"),
        encoding="utf-8",
    )

    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None), \
         patch("app.services.report_parser_service._build_report", wraps=_build_report) as build:
        result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)

    assert build.call_count == 1
    assert result["report"]["introduction"]["evidence_list"][0]["model"] == "SYNTHETIC-MODEL-CHANGED"


def test_unrelated_json_and_attachment_changes_do_not_invalidate_cache(tmp_path):
    data_root, _, unrelated = build_parse_cache_report_tree(tmp_path)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    unrelated.write_text("SYNTHETIC-NOISE-CHANGED", encoding="utf-8")
    (unrelated.parent / "new-unrelated.json").write_text("SYNTHETIC-NEW", encoding="utf-8")
    (unrelated.parent / "attachment.html").write_text("SYNTHETIC-HTML-CHANGED", encoding="utf-8")

    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None), \
         patch("app.services.report_parser_service._build_report", wraps=_build_report) as build:
        parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)

    assert build.call_count == 0


def test_new_candidate_membership_invalidates_cache(tmp_path):
    data_root, candidate, _ = build_parse_cache_report_tree(tmp_path)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    higher = candidate.with_name("device_metadata.json")
    write_synthetic_json(higher, {"rows": [
        {"c1": "设备名称", "c2": "SYNTHETIC-HIGHER-PHONE"},
        {"c1": "设备型号", "c2": "SYNTHETIC-HIGHER-MODEL"},
        {"c1": "序列号", "c2": "SYNTHETIC-HIGHER-SN"},
    ]})

    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None), \
         patch("app.services.report_parser_service._build_report", wraps=_build_report) as build:
        result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)

    assert build.call_count == 1
    assert result["report"]["introduction"]["evidence_list"][0]["model"]
