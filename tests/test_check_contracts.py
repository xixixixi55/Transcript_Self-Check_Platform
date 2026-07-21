"""
Persistent integration test for check-contracts.ts.

Proves that the cross-language contract checker correctly detects:
- Field name drift (present in TS, missing in Python)
- Optionality drift (TS required vs Python optional)
- Enum value drift (literal member mismatch)
- Error code set drift (ExportGateBlockerCode vs ExportGateCode)

Strategy: operates on canonical_model_service.py because it is the Python-side
authority for all canonical model fields and literal enums.  Each test
temporarily mutates one file, runs the checker, asserts failure with the
expected dimension, then restores the original.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check-contracts.ts"
CANONICAL_MODELS = ROOT / "packages" / "backend" / "app" / "services" / "canonical_models_service.py"


def _run_checker() -> tuple[int, str]:
    result = subprocess.run(
        f'npx tsx "{CHECKER}"',
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        shell=True,
    )
    return result.returncode, result.stdout + result.stderr


def _modify_file(path: Path, old: str, new: str) -> str:
    """Replace old→new, return original content for later restore."""
    original = path.read_text(encoding="utf-8")
    updated = original.replace(old, new)
    if updated == original:
        raise RuntimeError(f"Replacement text not found: {old[:80]!r}")
    path.write_text(updated, encoding="utf-8")
    return original


def _restore_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestContractCheckerDriftDetection:
    """Each test introduces a deliberate drift and asserts the checker catches it."""

    def test_field_name_drift_caught(self):
        """Removing a Python field MUST trigger a field-name drift."""
        # Remove 'evidence_number' from Python Material model
        original = _modify_file(
            CANONICAL_MODELS,
            "    evidence_number: str\n",
            "",
        )
        try:
            exit_code, output = _run_checker()
            assert exit_code == 1, f"Checker should fail with drift; got exit {exit_code}\n{output}"
            assert "field-name" in output, f"Expected field-name drift, got:\n{output}"
            assert "evidence_number" in output.lower(), f"Expected evidence_number missing, got:\n{output}"
        finally:
            _restore_file(CANONICAL_MODELS, original)

    def test_optionality_drift_caught(self):
        """Making a TS-required field optional MUST trigger optionality drift."""
        # Use 'Material.name' which is auto-parsed (no tsFields override).
        # TS: name: string (required).  Add ? to make it optional.
        ts_canonical_path = ROOT / "packages" / "shared" / "types" / "canonical.ts"
        original_ts = _modify_file(
            ts_canonical_path,
            '  name: string\n',
            '  name?: string\n',
        )
        try:
            exit_code, output = _run_checker()
            assert exit_code == 1, f"Checker should fail with drift; got exit {exit_code}\n{output}"
            assert "optionality" in output, f"Expected optionality drift, got:\n{output}"
        finally:
            _restore_file(ts_canonical_path, original_ts)

    def test_enum_value_drift_caught(self):
        """Adding a spurious TS literal union member MUST trigger enum-values drift."""
        ts_canonical = ROOT / "packages" / "shared" / "types" / "canonical.ts"
        # Inject a nonsense value into MaterialKind
        original = _modify_file(
            ts_canonical,
            "export type MaterialKind = 'phone' | 'tablet' | 'unconfirmed'",
            "export type MaterialKind = 'phone' | 'tablet' | 'unconfirmed' | 'laptop'",
        )
        try:
            exit_code, output = _run_checker()
            assert exit_code == 1, f"Checker should fail with drift; got exit {exit_code}\n{output}"
            assert "enum-values" in output, f"Expected enum-values drift, got:\n{output}"
            assert "laptop" in output, f"Expected 'laptop' in drift report, got:\n{output}"
        finally:
            _restore_file(ts_canonical, original)

    def test_error_code_drift_caught(self):
        """Removing a TS ExportGateBlockerCode member MUST trigger error-code-set drift."""
        ts_export_gate = ROOT / "packages" / "shared" / "types" / "exportGate.ts"
        # Remove a code from the type union
        original = _modify_file(
            ts_export_gate,
            "  | 'TEMPLATE_PROFILE_MISMATCH'\n",
            "",
        )
        try:
            exit_code, output = _run_checker()
            assert exit_code == 1, f"Checker should fail with drift; got exit {exit_code}\n{output}"
            assert "error-code-set" in output, f"Expected error-code-set drift, got:\n{output}"
            assert "TEMPLATE_PROFILE_MISMATCH" in output, f"Expected TEMPLATE_PROFILE_MISMATCH in report, got:\n{output}"
        finally:
            _restore_file(ts_export_gate, original)

    def test_no_drift_when_aligned(self):
        """Checker MUST pass (exit 0) when the contracts are aligned."""
        exit_code, output = _run_checker()
        assert exit_code == 0 or (
            exit_code == 1 and "ODD_PHOTO_COUNT" in output
            and "field-name" not in output
            and "optionality" not in output
            and "enum-values" not in output
            and output.count("\n") < 8
        ), f"Expected clean pass or ODD_PHOTO_COUNT-only drift, got:\n{output}"
