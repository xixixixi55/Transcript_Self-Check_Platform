"""报告解析并发任务复用的 SYNTHETIC 集成测试。"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from synthetic_report_builders import build_parse_cache_report_tree  # noqa: E402
from app.repository.report.meiya_report_source_adapter import (  # noqa: E402
    MEIYA_REPORT_SOURCE_ADAPTER,
)
from app.services.report import report_parser_service as parser_service  # noqa: E402
from app.services.report.report_parser_service import _build_report, parse_report  # noqa: E402


def test_same_directory_requests_share_snapshot_and_parser(tmp_path):
    build_parse_cache_report_tree(tmp_path)
    started = Event()
    second_joined = Event()
    release = Event()
    snapshot_calls = []
    run_calls = []

    original_snapshot = MEIYA_REPORT_SOURCE_ADAPTER.build_snapshot
    original_run = parser_service.REPORT_PARSE_INFLIGHT_REGISTRY.run

    def slow_snapshot(source_root):
        snapshot_calls.append(source_root)
        started.set()
        assert release.wait(timeout=5)
        return original_snapshot(source_root)

    def observe_run(key, builder, **kwargs):
        run_calls.append(key)
        if len(run_calls) == 2:
            second_joined.set()
        return original_run(key, builder, **kwargs)

    with patch.object(MEIYA_REPORT_SOURCE_ADAPTER, "build_snapshot", side_effect=slow_snapshot), \
         patch.object(parser_service.REPORT_PARSE_INFLIGHT_REGISTRY, "run", side_effect=observe_run), \
         patch.object(parser_service, "detect_winrar_version", return_value=None), \
         patch.object(parser_service, "_build_report", wraps=_build_report) as build, \
         ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(parse_report, str(tmp_path), str(tmp_path / "output"), False)
        assert started.wait(timeout=5)
        second = pool.submit(parse_report, str(tmp_path), str(tmp_path / "output"), False)
        assert second_joined.wait(timeout=5)
        release.set()
        first_result = first.result(timeout=10)
        second_result = second.result(timeout=10)

    assert first_result["report"] == second_result["report"]
    assert len(snapshot_calls) == 1
    assert build.call_count == 1
    assert not (tmp_path / "output" / "parsed").exists()
