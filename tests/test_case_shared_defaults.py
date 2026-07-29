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
from app.services.case_draft_service import _initialize_draft  # noqa: E402
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

    unchanged = repository.patch({"document_number": "   "}, updated["defaults"]["revision"])
    assert unchanged["status"] == "unchanged"
    assert unchanged["defaults"]["document_number"] == "SYNTHETIC-DOC-001"

    with pytest.raises(WorkbenchPersistenceError) as error:
        repository.patch({"case_name": "SYNTHETIC-FORBIDDEN"}, unchanged["defaults"]["revision"])
    assert error.value.code == "UNKNOWN_SHARED_DEFAULT_FIELD"
    assert repository.get()["document_number"] == "SYNTHETIC-DOC-001"


def test_parser_initialization_applies_inspectors_and_prefix_without_copying_full_disc_number():
    report = {
        "document_number": "",
        "introduction": {"inspection_place": "", "inspectors": []},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": "GP20260728-03"},
    }
    defaults = {
        "document_number": "SYNTHETIC-DOC-001",
        "inspection_place": "SYNTHETIC-PLACE",
        "inspection_method": "SYNTHETIC-METHOD",
        "hardware_device": "SYNTHETIC-HARDWARE",
        "inspector_order": ["SYNTHETIC-A|SYNTHETIC-UNIT|SYNTHETIC-001"],
        "disc_number_prefix": "ABC",
    }

    initialized, _ = _initialize_draft(copy.deepcopy(report), defaults)

    assert initialized["document_number"] == "SYNTHETIC-DOC-001"
    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-PLACE"
    assert initialized["introduction"]["inspectors"][0]["name"] == "SYNTHETIC-A"
    assert initialized["attachments"]["disc_number"] == "ABC20260728-03"
    assert initialized["attachments"]["disc_number"] != "ABC"


def test_shared_default_overrides_parser_value_for_new_case_without_mutating_defaults():
    report = {
        "document_number": "",
        "introduction": {"inspection_place": "SYNTHETIC-PARSER-PLACE", "inspectors": []},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    defaults = {
        "document_number": "SYNTHETIC-DOC-001",
        "inspection_place": "SYNTHETIC-SHARED-PLACE",
        "inspection_method": "",
        "hardware_device": "",
        "inspector_order": [],
        "disc_number_prefix": "",
    }

    initialized, _ = _initialize_draft(copy.deepcopy(report), defaults)

    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-SHARED-PLACE"
    assert defaults["inspection_place"] == "SYNTHETIC-SHARED-PLACE"


def test_parser_value_is_used_when_shared_default_is_empty():
    report = {
        "document_number": "",
        "introduction": {"inspection_place": "SYNTHETIC-PARSER-PLACE", "inspectors": []},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    initialized, _ = _initialize_draft(copy.deepcopy(report), {"inspection_place": ""})

    assert initialized["introduction"]["inspection_place"] == "SYNTHETIC-PARSER-PLACE"


def test_shared_inspectors_override_parser_inspectors_for_new_case():
    report = {
        "document_number": "",
        "introduction": {"inspection_place": "", "inspectors": [{"name": "SYNTHETIC-PARSER"}]},
        "inspection": {"method": "", "hardware_device": ""},
        "attachments": {"disc_number": ""},
    }
    initialized, _ = _initialize_draft(copy.deepcopy(report), {
        "inspector_order": ["SYNTHETIC-SHARED|SYNTHETIC-UNIT|SYNTHETIC-001"],
    })

    assert initialized["introduction"]["inspectors"] == [{
        "name": "SYNTHETIC-SHARED", "unit": "SYNTHETIC-UNIT", "badge_number": "SYNTHETIC-001",
    }]


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
