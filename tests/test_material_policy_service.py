"""第一阶段材料分类与导出门控的合成数据测试。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.export.export_gate_service import ExportGateInput, evaluate_export_gate
from app.services.inspection.material_policy_service import (
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


def test_reviewed_material_display_name_appends_type_after_product_family_name():
    reviewed_phone = {
        "device_name": "SYNTHETIC iPhone 14",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }
    reviewed_tablet = {
        "device_name": "SYNTHETIC iPad Air",
        "material_type": "tablet",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }

    assert reviewed_material_display_name(reviewed_phone) == "SYNTHETIC iPhone 14手机"
    assert reviewed_material_display_name(reviewed_tablet) == "SYNTHETIC iPad Air平板"


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
    assert classify_material_type("  iＰad Air ").status == "confirmed_by_report"
    assert classify_material_type("IＰAD Air").source == "report"
    assert classify_material_type("平板电脑").status == "confirmed_by_report"


def test_unknown_or_conflicting_device_type_stays_unconfirmed():
    assert classify_material_type("Model-phonecase").diagnostic_code == "MATERIAL_TYPE_DEVICE_TYPE_UNRECOGNIZED"
    assert classify_material_type("iPhone 平板").diagnostic_code == "MATERIAL_TYPE_CONFLICT"
    assert classify_material_type(None).source == "none"


@pytest.mark.parametrize("reported_type", ["手机壳", "非手机设备", "平板扫描仪"])
def test_chinese_type_substrings_do_not_confirm_material_type(reported_type):
    classification = classify_material_type(reported_type)

    assert classification.status == "unconfirmed"
    assert classification.diagnostic_code == "MATERIAL_TYPE_DEVICE_TYPE_UNRECOGNIZED"


def test_two_distinct_valid_imeis_infer_phone_when_explicit_type_is_missing():
    material = material_from_legacy_item(
        {
            "device_type": "",
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "imei2": "543210987654321",
        },
        0,
    )

    assert material.type == "phone"
    assert material.classification.status == "confirmed_by_report"
    assert material.classification.diagnostic_code == "MATERIAL_TYPE_INFERRED_FROM_DUAL_IMEI"


@pytest.mark.parametrize(
    ("brand", "expected_type"),
    [("iPhone", "phone"), (" iＰad ", "tablet")],
)
def test_apple_phone_brand_overrides_unreliable_phone_device_type(
    brand, expected_type,
):
    material = material_from_legacy_item(
        {
            "brand": brand,
            "device_type": "手机",
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "imei2": "543210987654321",
        },
        0,
    )

    assert material.type == expected_type
    assert material.classification.status == "confirmed_by_report"
    assert material.classification.diagnostic_code == "MATERIAL_TYPE_INFERRED_FROM_APPLE_BRAND"


def test_dual_imei_precedes_phone_device_type_and_phone_type_remains_last_fallback():
    dual_imei = material_from_legacy_item(
        {
            "brand": "SYNTHETIC-BRAND",
            "device_type": "手机",
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "imei2": "543210987654321",
        },
        0,
    )
    phone_type_only = material_from_legacy_item(
        {
            "brand": "SYNTHETIC-BRAND",
            "device_type": "手机",
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "imei2": "",
        },
        1,
    )

    assert dual_imei.type == "phone"
    assert dual_imei.classification.diagnostic_code == "MATERIAL_TYPE_INFERRED_FROM_DUAL_IMEI"
    assert phone_type_only.type == "phone"
    assert phone_type_only.classification.diagnostic_code is None


def test_non_exact_apple_brand_does_not_override_device_type():
    material = material_from_legacy_item(
        {
            "brand": "SYNTHETIC iPad ACCESSORY",
            "device_type": "手机",
            "device_type_source": "report_field",
            "imei1": "",
            "imei2": "",
        },
        0,
    )

    assert material.type == "phone"
    assert material.classification.diagnostic_code is None


@pytest.mark.parametrize(
    ("imei1", "imei2"),
    [
        ("123456789012345", ""),
        ("123456789012345", "123456789012345"),
        ("123456789012345", "not-an-imei"),
    ],
)
def test_incomplete_invalid_or_duplicate_imeis_do_not_infer_phone(imei1, imei2):
    material = material_from_legacy_item(
        {
            "device_type": "",
            "device_type_source": "report_field",
            "imei1": imei1,
            "imei2": imei2,
        },
        0,
    )

    assert material.type == "unconfirmed"


def test_explicit_tablet_and_type_conflict_are_not_overridden_by_dual_imei():
    tablet = material_from_legacy_item(
        {
            "device_type": "平板",
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "imei2": "543210987654321",
        },
        0,
    )
    conflict = material_from_legacy_item(
        {
            "device_type": "手机 / 平板",
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "imei2": "543210987654321",
        },
        1,
    )

    assert tablet.type == "tablet"
    assert conflict.type == "unconfirmed"
    assert conflict.classification.diagnostic_code == "MATERIAL_TYPE_CONFLICT"


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
            "device_type_source": "report_field",
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
            "device_type_source": "report_field",
            "imei1": "123456789012345",
            "serial_number": " SERIAL-SYNTHETIC-2 ",
            "evidence_number": "E-SYNTHETIC-2",
        },
        1,
    )
    assert [item.type for item in select_display_identifiers(phone)] == ["imei1"]
    assert [item.value for item in select_display_identifiers(tablet)] == ["SERIAL-SYNTHETIC-2"]


def test_missing_extractable_defaults_true_and_preserves_identifiers():
    material = material_from_legacy_item(
        {
            "device_type": "平板",
            "device_type_source": "report_field",
            "serial_number": "SERIAL-SYNTHETIC-ONLY",
            "evidence_number": "E-SYNTHETIC-SERIAL",
        },
        0,
    )

    assert material.extractable is True
    assert [(item.type, item.value) for item in material.identifiers] == [
        ("serial_number", "SERIAL-SYNTHETIC-ONLY"),
    ]


def test_explicit_extractable_value_remains_authoritative_without_imei():
    material = material_from_legacy_item(
        {"device_type": "平板", "serial_number": "SERIAL-SYNTHETIC", "extractable": True},
        0,
    )

    assert material.extractable is True


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
                {
                    "device_type": "手机",
                    "device_type_source": "report_field",
                    "evidence_number": "E-SYNTHETIC-1",
                },
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
                    "device_type_source": "report_field",
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


def test_dual_imei_inference_passes_export_gate_without_manual_confirmation():
    report = enrich_report_material_types({
        "introduction": {
            "evidence_list": [{
                "id": "material-SYNTHETIC-dual-imei",
                "device_type": "Android设备",
                "device_type_source": "report_field",
                "imei1": "123456789012345",
                "imei2": "543210987654321",
            }]
        }
    })

    material = report["introduction"]["evidence_list"][0]
    fields = unconfirmed_material_fields(report)
    result = evaluate_export_gate(
        ExportGateInput(material_types_confirmed=not fields, material_type_fields=fields)
    )

    assert material["material_type"] == "phone"
    assert material["material_type_status"] == "confirmed_by_report"
    assert material["material_type_diagnostic"] == "MATERIAL_TYPE_INFERRED_FROM_DUAL_IMEI"
    assert fields == ()
    assert result.allowed
    assert result.blockers == ()


def test_export_gate_rechecks_report_confirmed_material_type_against_device_type():
    report = {
        "introduction": {
            "evidence_list": [{
                "id": "material-forged",
                "device_type": "未知设备",
                "device_type_source": "report_field",
                "material_type": "phone",
                "material_type_status": "confirmed_by_report",
                "material_type_source": "report",
            }]
        }
    }
    assert unconfirmed_material_fields(report) == (
        "introduction.evidence_list[id=material-forged].material_type",
    )
