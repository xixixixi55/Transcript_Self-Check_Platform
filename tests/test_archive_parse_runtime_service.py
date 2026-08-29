"""归档解析串行化与短期复用的合成数据测试。"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive.archive_parse_runtime_service import ArchiveParseRuntime  # noqa: E402


def _result(filename: str = "sample.zip") -> dict[str, object]:
    return {
        "report": {"inspection": {"result": {"rar_filename": filename}}},
        "parsed_files": ["data_case_info.json"],
        "rar_info": {"filename": filename, "md5": "a" * 32, "size_bytes": 1},
    }


def test_same_archive_parse_is_serialized_and_reused_after_completion(tmp_path):
    runtime = ArchiveParseRuntime()
    archive = tmp_path / "sample.zip"
    archive.write_bytes(b"SYNTHETIC-ARCHIVE")
    started = Event()
    release = Event()
    calls = []

    def parse(*_args, **_kwargs):
        calls.append("parsed")
        started.set()
        assert release.wait(timeout=5)
        return _result()

    with patch(
        "app.services.archive.archive_parse_runtime_service.compute_md5",
        return_value="a" * 32,
    ), patch(
        "app.services.archive.archive_parse_runtime_service.parse_from_archive",
        side_effect=parse,
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(runtime.load_or_parse, str(archive), str(tmp_path), retain_source=False)
            assert started.wait(timeout=5)
            second = pool.submit(runtime.load_or_parse, str(archive), str(tmp_path), retain_source=False)
            release.set()
            results = [first.result(), second.result()]
        runtime.load_or_parse(str(archive), str(tmp_path), retain_source=False)

    assert calls == ["parsed"]
    assert all(item["rar_info"]["filename"] == "sample.zip" for item in results)


def test_clear_during_archive_parse_invalidates_result_generation(tmp_path):
    runtime = ArchiveParseRuntime()
    archive = tmp_path / "sample.zip"
    archive.write_bytes(b"SYNTHETIC-ARCHIVE")
    started = Event()
    release = Event()
    calls = []

    def parse(*_args, **_kwargs):
        calls.append("parsed")
        started.set()
        assert release.wait(timeout=5)
        return _result()

    with patch("app.services.archive.archive_parse_runtime_service.compute_md5", return_value="a" * 32), \
         patch("app.services.archive.archive_parse_runtime_service.parse_from_archive", side_effect=parse):
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(runtime.load_or_parse, str(archive), str(tmp_path), retain_source=False)
            assert started.wait(timeout=5)
            assert runtime.clear() == 0
            release.set()
            first.result()
        runtime.load_or_parse(str(archive), str(tmp_path), retain_source=False)

    assert calls == ["parsed", "parsed"]


def test_cached_archive_report_can_materialize_a_fresh_context_source(tmp_path):
    runtime = ArchiveParseRuntime()
    archive = tmp_path / "sample.zip"
    archive.write_bytes(b"SYNTHETIC-ARCHIVE")
    extracted = tmp_path / "extracted"
    extracted.mkdir()

    with patch("app.services.archive.archive_parse_runtime_service.compute_md5", return_value="a" * 32), \
         patch("app.services.archive.archive_parse_runtime_service.parse_from_archive", return_value=_result()) as parse, \
         patch("app.services.archive.archive_parse_runtime_service.extract_archive", return_value=str(extracted)) as extract:
        runtime.load_or_parse(str(archive), str(tmp_path), retain_source=False)
        result = runtime.load_or_parse(str(archive), str(tmp_path), retain_source=True)

    assert parse.call_count == 1
    extract.assert_called_once()
    assert result["_archive_source_root"] == str(extracted)
    assert os.path.isdir(result["_archive_source_cleanup_root"])
