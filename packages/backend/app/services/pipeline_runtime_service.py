"""Central runtime settings and non-invasive pipeline orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class PipelineMode(str, Enum):
    """The only supported migration modes."""

    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


class PipelineRunStatus(str, Enum):
    """Observable status without creating document side effects."""

    LEGACY_FORMAL_OUTPUT = "legacy_formal_output"
    SHADOW_COMPARE_ONLY = "shadow_compare_only"
    CANONICAL_NOT_ENABLED = "canonical_not_enabled"


@dataclass(frozen=True)
class RuntimeVersions:
    """Version anchors used to isolate future semantic caches."""

    schema_version: str = "canonical-v1"
    adapter_version: str = "report-adapter-v1"
    template_version: str = "current-template-v1"
    plan_version: str = "plan-v1"


@dataclass(frozen=True)
class PipelineSettings:
    """Immutable settings shared by pipeline services."""

    mode: PipelineMode = PipelineMode.LEGACY
    source: str = "default"
    invalid_value: str | None = None
    versions: RuntimeVersions = RuntimeVersions()

    @property
    def cache_namespace(self) -> str:
        """Keep mode-specific derived artifacts from sharing a cache namespace."""

        return f"pipeline-{self.mode.value}"


def load_pipeline_settings(
    config: Mapping[str, str] | None = None,
) -> PipelineSettings:
    """Read the mode once, safely falling back to legacy for invalid values.

    Tests can pass a mapping explicitly. Production callers omit it so only this
    function reads ``BIJI_PIPELINE_MODE``; parsers and renderers do not inspect
    environment variables themselves.
    """

    values = os.environ if config is None else config
    raw_value = values.get("BIJI_PIPELINE_MODE", "").strip().lower()
    if not raw_value:
        return PipelineSettings()
    try:
        return PipelineSettings(mode=PipelineMode(raw_value), source="environment")
    except ValueError:
        return PipelineSettings(
            source="invalid_fallback",
            invalid_value=raw_value,
        )


@dataclass(frozen=True)
class PipelineRunResult:
    """In-memory result for legacy/shadow/canonical orchestration."""

    mode: PipelineMode
    status: PipelineRunStatus
    formal_output: Any | None
    canonical_output: Any | None
    comparison: Any | None
    cache_namespace: str
    diagnostic_codes: tuple[str, ...] = ()


class PipelineOrchestrator:
    """Select a pipeline mode without invoking compression or rendering."""

    def __init__(self, settings: PipelineSettings) -> None:
        self._settings = settings

    @property
    def settings(self) -> PipelineSettings:
        return self._settings

    def run(
        self,
        *,
        legacy_output: Any,
        canonical_output: Any | None = None,
        comparison: Any | None = None,
    ) -> PipelineRunResult:
        if self._settings.mode is PipelineMode.LEGACY:
            return PipelineRunResult(
                mode=self._settings.mode,
                status=PipelineRunStatus.LEGACY_FORMAL_OUTPUT,
                formal_output=legacy_output,
                canonical_output=None,
                comparison=None,
                cache_namespace=self._settings.cache_namespace,
            )

        if self._settings.mode is PipelineMode.SHADOW:
            return PipelineRunResult(
                mode=self._settings.mode,
                status=PipelineRunStatus.SHADOW_COMPARE_ONLY,
                formal_output=legacy_output,
                canonical_output=canonical_output,
                comparison=comparison,
                cache_namespace=self._settings.cache_namespace,
            )

        return PipelineRunResult(
            mode=self._settings.mode,
            status=PipelineRunStatus.CANONICAL_NOT_ENABLED,
            formal_output=None,
            canonical_output=None,
            comparison=None,
            cache_namespace=self._settings.cache_namespace,
            diagnostic_codes=("CANONICAL_NOT_ENABLED",),
        )
