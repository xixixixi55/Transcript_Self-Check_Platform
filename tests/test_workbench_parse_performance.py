"""工作台旧版解析快速路径的合成数据计时证据。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.services.archive.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
from app.services.case.case_draft_service import CaseDraftService, _parse_source  # noqa: E402
from app.services.case.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.case.case_parse_dispatcher_service import CaseParseDispatcher  # noqa: E402
from app.services.report.report_parser_service import parse_report  # noqa: E402
from app.services.source.source_record_service import SourceRecordService  # noqa: E402


def _write_legacy_fixture(root: Path) -> Path:
    report_dir = root / "SYNTHETIC-ALLOWED-ROOT" / "SYNTHETIC-LEGACY-REPORT"
    data_dir = report_dir / "data" / "JC01" / "Base"
    data_dir.mkdir(parents=True)

    def write(relative: str, payload: object) -> None:
        target = report_dir / "data" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    write("data_case_info.json", {"contents": []})
    write("data_device_lists.json", {"contents": [{"c3": "SYNTHETIC-JC01"}]})
    write("data_report_info.json", {"contents": []})
    write("JC01/Base/device_table.json", {"rows": []})
    for index in range(4):
        write(f"noise/SYNTHETIC-{index}.json", {"value": "SYNTHETIC-NOISE"})
    return report_dir


@pytest.fixture()
def profile_fixture(tmp_path: Path):
    report_dir = _write_legacy_fixture(tmp_path)
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path / "db", "SYNTHETIC-PERF"),
        "SYNTHETIC-PERF",
    )
    source_service = SourceRecordService(
        database,
        ArchiveAuthorizationService(
            str(tmp_path / "SYNTHETIC-ALLOWED-ROOT"),
            str(tmp_path / "SYNTHETIC-OUTPUT"),
        ),
    )
    return report_dir, database, source_service


def test_same_synthetic_report_profiles_legacy_and_workbench_paths(profile_fixture, capsys):
    report_dir, database, source_service = profile_fixture
    legacy_output = report_dir.parent.parent / "SYNTHETIC-LEGACY-OUTPUT"
    metrics: dict[str, float | int] = {}

    legacy_start = time.perf_counter()
    legacy_result = parse_report(str(report_dir), str(legacy_output), compress=False)
    metrics["legacy_to_inspection_report_ms"] = (time.perf_counter() - legacy_start) * 1000
    assert isinstance(legacy_result.get("report"), dict)

    descriptor = source_service.register_report_directory(str(report_dir))
    cases = CaseDraftService(
        database,
        parser=lambda path, output: _timed_parser(path, output, metrics),
        source_service=source_service,
    )
    identifiers = cases.submit(descriptor)

    from app.services.source import source_record_service

    original_fingerprint_with_metadata = source_record_service._fingerprint_with_metadata
    original_verify_after_parse = source_service.verify_after_parse
    original_complete_parse = cases.workflow.complete_parse

    def timed_fingerprint_with_metadata(path: Path, should_cancel=None):
        started = time.perf_counter()
        metrics["metadata_started_perf"] = started
        metrics["fingerprint_started_perf"] = started
        metadata, value = original_fingerprint_with_metadata(path, should_cancel)
        metrics["source_identity_entry_count"] = int(metadata["identity_entry_count"])
        metrics["metadata_ms"] = (time.perf_counter() - started) * 1000
        metrics["fingerprint_ms"] = (time.perf_counter() - started) * 1000
        return metadata, value

    def timed_verify_after_parse(
        source_id: str, expected_revision: int | None = None, cancellation_event=None,
    ):
        started = time.perf_counter()
        metrics["verification_started_perf"] = started
        value = original_verify_after_parse(
            source_id,
            expected_revision=expected_revision,
            cancellation_event=cancellation_event,
        )
        metrics["verification_completed_perf"] = time.perf_counter()
        metrics["bounded_source_verification_ms"] = (time.perf_counter() - started) * 1000
        return value

    def timed_complete_parse(*args, **kwargs):
        started = time.perf_counter()
        value = original_complete_parse(*args, **kwargs)
        metrics["review_ready_perf"] = time.perf_counter()
        metrics["draft_persistence_ms"] = (time.perf_counter() - started) * 1000
        return value

    dispatcher = CaseParseDispatcher(max_workers=2)
    parse_started = time.perf_counter()
    metrics["task_start_perf"] = parse_started
    with patch.object(source_record_service, "_fingerprint_with_metadata", side_effect=timed_fingerprint_with_metadata), \
         patch.object(source_service, "verify_after_parse", side_effect=timed_verify_after_parse), \
         patch.object(cases.workflow, "complete_parse", side_effect=timed_complete_parse):
        dispatcher.dispatch(cases, identifiers["case_id"], identifiers["task_id"])
        deadline = time.perf_counter() + 5
        detail = CaseLifecycleService(database).detail(identifiers["case_id"])
        while detail["parse_task"]["status"] in {"queued", "running"} and time.perf_counter() < deadline:
            time.sleep(0.01)
            detail = CaseLifecycleService(database).detail(identifiers["case_id"])
        metrics["review_ready_ms"] = (time.perf_counter() - parse_started) * 1000
        metrics["review_ready_exact_ms"] = (
            float(metrics["review_ready_perf"]) - parse_started
        ) * 1000
        while detail["source"]["access_status"] == "pending" and time.perf_counter() < deadline:
            time.sleep(0.01)
            detail = CaseLifecycleService(database).detail(identifiers["case_id"])
        metrics["bounded_verification_complete_ms"] = (time.perf_counter() - parse_started) * 1000
        metrics["bounded_verification_exact_ms"] = (
            float(metrics["verification_completed_perf"]) - parse_started
        ) * 1000
    dispatcher.shutdown(wait=True)
    assert detail["shell"]["lifecycle"] == "review_ready"
    assert detail["draft"] is not None
    assert metrics["parser_started_perf"] < metrics["metadata_started_perf"]
    assert metrics["parser_started_perf"] < metrics["fingerprint_started_perf"]
    assert metrics["review_ready_perf"] <= metrics["verification_started_perf"]

    print("SYNTHETIC_PARSE_PROFILE " + json.dumps(metrics, sort_keys=True))
    captured = capsys.readouterr()
    assert "SYNTHETIC_PARSE_PROFILE" in captured.out
    print(captured.out, end="")


def _timed_parser(path: Path, output: Path, metrics: dict[str, float | int]):
    started = time.perf_counter()
    metrics["parser_started_perf"] = started
    task_started = float(metrics["task_start_perf"])
    metrics["parser_wait_before_start_ms"] = (started - task_started) * 1000
    result = _parse_source(path, output)
    metrics["parser_ms"] = (time.perf_counter() - started) * 1000
    return result
