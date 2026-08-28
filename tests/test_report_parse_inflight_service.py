"""有界同目录解析器任务共享的 SYNTHETIC 测试。"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.report_parse_inflight_service import (  # noqa: E402
    ReportParseInFlightCapacityError,
    ReportParseInFlightRegistry,
    ReportParseWaitTimeout,
)


def test_same_key_concurrent_calls_execute_one_builder(tmp_path):
    registry = ReportParseInFlightRegistry(max_entries=4)
    started = Event()
    release = Event()
    calls = []
    lock = Lock()

    def builder():
        with lock:
            calls.append("built")
        started.set()
        assert release.wait(timeout=5)
        return "SYNTHETIC-RESULT"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(registry.run, "opaque-same-key", builder)
        assert started.wait(timeout=5)
        second = pool.submit(registry.run, "opaque-same-key", builder)
        release.set()
        assert first.result(timeout=5) == "SYNTHETIC-RESULT"
        assert second.result(timeout=5) == "SYNTHETIC-RESULT"

    assert calls == ["built"]
    assert registry.active_count == 0


def test_waiter_timeout_detaches_without_cancelling_shared_task():
    registry = ReportParseInFlightRegistry(max_entries=2)
    started = Event()
    release = Event()
    calls = []

    def builder():
        calls.append("built")
        started.set()
        assert release.wait(timeout=5)
        return "SYNTHETIC-RESULT"

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(registry.run, "opaque-cancel-key", builder)
        assert started.wait(timeout=5)
        with pytest.raises(ReportParseWaitTimeout):
            registry.run("opaque-cancel-key", builder, wait_timeout=0.01)
        follower = pool.submit(registry.run, "opaque-cancel-key", builder)
        release.set()
        assert leader.result(timeout=5) == "SYNTHETIC-RESULT"
        assert follower.result(timeout=5) == "SYNTHETIC-RESULT"

    assert calls == ["built"]
    assert registry.active_count == 0


def test_max_lifetime_bounds_wait_without_starting_duplicate_task():
    registry = ReportParseInFlightRegistry(max_entries=2, max_lifetime_seconds=0.05)
    started = Event()
    release = Event()
    calls = []

    def builder():
        calls.append("built")
        started.set()
        assert release.wait(timeout=5)
        return "SYNTHETIC-RESULT"

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(registry.run, "opaque-lifetime-key", builder)
        assert started.wait(timeout=5)
        with pytest.raises(ReportParseWaitTimeout):
            registry.run("opaque-lifetime-key", builder, wait_timeout=0.2)
        release.wait(timeout=0.08)
        release.set()
        with pytest.raises(ReportParseWaitTimeout):
            leader.result(timeout=5)

    assert calls == ["built"]
    deadline = time.monotonic() + 1
    while registry.active_count and time.monotonic() < deadline:
        time.sleep(0.01)
    assert registry.active_count == 0


def test_shared_failure_reaches_waiters_and_next_request_can_retry():
    registry = ReportParseInFlightRegistry(max_entries=2)
    started = Event()
    release = Event()
    calls = []

    def failing():
        calls.append("failed")
        started.set()
        assert release.wait(timeout=5)
        raise ValueError("SYNTHETIC-FAILURE")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(registry.run, "opaque-failure-key", failing)
        assert started.wait(timeout=5)
        second = pool.submit(registry.run, "opaque-failure-key", failing)
        release.set()
        with pytest.raises(ValueError, match="SYNTHETIC-FAILURE"):
            first.result(timeout=5)
        with pytest.raises(ValueError, match="SYNTHETIC-FAILURE"):
            second.result(timeout=5)

    assert calls == ["failed"]
    assert registry.active_count == 0
    assert registry.run("opaque-failure-key", lambda: "SYNTHETIC-RETRY") == "SYNTHETIC-RETRY"


def test_distinct_keys_run_in_parallel_and_capacity_is_bounded():
    registry = ReportParseInFlightRegistry(max_entries=2)
    started_a = Event()
    started_b = Event()
    release = Event()

    def builder_a():
        started_a.set()
        assert release.wait(timeout=5)
        return "A"

    def builder_b():
        started_b.set()
        assert release.wait(timeout=5)
        return "B"

    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(registry.run, "opaque-a", builder_a)
        second = pool.submit(registry.run, "opaque-b", builder_b)
        assert started_a.wait(timeout=5)
        assert started_b.wait(timeout=5)
        with pytest.raises(ReportParseInFlightCapacityError):
            registry.run("opaque-c", lambda: "C")
        release.set()
        assert first.result(timeout=5) == "A"
        assert second.result(timeout=5) == "B"

    assert registry.active_count == 0
