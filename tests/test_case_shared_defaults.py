from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.shared_defaults_repository import SharedDefaultsRepository  # noqa: E402
from app.repository.workbench_database import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services import case_draft_service  # noqa: E402
from app.services.case_draft_service import (  # noqa: E402
    _initialize_draft,
    _prefix_report_software_for_selected_device,
)
from app.services.report_defaults_service import (  # noqa: E402
    DEFAULT_DOCUMENT_NUMBER,
    DEFAULT_HARDWARE_DEVICE,
    DEFAULT_INSPECTION_METHOD,
    DEFAULT_INSPECTION_PLACE,
)
from app.services.inspection_environment_service import InspectionEnvironmentService  # noqa: E402
from app.services.shared_defaults_service import SharedDefaultsService  # noqa: E402


def test_shared_defaults_patch_is_sparse_and_rejects_unknown_fields(tmp_path: Path):
    database = WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEFAULTS"), "SYNTHETIC-DEFAULTS")
    repository = SharedDefaultsRepository(database)
    initial = repository.get()

    updated = repository.patch({"document_number": "SYNTHETIC-DOC-001"}, initial["revision"])
    assert updated["status"] == "updated"
    assert updated["defaults"]["document_number"] == "SYNTHETIC-DOC-001"
    assert updated["defaults"]["inspection_place"] == ""

    second = repository.patch({"inspection_place": "SYNTHETIC-PLACE"}, updated["defaults"]["revision"])
    assert second["defaults"]["document_number"] == "SYNTHETIC-DOC-001"

    cleared = repository.patch(
        {"document_number": "   "}, second["defaults"]["revision"], allow_clear=True,
    )
    assert cleared["status"] == "updated"
    assert cleared["defaults"]["document_number"] == ""
    assert cleared["defaults"]["inspection_place"] == "SYNTHETIC-PLACE"

    with_inspectors = repository.patch(
        {"inspector_order": ["SYNTHETIC-A|SYNTHETIC-UNIT|SYNTHETIC-001"]},
        cleared["defaults"]["revision"],
    )
    cleared_inspectors = repository.patch(
        {"inspector_order": []}, with_inspectors["defaults"]["revision"], allow_clear=True,
    )
    assert cleared_inspectors["status"] == "updated"
    assert cleared_inspectors["defaults"]["inspector_order"] == []

    with pytest.raises(WorkbenchPersistenceError) as error:
        repository.patch({"case_name": "SYNTHETIC-FORBIDDEN"}, cleared_inspectors["defaults"]["revision"])
    assert error.value.code == "UNKNOWN_SHARED_DEFAULT_FIELD"
    assert repository.get()["document_number"] == ""


def test_entrust_unit_prefix_can_be_persisted_and_cleared(tmp_path: Path):
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-ENTRUST-PREFIX"),
        "SYNTHETIC-ENTRUST-PREFIX",
    )
    repository = SharedDefaultsRepository(database)

    initial = repository.get()
    assert initial["entrust_unit_prefix"] == ""

    updated = repository.patch(
        {"entrust_unit_prefix": "  SYNTHETIC-PUBLIC-SECURITY  "},
        initial["revision"],
    )
    assert updated["defaults"]["entrust_unit_prefix"] == "SYNTHETIC-PUBLIC-SECURITY"

    cleared = repository.patch(
        {"entrust_unit_prefix": "   "},
        updated["defaults"]["revision"],
    )
    assert cleared["status"] == "updated"
    assert cleared["defaults"]["entrust_unit_prefix"] == ""


def test_parser_non_empty_values_win_over_shared_defaults_without_mutating_inputs():
    report = {
        "document_number": "SYNTHETIC-PARSER-DOC",
        "introduction": {
            "inspection_place": "SYNTHETIC-PARSER-PLACE",
            "inspectors": [
                {"name": "SYNTHETIC-PARSER-A", "unit": "SYNTHETIC-UNIT-A", "badge_number": "SYNTHETIC-001"},
                {"name": "SYNTHETIC-PARSER-B", "unit": "SYNTHETIC-UNIT-B", "badge_number": "SYNTHETIC-002"},
            ],
        },
        "inspection": {
            "method": "SYNTHETIC-PARSER-METHOD",
            "hardware_device": "SYNTHETIC-PARSER-HARDWARE",
            "result": {"data_summary": "SYNTHETIC-PARSER-SUMMARY"},
        },
        "attachments": {"disc_number": "GP20260728-03"},
    }
    defaults = {
        "document_number": "SYNTHETIC-SHARED-DOC",
        "inspection_place": "SYNTHETIC-SHARED-PLACE",
        "inspection_method": "SYNTHETIC-SHARED-METHOD",
        "hardware_device": "SYNTHETIC-SHARED-HARDWARE",
        "inspector_order": ["SYNTHETIC-SHARED|SYNTHETIC-SHARED-UNIT|SYNTHETIC-999"],
        "disc_number_prefix": "ABC",
    }
    original_report = copy.deepcopy(report)
    original_defaults = copy.deepcopy(defaults)

    initialized, field_states = _initialize_draft(report, defaults)

    assert initialized["document_number"] == "SYNTHETIC-PARSER-DOC"
    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-PARSER-PLACE"
    assert initialized["inspection"]["method"] == "SYNTHETIC-PARSER-METHOD"
    assert initialized["inspection"]["hardware_device"] == "SYNTHETIC-PARSER-HARDWARE"
    assert initialized["introduction"]["inspectors"] == original_report["introduction"]["inspectors"]
    assert initialized["attachments"]["disc_number"] == "GP20260728-03"
    assert initialized["inspection"]["result"]["data_summary"] == "SYNTHETIC-PARSER-SUMMARY"
    assert all(field_states[path]["source"] == "report" for path in (
        "document_number",
        "introduction.inspection_place",
        "inspection.method",
        "inspection.hardware_device",
        "introduction.inspectors",
        "attachments.disc_number",
    ))
    assert report == original_report
    assert defaults == original_defaults


def test_parser_blank_missing_and_empty_array_values_use_shared_defaults():
    report = {
        "document_number": "   ",
        "introduction": {"inspection_place": "", "inspectors": []},
        "inspection": {
            "hardware_device": "\t",
            "result": {"data_summary": "SYNTHETIC-UNCHANGED-SUMMARY"},
        },
        "attachments": {"disc_number": ""},
    }
    defaults = {
        "entrust_unit_prefix": "SYNTHETIC-PREFIX",
        "document_number": "SYNTHETIC-DOC-001",
        "inspection_place": "SYNTHETIC-SHARED-PLACE",
        "inspection_method": "SYNTHETIC-SHARED-METHOD",
        "hardware_device": "SYNTHETIC-SHARED-HARDWARE",
        "inspector_order": [
            "SYNTHETIC-A|SYNTHETIC-UNIT-A|SYNTHETIC-001",
            "SYNTHETIC-B|SYNTHETIC-UNIT-B|SYNTHETIC-002",
        ],
        "disc_number_prefix": "ABC",
    }

    initialized, field_states = _initialize_draft(copy.deepcopy(report), defaults)

    assert initialized["introduction"]["entrust_unit_prefix"] == "SYNTHETIC-PREFIX"
    assert initialized["document_number"] == "SYNTHETIC-DOC-001"
    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-SHARED-PLACE"
    assert initialized["inspection"]["method"] == "SYNTHETIC-SHARED-METHOD"
    assert initialized["inspection"]["hardware_device"] == "SYNTHETIC-SHARED-HARDWARE"
    assert initialized["introduction"]["inspectors"] == [
        {"name": "SYNTHETIC-A", "unit": "SYNTHETIC-UNIT-A", "badge_number": "SYNTHETIC-001"},
        {"name": "SYNTHETIC-B", "unit": "SYNTHETIC-UNIT-B", "badge_number": "SYNTHETIC-002"},
    ]
    snapshot_id = initialized["introduction"]["inspector_snapshots"][0]["snapshot_id"]
    assert field_states[f"inspectors.{snapshot_id}.name"]["source"] == "system_default"
    assert initialized["inspection"]["result"]["data_summary"] == "SYNTHETIC-UNCHANGED-SUMMARY"
    assert initialized["attachments"]["disc_number"] == ""
    assert initialized["attachments"]["disc_number"] != defaults["disc_number_prefix"]
    assert all(field_states[path]["source"] == "system_default" for path in (
        "introduction.entrust_unit_prefix",
        "document_number",
        "introduction.inspection_place",
        "inspection.method",
        "inspection.hardware_device",
        "introduction.inspectors",
    ))


def test_parser_value_is_used_when_shared_default_is_empty():
    report = {
        "document_number": "",
        "introduction": {"inspection_place": "SYNTHETIC-PARSER-PLACE", "inspectors": []},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    initialized, _ = _initialize_draft(copy.deepcopy(report), {"inspection_place": ""})

    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-PARSER-PLACE"


def test_parser_inspector_snapshots_keep_structure_and_order_over_shared_defaults():
    report = {
        "document_number": "",
        "introduction": {
            "inspection_place": "",
            "inspectors": [],
            "inspector_snapshots": [
                {
                    "inspector_id": "SYNTHETIC-PARSER-2",
                    "name": "SYNTHETIC-PARSER-B",
                    "unit": "SYNTHETIC-UNIT-B",
                    "police_number": "SYNTHETIC-002",
                },
                {
                    "inspector_id": "SYNTHETIC-PARSER-1",
                    "name": "SYNTHETIC-PARSER-A",
                    "unit": "SYNTHETIC-UNIT-A",
                    "police_number": "SYNTHETIC-001",
                },
            ],
        },
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    initialized, field_states = _initialize_draft(copy.deepcopy(report), {
        "inspector_order": ["SYNTHETIC-SHARED|SYNTHETIC-UNIT|SYNTHETIC-001"],
    })

    snapshots = initialized["introduction"]["inspector_snapshots"]
    assert [item["inspector_id"] for item in snapshots] == [
        "SYNTHETIC-PARSER-2", "SYNTHETIC-PARSER-1",
    ]
    assert [item["selected_order"] for item in snapshots] == [0, 1]
    assert all(item["snapshot_id"] for item in snapshots)
    assert initialized["introduction"]["inspectors"] == []
    assert field_states["introduction.inspectors"]["source"] == "report"


def test_parser_empty_value_keeps_shared_prefill_and_service_rejects_forged_deployment(tmp_path: Path):
    report = {
        "document_number": "",
        "introduction": {"inspection_place": "", "inspectors": []},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    defaults = {
        "document_number": "", "inspection_place": "SYNTHETIC-SHARED-PLACE",
        "inspection_method": "", "hardware_device": "", "inspector_order": [], "disc_number_prefix": "",
    }
    initialized, _ = _initialize_draft(copy.deepcopy(report), defaults)
    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-SHARED-PLACE"
    database = WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-SERVER"), "SYNTHETIC-SERVER")
    with pytest.raises(WorkbenchPersistenceError) as error:
        SharedDefaultsService(database).patch(
            {"inspection_place": "SYNTHETIC-PLACE"}, 0,
            {"identity_kind": "local_session", "client_instance_id": "SYNTHETIC-C", "session_id": "SYNTHETIC-S", "deployment_instance_id": "SYNTHETIC-FORGED"},
        )
    assert error.value.code == "UNAUTHENTICATED_IDENTITY_REQUIRED"


def test_repository_rebuild_keeps_deployment_instance_defaults(tmp_path: Path):
    path = database_path_for_deployment(tmp_path, "SYNTHETIC-STABLE")
    first = WorkbenchDatabase(path, "SYNTHETIC-STABLE")
    repository = SharedDefaultsRepository(first)
    saved = repository.patch({"inspection_place": "SYNTHETIC-PERSISTED-PLACE"}, repository.get()["revision"])

    restarted = WorkbenchDatabase(path, "SYNTHETIC-STABLE")
    assert SharedDefaultsRepository(restarted).get()["inspection_place"] == "SYNTHETIC-PERSISTED-PLACE"
    assert saved["defaults"]["deployment_instance_id"] == "SYNTHETIC-STABLE"


def test_shared_default_change_only_affects_later_new_case_initialization(tmp_path: Path):
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-NEW-CASES"),
        "SYNTHETIC-NEW-CASES",
    )
    repository = SharedDefaultsRepository(database)
    first_defaults = repository.patch(
        {"inspection_place": "SYNTHETIC-FIRST-PLACE"},
        repository.get()["revision"],
    )["defaults"]
    blank_report = {
        "document_number": "",
        "introduction": {"inspection_place": "", "inspectors": []},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    existing_case, _ = _initialize_draft(blank_report, first_defaults)

    second_defaults = repository.patch(
        {"inspection_place": "SYNTHETIC-SECOND-PLACE"},
        first_defaults["revision"],
    )["defaults"]
    later_case, _ = _initialize_draft(blank_report, second_defaults)

    assert existing_case["introduction"]["inspection_place"] == "SYNTHETIC-FIRST-PLACE"
    assert later_case["introduction"]["inspection_place"] == "SYNTHETIC-SECOND-PLACE"


def test_parser_system_default_value_yields_to_shared_default():
    """Parser returning only the hardcoded system defaults must not block shared-default prefill."""
    report = {
        "document_number": DEFAULT_DOCUMENT_NUMBER,
        "introduction": {"inspection_place": DEFAULT_INSPECTION_PLACE, "inspectors": []},
        "inspection": {
            "method": DEFAULT_INSPECTION_METHOD,
            "hardware_device": DEFAULT_HARDWARE_DEVICE,
        },
        "attachments": {"disc_number": ""},
    }
    defaults = {
        "document_number": "SYNTHETIC-SHARED-DOC",
        "inspection_place": "SYNTHETIC-SHARED-PLACE",
        "inspection_method": "SYNTHETIC-SHARED-METHOD",
        "hardware_device": "SYNTHETIC-SHARED-HARDWARE",
        "inspector_order": [],
        "disc_number_prefix": "",
    }

    initialized, field_states = _initialize_draft(copy.deepcopy(report), defaults)

    assert initialized["document_number"] == "SYNTHETIC-SHARED-DOC"
    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-SHARED-PLACE"
    assert initialized["inspection"]["method"] == "SYNTHETIC-SHARED-METHOD"
    assert initialized["inspection"]["hardware_device"] == "SYNTHETIC-SHARED-HARDWARE"
    assert all(field_states[path]["source"] == "system_default" for path in (
        "document_number",
        "introduction.inspection_place",
        "inspection.method",
        "inspection.hardware_device",
    ))


def test_environment_projection_uses_hardware_after_shared_default_selection():
    report = {
        "introduction": {"inspection_place": "", "inspectors": []},
        "inspection": {
            "method": "", "hardware_device": "",
            "process_steps": [{"step_number": 3, "content": "SYNTHETIC placeholder"}],
        },
        "attachments": {"disc_number": ""},
    }
    initialized, _ = _initialize_draft(report, {
        "hardware_device": "SYNTHETIC-SHARED-HARDWARE",
    })

    class SyntheticRepository:
        def read(self):
            return {
                "operating_system": {},
                "huorong": {"detected": False, "version": ""},
            }

    projected = InspectionEnvironmentService(SyntheticRepository()).apply_to_report(initialized)
    step_three = projected["inspection"]["process_steps"][0]["content"]
    assert "SYNTHETIC-SHARED-HARDWARE" in step_three
    assert "操作系统信息待确认" in step_three


def test_company_prefix_resolves_after_shared_hardware_default(monkeypatch):
    report = {
        "document_number": DEFAULT_DOCUMENT_NUMBER,
        "introduction": {"inspection_place": "", "inspectors": []},
        "inspection": {
            "method": "", "hardware_device": DEFAULT_HARDWARE_DEVICE,
            "primary_software": {
                "name": "SYNTHETIC软件", "version": "V1",
                "confirmation_status": "confirmed_by_report", "provenance": [], "candidates": [],
            },
            "software_tools": [{"name": "SYNTHETIC软件", "version": "V1"}],
            "process_steps": [{"step_number": 4, "content": "启动SYNTHETIC软件（版本号为V1）。"}],
            "result": {"software_name": "SYNTHETIC软件", "software_version": "V1"},
        },
        "attachments": {"disc_number": ""},
    }
    initialized, _ = _initialize_draft(report, {"hardware_device": "SYNTHETIC SHARED DEVICE"})
    observed = []
    monkeypatch.setattr(
        case_draft_service, "company_for_device_name",
        lambda device_name: observed.append(device_name) or "TEST公司",
    )

    prefixed = _prefix_report_software_for_selected_device(initialized)

    assert observed == ["SYNTHETIC SHARED DEVICE"]
    assert prefixed["inspection"]["primary_software"]["name"] == "TEST公司SYNTHETIC软件"


def test_parser_system_default_value_kept_when_no_shared_default():
    """Without a shared default, the parser's system default remains and is sourced as system_default."""
    report = {
        "document_number": DEFAULT_DOCUMENT_NUMBER,
        "introduction": {"inspection_place": DEFAULT_INSPECTION_PLACE, "inspectors": []},
        "inspection": {
            "method": DEFAULT_INSPECTION_METHOD,
            "hardware_device": DEFAULT_HARDWARE_DEVICE,
        },
        "attachments": {"disc_number": ""},
    }
    defaults = {
        "document_number": "", "inspection_place": "", "inspection_method": "",
        "hardware_device": "", "inspector_order": [], "disc_number_prefix": "",
    }

    initialized, field_states = _initialize_draft(copy.deepcopy(report), defaults)

    assert initialized["document_number"] == DEFAULT_DOCUMENT_NUMBER
    assert initialized["introduction"]["inspection_place"] == DEFAULT_INSPECTION_PLACE
    assert initialized["inspection"]["method"] == DEFAULT_INSPECTION_METHOD
    assert initialized["inspection"]["hardware_device"] == DEFAULT_HARDWARE_DEVICE
    assert all(field_states[path]["source"] == "system_default" for path in (
        "document_number",
        "introduction.inspection_place",
        "inspection.method",
        "inspection.hardware_device",
    ))
