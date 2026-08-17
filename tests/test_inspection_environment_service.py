import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.services.inspection_environment_service import InspectionEnvironmentService


class SyntheticRepository:
    def __init__(self, facts):
        self.facts = facts

    def read(self):
        return self.facts


def test_captures_windows_11_and_projects_detected_huorong():
    service = InspectionEnvironmentService(SyntheticRepository({
        "operating_system": {
            "product_name": "Windows 10 Pro", "edition_id": "Professional",
            "display_version": "TEST-24H2", "build_number": "22631", "architecture": "AMD64",
        },
        "huorong": {"detected": True, "version": "TEST-6.0.7.0"},
    }))
    report = {
        "inspection": {
            "hardware_device": "TEST-A 手机取证工作站",
            "process_steps": [
                {"step_number": 2, "content": "SYNTHETIC step 2"},
                {"step_number": 3, "content": "SYNTHETIC old environment"},
                {"step_number": 4, "content": "SYNTHETIC step 4"},
            ],
        },
    }
    projected = service.apply_to_report(report)
    snapshot = projected["inspection"]["environment_snapshot"]
    content = projected["inspection"]["process_steps"][1]["content"]
    assert snapshot["operating_system"]["display_name"] == "Windows 11 TEST-24H2 专业版 64位"
    assert "TEST-A 手机取证工作站" in content
    assert "火绒安全软件（版本号为TEST-6.0.7.0）" in content
    assert projected["inspection"]["process_steps"][0]["content"] == "SYNTHETIC step 2"
    assert projected["inspection"]["process_steps"][2]["content"] == "SYNTHETIC step 4"


def test_marks_unknown_huorong_version_without_using_a_default():
    service = InspectionEnvironmentService(SyntheticRepository({
        "operating_system": {"product_name": "Windows 11", "architecture": "AMD64"},
        "huorong": {"detected": True, "version": ""},
    }))
    snapshot = service.capture()
    assert snapshot["security_software"] == {
        "name": "火绒安全软件", "version": "", "status": "version_unknown",
    }


def test_formats_synthetic_windows_10_32_bit_without_upgrading_the_name():
    service = InspectionEnvironmentService(SyntheticRepository({
        "operating_system": {
            "product_name": "Windows 10 Enterprise", "edition_id": "Enterprise",
            "display_version": "TEST-22H2", "build_number": "19045", "architecture": "x86",
        },
        "huorong": {"detected": False, "version": ""},
    }))
    assert service.capture()["operating_system"]["display_name"] == (
        "Windows 10 TEST-22H2 企业版 32位"
    )


def test_missing_facts_use_pending_language_without_false_scan_result():
    service = InspectionEnvironmentService(SyntheticRepository({
        "operating_system": {}, "huorong": {"detected": False, "version": ""},
    }))
    projected = service.apply_to_report({
        "inspection": {
            "hardware_device": "", "process_steps": [{"step_number": 3, "content": "old"}],
        },
    })
    content = projected["inspection"]["process_steps"][0]["content"]
    assert "检查硬件设备待确认" in content
    assert "操作系统信息待确认" in content
    assert "安全软件待确认（版本号待确认）" in content
    assert "杀毒的结果待确认" in content
    assert "未发现病毒" not in content
