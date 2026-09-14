"""SYNTHETIC：陌生报告发现、确认、复用和已知格式隔离合同。"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.report import report_profile_service as profile_service_module  # noqa: E402
from app.repository.report import report_profile_discovery_repository as discovery_module  # noqa: E402
from app.repository.report.report_source_adapter import ReportAdapterDetectionError  # noqa: E402
from app.repository.workbench.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.repository.workbench.workbench_database import (  # noqa: E402
    WorkbenchDatabase, database_path_for_deployment,
)
from app.services.canonical.canonical_report_projector_service import (  # noqa: E402
    project_report_snapshot,
)
from app.services.report.report_profile_service import ReportProfileService  # noqa: E402
from synthetic_report_builders import build_parse_cache_report_tree  # noqa: E402


def _database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-PROFILE"),
        "SYNTHETIC-PROFILE",
    )


def _unknown_report(root: Path, suffix: str = "A") -> Path:
    root.mkdir()
    (root / "metadata.json").write_text(json.dumps({
        "案件名称": f"SYNTHETIC-CASE-{suffix}",
        "案件编号": f"SYNTHETIC-NO-{suffix}",
        "送检单位": f"SYNTHETIC-UNIT-{suffix}",
        "软件名称": "SYNTHETIC-FORENSIC",
        "软件版本": "9.1",
        "materials": [
            {
                "检材编号": f"SYNTHETIC-MATERIAL-{suffix}-1",
                "设备名称": "SYNTHETIC-PHONE",
                "设备型号": f"SYNTHETIC-MODEL-{suffix}-1",
                "IMEI1": "111111111111111",
            },
            {
                "检材编号": f"SYNTHETIC-MATERIAL-{suffix}-2",
                "设备名称": "SYNTHETIC-TABLET",
                "设备型号": f"SYNTHETIC-MODEL-{suffix}-2",
                "IMEI1": "222222222222222",
            },
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (root / "application.js").write_text(
        "SYNTHETIC_UNTRUSTED_FUNCTION();", encoding="utf-8",
    )
    return root


def test_known_adapter_short_circuits_profile_repository_and_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    known = tmp_path / "SYNTHETIC-KNOWN"
    build_parse_cache_report_tree(known)
    service = ReportProfileService(_database(tmp_path))
    monkeypatch.setattr(
        service.repository,
        "find_confirmed",
        lambda _fingerprint: pytest.fail("known adapter queried ReportProfile"),
    )

    result = service.prepare_selection(known)

    assert result["kind"] == "builtin"
    assert result["adapter"]["adapter_id"] == "meiya-new-v1"


def test_unknown_profile_requires_confirmation_persists_no_values_and_projects_all_materials(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    service = ReportProfileService(database)
    source = _unknown_report(tmp_path / "SYNTHETIC-UNKNOWN")

    discovery = service.prepare_selection(source)
    assert discovery["kind"] == "discovery"
    selected = [
        candidate["candidate_id"]
        for candidate in discovery["candidates"]
        if candidate["canonical_field"] in {
            "case.case_name", "case.case_number", "case.entrust_unit",
            "software.name", "software.version", "material.evidence_number",
            "material.name", "material.model", "material.imei1",
        }
    ]
    profile, confirmed_source = service.confirm(
        discovery["discovery_token"], selected, "SYNTHETIC 通用报告",
    )
    snapshot = service.build_snapshot(
        confirmed_source, profile["profile_id"], profile["version"],
    )
    report = project_report_snapshot(snapshot).report

    assert [
        report["introduction"]["entrust_unit"],
        report["case_number"],
        report["inspection"]["primary_software"]["name"],
        [item["evidence_number"] for item in report["introduction"]["evidence_list"]],
        [item["model"] for item in report["introduction"]["evidence_list"]],
    ] == [
        "SYNTHETIC-UNIT-A",
        "SYNTHETIC-NO-A",
        "SYNTHETIC-FORENSIC",
        ["SYNTHETIC-MATERIAL-A-1", "SYNTHETIC-MATERIAL-A-2"],
        ["SYNTHETIC-MODEL-A-1", "SYNTHETIC-MODEL-A-2"],
    ]
    with sqlite3.connect(database.database_path) as connection:
        persisted = connection.execute(
            "SELECT status, mappings_json FROM report_profiles",
        ).fetchone()
    assert persisted is not None and persisted[0] == "confirmed"
    assert "SYNTHETIC-CASE-A" not in persisted[1]
    assert "111111111111111" not in persisted[1]
    assert "preview_values" not in persisted[1]
    assert "application.js" not in snapshot.parsed_files
    duplicate = service.repository.save_confirmed(
        profile_id="report-profile-synthetic-duplicate",
        display_name="SYNTHETIC 通用报告",
        structure_fingerprint=profile["structure_fingerprint"],
        mappings=list(reversed(profile["mappings"])),
    )
    assert (duplicate["profile_id"], duplicate["display_name"]) == (
        profile["profile_id"], "SYNTHETIC 通用报告",
    )
    unsafe_mapping = [dict(profile["mappings"][0])]
    unsafe_mapping[0]["source_file"] = r"C:\SYNTHETIC\secret.json"
    with pytest.raises(WorkbenchPersistenceError) as unsafe_path:
        service.repository.save_confirmed(
            profile_id="report-profile-synthetic-absolute",
            display_name="SYNTHETIC ABSOLUTE",
            structure_fingerprint="synthetic-absolute-fingerprint",
            mappings=unsafe_mapping,
        )
    assert unsafe_path.value.code == "REPORT_PROFILE_INVALID"
    with pytest.raises(WorkbenchPersistenceError) as concurrent_conflict:
        service.repository.save_confirmed(
            profile_id="report-profile-synthetic-conflict",
            display_name="SYNTHETIC 覆盖尝试",
            structure_fingerprint=profile["structure_fingerprint"],
            mappings=profile["mappings"],
        )
    assert concurrent_conflict.value.code == "REPORT_PROFILE_CONFLICT"
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO report_profiles(profile_id,version,schema_version,display_name,"
            "structure_fingerprint,adapter_id,adapter_version,status,mappings_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "report-profile-synthetic-draft", 1, 1, "SYNTHETIC 草稿",
                "synthetic-draft-fingerprint", "report-profile-v1", "1.0.0",
                "draft", persisted[1], "2026-09-13T00:00:00Z", "2026-09-13T00:00:00Z",
            ),
        )
    assert service.repository.find_confirmed("synthetic-draft-fingerprint") is None


def test_confirmed_profile_reuses_same_structure_but_rejects_key_drift(
    tmp_path: Path,
) -> None:
    service = ReportProfileService(_database(tmp_path))
    first = _unknown_report(tmp_path / "SYNTHETIC-FIRST", "A")
    discovery = service.prepare_selection(first)
    selected = [
        item["candidate_id"] for item in discovery["candidates"]
        if item["canonical_field"] in {"case.case_name", "material.model"}
    ]
    profile, _ = service.confirm(
        discovery["discovery_token"], selected, "SYNTHETIC 结构",
    )
    same_shape = _unknown_report(tmp_path / "SYNTHETIC-SECOND", "B")

    assert service.prepare_selection(same_shape)["profile"]["profile_id"] == profile["profile_id"]

    partial = _unknown_report(tmp_path / "SYNTHETIC-PARTIAL", "C")
    partial_payload = json.loads((partial / "metadata.json").read_text(encoding="utf-8"))
    partial_payload["materials"][1].pop("设备型号")
    (partial / "metadata.json").write_text(
        json.dumps(partial_payload, ensure_ascii=False), encoding="utf-8",
    )
    assert service.prepare_selection(partial)["kind"] == "discovery"
    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_NOT_FOUND"):
        service.detect_confirmed(partial)
    with pytest.raises(WorkbenchPersistenceError) as incomplete_material:
        service.build_snapshot(partial, profile["profile_id"], profile["version"])
    assert incomplete_material.value.code == "REPORT_PROFILE_STRUCTURE_CHANGED"

    payload = json.loads((same_shape / "metadata.json").read_text(encoding="utf-8"))
    payload["materials"][0]["changed_model_key"] = payload["materials"][0].pop("设备型号")
    (same_shape / "metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8",
    )
    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_NOT_FOUND"):
        service.detect_confirmed(same_shape)


def test_structure_fingerprint_includes_empty_containers_and_metadata_file_set(
    tmp_path: Path,
) -> None:
    root = _unknown_report(tmp_path / "SYNTHETIC-EMPTY-STRUCTURE")
    baseline = discovery_module.discover_report_structure(root).structure_fingerprint
    payload = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    payload["new_container"] = []
    (root / "metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8",
    )
    with_empty_container = discovery_module.discover_report_structure(root).structure_fingerprint
    (root / "extra.json").write_text("{}", encoding="utf-8")
    with_extra_file = discovery_module.discover_report_structure(root).structure_fingerprint

    assert len({baseline, with_empty_container, with_extra_file}) == 3


def test_discovery_rejects_excessive_metadata_tree_before_profile_creation(
    tmp_path: Path,
) -> None:
    service = ReportProfileService(_database(tmp_path))
    root = tmp_path / "SYNTHETIC-TOO-DEEP"
    root.mkdir()
    nested: object = "SYNTHETIC-VALUE"
    for _ in range(34):
        nested = {"child": nested}
    (root / "metadata.json").write_text(json.dumps(nested), encoding="utf-8")

    with pytest.raises(WorkbenchPersistenceError) as error:
        service.prepare_selection(root)
    assert error.value.code == "REPORT_DISCOVERY_BUDGET_EXCEEDED"


def test_discovery_entry_budget_stops_scandir_before_unbounded_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    yielded = 0

    class FakeEntry:
        def __init__(self, index: int) -> None:
            self.name = f"entry-{index:05d}.json"

    class FakeScandir:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            nonlocal yielded
            for index in range(discovery_module.MAX_DISCOVERY_ENTRIES + 100):
                yielded += 1
                yield FakeEntry(index)

    monkeypatch.setattr(discovery_module.os, "scandir", lambda _path: FakeScandir())
    with pytest.raises(WorkbenchPersistenceError) as error:
        discovery_module._candidate_files(tmp_path)
    assert error.value.code == "REPORT_DISCOVERY_BUDGET_EXCEEDED"
    assert yielded == discovery_module.MAX_DISCOVERY_ENTRIES + 1


def test_confirmation_rejects_expired_session_and_conflicting_field_choices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _database(tmp_path)
    service = ReportProfileService(database)
    source = _unknown_report(tmp_path / "SYNTHETIC-CONFLICT")
    (source / "secondary.json").write_text(
        json.dumps({"案件名": "SYNTHETIC-SECOND-CANDIDATE"}, ensure_ascii=False),
        encoding="utf-8",
    )
    discovery = service.prepare_selection(source)
    duplicate_field_candidates = [
        item["candidate_id"] for item in discovery["candidates"]
        if item["canonical_field"] == "case.case_name"
    ]

    with pytest.raises(WorkbenchPersistenceError) as conflict:
        service.confirm(
            discovery["discovery_token"], duplicate_field_candidates,
            "SYNTHETIC 冲突映射",
        )
    assert conflict.value.code == "REPORT_PROFILE_FIELD_CONFLICT"

    current_time = profile_service_module.time.monotonic()
    monkeypatch.setattr(
        profile_service_module.time, "monotonic",
        lambda: current_time + profile_service_module._SESSION_TTL_SECONDS + 1,
    )
    with pytest.raises(WorkbenchPersistenceError) as expired:
        service.confirm(
            discovery["discovery_token"], [duplicate_field_candidates[0]],
            "SYNTHETIC 过期映射",
        )
    assert expired.value.code == "REPORT_DISCOVERY_SESSION_EXPIRED"

    with sqlite3.connect(database.database_path) as connection:
        persisted_count = connection.execute(
            "SELECT COUNT(*) FROM report_profiles",
        ).fetchone()[0]
    assert persisted_count == 0


def test_discovery_excludes_sensitive_subtrees_from_reads_candidates_and_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _unknown_report(tmp_path / "SYNTHETIC-EXCLUDED")
    sensitive_files = []
    for directory_name in ("附件", "attachment-data", "tool-program-details"):
        directory = root / directory_name
        directory.mkdir()
        secret = directory / "secret.json"
        secret.write_text(
            json.dumps({"案件名称": f"SYNTHETIC-SECRET-{directory_name}"}, ensure_ascii=False),
            encoding="utf-8",
        )
        sensitive_files.append(secret)
    original_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        if path in sensitive_files:
            pytest.fail("excluded report subtree must never be opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    first = discovery_module.discover_report_structure(root)
    with original_open(sensitive_files[0], "w", encoding="utf-8") as stream:
        stream.write(json.dumps({"案件名称": "SYNTHETIC-CHANGED-SECRET"}, ensure_ascii=False))
    second = discovery_module.discover_report_structure(root)

    assert first.source_fingerprint == second.source_fingerprint
    assert {item.relative_path for item in first.dependencies} == {"metadata.json"}
    assert all("SYNTHETIC-SECRET" not in value for item in first.candidates for value in item["preview_values"])


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (("replace", "REPORT_DISCOVERY_STRUCTURE_CHANGED"), ("grow", "REPORT_DISCOVERY_BUDGET_EXCEEDED")),
)
def test_discovery_rejects_file_replacement_or_growth_after_enumeration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, expected_code: str,
) -> None:
    root = _unknown_report(tmp_path / f"SYNTHETIC-TOCTOU-{mutation}")
    metadata = root / "metadata.json"
    original_read = discovery_module.read_bounded_dependency
    changed = False

    def mutate_before_read(
        path, dependency_root, max_bytes, *, expected_identity=None, expected_ancestors=None,
    ):
        nonlocal changed
        if not changed and path == metadata:
            changed = True
            if mutation == "grow":
                path.write_bytes(b" " * (max_bytes + 1))
            else:
                previous = path.with_suffix(".previous")
                path.replace(previous)
                path.write_text('{"案件名称":"SYNTHETIC-REPLACED"}', encoding="utf-8")
        return original_read(
            path, dependency_root, max_bytes,
            expected_identity=expected_identity,
            expected_ancestors=expected_ancestors,
        )

    monkeypatch.setattr(discovery_module, "read_bounded_dependency", mutate_before_read)
    with pytest.raises(WorkbenchPersistenceError) as error:
        discovery_module.discover_report_structure(root)
    assert error.value.code == expected_code


def test_discovery_rejects_ancestor_replacement_before_opening_external_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    root = tmp_path / "SYNTHETIC-ANCESTOR-SWAP"
    data = root / "metadata"
    data.mkdir(parents=True)
    candidate_path = data / "case.json"
    candidate_path.write_text('{"案件名称":"SYNTHETIC-SAFE"}', encoding="utf-8")
    external = tmp_path / "SYNTHETIC-EXTERNAL-METADATA"
    original_candidates = discovery_module._candidate_files

    def swap_ancestor(source_root: Path):
        selected = original_candidates(source_root)
        data.rename(external)
        if os.name == "nt":
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "New-Item -ItemType Junction -Path $env:SYNTHETIC_LINK "
                    "-Target $env:SYNTHETIC_TARGET | Out-Null",
                ],
                env={
                    **os.environ,
                    "SYNTHETIC_LINK": str(data),
                    "SYNTHETIC_TARGET": str(external),
                },
                check=True,
                capture_output=True,
            )
        else:
            data.symlink_to(external, target_is_directory=True)
        return selected

    original_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        if path == candidate_path:
            pytest.fail("metadata reached through a replaced ancestor must not be opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(discovery_module, "_candidate_files", swap_ancestor)
    monkeypatch.setattr(Path, "open", guarded_open)
    try:
        with pytest.raises(WorkbenchPersistenceError) as error:
            discovery_module.discover_report_structure(root)
        assert error.value.code == "REPORT_DISCOVERY_STRUCTURE_CHANGED"
    finally:
        if data.exists() or data.is_symlink():
            if os.name == "nt":
                os.rmdir(data)
            else:
                data.unlink()


def test_discovery_binds_ancestor_identity_even_when_file_identity_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "SYNTHETIC-ANCESTOR-HARDLINK"
    data = root / "metadata"
    data.mkdir(parents=True)
    metadata = data / "case.json"
    metadata.write_text('{"案件名称":"SYNTHETIC-SAFE"}', encoding="utf-8")
    old_data = root / "metadata-old"
    original_candidates = discovery_module._candidate_files

    def replace_parent_with_hardlink(source_root: Path):
        selected = original_candidates(source_root)
        data.rename(old_data)
        data.mkdir()
        os.link(old_data / "case.json", metadata)
        return selected

    monkeypatch.setattr(discovery_module, "_candidate_files", replace_parent_with_hardlink)
    with pytest.raises(WorkbenchPersistenceError) as error:
        discovery_module.discover_report_structure(root)
    assert error.value.code == "REPORT_DISCOVERY_STRUCTURE_CHANGED"


def test_confirmation_rejects_ambiguous_scalar_and_cross_collection_materials(
    tmp_path: Path,
) -> None:
    scalar_root = tmp_path / "SYNTHETIC-SCALAR-CARDINALITY"
    scalar_root.mkdir()
    (scalar_root / "metadata.json").write_text(json.dumps({
        "cases": [{"案件名称": "SYNTHETIC-A"}, {"案件名称": "SYNTHETIC-B"}],
    }, ensure_ascii=False), encoding="utf-8")
    service = ReportProfileService(_database(tmp_path / "scalar-db"))
    scalar_discovery = service.prepare_selection(scalar_root)
    scalar_candidate = next(
        item["candidate_id"] for item in scalar_discovery["candidates"]
        if item["canonical_field"] == "case.case_name"
    )
    with pytest.raises(WorkbenchPersistenceError) as scalar_error:
        service.confirm(scalar_discovery["discovery_token"], [scalar_candidate], "SYNTHETIC")
    assert scalar_error.value.code == "REPORT_PROFILE_CARDINALITY_INVALID"

    material_root = tmp_path / "SYNTHETIC-CROSS-COLLECTION"
    material_root.mkdir()
    (material_root / "metadata.json").write_text(json.dumps({
        "left": [{"检材编号": "SYNTHETIC-01"}],
        "right": [{"型号": "SYNTHETIC-MODEL-01"}],
    }, ensure_ascii=False), encoding="utf-8")
    material_discovery = service.prepare_selection(material_root)
    material_candidates = [
        item["candidate_id"] for item in material_discovery["candidates"]
        if item["canonical_field"] in {"material.evidence_number", "material.model"}
    ]
    with pytest.raises(WorkbenchPersistenceError) as material_error:
        service.confirm(
            material_discovery["discovery_token"], material_candidates, "SYNTHETIC",
        )
    assert material_error.value.code == "REPORT_PROFILE_MATERIAL_COLLECTION_CONFLICT"


def test_discovery_rejects_non_finite_json_numbers_and_mixed_type_candidates(
    tmp_path: Path,
) -> None:
    for directory_name, payload in (
        ("SYNTHETIC-NON-FINITE-TOKENS", '{"values":[NaN,Infinity,-Infinity]}'),
        ("SYNTHETIC-NUMERIC-OVERFLOW", '{"materials":[{"型号":1e999}]}'),
    ):
        non_finite = tmp_path / directory_name
        non_finite.mkdir()
        (non_finite / "metadata.json").write_text(payload, encoding="utf-8")
        with pytest.raises(WorkbenchPersistenceError) as invalid:
            discovery_module.discover_report_structure(non_finite)
        assert invalid.value.code == "REPORT_DISCOVERY_INVALID_METADATA"

    mixed = tmp_path / "SYNTHETIC-MIXED-TYPES"
    mixed.mkdir()
    (mixed / "metadata.json").write_text(json.dumps({
        "materials": [{"型号": "SYNTHETIC-MODEL"}, {"型号": 42}],
    }, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(WorkbenchPersistenceError) as no_safe_candidate:
        discovery_module.discover_report_structure(mixed)
    assert no_safe_candidate.value.code == "REPORT_DISCOVERY_NO_FIELDS"


def test_profile_projection_preserves_exact_confirmed_software_provenance(
    tmp_path: Path,
) -> None:
    service = ReportProfileService(_database(tmp_path))
    root = tmp_path / "SYNTHETIC-PROVENANCE"
    (root / "sub").mkdir(parents=True)
    (root / "case.json").write_text(
        json.dumps({"案件名称": "SYNTHETIC-CASE"}, ensure_ascii=False), encoding="utf-8",
    )
    (root / "sub" / "software.json").write_text(json.dumps({
        "tool": {"软件名称": "SYNTHETIC-TOOL"},
        "软件版本": "SYNTHETIC-1.0",
    }, ensure_ascii=False), encoding="utf-8")
    discovery = service.prepare_selection(root)
    selected = [
        item["candidate_id"] for item in discovery["candidates"]
        if item["canonical_field"] in {
            "case.case_name", "software.name", "software.version",
        }
    ]
    profile, _ = service.confirm(
        discovery["discovery_token"], selected, "SYNTHETIC PROVENANCE",
    )
    report = project_report_snapshot(service.build_snapshot(
        root, profile["profile_id"], profile["version"],
    )).report

    assert {
        (item["source_file"], item["json_path"], item["confidence"])
        for item in report["inspection"]["primary_software"]["provenance"]
    } == {
        ("sub/software.json", "$/tool/软件名称", 0.95),
        ("sub/software.json", "$/软件版本", 0.95),
    }


def test_total_byte_budget_is_passed_to_reader_as_a_hard_remaining_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "SYNTHETIC-TOTAL-BUDGET"
    root.mkdir()
    for index in range(5):
        (root / f"metadata-{index}.json").write_text(
            json.dumps({"案件名称": "X" * 900_000}, ensure_ascii=False),
            encoding="utf-8",
        )
    original_read = discovery_module.read_bounded_dependency
    read_limits: list[int] = []

    def track_limit(path, dependency_root, max_bytes, **kwargs):
        read_limits.append(max_bytes)
        return original_read(path, dependency_root, max_bytes, **kwargs)

    monkeypatch.setattr(discovery_module, "read_bounded_dependency", track_limit)
    with pytest.raises(WorkbenchPersistenceError) as error:
        discovery_module.discover_report_structure(root)
    assert error.value.code == "REPORT_DISCOVERY_BUDGET_EXCEEDED"
    assert read_limits[-1] < discovery_module.MAX_DISCOVERY_FILE_BYTES


def test_profile_source_snapshot_is_bound_to_the_recorded_profile_version(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    service = ReportProfileService(database)
    source = _unknown_report(tmp_path / "SYNTHETIC-VERSIONED")
    discovery = service.prepare_selection(source)
    selected = [
        item["candidate_id"] for item in discovery["candidates"]
        if item["canonical_field"] == "case.case_name"
    ]
    profile, _ = service.confirm(discovery["discovery_token"], selected, "SYNTHETIC V1")
    version_two_mappings = [dict(profile["mappings"][0])]
    version_two_mappings[0]["json_path"] = "$/案件编号"
    with database.transaction() as connection:
        connection.execute(
            "UPDATE report_profiles SET status='retired' WHERE profile_id=? AND version=1",
            (profile["profile_id"],),
        )
        connection.execute(
            "INSERT INTO report_profiles(profile_id,version,schema_version,display_name,"
            "structure_fingerprint,adapter_id,adapter_version,status,mappings_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                profile["profile_id"], 2, 1, "SYNTHETIC V2",
                profile["structure_fingerprint"], "report-profile-v1", "1.0.0",
                "confirmed", json.dumps(version_two_mappings, ensure_ascii=False),
                "2026-09-13T00:00:00Z", "2026-09-13T00:00:00Z",
            ),
        )

    with pytest.raises(WorkbenchPersistenceError) as retired:
        service.build_snapshot(source, profile["profile_id"], 1)
    version_two = service.build_snapshot(source, profile["profile_id"], 2)

    assert retired.value.code == "REPORT_PROFILE_NOT_CONFIRMED"
    assert version_two.source_key.startswith(f"profile:{profile['profile_id']}@2:")
    assert version_two.case_info["case_name"] == "SYNTHETIC-NO-A"


def test_competing_confirmations_with_different_mappings_fail_stably(
    tmp_path: Path,
) -> None:
    service = ReportProfileService(_database(tmp_path))
    source = _unknown_report(tmp_path / "SYNTHETIC-COMPETING")
    (source / "secondary.json").write_text(
        json.dumps({"案件名": "SYNTHETIC-SECONDARY"}, ensure_ascii=False),
        encoding="utf-8",
    )
    first = service.prepare_selection(source)
    second = service.prepare_selection(source)
    first_candidate = next(
        item["candidate_id"] for item in first["candidates"]
        if item["canonical_field"] == "case.case_name"
        and item["source_file"] == "metadata.json"
    )
    second_candidate = next(
        item["candidate_id"] for item in second["candidates"]
        if item["canonical_field"] == "case.case_name"
        and item["source_file"] == "secondary.json"
    )
    service.confirm(first["discovery_token"], [first_candidate], "SYNTHETIC SHAPE")

    with pytest.raises(WorkbenchPersistenceError) as conflict:
        service.confirm(
            second["discovery_token"], [second_candidate], "SYNTHETIC SHAPE",
        )

    assert conflict.value.code == "REPORT_PROFILE_CONFLICT"
    with sqlite3.connect(service.repository.database.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM report_profiles WHERE status='confirmed'",
        ).fetchone()[0] == 1
