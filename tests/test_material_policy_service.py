"""Synthetic tests for stage-one material classification and export gating."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.export_gate_service import ExportGateInput, evaluate_export_gate
from app.services.material_policy_service import (
    classify_material_type,
    enrich_report_material_types,
    material_from_legacy_item,
    reviewed_material_display_name,
    select_display_identifiers,
    unconfirmed_material_fields,
)


def test_reviewed_material_display_name_appends_type_without_duplication():
    reviewed_phone = {
        "device_name": "SYNTHETIC HUAWEI SGU-AL10",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }
    reviewed_tablet = {
        "device_name": "SYNTHETIC TABLET TEST",
        "material_type": "tablet",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }

    assert reviewed_material_display_name(reviewed_phone) == "SYNTHETIC HUAWEI SGU-AL10手机"
    assert reviewed_material_display_name(reviewed_tablet) == "SYNTHETIC TABLET TEST"


def test_reviewed_material_display_name_distinguishes_type_from_product_text():
    reviewed_phone = {
        "device_name": "SYNTHETIC 手机壳 X",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }
    reviewed_tablet = {
        "device_name": "SYNTHETIC 平板电脑 X",
        "material_type": "tablet",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }

    assert reviewed_material_display_name(reviewed_phone) == "SYNTHETIC 手机壳 X手机"
    assert reviewed_material_display_name(reviewed_tablet) == "SYNTHETIC 平板电脑 X"


def test_reviewed_material_display_name_handles_empty_and_unconfirmed_items():
    assert reviewed_material_display_name({
        "model": "SYNTHETIC MODEL",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }) == "SYNTHETIC MODEL手机"
    assert reviewed_material_display_name({
        "device_type": "手机",
        "material_type": "phone",
        "material_type_status": "confirmed_by_report",
        "material_type_source": "report",
    }) == "手机"
    assert reviewed_material_display_name({
        "device_name": "SYNTHETIC HUAWEI",
        "device_type": "Android设备",
    }) is None


def test_controlled_device_type_words_classify_phone_and_tablet():
    assert classify_material_type("  iＰhone 14 ").status == "confirmed_by_report"
    assert classify_material_type("iＰhone 14").source == "report"
    assert classify_material_type("平板电脑").status == "confirmed_by_report"


def test_unknown_or_conflicting_device_type_stays_unconfirmed():
    assert classify_material_type("Model-phonecase").diagnostic_code == "MATERIAL_TYPE_DEVICE_TYPE_UNRECOGNIZED"
    assert classify_material_type("iPhone 平板").diagnostic_code == "MATERIAL_TYPE_CONFLICT"
    assert classify_material_type(None).source == "none"


def test_classification_does_not_use_identifier_or_model_values():
    material = material_from_legacy_item(
        {
            "id": "material-synthetic-1",
            "device_type": "Unknown device",
            "model": "iPhone model value must not classify",
            "imei1": "123456789012345",
            "serial_number": "SERIAL-SYNTHETIC-1",
            "evidence_number": "E-SYNTHETIC-1",
        },
        0,
    )
    assert material.type == "unconfirmed"
    assert select_display_identifiers(material) == ()


def test_legacy_display_device_name_is_not_an_explicit_type_candidate():
    material = material_from_legacy_item(
        {"device_type": "iPhone 15", "device_type_source": "legacy_display"},
        0,
    )
    assert material.type == "unconfirmed"
    assert material.classification.diagnostic_code == "MATERIAL_TYPE_DEVICE_TYPE_NOT_EXPLICIT"


def test_manual_confirmation_can_override_legacy_display_label():
    material = material_from_legacy_item(
        {
            "device_type": "iPhone 15",
            "device_type_source": "legacy_display",
            "material_type": "tablet",
            "material_type_status": "confirmed_by_user",
            "material_type_source": "user",
        },
        0,
    )
    assert material.type == "tablet"
    assert material.classification.status == "confirmed_by_user"


def test_display_policy_selects_only_allowed_valid_identifiers():
    phone = material_from_legacy_item(
        {
            "device_type": "手机",
            "imei1": "123456789012345",
            "imei2": "not-an-imei",
            "serial_number": "SERIAL-SYNTHETIC-1",
            "evidence_number": "E-SYNTHETIC-1",
        },
        0,
    )
    tablet = material_from_legacy_item(
        {
            "device_type": "tablet",
            "imei1": "123456789012345",
            "serial_number": " SERIAL-SYNTHETIC-2 ",
            "evidence_number": "E-SYNTHETIC-2",
        },
        1,
    )
    assert [item.type for item in select_display_identifiers(phone)] == ["imei1"]
    assert [item.value for item in select_display_identifiers(tablet)] == ["SERIAL-SYNTHETIC-2"]


def test_manual_confirmation_is_distinct_from_report_candidate():
    material = material_from_legacy_item(
        {
            "device_type": "Unknown",
            "material_type": "tablet",
            "material_type_status": "confirmed_by_user",
            "material_type_source": "user",
            "evidence_number": "E-SYNTHETIC-3",
        },
        0,
    )
    assert material.type == "tablet"
    assert material.classification.status == "confirmed_by_user"
    assert material.classification.source == "user"


def test_old_material_type_without_status_is_not_treated_as_confirmed():
    material = material_from_legacy_item(
        {"device_type": "手机", "material_type": "phone", "evidence_number": "E-SYNTHETIC-4"},
        0,
    )
    assert material.type == "unconfirmed"
    assert material.classification.diagnostic_code == "MATERIAL_TYPE_STATUS_MISSING"


def test_unconfirmed_classification_never_selects_display_identifiers():
    material = material_from_legacy_item(
        {
            "device_type": "手机",
            "material_type": "phone",
            "material_type_status": "unconfirmed",
            "material_type_source": "report",
            "imei1": "123456789012345",
            "evidence_number": "E-SYNTHETIC-5",
        },
        0,
    )
    assert material.type == "unconfirmed"
    assert select_display_identifiers(material) == ()


def test_enrichment_preserves_manual_state_and_adds_report_candidate():
    report = {
        "introduction": {
            "evidence_list": [
                {"device_type": "手机", "evidence_number": "E-SYNTHETIC-1"},
                {
                    "device_type": "Unknown",
                    "material_type": "tablet",
                    "material_type_status": "confirmed_by_user",
                    "material_type_source": "user",
                    "evidence_number": "E-SYNTHETIC-2",
                },
            ]
        }
    }
    enriched = enrich_report_material_types(report)
    first, second = enriched["introduction"]["evidence_list"]
    assert first["material_type_status"] == "confirmed_by_report"
    assert second["material_type_status"] == "confirmed_by_user"
    assert "material_type_status" not in report["introduction"]["evidence_list"][0]


def test_export_gate_locates_each_unconfirmed_material_without_sensitive_values():
    report = {
        "introduction": {
            "evidence_list": [
                {
                    "id": "material-1",
                    "device_type": "手机",
                    "material_type": "phone",
                    "material_type_status": "confirmed_by_report",
                    "material_type_source": "report",
                },
                {"id": "material-2", "material_type": "unconfirmed", "material_type_status": "unconfirmed"},
            ]
        }
    }
    fields = unconfirmed_material_fields(report)
    result = evaluate_export_gate(
        ExportGateInput(material_types_confirmed=not fields, material_type_fields=fields)
    )
    assert fields == ("introduction.evidence_list[id=material-2].material_type",)
    assert not result.allowed
    assert result.blockers[0].code.value == "MATERIAL_TYPE_UNCONFIRMED"
    assert result.blockers[0].field == fields[0]


def test_export_gate_rechecks_report_confirmed_material_type_against_device_type():
    report = {
        "introduction": {
            "evidence_list": [{
                "id": "material-forged",
                "device_type": "未知设备",
                "material_type": "phone",
                "material_type_status": "confirmed_by_report",
                "material_type_source": "report",
            }]
        }
    }
    assert unconfirmed_material_fields(report) == (
        "introduction.evidence_list[id=material-forged].material_type",
    )
