import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.repository.inspection.local_inspection_environment_repository import LocalInspectionEnvironmentRepository


def test_reads_synthetic_windows_and_huorong_registry_facts():
    repository = LocalInspectionEnvironmentRepository(
        system_reader=lambda: {
            "product_name": "Windows 10 Pro", "edition_id": "Professional",
            "display_version": "TEST-24H2", "build_number": "22631", "architecture": "AMD64",
        },
        software_reader=lambda: [{
            "display_name": "火绒安全软件 TEST", "display_version": "TEST-6.0.7.0",
            "install_location": "", "display_icon": "",
        }],
        platform_name="nt",
    )
    facts = repository.read()
    assert facts["operating_system"]["build_number"] == "22631"
    assert facts["huorong"] == {"detected": True, "version": "TEST-6.0.7.0"}


def test_prefers_huorong_security_software_over_app_store():
    repository = LocalInspectionEnvironmentRepository(
        system_reader=lambda: {},
        software_reader=lambda: [
            {
                "display_name": "火绒应用商店 TEST",
                "display_version": "TEST-STORE-1.0",
                "install_location": "C:/SYNTHETIC/HuorongStore",
                "display_icon": "",
            },
            {
                "display_name": "火绒安全软件 TEST",
                "display_version": "TEST-SECURITY-6.0.7.0",
                "install_location": "C:/SYNTHETIC/HuorongSecurity",
                "display_icon": "",
            },
        ],
        path_exists=lambda _path: False,
        platform_name="nt",
    )

    assert repository.read()["huorong"] == {
        "detected": True,
        "version": "TEST-SECURITY-6.0.7.0",
    }


def test_does_not_treat_huorong_app_store_as_security_software():
    repository = LocalInspectionEnvironmentRepository(
        system_reader=lambda: {},
        software_reader=lambda: [{
            "display_name": "火绒应用商店 TEST",
            "display_version": "TEST-STORE-1.0",
            "install_location": "C:/SYNTHETIC/HuorongStore",
            "display_icon": "",
        }],
        path_exists=lambda _path: False,
        platform_name="nt",
    )

    assert repository.read()["huorong"] == {"detected": False, "version": ""}


def test_uses_synthetic_file_version_when_registry_version_is_missing():
    repository = LocalInspectionEnvironmentRepository(
        system_reader=lambda: {},
        software_reader=lambda: [{
            "display_name": "Huorong Internet Security TEST", "display_version": "",
            "install_location": "C:/SYNTHETIC/Huorong", "display_icon": "",
        }],
        file_version_reader=lambda _path: "TEST-7.0.0.0",
        path_exists=lambda path: path.name == "HipsMain.exe",
        platform_name="nt",
    )
    assert repository.read()["huorong"] == {"detected": True, "version": "TEST-7.0.0.0"}


def test_preserves_detected_huorong_when_all_synthetic_version_sources_are_empty():
    repository = LocalInspectionEnvironmentRepository(
        system_reader=lambda: {},
        software_reader=lambda: [{
            "display_name": "火绒安全软件 TEST", "display_version": "",
            "install_location": "", "display_icon": "",
        }],
        path_exists=lambda _path: False,
        platform_name="nt",
    )
    assert repository.read()["huorong"] == {"detected": True, "version": ""}


def test_reports_huorong_not_detected_from_empty_synthetic_sources():
    repository = LocalInspectionEnvironmentRepository(
        system_reader=lambda: {}, software_reader=lambda: [],
        path_exists=lambda _path: False, platform_name="nt",
    )
    assert repository.read()["huorong"] == {"detected": False, "version": ""}


def test_returns_unavailable_facts_for_non_windows_or_reader_errors():
    non_windows = LocalInspectionEnvironmentRepository(platform_name="posix")
    assert non_windows.read() == {
        "operating_system": {}, "huorong": {"detected": False, "version": ""},
    }

    def fail():
        raise OSError("SYNTHETIC access denied")

    failed = LocalInspectionEnvironmentRepository(
        system_reader=fail, software_reader=fail, platform_name="nt",
        path_exists=lambda _path: False,
    )
    assert failed.read() == {
        "operating_system": {}, "huorong": {"detected": False, "version": ""},
    }
