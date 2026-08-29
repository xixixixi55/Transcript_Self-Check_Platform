import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_authorization_repository import (  # noqa: E402
    ArchiveAuthorizationError,
    ArchiveAuthorizationStore,
)


def make_store(tmp_path, extra_roots=()):
    upload = tmp_path / "upload-root"
    upload.mkdir(exist_ok=True)
    env = {"BIJI_ALLOWED_INPUT_ROOTS": ";".join(str(path) for path in extra_roots)}
    return ArchiveAuthorizationStore(upload, environment=env), upload


def test_configured_roots_allow_children_and_multiple_disks(tmp_path):
    extra_a = tmp_path / "configured-a"
    extra_b = tmp_path / "configured-b"
    case_a = extra_a / "case-a"
    case_b = extra_b / "case-b"
    case_upload = tmp_path / "upload-root" / "case-upload"
    for path in (extra_a, extra_b, case_a, case_b, case_upload):
        path.mkdir(parents=True, exist_ok=True)
    store, _ = make_store(tmp_path, (extra_a, extra_b))

    assert store.authorize_directory(str(case_a)).authorization_type == "configured_root"
    assert store.authorize_directory(str(case_b)).authorization_type == "configured_root"
    assert store.authorize_directory(str(case_upload)).authorization_type == "configured_root"


def test_configured_roots_ignore_empty_items_dedupe_case_and_warn_on_invalid(tmp_path):
    upload = tmp_path / "upload-root"
    upload.mkdir()
    extra = tmp_path / "configured"
    extra.mkdir()
    missing = tmp_path / "missing"
    env = {
        "BIJI_ALLOWED_INPUT_ROOTS": ";".join(("", str(extra), str(extra).upper(), str(missing), "relative")),
    }
    with pytest.warns(RuntimeWarning, match="ARCHIVE_CONFIGURED_ROOT_INVALID"):
        store = ArchiveAuthorizationStore(upload, environment=env)
    assert len(store.configured_roots) == 2
    assert set(store.configuration_warnings) == {"ARCHIVE_CONFIGURED_ROOT_INVALID"}
    assert not any(str(tmp_path / "missing") in warning for warning in store.configuration_warnings)


def test_configured_root_itself_and_prefix_sibling_are_rejected(tmp_path):
    store, upload = make_store(tmp_path)
    sibling = tmp_path / "upload-root-backup"
    sibling.mkdir()
    with pytest.raises(ArchiveAuthorizationError) as root_error:
        store.authorize_directory(str(upload))
    assert root_error.value.code == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"
    with pytest.raises(ArchiveAuthorizationError) as sibling_error:
        store.authorize_directory(str(sibling))
    assert sibling_error.value.code == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"


def test_unconfigured_directory_is_rejected_without_a_grant(tmp_path):
    store, _ = make_store(tmp_path)
    outside = tmp_path / "scattered-case"
    outside.mkdir()
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(str(outside))
    assert error.value.code == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"


def test_disabled_authorization_allows_unconfigured_directory_but_keeps_output_guard(tmp_path):
    store, _ = make_store(tmp_path)
    outside = tmp_path / "SYNTHETIC-OUTSIDE"
    outside.mkdir()

    authorized = store.authorize_directory(
        str(outside), source_authorization_enabled=False,
    )
    assert authorized.resolved_input_root == outside.resolve()
    assert authorized.authorization_type == "unrestricted_local_directory"

    with pytest.raises(ArchiveAuthorizationError) as overlap:
        store.authorize_directory(
            str(outside),
            source_authorization_enabled=False,
            output_roots=(str(outside / "output"),),
        )
    assert overlap.value.code == "ARCHIVE_INPUT_OUTPUT_OVERLAP"


def test_exact_grant_is_one_use_short_lived_and_path_bound(tmp_path):
    store, _ = make_store(tmp_path)
    case_a = tmp_path / "case-a"
    case_b = tmp_path / "case-b"
    case_a.mkdir()
    case_b.mkdir()
    token = store.issue_exact_directory_grant(str(case_a))
    assert str(case_a) not in token
    assert str(case_b) not in token
    with pytest.raises(ArchiveAuthorizationError) as mismatch:
        store.authorize_directory(str(case_b), grant_token=token)
    assert mismatch.value.code == "ARCHIVE_AUTHORIZATION_INVALID"
    assert store.authorize_directory(str(case_a), grant_token=token).authorization_type == "exact_directory_grant"
    with pytest.raises(ArchiveAuthorizationError) as reused:
        store.authorize_directory(str(case_a), grant_token=token)
    assert reused.value.code == "ARCHIVE_AUTHORIZATION_INVALID"


def test_exact_grant_expiry_and_unknown_token_are_stable(tmp_path):
    now = [100.0]
    store, _ = make_store(tmp_path)
    store._clock = lambda: now[0]
    case = tmp_path / "case"
    case.mkdir()
    token = store.issue_exact_directory_grant(str(case))
    now[0] += 301
    with pytest.raises(ArchiveAuthorizationError) as expired:
        store.authorize_directory(str(case), grant_token=token)
    assert expired.value.code == "ARCHIVE_AUTHORIZATION_EXPIRED"
    with pytest.raises(ArchiveAuthorizationError) as missing:
        store.authorize_directory(str(case), grant_token="unknown-token")
    assert missing.value.code == "ARCHIVE_AUTHORIZATION_INVALID"


@pytest.mark.parametrize("source_authorization_enabled", [True, False])
@pytest.mark.parametrize("raw", ["", "relative\\case", "..\\case", r"\\server\share\case", r"\\?\C:\case", r"\\.\pipe\case"])
def test_invalid_relative_network_and_device_paths_are_rejected(tmp_path, raw, source_authorization_enabled):
    store, _ = make_store(tmp_path)
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(raw, source_authorization_enabled=source_authorization_enabled)
    assert error.value.code in {"ARCHIVE_INPUT_PATH_INVALID", "ARCHIVE_INPUT_LINK_NOT_ALLOWED"}


def test_output_overlap_is_rejected_in_both_directions(tmp_path):
    store, _ = make_store(tmp_path)
    case = tmp_path / "case"
    nested_output = case / "output"
    case.mkdir()
    with pytest.raises(ArchiveAuthorizationError) as input_inside:
        store.authorize_directory(str(case), output_roots=(str(tmp_path),))
    assert input_inside.value.code == "ARCHIVE_INPUT_OUTPUT_OVERLAP"
    allowed_case = tmp_path / "upload-root" / "case"
    allowed_case.mkdir()
    with pytest.raises(ArchiveAuthorizationError) as output_inside:
        store.authorize_directory(str(allowed_case), output_roots=(str(allowed_case / "staging"),))
    assert output_inside.value.code == "ARCHIVE_INPUT_OUTPUT_OVERLAP"


@pytest.mark.parametrize("source_authorization_enabled", [True, False])
def test_reparse_point_is_rejected_at_any_path_level(tmp_path, monkeypatch, source_authorization_enabled):
    store, upload = make_store(tmp_path)
    case = upload / "case"
    case.mkdir()
    from app.repository.archive import archive_authorization_repository as repository

    monkeypatch.setattr(repository, "_is_reparse_point", lambda path: path == case)
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(str(case), source_authorization_enabled=source_authorization_enabled)
    assert error.value.code == "ARCHIVE_INPUT_LINK_NOT_ALLOWED"


@pytest.mark.parametrize("source_authorization_enabled", [True, False])
def test_injected_symlink_boundary_is_rejected_without_os_link_creation(tmp_path, monkeypatch, source_authorization_enabled):
    store, upload = make_store(tmp_path)
    case = upload / "case"
    case.mkdir()
    from app.repository.archive import archive_authorization_repository as repository

    monkeypatch.setattr(repository, "_is_unsafe_special_path", lambda path: path == case)
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(str(case), source_authorization_enabled=source_authorization_enabled)
    assert error.value.code == "ARCHIVE_INPUT_LINK_NOT_ALLOWED"
