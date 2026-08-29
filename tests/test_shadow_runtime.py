"""Shadow 诊断的合成数据保留与并发测试。"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.runtime.pipeline_runtime_service import load_pipeline_settings
from app.services.shadow.shadow_runtime_service import ShadowRuntimeStore, ShadowStageRecord


def test_shadow_store_starts_new_generation_and_has_capacity_eviction():
    now = [100.0]
    store = ShadowRuntimeStore(max_records=2, ttl_seconds=60, clock=lambda: now[0])
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})

    first = store.start(settings, "SYNTHETIC-context-1")
    store.record(first.run_id, ShadowStageRecord("parse", "matched"))
    same = store.start(settings, "SYNTHETIC-context-1")
    assert same.run_id != first.run_id
    assert store.public_summary(run_id=first.run_id) is None
    assert "run_id" not in (store.public_summary(context_id="SYNTHETIC-context-1") or {})

    second = store.start(settings, "SYNTHETIC-context-2")
    now[0] += 1
    store.ensure(settings, "SYNTHETIC-context-1")
    now[0] += 1
    third = store.start(settings, "SYNTHETIC-context-3")
    assert store.size() == 2
    assert store.public_summary(context_id="SYNTHETIC-context-2") is None
    assert store.public_summary(context_id="SYNTHETIC-context-3")["context_id"] == "SYNTHETIC-context-3"
    assert second.run_id != third.run_id


def test_shadow_store_ignores_out_of_order_stage_results():
    store = ShadowRuntimeStore(max_records=4, ttl_seconds=60, clock=lambda: 100.0)
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})

    first = store.issue_stage(settings, "SYNTHETIC-context", "archive", new_run=True)
    second = store.issue_stage(settings, "SYNTHETIC-context", "archive")
    stale = ShadowStageRecord("archive", "matched", task_token=first.task_token)
    current = ShadowStageRecord("archive", "different", task_token=second.task_token)

    assert not store.record(first.run_id, stale, task_token=first.task_token)
    assert store.record(second.run_id, current, task_token=second.task_token)
    summary = store.public_summary(context_id="SYNTHETIC-context")
    assert summary["stages"]["archive"]["status"] == "different"
    assert summary["status"] == "partial"


def test_shadow_store_reports_final_status_only_after_all_three_stages():
    store = ShadowRuntimeStore(max_records=2, ttl_seconds=60, clock=lambda: 100.0)
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    handles = [
        store.issue_stage(settings, "SYNTHETIC-context", stage, new_run=index == 0)
        for index, stage in enumerate(("parse", "archive", "export"))
    ]
    assert store.record(
        handles[0].run_id,
        ShadowStageRecord("parse", "pending", task_token=handles[0].task_token),
        task_token=handles[0].task_token,
    )
    assert store.public_summary(context_id="SYNTHETIC-context")["status"] == "processing"

    for handle, stage in zip(handles, ("parse", "archive", "export")):
        assert store.record(
            handle.run_id,
            ShadowStageRecord(stage, "matched", task_token=handle.task_token),
            task_token=handle.task_token,
        )

    summary = store.public_summary(context_id="SYNTHETIC-context")
    assert summary["status"] == "matched"


def test_shadow_store_ttl_cleanup_removes_context_index_and_diagnostics():
    now = [100.0]
    store = ShadowRuntimeStore(max_records=4, ttl_seconds=10, clock=lambda: now[0])
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    handle = store.start(settings, "SYNTHETIC-context")
    store.record(handle.run_id, ShadowStageRecord("parse", "matched"))

    now[0] = 110.0
    assert store.public_summary(context_id="SYNTHETIC-context") is None
    assert store.cleanup_expired() == 0
    assert store.size() == 0


def test_shadow_store_public_reads_are_snapshots_and_safe_during_concurrent_writes():
    store = ShadowRuntimeStore(max_records=32, ttl_seconds=60)
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    handles = [store.start(settings, f"SYNTHETIC-context-{index}") for index in range(8)]

    def write_and_read(handle):
        store.record(handle.run_id, ShadowStageRecord("parse", "matched"))
        summary = store.public_summary(run_id=handle.run_id)
        summary["stages"].clear()
        return store.public_summary(run_id=handle.run_id)["stages"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(write_and_read, handles))

    assert all("parse" in result for result in results)
