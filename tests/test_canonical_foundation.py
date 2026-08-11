"""Synthetic tests for the canonical model and compatibility projection."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.canonical_adapter_service import (
    canonical_to_inspection_report,
    inspection_report_to_canonical,
)
from app.services.canonical_models_service import (
    CanonicalCaseInfo,
    CanonicalInspectionCase,
    FieldProvenance,
    InspectorSnapshot,
    Material,
    MaterialIdentifier,
    SoftwareTool,
)


def _canonical_case() -> CanonicalInspectionCase:
    provenance = FieldProvenance(
        source_type="synthetic_fixture",
        source_file="fixture.json",
        json_path="case.materials[0]",
        adapter="synthetic-adapter",
        confidence=1,
    )
    material = Material(
        id="material-1",
        evidence_number="E-001",
        type="phone",
        name="Synthetic phone",
        model="Model-X",
        identifiers=[
            MaterialIdentifier(type="imei1", value="imei-synthetic-1", provenance=[provenance]),
            MaterialIdentifier(type="serial_number", value="serial-synthetic-1", provenance=[provenance]),
        ],
        provenance=[provenance],
    )
    return CanonicalInspectionCase(
        case_info=CanonicalCaseInfo(
            title="Synthetic inspection",
            document_number="DOC-001",
            case_number="CASE-001",
        ),
        materials=[material],
        inspectors=[
            InspectorSnapshot(
                inspector_id="inspector-1",
                name="Synthetic inspector",
                unit="Synthetic unit",
                police_number="P-001",
                selected_order=0,
            )
        ],
        software_tools=[
            SoftwareTool(
                category="main_forensic",
                name="Synthetic forensic tool",
                version="1.0",
                display_name="Synthetic forensic tool 1.0",
                provenance=[provenance],
                confirmation_status="confirmed",
            )
        ],
    )


def test_canonical_to_inspection_report_preserves_identifiers_and_order():
    report = canonical_to_inspection_report(_canonical_case())

    assert report["case_number"] == "CASE-001"
    assert report["introduction"]["evidence_list"][0]["imei1"] == "imei-synthetic-1"
    assert report["introduction"]["evidence_list"][0]["serial_number"] == "serial-synthetic-1"
    assert report["introduction"]["inspectors"][0]["badge_number"] == "P-001"
    assert report["inspection"]["result"]["software_name"] == "Synthetic forensic tool"


def test_entrust_unit_prefix_survives_canonical_compatibility_projection():
    legacy = {
        "title": "Synthetic inspection",
        "document_number": "SYNTHETIC-DOC-001",
        "introduction": {
            "entrust_unit_prefix": "SYNTHETIC-PUBLIC-SECURITY",
            "entrust_unit": "SYNTHETIC-STATION",
        },
    }

    canonical = inspection_report_to_canonical(legacy).canonical_case
    assert canonical.case_info.introduction.entrust_unit_prefix == "SYNTHETIC-PUBLIC-SECURITY"
    projected = canonical_to_inspection_report(canonical)
    assert projected["introduction"]["entrust_unit_prefix"] == "SYNTHETIC-PUBLIC-SECURITY"
    assert projected["introduction"]["entrust_unit"] == "SYNTHETIC-STATION"

    legacy["introduction"]["entrust_unit_prefix"] = ""
    empty = inspection_report_to_canonical(legacy).canonical_case
    assert empty.case_info.introduction.entrust_unit_prefix == ""
    assert canonical_to_inspection_report(empty)["introduction"]["entrust_unit_prefix"] == ""

    del legacy["introduction"]["entrust_unit_prefix"]
    missing = inspection_report_to_canonical(legacy).canonical_case
    assert missing.case_info.introduction.entrust_unit_prefix == ""


def test_canonical_model_supports_all_material_states_and_identifier_types():
    materials = [
        Material(
            id="phone-1",
            evidence_number="E-001",
            type="phone",
            identifiers=[
                MaterialIdentifier(type="imei1", value="imei-one"),
                MaterialIdentifier(type="imei2", value="imei-two"),
            ],
        ),
        Material(
            id="tablet-1",
            evidence_number="E-002",
            type="tablet",
            identifiers=[MaterialIdentifier(type="serial_number", value="serial-one")],
        ),
        Material(
            id="unknown-1",
            evidence_number="E-003",
            type="unconfirmed",
            identifiers=[MaterialIdentifier(type="serial_number", value="serial-two")],
        ),
    ]

    assert [material.type for material in materials] == [
        "phone",
        "tablet",
        "unconfirmed",
    ]
    assert [identifier.type for identifier in materials[0].identifiers] == [
        "imei1",
        "imei2",
    ]
    assert materials[1].identifiers[0].type == "serial_number"
    assert materials[2].identifiers[0].value == "serial-two"


def test_canonical_projection_preserves_material_and_inspector_input_order():
    case = _canonical_case()
    case.materials.append(
        Material(id="material-2", evidence_number="E-002", type="tablet")
    )
    case.inspectors.append(
        InspectorSnapshot(
            inspector_id="inspector-2",
            name="Second synthetic inspector",
            unit="Synthetic unit",
            police_number="P-002",
            selected_order=1,
        )
    )

    report = canonical_to_inspection_report(case)

    assert [item["evidence_number"] for item in report["introduction"]["evidence_list"]] == [
        "E-001",
        "E-002",
    ]
    assert [item["name"] for item in report["introduction"]["inspectors"]] == [
        "Synthetic inspector",
        "Second synthetic inspector",
    ]


def test_canonical_projection_does_not_pollute_legacy_dto_with_new_fields():
    report = canonical_to_inspection_report(_canonical_case())

    assert "provenance" not in report
    assert "archive_manifest" not in report
    assert "template_profile" not in report


def test_legacy_to_canonical_is_limited_migration_and_does_not_infer_material_type():
    result = inspection_report_to_canonical(
        {
            "title": "Synthetic inspection",
            "document_number": "DOC-001",
            "case_number": "CASE-001",
            "introduction": {
                "evidence_list": [
                    {
                        "id": "material-1",
                        "device_type": "Unknown device",
                        "imei1": "imei-synthetic-1",
                        "evidence_number": "E-001",
                    }
                ],
                "inspectors": [
                    {"name": "Synthetic inspector", "unit": "Synthetic unit", "badge_number": "P-001"}
                ],
                "inspector_snapshots": [
                    {
                        "snapshot_id": "SYNTHETIC-SNAPSHOT-001",
                        "name": "Synthetic inspector",
                        "unit": "Synthetic unit",
                        "police_number": "P-001",
                    }
                ],
                "inspection_time_range": "synthetic-range",
            },
            "inspection": {
                "software_tools": [{"name": "Unknown tool", "version": "1.0"}]
            },
        }
    )

    assert result.canonical_case.materials[0].type == "unconfirmed"
    assert result.canonical_case.materials[0].identifiers[0].type == "imei1"
    assert result.canonical_case.inspectors[0].selected_order == 0
    assert result.canonical_case.inspectors[0].snapshot_id == "SYNTHETIC-SNAPSHOT-001"
    assert "archive_manifest" in result.missing_fields
    assert "LEGACY_INPUT_INCOMPLETE" in result.diagnostic_codes


def test_legacy_migration_does_not_turn_missing_values_into_literal_none():
    result = inspection_report_to_canonical(
        {"title": None, "document_number": None, "introduction": None, "inspection": None}
    )

    assert result.canonical_case.case_info.title == ""
    assert result.canonical_case.case_info.document_number == ""
    assert result.canonical_case.materials == []


def test_legacy_disc_number_best_effort_migration_derives_sequence_and_date():
    result = inspection_report_to_canonical({
        "title": "Synthetic inspection",
        "document_number": "DOC-001",
        "attachments": {
            "disc_number": "gp20260706-09",
            "burning_date": "2099年1月1日",
        },
    })

    sequence = result.canonical_case.attachments.disc_sequence
    assert sequence is not None
    assert sequence.first_disc_number == "GP20260706-09"
    assert sequence.date == "2026-07-06"
    assert result.canonical_case.attachments.burning_date == "2026年7月6日"


def test_legacy_invalid_disc_number_does_not_preserve_manual_date():
    result = inspection_report_to_canonical({
        "title": "Synthetic inspection",
        "document_number": "DOC-001",
        "attachments": {
            "disc_number": "GP20260230-01",
            "burning_date": "2026年2月30日",
        },
    })

    assert result.canonical_case.attachments.disc_sequence is None
    assert result.canonical_case.attachments.burning_date is None
