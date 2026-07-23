"""Bounded, TTL-managed and thread-safe Shadow observations."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from uuid import uuid4

from .pipeline_runtime_service import PipelineMode, PipelineSettings
from .shadow_comparison_service import ShadowComparisonResult


SHADOW_RUNTIME_MAX_RECORDS = 256
SHADOW_RUNTIME_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class ShadowStageRecord:
    stage: str
    status: str
    comparison: ShadowComparisonResult | None = None
    diagnostic_codes: tuple[str, ...] = ()
    observation_point: str = "sidecar"
    task_token: str | None = None


@dataclass(frozen=True)
class ShadowRunHandle:
    run_id: str
    context_id: str | None
    task_token: str | None = None


@dataclass
class ShadowRunRecord:
    run_id: str
    settings: PipelineSettings
    context_id: str | None
    created_at: float
    expires_at: float
    last_accessed_at: float
    stages: dict[str, ShadowStageRecord]
    stage_tokens: dict[str, str]


class ShadowRuntimeStore:
    """Store only safe diagnostics; no report/canonical values or paths persist."""

    def __init__(
        self, *, max_records: int = SHADOW_RUNTIME_MAX_RECORDS,
        ttl_seconds: float = SHADOW_RUNTIME_TTL_SECONDS, clock=time.time,
    ) -> None:
        if max_records < 1 or ttl_seconds <= 0:
            raise ValueError("SHADOW_RUNTIME_RETENTION_INVALID")
        self.max_records = max_records
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._records: dict[str, ShadowRunRecord] = {}
        self._context_index: dict[str, str] = {}
        self._lock = threading.RLock()

    def start(self, settings: PipelineSettings, context_id: str | None) -> ShadowRunHandle:
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            self._remove_context_run_locked(context_id)
            record = ShadowRunRecord(
                str(uuid4()), settings, context_id, now, now + self.ttl_seconds,
                now, {}, {},
            )
            self._records[record.run_id] = record
            if context_id:
                self._context_index[context_id] = record.run_id
            self._evict_locked(protected=record.run_id)
            return ShadowRunHandle(record.run_id, context_id)

    def ensure(self, settings: PipelineSettings, context_id: str | None) -> ShadowRunHandle:
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            existing = self._record_for_context_locked(context_id)
            if existing is not None:
                existing.settings = settings
                existing.expires_at = now + self.ttl_seconds
                existing.last_accessed_at = now
                return ShadowRunHandle(existing.run_id, existing.context_id)
        return self.start(settings, context_id)

    def issue_stage(
        self, settings: PipelineSettings, context_id: str | None, stage: str,
        *, new_run: bool = False,
    ) -> ShadowRunHandle:
        handle = self.start(settings, context_id) if new_run else self.ensure(settings, context_id)
        token = str(uuid4())
        with self._lock:
            record = self._records.get(handle.run_id)
            if record is None:
                raise KeyError("SHADOW_RUNTIME_RUN_NOT_FOUND")
            record.stage_tokens[stage] = token
        return ShadowRunHandle(handle.run_id, handle.context_id, token)

    def record(
        self, run_id: str, stage: ShadowStageRecord, *, task_token: str | None = None,
    ) -> bool:
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            record = self._records.get(run_id)
            if record is None:
                return False
            expected_token = record.stage_tokens.get(stage.stage)
            supplied_token = task_token or stage.task_token
            if expected_token is not None and supplied_token != expected_token:
                return False
            record.stages[stage.stage] = stage
            record.last_accessed_at = now
            record.expires_at = now + self.ttl_seconds
            self._evict_locked(protected=run_id)
            return True

    def public_summary(
        self, *, context_id: str | None = None, run_id: str | None = None,
    ) -> dict[str, object] | None:
        with self._lock:
            self._cleanup_locked(self._clock())
            record = self._records.get(run_id) if run_id else self._record_for_context_locked(context_id)
            return self._public_dict(record) if record else None

    def cleanup_expired(self, now: float | None = None) -> int:
        with self._lock:
            return self._cleanup_locked(self._clock() if now is None else now)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._context_index.clear()

    def size(self) -> int:
        with self._lock:
            self._cleanup_locked(self._clock())
            return len(self._records)

    def _record_for_context_locked(self, context_id: str | None) -> ShadowRunRecord | None:
        if not context_id:
            return None
        run_id = self._context_index.get(context_id)
        record = self._records.get(run_id) if run_id else None
        if record is None and run_id:
            self._context_index.pop(context_id, None)
        return record

    def _remove_context_run_locked(self, context_id: str | None) -> None:
        if not context_id:
            return
        old_run_id = self._context_index.pop(context_id, None)
        if old_run_id:
            self._records.pop(old_run_id, None)

    def _cleanup_locked(self, now: float) -> int:
        expired = [run_id for run_id, item in self._records.items() if item.expires_at <= now]
        for run_id in expired:
            record = self._records.pop(run_id)
            if record.context_id and self._context_index.get(record.context_id) == run_id:
                self._context_index.pop(record.context_id, None)
        return len(expired)

    def _evict_locked(self, *, protected: str | None = None) -> None:
        while len(self._records) > self.max_records:
            candidates = [item for item in self._records.values() if item.run_id != protected]
            if not candidates:
                return
            oldest = min(candidates, key=lambda item: (item.last_accessed_at, item.created_at))
            self._records.pop(oldest.run_id, None)
            if oldest.context_id and self._context_index.get(oldest.context_id) == oldest.run_id:
                self._context_index.pop(oldest.context_id, None)

    def _public_dict(self, record: ShadowRunRecord | None) -> dict[str, object] | None:
        if record is None:
            return None
        stages = {
            name: {
                "status": item.status,
                "observation_point": item.observation_point,
                "comparison": self._comparison_dict(item.comparison),
                "diagnostic_codes": list(item.diagnostic_codes),
            }
            for name, item in record.stages.items()
        }
        statuses = tuple(item["status"] for item in stages.values())
        expected_stages = {"parse", "archive", "export"}
        status = (
            "failed" if "failed" in statuses else
            "processing" if "pending" in statuses else
            "partial" if set(stages) != expected_stages else
            "not_comparable" if "not_comparable" in statuses else
            "different" if "different" in statuses else
            "matched" if statuses else "incomplete"
        )
        codes = tuple(code for item in stages.values() for code in item["diagnostic_codes"])
        return {
            "mode": record.settings.mode.value,
            "status": status,
            "context_id": record.context_id,
            "settings": record.settings.public_dict(),
            "retention": {"max_records": self.max_records, "ttl_seconds": self.ttl_seconds},
            "stages": stages,
            "diagnostic_codes": list(dict.fromkeys(codes)),
        }

    @staticmethod
    def _comparison_dict(comparison: ShadowComparisonResult | None) -> dict[str, object] | None:
        if comparison is None:
            return None
        return comparison.to_public_dict()


SHADOW_RUNTIME_STORE = ShadowRuntimeStore()


def public_pipeline_metadata(settings: PipelineSettings) -> dict[str, object]:
    status = {
        PipelineMode.LEGACY: "legacy_formal_output",
        PipelineMode.SHADOW: "shadow_compare_only",
        PipelineMode.CANONICAL: "canonical_not_enabled",
    }[settings.mode]
    return {"mode": settings.mode.value, "status": status, "settings": settings.public_dict()}


def shadow_runtime_failure(
    settings: PipelineSettings, context_id: str | None, stage: str, code: str = "SHADOW_RUNTIME_FAILED",
) -> dict[str, object]:
    return {
        "mode": settings.mode.value, "status": "failed", "context_id": context_id,
        "settings": settings.public_dict(), "stages": {
            stage: {"status": "failed", "observation_point": "controller_boundary",
                    "comparison": None, "diagnostic_codes": [code]}
        }, "diagnostic_codes": [code],
    }


__all__ = [
    "SHADOW_RUNTIME_MAX_RECORDS", "SHADOW_RUNTIME_STORE", "SHADOW_RUNTIME_TTL_SECONDS",
    "ShadowRunHandle", "ShadowRunRecord", "ShadowRuntimeStore", "ShadowStageRecord",
    "public_pipeline_metadata", "shadow_runtime_failure",
]
