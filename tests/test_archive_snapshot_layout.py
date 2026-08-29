import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive.archive_input_snapshot_layout_service import (  # noqa: E402
    private_snapshot_root,
)


def test_private_snapshot_root_defaults_to_project_external_snapshots(monkeypatch):
    monkeypatch.delenv("BIJI_ARCHIVE_EXTERNAL_ROOT", raising=False)
    root = private_snapshot_root()
    assert isinstance(root, Path)
    assert root.name == "external-snapshots"
    assert root.is_absolute()


def test_private_snapshot_root_respects_external_override(monkeypatch, tmp_path):
    override = tmp_path / "snapshots"
    monkeypatch.setenv("BIJI_ARCHIVE_EXTERNAL_ROOT", str(override))
    assert private_snapshot_root() == override
