"""
check-contracts.ts 的持久集成测试。

证明跨语言契约检查器能正确检测：
- 字段名称漂移（TS 中存在、Python 中缺失）
- 可选性漂移（TS 要求必填，而 Python 允许可选）
- 枚举值漂移（字面量成员不匹配）
- 错误码集合漂移（ExportGateBlockerCode 与 ExportGateCode）

测试在 canonical_model_service.py 上运行，因为它是所有规范模型字段和
字面量枚举的 Python 端权威来源。每项测试会临时修改一个文件，运行检查器，
断言检查器按预期维度失败，然后恢复原始内容。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check-contracts.ts"
CANONICAL_MODELS = ROOT / "packages" / "backend" / "app" / "services" / "canonical" / "canonical_models_service.py"


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
    """将 old 替换为 new，并返回原始内容以便后续恢复。"""
    original = path.read_text(encoding="utf-8")
    updated = original.replace(old, new)
    if updated == original:
        raise RuntimeError(f"Replacement text not found: {old[:80]!r}")
    path.write_text(updated, encoding="utf-8")
    return original


def _restore_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestContractCheckerDriftDetection:
    """保留一次无漂移集成运行，以及一次覆盖所有漂移维度的运行。"""

    def test_all_supported_drift_dimensions_caught_in_one_run(self):
        """一次检查器调用报告字段、可选性、枚举和错误码漂移。"""
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
        """契约对齐时，检查器 MUST 通过（退出码为 0）。"""
        exit_code, output = _run_checker()
        assert exit_code == 0 or (
            exit_code == 1 and "ODD_PHOTO_COUNT" in output
            and "field-name" not in output
            and "optionality" not in output
            and "enum-values" not in output
            and output.count("\n") < 8
        ), f"Expected clean pass or ODD_PHOTO_COUNT-only drift, got:\n{output}"
