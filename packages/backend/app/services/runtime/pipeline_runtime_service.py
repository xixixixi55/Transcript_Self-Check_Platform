"""中央运行时设置和非侵入式流水线编排。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


PIPELINE_CONFIG_VERSION = "pipeline-config-v1"


def _configured_at() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineMode(str, Enum):
    """唯一受支持的迁移模式。"""

    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


class PipelineRunStatus(str, Enum):
    """不产生文档副作用的可观察状态。"""

    LEGACY_FORMAL_OUTPUT = "legacy_formal_output"
    SHADOW_COMPARE_ONLY = "shadow_compare_only"
    CANONICAL_NOT_ENABLED = "canonical_not_enabled"


@dataclass(frozen=True)
class RuntimeVersions:
    """用于隔离未来语义缓存的版本锚点。"""

    schema_version: str = "canonical-v1"
    adapter_version: str = "report-adapter-v1"
    template_version: str = "current-template-v1"
    plan_version: str = "plan-v1"


@dataclass(frozen=True)
class PipelineSettings:
    """流水线服务共享的不可变设置。"""

    mode: PipelineMode = PipelineMode.LEGACY
    source: str = "default"
    invalid_value: str | None = None
    versions: RuntimeVersions = RuntimeVersions()
    config_version: str = PIPELINE_CONFIG_VERSION
    configured_at: str = ""

    @property
    def cache_namespace(self) -> str:
        """防止特定模式派生工件共享缓存命名空间。"""

        return f"pipeline-{self.mode.value}"

    def public_dict(self) -> dict[str, object]:
        """仅暴露稳定模式元数据；绝不暴露环境内容。"""
        return {
            "mode": self.mode.value,
            "source": self.source,
            "config_version": self.config_version,
            "configured_at": self.configured_at,
            "versions": {
                "schema_version": self.versions.schema_version,
                "adapter_version": self.versions.adapter_version,
                "template_version": self.versions.template_version,
                "plan_version": self.versions.plan_version,
            },
        }


def pipeline_settings_for_app(app: Any) -> PipelineSettings:
    """读取控制器使用的唯一启动期自有设置对象。"""

    settings = getattr(getattr(app, "state", None), "pipeline_settings", None)
    return settings if isinstance(settings, PipelineSettings) else PipelineSettings()


def load_pipeline_settings(
    config: Mapping[str, str] | None = None,
) -> PipelineSettings:
    """仅读取一次模式，对无效值安全回退到旧版。

    测试可显式传入映射。生产调用方省略该值，因此只有此函数读取
    `BIJI_PIPELINE_MODE`；解析器和渲染器自身不检查环境变量。
    """

    values = os.environ if config is None else config
    raw_value = values.get("BIJI_PIPELINE_MODE", "").strip().lower()
    if not raw_value:
        return PipelineSettings(configured_at=_configured_at())
    try:
        return PipelineSettings(
            mode=PipelineMode(raw_value),
            source="environment",
            configured_at=_configured_at(),
        )
    except ValueError:
        return PipelineSettings(
            source="invalid_fallback",
            invalid_value=raw_value,
            configured_at=_configured_at(),
        )


@dataclass(frozen=True)
class PipelineRunResult:
    """旧版、Shadow 和规范编排的内存结果。"""

    mode: PipelineMode
    status: PipelineRunStatus
    formal_output: Any | None
    canonical_output: Any | None
    comparison: Any | None
    cache_namespace: str
    diagnostic_codes: tuple[str, ...] = ()


class PipelineOrchestrator:
    """选择流水线模式，不调用压缩或渲染。"""

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
