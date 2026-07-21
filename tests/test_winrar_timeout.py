"""Comprehensive tests for WinRAR timeout governance.

Covers:
  - Default timeout policy & bounds
  - Size-based computation (10 MiB/s floor)
  - 135 GB at 10 MiB/s NOT truncated (capped at 14 400 s = 4 h)
  - 135 GB + 1 is blocked by planner, not by timeout
  - Env-var override (legal, zero, negative, above env max, at env max)
  - Simulated timeout → process killed → staging cleaned
  - Normal execution NOT prematurely terminated
  - Explicit timeout constructor parameter (test escape hatch)
  - Non-zero exit code path still works
  - Replan per-attempt timeout semantics
  - Export Gate code integration
  - Locking / concurrency safety
"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_input_repository import build_input_inventory  # noqa: E402
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import (  # noqa: E402
    ArchiveExecutionError,
    WinRarExecutor,
)

GB = 1_000_000_000


def capability() -> WinRarCapability:
    return WinRarCapability(True, "fake-winrar", "WinRAR.exe", "6.24", True)


def _make_plan(plan_id="p1", base="case", vol=4_000_000_000):
    return SimpleNamespace(plan_id=plan_id, archive_base_name=base, volume_size_bytes=vol)


def _inventory(tmp_path: Path, size: int):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"\x00" * size)
    return build_input_inventory(source)


def _run_ok(args, **kwargs):
    archive_path = Path(
        next(item for item in args if item.endswith(".rar") and not item.startswith("@"))
    )
    archive_path.write_bytes(b"ok")
    return subprocess.CompletedProcess(args, 0, "", "")


# ============================================================================
# 1. Default policy
# ============================================================================


class TestTimeoutPolicy:
    def test_default_timeout_for_zero_bytes(self):
        assert WinRarExecutor.compute_timeout(0) == 300

    def test_default_timeout_for_small_input(self):
        # 1 MiB at 10 MiB/s ≈ 0.1 s → floor of 300 s
        assert WinRarExecutor.compute_timeout(1024 * 1024) == 300

    def test_timeout_scales_with_10_mibs_throughput(self):
        # 8 GB / (10 * 1024 * 1024) = 8e9 / 10_485_760 ≈ 762 s
        expected = int(8_000_000_000 / (10 * 1024 * 1024))
        assert WinRarExecutor.compute_timeout(8_000_000_000) == expected

    def test_135gb_not_truncated(self):
        """135 GB (planner max) at 10 MiB/s ≈ 12 874 s < 14 400 s cap."""
        timeout_135 = WinRarExecutor.compute_timeout(135 * GB)
        size_based = int(135 * GB / (10 * 1024 * 1024))
        assert size_based < 14_400, "135 GB must fit under the 4 h cap"
        assert timeout_135 == size_based
        assert timeout_135 > 7200, "135 GB must NOT be truncated to 2 h"

    def test_capped_at_4_hours(self):
        # 200 GB → would be ~19 073 s, capped at 14 400
        assert WinRarExecutor.compute_timeout(200 * GB) == 14_400

    def test_bounds_are_3_tuple(self):
        default, computed_max, env_max = WinRarExecutor.timeout_bounds()
        assert default == 300
        assert computed_max == 14_400
        assert env_max == 86_400


# ============================================================================
# 2. 135 GB + 1 → planner blocks, not timeout
# ============================================================================


class TestPlannerBlocksOver135GB:
    def test_135gb_plus_1_byte_blocked_by_planner(self):
        """Timeout policy never handles >135 GB — planner rejects it first."""
        from app.services.archive_planner_service import (
            ArchiveSourceEntry,
            PRODUCTION_ARCHIVE_POLICY,
            plan_archive,
        )
        over = 135 * GB + 1
        entries = (ArchiveSourceEntry("big.bin", over, 0),)
        plan = plan_archive("huge", entries, policy=PRODUCTION_ARCHIVE_POLICY)
        assert plan.status != "planned"
        assert any(d.code == "ARCHIVE_TOO_LARGE" for d in plan.diagnostics)


# ============================================================================
# 3. Env var override
# ============================================================================


class TestEnvTimeoutOverride:
    def test_env_overrides_computed_value(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "600")
        assert WinRarExecutor.compute_timeout(1_000_000_000) == 600

    def test_env_at_env_max_86400(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "86400")
        assert WinRarExecutor.compute_timeout(0) == 86_400

    def test_env_above_env_max_is_ignored(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "99999")
        assert WinRarExecutor.compute_timeout(0) == 300

    def test_negative_is_ignored(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "-1")
        assert WinRarExecutor.compute_timeout(0) == 300

    def test_zero_is_ignored(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "0")
        assert WinRarExecutor.compute_timeout(0) == 300

    def test_garbage_is_ignored(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "twelve")
        assert WinRarExecutor.compute_timeout(0) == 300


# ============================================================================
# 3.1 Warning log on invalid env-var (sanitised)
# ============================================================================


class TestEnvTimeoutWarning:
    def test_no_warning_when_env_unset(self, caplog):
        WinRarExecutor.compute_timeout(0)
        assert "BIJI_ARCHIVE_TIMEOUT_SECONDS" not in caplog.text

    def test_no_warning_when_env_valid(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "3600")
        WinRarExecutor.compute_timeout(0)
        assert "BIJI_ARCHIVE_TIMEOUT_SECONDS" not in caplog.text

    def test_warning_when_env_non_numeric(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "twelve")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300  # safe fallback
        assert "非数字" in caplog.text
        assert "已回退到默认计算" in caplog.text
        assert "1–86400" in caplog.text
        # Raw value "twelve" is NOT in the log
        assert "twelve" not in caplog.text

    def test_warning_when_env_above_max(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "99999")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300  # safe fallback
        assert "超出允许范围" in caplog.text
        assert "已回退到默认计算" in caplog.text
        assert "1–86400" in caplog.text

    def test_warning_when_env_negative(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "-5")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300  # safe fallback
        # Negative is treated as out of range (not non-numeric)
        assert "超出允许范围" in caplog.text
        assert "1–86400" in caplog.text

    def test_warning_contains_no_paths(self, monkeypatch, caplog, tmp_path):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "not-a-number")
        WinRarExecutor.compute_timeout(0)
        assert "\\" not in caplog.text
        assert "C:" not in caplog.text
        assert "D:" not in caplog.text


# ============================================================================
# 4. Explicit constructor timeout (test escape hatch)
# ============================================================================


class TestExplicitTimeout:
    def test_explicit_wins_over_computed(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", timeout_seconds=123)
        source = tmp_path / "source"
        source.mkdir()
        (source / "x.txt").write_text("hi", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = SimpleNamespace(plan_id="p", archive_base_name="x", volume_size_bytes=4)

        def runner(args, **kwargs):
            assert kwargs["timeout"] == 123
            archive_path = Path(
                next(item for item in args if item.endswith(".rar") and not item.startswith("@"))
            )
            archive_path.write_bytes(b"ok")
            return subprocess.CompletedProcess(args, 0, "", "")

        executor._process_runner = runner
        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert result.returncode == 0

    def test_explicit_zero_raises(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", timeout_seconds=0)
        source = tmp_path / "source"
        source.mkdir()
        (source / "x.txt").write_text("hi", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = SimpleNamespace(plan_id="p", archive_base_name="x", volume_size_bytes=4)
        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert exc.value.code == "ARCHIVE_EXECUTION_FAILED"


# ============================================================================
# 5. Simulated timeout → process killed → staging cleaned
# ============================================================================


class TestTimeoutCleanup:
    def test_timeout_cleans_staging_and_raises_timeout_code(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")

        def runner(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 300))

        executor = WinRarExecutor(
            tmp_path / "staging", timeout_seconds=1, process_runner=runner
        )
        inventory = build_input_inventory(source)
        plan = _make_plan()

        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())

        assert exc.value.code == "ARCHIVE_EXECUTION_TIMEOUT"
        assert list((tmp_path / "staging").glob("archive-*")) == []

    def test_subprocess_error_cleans_staging_and_raises_failure_code(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")

        def runner(args, **kwargs):
            raise OSError("disk full")

        executor = WinRarExecutor(
            tmp_path / "staging", timeout_seconds=300, process_runner=runner
        )
        inventory = build_input_inventory(source)
        plan = _make_plan()

        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())

        assert exc.value.code == "ARCHIVE_EXECUTION_FAILED"
        assert list((tmp_path / "staging").glob("archive-*")) == []


# ============================================================================
# 6. Normal execution not prematurely terminated
# ============================================================================


class TestNormalExecution:
    def test_small_input_completes_with_default_timeout(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 1024)
        plan = _make_plan(vol=4_000_000_000)

        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert result.returncode == 0
        assert result.timed_out is False
        assert (result.staging_dir / "case.part1.rar").is_file()

    def test_single_volume_naming_normalized(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 512)
        plan = _make_plan()

        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert (result.staging_dir / "case.part1.rar").is_file()
        assert not (result.staging_dir / "case.rar").exists()

    def test_multi_volume_output_is_untouched(self, tmp_path):
        def multi_runner(args, **kwargs):
            archive_path = Path(
                next(item for item in args if item.endswith(".rar") and not item.startswith("@"))
            )
            archive_path.with_name(f"{archive_path.stem}.part1.rar").write_bytes(b"a")
            archive_path.with_name(f"{archive_path.stem}.part2.rar").write_bytes(b"b")
            return subprocess.CompletedProcess(args, 0, "", "")

        executor = WinRarExecutor(tmp_path / "staging", process_runner=multi_runner)
        inventory = _inventory(tmp_path, 4096)
        plan = _make_plan()

        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert (result.staging_dir / "case.part1.rar").is_file()
        assert (result.staging_dir / "case.part2.rar").is_file()


# ============================================================================
# 7. Replan per-attempt timeout semantics
# ============================================================================


class TestReplanTimeoutSemantics:
    def test_each_attempt_computes_fresh_timeout(self, tmp_path):
        """Every execute() call recomputes timeout from input bytes.
        Input bytes don't change across replans, so timeout is consistent
        but each attempt is independently timed."""
        call_timeouts = []

        def tracking_runner(args, **kwargs):
            call_timeouts.append(kwargs["timeout"])
            archive_path = Path(
                next(item for item in args if item.endswith(".rar") and not item.startswith("@"))
            )
            archive_path.write_bytes(b"ok")
            return subprocess.CompletedProcess(args, 0, "", "")

        executor = WinRarExecutor(tmp_path / "staging", process_runner=tracking_runner)
        inventory = _inventory(tmp_path, 64 * 1024 * 1024)  # 64 MiB → timeout = 300
        plan = _make_plan()

        result1 = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert result1.returncode == 0

        # Simulate replan to higher tier (same input files, different plan)
        plan2 = _make_plan(vol=22_000_000_000)
        result2 = executor.execute(plan2, inventory.files, inventory.source_root, capability())
        assert result2.returncode == 0

        # Both attempts got independently computed timeouts (same input → same value)
        assert len(call_timeouts) == 2
        assert call_timeouts[0] == call_timeouts[1] == 300


# ============================================================================
# 8. Export Gate integration
# ============================================================================


class TestExportGateIntegration:
    def test_timeout_error_code_is_in_export_gate_enum(self):
        from app.services.export_gate_service import ExportGateCode
        assert hasattr(ExportGateCode, "ARCHIVE_EXECUTION_TIMEOUT")
        assert ExportGateCode.ARCHIVE_EXECUTION_TIMEOUT == "ARCHIVE_EXECUTION_TIMEOUT"

    def test_timeout_error_code_can_flow_through_archive_error(self):
        error = ArchiveExecutionError("ARCHIVE_EXECUTION_TIMEOUT", "超时了")
        assert error.code == "ARCHIVE_EXECUTION_TIMEOUT"
        assert error.safe_message == "超时了"
        from app.services.export_gate_service import ExportGateCode
        assert error.code == ExportGateCode.ARCHIVE_EXECUTION_TIMEOUT.value


# ============================================================================
# 9. Locking safety
# ============================================================================


class TestLocking:
    def test_concurrent_same_plan_is_rejected(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 64)
        plan = _make_plan(plan_id="lock-test")

        lock = WinRarExecutor._lock_for("lock-test")
        assert lock.acquire(blocking=False)

        try:
            with pytest.raises(ArchiveExecutionError) as exc:
                executor.execute(plan, inventory.files, inventory.source_root, capability())
            assert exc.value.code == "ARCHIVE_EXECUTION_IN_PROGRESS"
        finally:
            lock.release()


# ============================================================================
# 10. Non-zero exit with cleanup
# ============================================================================


class TestNonZeroExit:
    def test_nonzero_returncode_cleans_staging(self, tmp_path):
        def failing_runner(args, **kwargs):
            archive_path = Path(
                next(item for item in args if item.endswith(".rar") and not item.startswith("@"))
            )
            archive_path.write_bytes(b"partial")
            return subprocess.CompletedProcess(args, 7, "", "some error")

        executor = WinRarExecutor(tmp_path / "staging", process_runner=failing_runner)
        inventory = _inventory(tmp_path, 128)
        plan = _make_plan()

        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert result.returncode == 7
        assert result.diagnostic_code == "ARCHIVE_EXECUTION_FAILED"
        assert not result.staging_dir.exists()

    def test_source_list_cleaned_after_success(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 256)
        plan = _make_plan()

        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert not (result.staging_dir / "source-list.txt").exists()


# ============================================================================
# 11. Timeout error message is sanitised (no absolute paths)
# ============================================================================


class TestTimeoutMessageSanitised:
    def test_timeout_message_contains_no_paths(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")

        def runner(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 300))

        executor = WinRarExecutor(
            tmp_path / "staging", timeout_seconds=1, process_runner=runner
        )
        inventory = build_input_inventory(source)
        plan = _make_plan()

        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())

        msg = exc.value.safe_message
        assert "\\" not in msg
        assert "/" not in msg or "秒" in msg  # no path separators
        assert str(tmp_path) not in msg
        assert str(source.resolve()) not in msg
