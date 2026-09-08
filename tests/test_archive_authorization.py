import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_authorization_repository import (  # noqa: E402
    ArchiveAuthorizationError,
    ArchiveAuthorizationStore,
)


def make_store(tmp_path):
    upload = tmp_path / "SYNTHETIC-UPLOAD"
    upload.mkdir(exist_ok=True)
    return ArchiveAuthorizationStore(), upload


def test_local_directory_needs_no_input_allowlist_and_keeps_output_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("BIJI_ALLOWED_INPUT_ROOTS", str(tmp_path / "SYNTHETIC-MISSING"))
    store, _ = make_store(tmp_path)
    outside = tmp_path / "SYNTHETIC-OUTSIDE"
    outside.mkdir()
    authorized = store.authorize_directory(str(outside))
    assert authorized.resolved_input_root == outside.resolve()
    assert authorized.authorization_type == "unrestricted_local_directory"
    with pytest.raises(ArchiveAuthorizationError) as overlap:
        store.authorize_directory(str(outside), output_roots=(str(outside / "output"),))
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
        store._consume_grant(token, case_b.resolve())
    assert mismatch.value.code == "ARCHIVE_AUTHORIZATION_INVALID"
    assert store._consume_grant(token, case_a.resolve()).authorization_type == "exact_directory_grant"
    with pytest.raises(ArchiveAuthorizationError) as reused:
        store._consume_grant(token, case_a.resolve())
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
        store._consume_grant(token, case.resolve())
    assert expired.value.code == "ARCHIVE_AUTHORIZATION_EXPIRED"
    with pytest.raises(ArchiveAuthorizationError) as missing:
        store._consume_grant("unknown-token", case.resolve())
    assert missing.value.code == "ARCHIVE_AUTHORIZATION_INVALID"


@pytest.mark.parametrize("raw", ["", "relative\\case", "..\\case", r"\\server\share\case", r"\\?\C:\case", r"\\.\pipe\case"])
def test_invalid_relative_network_and_device_paths_are_rejected(tmp_path, raw):
    store, _ = make_store(tmp_path)
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(raw)
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
    allowed_case.mkdir(parents=True)
    with pytest.raises(ArchiveAuthorizationError) as output_inside:
        store.authorize_directory(str(allowed_case), output_roots=(str(allowed_case / "staging"),))
    assert output_inside.value.code == "ARCHIVE_INPUT_OUTPUT_OVERLAP"


def test_reparse_point_is_rejected_at_any_path_level(tmp_path, monkeypatch):
    store, upload = make_store(tmp_path)
    case = upload / "case"
    case.mkdir()
    from app.repository.archive import archive_authorization_repository as repository

    monkeypatch.setattr(repository, "_is_reparse_point", lambda path: path == case)
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(str(case))
    assert error.value.code == "ARCHIVE_INPUT_LINK_NOT_ALLOWED"


def test_injected_symlink_boundary_is_rejected_without_os_link_creation(tmp_path, monkeypatch):
    store, upload = make_store(tmp_path)
    case = upload / "case"
    case.mkdir()
    from app.repository.archive import archive_authorization_repository as repository

    monkeypatch.setattr(repository, "_is_unsafe_special_path", lambda path: path == case)
    with pytest.raises(ArchiveAuthorizationError) as error:
        store.authorize_directory(str(case))
    assert error.value.code == "ARCHIVE_INPUT_LINK_NOT_ALLOWED"
