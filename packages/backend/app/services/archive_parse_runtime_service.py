"""按内容标识串行化并短暂复用上传归档解析。"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
import threading
from collections import OrderedDict
import weakref

from ..repository.file_storage import compute_md5, extract_archive
from .report.report_parser_service import parse_from_archive


MAX_CACHED_ARCHIVE_RESULTS = 8


class ArchiveParseRuntime:
    """防止客户端超时后重复解析归档。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._key_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
        self._results: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._generation = 0

    def load_or_parse(
        self,
        archive_path: str,
        output_dir: str,
        *,
        retain_source: bool,
    ) -> dict[str, object]:
        extension = os.path.splitext(archive_path)[1].casefold()
        archive_md5 = compute_md5(archive_path)
        key = f"{extension}\0{archive_md5}"
        with self._lock:
            generation = self._generation
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            with self._lock:
                cached = self._results.get(key)
                if cached is not None:
                    self._results.move_to_end(key)
                    cached = copy.deepcopy(cached)
            if cached is not None:
                if retain_source:
                    return self._materialize_source(archive_path, cached)
                return self._with_archive_filename(archive_path, cached)

            result = parse_from_archive(
                archive_path,
                output_dir,
                retain_source=retain_source,
                archive_md5=archive_md5,
            )
            cache_result = copy.deepcopy(result)
            cache_result.pop("_archive_source_root", None)
            cache_result.pop("_archive_source_cleanup_root", None)
            with self._lock:
                if generation == self._generation:
                    self._results[key] = cache_result
                    self._results.move_to_end(key)
                    while len(self._results) > MAX_CACHED_ARCHIVE_RESULTS:
                        self._results.popitem(last=False)
            return result

    def clear(self) -> int:
        with self._lock:
            self._generation += 1
            count = len(self._results)
            self._results.clear()
            return count

    def _materialize_source(
        self,
        archive_path: str,
        cached: dict[str, object],
    ) -> dict[str, object]:
        tmp_dir = tempfile.mkdtemp(prefix="biji_archive_context_")
        try:
            extracted_root = extract_archive(archive_path, tmp_dir)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        result = self._with_archive_filename(archive_path, cached)
        result["_archive_source_root"] = extracted_root
        result["_archive_source_cleanup_root"] = tmp_dir
        return result

    @staticmethod
    def _with_archive_filename(
        archive_path: str,
        result: dict[str, object],
    ) -> dict[str, object]:
        filename = os.path.basename(archive_path)
        report = result.get("report")
        if isinstance(report, dict):
            inspection = report.get("inspection")
            if isinstance(inspection, dict):
                report_result = inspection.get("result")
                if isinstance(report_result, dict):
                    report_result["rar_filename"] = filename
        rar_info = result.get("rar_info")
        if isinstance(rar_info, dict):
            rar_info["filename"] = filename
        return result


ARCHIVE_PARSE_RUNTIME = ArchiveParseRuntime()


def parse_archive_with_reuse(
    archive_path: str,
    output_dir: str,
    *,
    retain_source: bool = False,
) -> dict[str, object]:
    return ARCHIVE_PARSE_RUNTIME.load_or_parse(
        archive_path, output_dir, retain_source=retain_source,
    )


def clear_archive_parse_cache() -> int:
    return ARCHIVE_PARSE_RUNTIME.clear()


__all__ = [
    "ARCHIVE_PARSE_RUNTIME",
    "clear_archive_parse_cache",
    "parse_archive_with_reuse",
]
