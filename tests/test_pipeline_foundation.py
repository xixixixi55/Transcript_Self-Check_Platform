"""Foundation tests for centralized pipeline mode and Export Gate facts."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.export_gate_service import (
    ExportGateCode,
    ExportGateInput,
    ExportGateIssue,
    evaluate_export_gate,
)
from app.services.pipeline_runtime_service import (
    PipelineMode,
    PipelineOrchestrator,
    PipelineRunStatus,
    load_pipeline_settings,
)


def test_pipeline_mode_defaults_to_legacy_without_environment_dependency():
    settings = load_pipeline_settings({})

    assert settings.mode is PipelineMode.LEGACY
    assert settings.source == "default"
    assert settings.cache_namespace == "pipeline-legacy"


def test_pipeline_mode_accepts_test_override_and_isolates_cache_namespace():
    shadow = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    canonical = load_pipeline_settings({"BIJI_PIPELINE_MODE": "canonical"})

    assert shadow.mode is PipelineMode.SHADOW
    assert canonical.mode is PipelineMode.CANONICAL
    assert shadow.cache_namespace != canonical.cache_namespace


def test_pipeline_mode_config_override_does_not_mutate_environment_or_later_tests(monkeypatch):
    monkeypatch.setenv("BIJI_PIPELINE_MODE", "shadow")

    explicit = load_pipeline_settings({"BIJI_PIPELINE_MODE": "canonical"})
    isolated_default = load_pipeline_settings({})

    assert explicit.mode is PipelineMode.CANONICAL
    assert isolated_default.mode is PipelineMode.LEGACY


def test_invalid_pipeline_mode_falls_back_to_legacy_with_diagnostic_fact():
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "unsupported"})

    assert settings.mode is PipelineMode.LEGACY
    assert settings.source == "invalid_fallback"
    assert settings.invalid_value == "unsupported"


def test_pipeline_orchestrator_shadow_does_not_create_second_formal_output():
    result = PipelineOrchestrator(
        load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    ).run(legacy_output="legacy-doc", canonical_output="canonical-data")

    assert result.status is PipelineRunStatus.SHADOW_COMPARE_ONLY
    assert result.formal_output == "legacy-doc"
    assert result.canonical_output == "canonical-data"


def test_pipeline_orchestrator_legacy_discards_canonical_and_shadow_inputs():
    result = PipelineOrchestrator(load_pipeline_settings({})).run(
        legacy_output="legacy-doc",
        canonical_output="canonical-data",
        comparison="comparison-data",
    )

    assert result.formal_output == "legacy-doc"
    assert result.canonical_output is None
    assert result.comparison is None


def test_pipeline_orchestrator_canonical_is_explicitly_not_enabled_in_foundation():
    result = PipelineOrchestrator(
        load_pipeline_settings({"BIJI_PIPELINE_MODE": "canonical"})
    ).run(legacy_output="legacy-doc", canonical_output="canonical-data")

    assert result.status is PipelineRunStatus.CANONICAL_NOT_ENABLED
    assert result.formal_output is None
    assert result.diagnostic_codes == ("CANONICAL_NOT_ENABLED",)


def test_export_gate_reports_all_blockers_and_keeps_warnings_separate():
    warning = ExportGateIssue("INFO", "photos", "图片输入为空。")
    result = evaluate_export_gate(
        ExportGateInput(
            material_types_confirmed=False,
            primary_software_confirmed=False,
            photo_count_valid=False,
            automatic_archive_required=True,
            winrar_available=False,
            archive_manifest_required=True,
            archive_manifest_present=False,
            warnings=(warning,),
        )
    )

    assert not result.allowed
    assert [item.code for item in result.blockers] == [
        ExportGateCode.MATERIAL_TYPE_UNCONFIRMED,
        ExportGateCode.PRIMARY_SOFTWARE_UNCONFIRMED,
        ExportGateCode.ODD_PHOTO_COUNT,
        ExportGateCode.WINRAR_UNAVAILABLE,
        ExportGateCode.ARCHIVE_MANIFEST_MISSING,
    ]
    assert result.warnings == (warning,)


def test_export_gate_is_pure_and_allows_editable_non_archive_state():
    result = evaluate_export_gate(
        ExportGateInput(
            automatic_archive_required=False,
            archive_manifest_required=False,
            warnings=(),
        )
    )

    assert result.allowed
    assert result.blockers == ()
