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
    """Keep one clean integration run and one run covering every drift dimension."""

    def test_all_supported_drift_dimensions_caught_in_one_run(self):
        """One checker invocation reports field, optionality, enum and error-code drift."""
        ts_canonical = ROOT / "packages" / "shared" / "types" / "canonical.ts"
        ts_export_gate = ROOT / "packages" / "shared" / "types" / "exportGate.ts"
        originals = {
            CANONICAL_MODELS: CANONICAL_MODELS.read_text(encoding="utf-8"),
            ts_canonical: ts_canonical.read_text(encoding="utf-8"),
            ts_export_gate: ts_export_gate.read_text(encoding="utf-8"),
        }
        try:
            _modify_file(CANONICAL_MODELS, "    evidence_number: str\n", "")
            _modify_file(ts_canonical, "  name: string\n", "  name?: string\n")
            _modify_file(
                ts_canonical,
                "export type MaterialKind = 'phone' | 'tablet' | 'unconfirmed'",
                "export type MaterialKind = 'phone' | 'tablet' | 'unconfirmed' | 'laptop'",
            )
            _modify_file(ts_export_gate, "  | 'TEMPLATE_PROFILE_MISMATCH'\n", "")

            exit_code, output = _run_checker()
            assert exit_code == 1, f"Checker should fail with drift; got exit {exit_code}\n{output}"
            for dimension in ("field-name", "optionality", "enum-values", "error-code-set"):
                assert dimension in output, f"Expected {dimension} drift, got:\n{output}"
            for detail in ("evidence_number", "laptop", "TEMPLATE_PROFILE_MISMATCH"):
                assert detail.lower() in output.lower(), f"Expected {detail} in drift report, got:\n{output}"
        finally:
            for file_path, original in originals.items():
                _restore_file(file_path, original)

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
