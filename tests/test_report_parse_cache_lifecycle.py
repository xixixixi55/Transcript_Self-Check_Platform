"""解析器缓存生命周期与安全边界的 SYNTHETIC 测试。"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from synthetic_report_builders import build_parse_cache_report_tree  # noqa: E402
from app.repository.report.report_parse_input_metadata_repository import validate_cached_input_metadata  # noqa: E402
from app.repository.report.report_parse_input_models import DependencyRecord, ReportParseInputError  # noqa: E402
from app.repository.report.report_parse_input_repository import build_report_parse_input_snapshot  # noqa: E402
from app.services.report.report_parser_service import _build_report, parse_report  # noqa: E402
from app.services.report.report_parsing_cache_service import ReportParsingCacheService  # noqa: E402


def test_deleted_selected_candidate_invalidates_cache(tmp_path):
    data_root, candidate, _ = build_parse_cache_report_tree(tmp_path)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    candidate.unlink()

    with patch("app.services.report.report_parser_service.detect_winrar_version", return_value=None), \
         patch("app.services.report.report_parser_service._build_report", wraps=_build_report) as build:
        result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)

    assert build.call_count == 1
    assert result["report"]["introduction"]["evidence_list"][0]["model"] == ""


def test_deleted_core_file_fails_safely_and_does_not_reuse_old_cache(tmp_path):
    data_root, _, _ = build_parse_cache_report_tree(tmp_path)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    (data_root / "data_case_info.json").unlink()

    with patch("app.services.report.report_parser_service.detect_winrar_version", return_value=None), \
         patch("app.services.report.report_parser_service._build_report", wraps=_build_report):
        try:
            parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
        except Exception as error:
            assert str(tmp_path) not in str(error)
        else:
            raise AssertionError("deleted core input must not reuse the old cache")


def test_old_cache_without_dependency_manifest_is_safely_rebuilt(tmp_path):
    build_parse_cache_report_tree(tmp_path)
    snapshot = build_report_parse_input_snapshot(str(tmp_path))
    cache_dir = tmp_path / "output" / "parsed"
    cache_dir.mkdir(parents=True)
    cache_key = snapshot.source_key
    (cache_dir / f"{cache_key}.json").write_text(json.dumps({
        "cache_key": cache_key,
        "cache_version": 7,
        "source_fingerprint": "0" * 64,
        "last_accessed_at": 1,
        "result": {"report": {"old": True}},
    }), encoding="utf-8")

    with patch("app.services.report.report_parser_service.detect_winrar_version", return_value=None):
        result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)

    assert result["report"]["case_number"] == "SYNTHETIC-CACHE-001"


def test_same_directory_requests_share_snapshot_and_parser(tmp_path):
    build_parse_cache_report_tree(tmp_path)
    started = Event()
    release = Event()
    snapshot_calls = []

    from app.services.report import report_parser_service as parser_service
    original_snapshot = parser_service.build_report_parse_input_snapshot

    def slow_snapshot(source_dir):
        snapshot_calls.append(source_dir)
        started.set()
        assert release.wait(timeout=5)
        return original_snapshot(source_dir)

    with patch.object(parser_service, "build_report_parse_input_snapshot", side_effect=slow_snapshot), \
         patch.object(parser_service, "detect_winrar_version", return_value=None), \
         patch.object(parser_service, "_build_report", wraps=_build_report) as build, \
         ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(parse_report, str(tmp_path), str(tmp_path / "output"), False)
        assert started.wait(timeout=5)
        second = pool.submit(parse_report, str(tmp_path), str(tmp_path / "output"), False)
        release.set()
        first_result = first.result(timeout=10)
        second_result = second.result(timeout=10)

    assert first_result["report"] == second_result["report"]
    assert len(snapshot_calls) == 1
    assert build.call_count == 1


def test_cache_clear_during_snapshot_build_blocks_old_manifest_write(tmp_path):
    build_parse_cache_report_tree(tmp_path)
    snapshot = build_report_parse_input_snapshot(str(tmp_path))
    service = ReportParsingCacheService()
    started = Event()
    release = Event()
    cache_dir = tmp_path / "output" / "parsed"

    def delayed_snapshot():
        started.set()
        assert release.wait(timeout=5)
        return snapshot

    def build():
        return {"report": {"case": "SYNTHETIC"}, "cache_version": 7}

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            service.load_or_build,
            str(tmp_path), str(cache_dir), 7, build,
            fingerprint_dir=str(tmp_path / "data"),
            snapshot_builder=delayed_snapshot,
            generation_token=service.current_generation(),
        )
        assert started.wait(timeout=5)
        assert service.clear_all(str(cache_dir)) == 0
        release.set()
        assert future.result(timeout=10)["report"]["case"] == "SYNTHETIC"

    assert not list(cache_dir.glob("*.json"))
    service.load_or_build(
        str(tmp_path), str(cache_dir), 7, build,
        fingerprint_dir=str(tmp_path / "data"),
        snapshot_builder=lambda: snapshot,
        generation_token=service.current_generation(),
    )
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_cache_clear_starts_new_generation_without_waiting_for_old_task(tmp_path):
    build_parse_cache_report_tree(tmp_path)
    service = ReportParsingCacheService()
    old_started = Event()
    old_release = Event()
    new_started = Event()
    snapshot = build_report_parse_input_snapshot(str(tmp_path))

    def old_snapshot():
        old_started.set()
        assert old_release.wait(timeout=5)
        return snapshot

    def new_snapshot():
        new_started.set()
        return snapshot

    def build():
        return {"report": {"case": "SYNTHETIC"}, "cache_version": 7}

    cache_dir = tmp_path / "output" / "parsed"
    old_generation = service.current_generation()
    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(
            service.load_or_build,
            str(tmp_path), str(cache_dir), 7, build,
            fingerprint_dir=str(tmp_path / "data"),
            snapshot_builder=old_snapshot,
            generation_token=old_generation,
        )
        assert old_started.wait(timeout=5)
        assert service.clear_all(str(cache_dir)) == 0
        new = pool.submit(
            service.load_or_build,
            str(tmp_path), str(cache_dir), 7, build,
            fingerprint_dir=str(tmp_path / "data"),
            snapshot_builder=new_snapshot,
            generation_token=service.current_generation(),
        )
        assert new_started.wait(timeout=5)
        assert new.result(timeout=5)["report"]["case"] == "SYNTHETIC"
        old_release.set()
        assert old.result(timeout=5)["report"]["case"] == "SYNTHETIC"

    assert len(list(cache_dir.glob("*.json"))) == 1


def test_same_directory_retry_joins_during_metadata_validation(tmp_path):
    build_parse_cache_report_tree(tmp_path)
    parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    started = Event()
    release = Event()

    from app.services.report import report_parsing_cache_service as cache_service
    original_validate = cache_service.validate_cached_input_metadata

    def delayed_validate(*args, **kwargs):
        started.set()
        assert release.wait(timeout=5)
        return original_validate(*args, **kwargs)

    with patch.object(cache_service, "validate_cached_input_metadata", side_effect=delayed_validate) as validate, \
         patch("app.services.report.report_parser_service._build_report", wraps=_build_report) as build, \
         patch("app.services.report.report_parser_service.detect_winrar_version", return_value=None), \
         ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(parse_report, str(tmp_path), str(tmp_path / "output"), False)
        assert started.wait(timeout=5)
        second = pool.submit(parse_report, str(tmp_path), str(tmp_path / "output"), False)
        release.set()
        assert first.result(timeout=10)["report"]
        assert second.result(timeout=10)["report"]

    assert validate.call_count == 1
    assert build.call_count == 0


def test_unsafe_cached_dependency_path_is_rejected(tmp_path):
    data_root, _, _ = build_parse_cache_report_tree(tmp_path)
    with pytest.raises(ReportParseInputError):
        validate_cached_input_metadata(
            str(data_root),
            (DependencyRecord("../outside.json", 1, 1, "1:1", "0" * 64),),
            (),
        )
