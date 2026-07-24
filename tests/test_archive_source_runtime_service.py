"""SYNTHETIC tests for preview-source and formal-context lifecycle separation."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_authorization_repository import AuthorizedInputRoot  # noqa: E402
from app.repository.archive_input_repository import build_input_inventory  # noqa: E402
from app.services.archive_runtime_service import ArchiveRuntimeError  # noqa: E402
from app.services.archive_source_runtime_service import (  # noqa: E402
    ArchiveSourceRuntimeStore,
    prepare_archive_source,
    resolve_archive_context_id,
)
from app.services import archive_source_runtime_service  # noqa: E402


def _authorized(root: Path) -> AuthorizedInputRoot:
    return AuthorizedInputRoot(root.resolve(), "exact_directory_grant", "SYNTHETIC-root")


def _report() -> dict:
    return {"introduction": {"case_summary": "SYNTHETIC-CASE"}}


def test_preview_source_does_not_build_inventory_and_has_explicit_state(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    store = ArchiveSourceRuntimeStore()
    with patch(
        "app.services.archive_runtime_service.build_input_inventory",
        side_effect=AssertionError("preview must not inventory"),
    ):
        source_id = store.create(_authorized(source))
        summary = store.public_summary(source_id)

    assert summary["status"] == "not_prepared"
    assert summary["context_kind"] == "preview_source"
    assert summary["inventory_ready"] is False
    assert summary["file_count"] is None
    assert str(source) not in str(summary)


def test_same_source_preparation_builds_one_formal_context(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    store = ArchiveSourceRuntimeStore()
    source_id = store.create(_authorized(source))
    started = Event()
    release = Event()
    calls = []

    def builder(authorized, cleanup):
        calls.append(authorized.authorized_root_id)
        started.set()
        assert release.wait(timeout=5)
        return "formal-context"

    def formal_summary(context_id):
        if context_id == source_id:
            raise ArchiveRuntimeError("ARCHIVE_CONTEXT_NOT_FOUND", "synthetic source")
        return {"archive_context_id": context_id}

    with patch.object(
        archive_source_runtime_service.ARCHIVE_RUNTIME_STORE,
        "get_context_summary",
        side_effect=formal_summary,
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(store.prepare, source_id, builder)
            assert started.wait(timeout=5)
            assert store.public_summary(source_id)["status"] == "preparing"
            second = pool.submit(store.prepare, source_id, builder)
            release.set()
            assert first.result(timeout=5) == "formal-context"
            assert second.result(timeout=5) == "formal-context"
        assert store.formal_context_id(source_id) == "formal-context"

    assert calls == ["SYNTHETIC-root"]


def test_preparation_failure_is_retryable(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    store = ArchiveSourceRuntimeStore()
    source_id = store.create(_authorized(source))
    calls = []

    def builder(authorized, cleanup):
        calls.append("attempt")
        if len(calls) == 1:
            raise ArchiveRuntimeError("ARCHIVE_INPUT_CHANGED", "synthetic failure")
        return "formal-context"

    with pytest.raises(ArchiveRuntimeError):
        store.prepare(source_id, builder)
    assert store.public_summary(source_id)["status"] == "failed"
    assert store.prepare(source_id, builder) == "formal-context"
    assert calls == ["attempt", "attempt"]


def test_unprepared_source_cannot_resolve_formal_context(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    store = ArchiveSourceRuntimeStore()
    source_id = store.create(_authorized(source))

    with patch(
        "app.services.archive_source_runtime_service.ARCHIVE_SOURCE_RUNTIME_STORE",
        store,
    ), pytest.raises(ArchiveRuntimeError) as error:
        resolve_archive_context_id(source_id)

    assert error.value.code == "ARCHIVE_CONTEXT_NOT_PREPARED"


def test_expired_source_is_explicit_and_capacity_is_reclaimed(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    clock = [0.0]
    store = ArchiveSourceRuntimeStore(ttl_seconds=5, max_entries=1, clock=lambda: clock[0])
    source_id = store.create(_authorized(source))
    clock[0] = 6.0

    with pytest.raises(ArchiveRuntimeError) as error:
        store.public_summary(source_id)
    assert error.value.code == "ARCHIVE_SOURCE_EXPIRED"
    assert store.create(_authorized(source))


def test_authorization_change_blocks_preparation(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    store = ArchiveSourceRuntimeStore()
    source_id = store.create(_authorized(source))
    source.rename(tmp_path / "moved-case")

    with pytest.raises(ArchiveRuntimeError) as error:
        store.prepare(source_id, lambda authorized, cleanup: "formal-context")
    assert error.value.code == "ARCHIVE_AUTHORIZATION_INVALID"


def test_explicit_preparation_uses_full_inventory_and_context_gates(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    (source / "input.bin").write_bytes(b"SYNTHETIC")
    from app.services.archive_source_runtime_service import create_preview_source

    source_id = create_preview_source(_authorized(source))
    with patch(
        "app.services.archive_runtime_service.build_input_inventory",
        wraps=build_input_inventory,
    ) as build_inventory:
        context_id = prepare_archive_source(source_id, _report(), output_root=str(tmp_path / "output"))

    assert context_id
    assert build_inventory.call_count == 1
    summary = archive_source_runtime_service.get_preview_source_summary(source_id)
    assert summary["context_kind"] == "formal"
    assert summary["inventory_ready"] is True
