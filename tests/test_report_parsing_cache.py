"""持久报告解析缓存的合成数据测试。"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.report_parsing_cache_service import ReportParsingCacheService  # noqa: E402


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return float(self.value)


def make_report(root: Path, name: str) -> Path:
    report = root / name
    (report / "data").mkdir(parents=True)
    (report / "data" / "report.json").write_text(name, encoding="utf-8")
    return report


def parse_with(service, source, cache_dir, calls, *, version=7):
    def build():
        calls.append(str(source))
        return {"report": {"source": source.name}, "cache_version": version}

    return service.load_or_build(str(source), str(cache_dir), version, build)


def test_five_entries_are_retained_and_sixth_evicts_oldest(tmp_path):
    clock = Clock()
    service = ReportParsingCacheService(clock=clock)
    cache_dir = tmp_path / "output" / "parsed"
    sources = [make_report(tmp_path, f"report-{index}") for index in range(6)]
    calls = []

    for source in sources[:5]:
        parse_with(service, source, cache_dir, calls)
    assert len(list(cache_dir.glob("*.json"))) == 5
    parse_with(service, sources[5], cache_dir, calls)

    assert len(list(cache_dir.glob("*.json"))) == 5
    assert parse_with(service, sources[0], cache_dir, calls)["report"]["source"] == "report-0"
    assert len(calls) == 7  # 前五次初始构建、第六次构建，再访问已淘汰的第一项时未命中


def test_cache_hit_updates_lru_and_protects_recent_entry(tmp_path):
    clock = Clock()
    service = ReportParsingCacheService(clock=clock)
    cache_dir = tmp_path / "parsed"
    sources = [make_report(tmp_path, f"case-{index}") for index in range(6)]
    calls = []
    for source in sources[:5]:
        parse_with(service, source, cache_dir, calls)
    parse_with(service, sources[0], cache_dir, calls)
    parse_with(service, sources[5], cache_dir, calls)

    parse_with(service, sources[0], cache_dir, calls)
    before_second_lookup = len(calls)
    parse_with(service, sources[1], cache_dir, calls)
    assert len(calls) == before_second_lookup + 1  # 被淘汰的是第二项，而不是第一项


def test_same_directory_with_trailing_separator_is_one_entry(tmp_path):
    clock = Clock()
    service = ReportParsingCacheService(clock=clock)
    source = make_report(tmp_path, "same-report")
    cache_dir = tmp_path / "parsed"
    calls = []
    parse_with(service, source, cache_dir, calls)
    parse_with(service, Path(str(source) + os.sep), cache_dir, calls)

    assert len(calls) == 1
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_windows_case_difference_is_one_entry(tmp_path):
    if os.name != "nt":
        pytest.skip("大小写路径等价只适用于 Windows。")
    clock = Clock()
    service = ReportParsingCacheService(clock=clock)
    source = make_report(tmp_path, "Case-Report")
    calls = []
    parse_with(service, source, tmp_path / "parsed", calls)
    parse_with(service, Path(str(source).upper()), tmp_path / "parsed", calls)

    assert len(calls) == 1
    assert len(list((tmp_path / "parsed").glob("*.json"))) == 1


def test_content_fingerprint_change_rebuilds_cache(tmp_path):
    clock = Clock()
    service = ReportParsingCacheService(clock=clock)
    source = make_report(tmp_path, "changing-report")
    calls = []
    cache_dir = tmp_path / "parsed"
    parse_with(service, source, cache_dir, calls)
    (source / "data" / "report.json").write_text("changed", encoding="utf-8")
    parse_with(service, source, cache_dir, calls)

    assert len(calls) == 2
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_corrupt_and_old_entries_do_not_consume_limit_and_restart_hits(tmp_path):
    clock = Clock()
    first_service = ReportParsingCacheService(clock=clock)
    cache_dir = tmp_path / "parsed"
    sources = [make_report(tmp_path, f"restart-{index}") for index in range(5)]
    calls = []
    for source in sources:
        parse_with(first_service, source, cache_dir, calls)
    (cache_dir / "damaged.json").write_text("not-json", encoding="utf-8")
    (cache_dir / "old.json").write_text(json.dumps({"cache_version": 1}), encoding="utf-8")

    restarted = ReportParsingCacheService(clock=clock)
    before = len(calls)
    result = parse_with(restarted, sources[0], cache_dir, calls)

    assert result["report"]["source"] == sources[0].name
    assert len(calls) == before
    assert len(list(cache_dir.glob("*.json"))) == 5


def test_concurrent_same_directory_builds_once_and_keeps_limit(tmp_path):
    service = ReportParsingCacheService()
    source = make_report(tmp_path, "concurrent-report")
    cache_dir = tmp_path / "parsed"
    calls = []
    call_lock = Lock()

    def build():
        with call_lock:
            calls.append("built")
        return {"report": {"source": source.name}, "cache_version": 7}

    def parse():
        return service.load_or_build(str(source), str(cache_dir), 7, build)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: parse(), range(4)))

    assert len(calls) == 1
    assert all(result["report"]["source"] == source.name for result in results)
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_clear_during_inflight_build_invalidates_result_without_breaking_lock(tmp_path):
    service = ReportParsingCacheService()
    source = make_report(tmp_path, "inflight-clear-report")
    cache_dir = tmp_path / "parsed"
    started = Event()
    release = Event()
    calls = []

    def build():
        calls.append("built")
        started.set()
        assert release.wait(timeout=5)
        return {"report": {"source": source.name}, "cache_version": 7}

    def parse():
        return service.load_or_build(str(source), str(cache_dir), 7, build)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(parse)
        assert started.wait(timeout=5)
        assert service.clear_all(str(cache_dir)) == 0
        release.set()
        assert first.result()["report"]["source"] == source.name

    # 清理操作使执行中的结果失效，但下一请求持有同一个目录级锁，
    # 并在锁释放后只重建一次。
    assert not list(cache_dir.glob("*.json"))
    parse()
    assert calls == ["built", "built"]
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_clear_during_fingerprint_invalidates_request_started_before_clear(tmp_path):
    service = ReportParsingCacheService()
    source = make_report(tmp_path, "fingerprint-clear-report")
    cache_dir = tmp_path / "parsed"
    started = Event()
    release = Event()

    def fingerprint(_path):
        started.set()
        assert release.wait(timeout=5)
        return "SYNTHETIC-FINGERPRINT"

    def build():
        return {"report": {"source": source.name}, "cache_version": 7}

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(
            service.load_or_build,
            str(source),
            str(cache_dir),
            7,
            build,
            fingerprint=fingerprint,
        )
        assert started.wait(timeout=5)
        assert service.clear_all(str(cache_dir)) == 0
        release.set()
        first.result()

    assert not list(cache_dir.glob("*.json"))


def test_clear_is_idempotent_and_never_deletes_archive_or_defaults(tmp_path):
    service = ReportParsingCacheService()
    cache_dir = tmp_path / "output" / "parsed"
    source = make_report(tmp_path, "clear-report")
    calls = []
    parse_with(service, source, cache_dir, calls)
    rar = tmp_path / "output" / "compressed" / "context" / "manifest" / "case.rar"
    manifest = rar.with_name("ArchiveManifest.json")
    defaults = tmp_path / "output" / "defaults.json"
    rar.parent.mkdir(parents=True)
    rar.write_bytes(b"SYNTHETIC-RAR")
    manifest.write_text("{\"validation_status\":\"validated\"}", encoding="utf-8")
    defaults.write_text("{}", encoding="utf-8")

    assert service.clear_all(str(cache_dir)) == 1
    assert service.clear_all(str(cache_dir)) == 0
    parse_with(service, source, cache_dir, calls)
    assert len(calls) == 2
    assert rar.is_file()
    assert manifest.is_file()
    assert defaults.is_file()


def test_cache_store_key_does_not_expose_local_path(tmp_path):
    cache_dir = tmp_path / "parsed"

    key = ReportParsingCacheService._store_key(str(cache_dir))

    assert str(cache_dir) not in key
    assert len(key) == 64
