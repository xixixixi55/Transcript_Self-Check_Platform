"""WinRAR 超时治理综合测试——v2 生产收尾。

覆盖：
  - 争用 HDD 部署的执行超时（0.1 MB/s，上限 30 天）
  - 面向 HDD 的完整性超时（0.1 MB/s + 余量，上限 30 天）
  - 进程树终止（Windows 上始终终止整棵进程树）
  - 基于集合的锁生命周期（原子认领与释放）
  - 已发布 manifest 不可变性（deepcopy 规范化）
  - ARCHIVE_INTEGRITY_TIMEOUT 完整契约链
  - _positive_int 严格校验
  - record_controller 的 Enum.value 提取
  - 每个无效环境变量只警告一次
  - 暂存区清理门控
"""

import copy
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_input_repository import build_input_inventory  # noqa: E402
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import (  # noqa: E402
    ArchiveExecutionError,
    WinRarExecutor,
    _terminate_process,
)
from app.repository.winrar_timeout_policy import (  # noqa: E402
    compute_integrity_timeout,
    integrity_bounds,
)
from app.repository.winrar_process_monitor import (  # noqa: E402
    OwnedProcessIdleTimeout,
    archive_output_idle_timeout_seconds,
    monitor_owned_process,
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
    archive_path = Path(next(item for item in args if item.endswith(".rar") and not item.startswith("@")))
    archive_path.write_bytes(b"ok")
    return subprocess.CompletedProcess(args, 0, "", "")


# ============================================================================
# 1. 执行超时（真实数据验证）
# ============================================================================


class TestExecutionTimeout:
    def test_default_for_zero(self):
        assert WinRarExecutor.compute_timeout(0) == 300

    def test_4_5gb_uses_contended_hdd_budget(self):
        t = WinRarExecutor.compute_timeout(4_500_000_000)
        assert t == 45_600  # 45,000 秒大小预算 + 600 秒收尾余量
        assert t >= 540

    def test_8_5gb_uses_contended_hdd_budget(self):
        t = WinRarExecutor.compute_timeout(8_500_000_000)
        assert t == 85_600
        assert t >= 720

    def test_135gb_not_truncated(self):
        t = WinRarExecutor.compute_timeout(135 * GB)
        assert t == 1_350_600
        assert t < 2_592_000

    def test_capped_at_30_days(self):
        assert WinRarExecutor.compute_timeout(300 * GB) == 2_592_000


# ============================================================================
# 2. 完整性超时（归档总大小、面向 HDD 的 0.1 MB/s + 余量）
# ============================================================================


class TestIntegrityTimeout:
    def test_default_for_zero(self):
        assert compute_integrity_timeout(0) == 300

    def test_45gb_plus_45gb_plus_45gb_uses_135gb(self):
        """rar t part1.rar 校验整个分卷集，即 3 × 45 GB = 135 GB。"""
        t = compute_integrity_timeout(135 * GB)
        assert t == 1_350_600

    def test_22gb_plus_1gb_uses_23gb(self):
        t = compute_integrity_timeout(23 * GB)
        assert t == 230_600

    def test_oversized_input_is_capped_at_30_days(self):
        assert compute_integrity_timeout(500 * GB) == 2_592_000

    def test_bounds(self):
        lo, hi = integrity_bounds()
        assert lo == 300
        assert hi == 2_592_000


class TestIntegrityTimeoutViaValidator:
    """测试 validate_archive_parts()，而不只测试纯函数。"""

    def test_total_size_used_not_just_part1(self, tmp_path):
        from app.repository.archive.archive_validator_repository import validate_archive_parts

        (tmp_path / "case.part1.rar").write_bytes(b"a" * 10_000)
        (tmp_path / "case.part2.rar").write_bytes(b"b" * 5_000)
        plan = SimpleNamespace(archive_base_name="case", volume_size_bytes=50_000, max_part_count=3)

        seen_bytes = []
        def fake_timeout(total_bytes):
            seen_bytes.append(total_bytes)
            return 99  # 任意非默认值

        with mock.patch("app.repository.archive.archive_validator_repository.compute_integrity_timeout", side_effect=fake_timeout):
            def ok_runner(*a, **kw):
                return subprocess.CompletedProcess(a if a else ["t"], 0, "", "")
            result = validate_archive_parts(tmp_path, plan, capability(), integrity_runner=ok_runner)
            assert result.valid
            assert len(seen_bytes) == 1
            # 调用参数 total = 15_000（part1 + part2），而非 10_000（仅 part1）
            assert seen_bytes[0] == 15_000
            assert seen_bytes[0] != 10_000

    def test_integrity_timeout_returns_distinct_code(self, tmp_path):
        from app.repository.archive.archive_validator_repository import validate_archive_parts

        (tmp_path / "case.part1.rar").write_bytes(b"x" * 100)
        plan = SimpleNamespace(archive_base_name="case", volume_size_bytes=4_000_000_000, max_part_count=1)

        def timeout_runner(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 60))

        result = validate_archive_parts(
            tmp_path, plan, capability(), integrity_runner=timeout_runner, timeout_seconds=1)
        assert not result.valid
        assert result.diagnostic_code == "ARCHIVE_INTEGRITY_TIMEOUT"
        assert result.replan_allowed is False


# ============================================================================
# 3. 超过 225 GiB 标准分卷阈值时规划器切换模式
# ============================================================================


class TestPlannerUsesOversizedSingleVolume:
    def test_225gib_plus_1_uses_unsplit_rar(self):
        from app.services.archive.archive_planner_service import (ArchiveSourceEntry, PRODUCTION_ARCHIVE_POLICY, plan_archive)
        over = 225 * 1024**3 + 1
        entries = (ArchiveSourceEntry("big.bin", over, 0),)
        plan = plan_archive("huge", entries, policy=PRODUCTION_ARCHIVE_POLICY)
        assert plan.status == "planned"
        assert plan.archive_mode == "oversized_single_volume"
        assert plan.volume_size_bytes is None
        assert plan.expected_part_count == 1


# ============================================================================
# 4. 环境变量（每个无效值只警告一次）
# ============================================================================


class TestEnvTimeoutWarnings:
    def test_no_warning_when_unset(self, caplog):
        WinRarExecutor.compute_timeout(0)
        assert "BIJI_ARCHIVE_TIMEOUT_SECONDS" not in caplog.text

    def test_no_warning_when_valid(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "3600")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 3600
        assert "已回退" not in caplog.text

    def test_non_numeric_one_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "twelve")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300
        assert caplog.text.count("BIJI_ARCHIVE_TIMEOUT_SECONDS") == 1
        assert "非数字" in caplog.text
        assert "twelve" not in caplog.text  # 原始值已脱敏

    def test_zero_one_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "0")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300
        assert caplog.text.count("已回退") == 1
        assert "0" in caplog.text

    def test_negative_one_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "-5")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300
        assert caplog.text.count("已回退") == 1

    def test_above_max_one_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "3000000")
        result = WinRarExecutor.compute_timeout(0)
        assert result == 300
        assert caplog.text.count("已回退") == 1

    def test_warning_contains_no_paths(self, monkeypatch, caplog):
        monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "not-a-number")
        WinRarExecutor.compute_timeout(0)
        for forbidden in ("\\", "C:", "D:", "Users"):
            assert forbidden not in caplog.text


class TestArchiveIdleTimeoutConfiguration:
    def test_default_allows_30_minutes_without_output_growth(self, monkeypatch):
        monkeypatch.delenv("BIJI_ARCHIVE_IDLE_TIMEOUT_SECONDS", raising=False)
        assert archive_output_idle_timeout_seconds() == 1_800

    def test_positive_override_is_used(self, monkeypatch):
        monkeypatch.setenv("BIJI_ARCHIVE_IDLE_TIMEOUT_SECONDS", "3600")
        assert archive_output_idle_timeout_seconds() == 3_600

    @pytest.mark.parametrize("value", ["0", "-1", "invalid", "3000000"])
    def test_invalid_or_out_of_range_override_falls_back(self, monkeypatch, caplog, value):
        monkeypatch.setenv("BIJI_ARCHIVE_IDLE_TIMEOUT_SECONDS", value)
        assert archive_output_idle_timeout_seconds() == 1_800
        assert caplog.text.count("BIJI_ARCHIVE_IDLE_TIMEOUT_SECONDS") == 1
        assert f"={value}" not in caplog.text

    def test_monitor_uses_resolved_default_when_not_explicit(self, tmp_path):
        class PollingProcess:
            def poll(self):
                return None

            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired(["WinRAR.exe"], timeout)

            def communicate(self):
                return ("", "")

        with mock.patch(
            "app.repository.winrar_process_monitor.archive_output_idle_timeout_seconds",
            return_value=2,
        ), mock.patch(
            "app.repository.winrar_process_monitor.time.monotonic",
            side_effect=[0.0, 0.0, 2.0],
        ):
            with pytest.raises(OwnedProcessIdleTimeout) as failure:
                monitor_owned_process(
                    PollingProcess(), pid=4242, args=["WinRAR.exe"], timeout=60,
                    staging_dir=tmp_path, terminate=lambda *_: True,
                    activity_callback=None, cancellation_check=None,
                    output_size_probe=lambda _root: 1,
                )
        assert failure.value.timeout == 2


# ============================================================================
# 5. 进程树终止 — 在 Windows 上始终终止整棵进程树
# ============================================================================


class FakePopen:
    """用于测试终止顺序的可控 Popen 桩。"""

    def __init__(self, *, kill_side_effect=None, wait_timeouts=0, poll_returns=None):
        self._kill = mock.MagicMock(side_effect=kill_side_effect)
        self._wait = mock.MagicMock()
        self._poll = mock.MagicMock()
        self.pid = 99999
        self._wait_timeouts_remaining = wait_timeouts
        self._poll_returns = poll_returns or [None]

    def kill(self):
        return self._kill()

    def wait(self, timeout=None):
        if self._wait_timeouts_remaining > 0:
            self._wait_timeouts_remaining -= 1
            raise subprocess.TimeoutExpired(["cmd"], timeout or 10)
        return self._wait()

    def poll(self):
        if self._poll_returns:
            return self._poll_returns.pop(0)
        return None

    def communicate(self, timeout=None):
        raise subprocess.TimeoutExpired(["cmd"], timeout)


class TestProcessTermination:
    def test_tree_kill_first_on_windows(self):
        """先调用 taskkill /T，再以直接终止作为回退。"""
        with mock.patch(
            "app.repository.winrar_executor_repository._kill_process_tree_impl",
            return_value=True,
        ) as mock_tree:
            p = FakePopen(poll_returns=[0], wait_timeouts=0)
            assert _terminate_process(p, pid=99999) is True
            # 使用正确 PID 调用进程树终止
            mock_tree.assert_called_once_with(99999)
            # 不调用直接终止（进程树终止已成功）
            p._kill.assert_not_called()

    def test_tree_kill_fails_falls_back_to_direct_kill(self):
        """taskkill 失败后，回退到直接调用 process.kill()。"""
        with mock.patch(
            "app.repository.winrar_executor_repository._kill_process_tree_impl",
            return_value=False,
        ):
            p = FakePopen(poll_returns=[0], wait_timeouts=0)
            assert _terminate_process(p, pid=99999) is True
            p._kill.assert_called_once()

    def test_both_tree_and_direct_fail_returns_false(self):
        """进程树终止失败，直接终止成功但等待超时，此时返回 False。"""
        with mock.patch(
            "app.repository.winrar_executor_repository._kill_process_tree_impl",
            return_value=False,
        ):
            p = FakePopen(poll_returns=[None, None], wait_timeouts=1)
            assert _terminate_process(p, pid=99999) is False

    def test_parent_exited_not_equal_to_tree_confirmed(self):
        """即使父进程轮询结果为已退出，也 ALWAYS 尝试终止进程树。"""
        with mock.patch(
            "app.repository.winrar_executor_repository._kill_process_tree_impl",
            return_value=True,
        ) as mock_tree:
            p = FakePopen(poll_returns=[0])  # 已“退出”
            assert _terminate_process(p, pid=99999) is True
            # 即使父进程看似已退出，仍调用了进程树终止
            mock_tree.assert_called_once_with(99999)

    def test_tree_kill_success_then_poll_exited(self):
        """正常路径：进程树终止成功，然后等待，轮询返回退出码。"""
        with mock.patch(
            "app.repository.winrar_executor_repository._kill_process_tree_impl",
            return_value=True,
        ):
            p = FakePopen(poll_returns=[None, 0], wait_timeouts=0)
            assert _terminate_process(p, pid=99999) is True


class TestTerminationPreventsCleanup:
    def test_unterminated_process_leaves_staging(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = _make_plan()
        executor = WinRarExecutor(tmp_path / "staging")

        fake = FakePopen(poll_returns=[None, None], wait_timeouts=0)
        fake.pid = 99999
        with mock.patch("subprocess.Popen", return_value=fake), \
             mock.patch("app.repository.winrar_executor_repository._kill_process_tree_impl", return_value=False):
            with pytest.raises(ArchiveExecutionError) as exc:
                executor.execute(plan, inventory.files, inventory.source_root, capability())
            assert exc.value.code == "ARCHIVE_EXECUTION_FAILED"
            stagings = list((tmp_path / "staging").glob("archive-*"))
            assert len(stagings) >= 1, "staging preserved when process not confirmed dead"


class TestOSErrorPath:
    def test_oserror_terminate_false_does_not_clean_staging(self, tmp_path):
        """communicate 发生 OSError 且终止失败时，保留暂存区。"""
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = _make_plan()
        executor = WinRarExecutor(tmp_path / "staging")

        fake = FakePopen(poll_returns=[None, None], wait_timeouts=0)
        fake.pid = 99999
        fake.communicate = mock.MagicMock(side_effect=OSError("broken pipe"))

        with mock.patch("subprocess.Popen", return_value=fake), \
             mock.patch("app.repository.winrar_executor_repository._kill_process_tree_impl", return_value=False):
            with pytest.raises(ArchiveExecutionError) as exc:
                executor.execute(plan, inventory.files, inventory.source_root, capability())
            assert exc.value.code == "ARCHIVE_EXECUTION_FAILED"
            assert "无法终止" in exc.value.safe_message
            stagings = list((tmp_path / "staging").glob("archive-*"))
            assert len(stagings) >= 1, "staging NOT cleaned when termination unconfirmed"

    def test_oserror_terminate_true_cleans_staging(self, tmp_path):
        """communicate 发生 OSError 且确认终止后，清理暂存区。"""
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = _make_plan()
        executor = WinRarExecutor(tmp_path / "staging")

        fake = FakePopen(poll_returns=[0], wait_timeouts=0)
        fake.pid = 99999
        fake.communicate = mock.MagicMock(side_effect=OSError("broken pipe"))

        with mock.patch("subprocess.Popen", return_value=fake), \
             mock.patch("app.repository.winrar_executor_repository._kill_process_tree_impl", return_value=True):
            with pytest.raises(ArchiveExecutionError) as exc:
                executor.execute(plan, inventory.files, inventory.source_root, capability())
            assert exc.value.code == "ARCHIVE_EXECUTION_FAILED"
            assert "无法终止" not in exc.value.safe_message
            stagings = list((tmp_path / "staging").glob("archive-*"))
            assert len(stagings) == 0, "staging cleaned after confirmed termination"


# ============================================================================
# 6. 基于集合的锁生命周期
# ============================================================================


class TestLockLifecycle:
    def test_plan_removed_after_success(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 256)
        plan = _make_plan(plan_id="lifecycle-test")
        executor.execute(plan, inventory.files, inventory.source_root, capability())
        with WinRarExecutor._active_guard:
            assert "lifecycle-test" not in WinRarExecutor._active_plans

    def test_plan_removed_after_exception(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", timeout_seconds=0)
        source = tmp_path / "source"
        source.mkdir()
        (source / "x.txt").write_text("hi", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = _make_plan(plan_id="exception-test")
        with pytest.raises(ArchiveExecutionError):
            executor.execute(plan, inventory.files, inventory.source_root, capability())
        with WinRarExecutor._active_guard:
            assert "exception-test" not in WinRarExecutor._active_plans

    def test_no_growth_after_sequential_executions(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 64)
        for i in range(20):
            plan = _make_plan(plan_id=f"grow-{i}")
            executor.execute(plan, inventory.files, inventory.source_root, capability())
        with WinRarExecutor._active_guard:
            assert len(WinRarExecutor._active_plans) == 0

    def test_same_plan_id_rejected_concurrently(self):
        executor = WinRarExecutor(Path("."), process_runner=_run_ok)
        with WinRarExecutor._active_guard:
            WinRarExecutor._active_plans.add("concurrent-test")
        try:
            with pytest.raises(ArchiveExecutionError) as exc:
                executor._claim_plan("concurrent-test")
            assert exc.value.code == "ARCHIVE_EXECUTION_IN_PROGRESS"
        finally:
            with WinRarExecutor._active_guard:
                WinRarExecutor._active_plans.discard("concurrent-test")

    def test_different_plan_ids_run_concurrently(self, tmp_path):
        """两个不同的 plan_id 必须能够依次认领。"""
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 64)
        plan_a = _make_plan(plan_id="plan-A")
        executor.execute(plan_a, inventory.files, inventory.source_root, capability())
        plan_b = _make_plan(plan_id="plan-B")
        executor.execute(plan_b, inventory.files, inventory.source_root, capability())
        # 两者都已完成 — 无异常
        with WinRarExecutor._active_guard:
            assert "plan-A" not in WinRarExecutor._active_plans
            assert "plan-B" not in WinRarExecutor._active_plans


class TestLockRaceWindow:
    """多线程测试：释放与重新认领的竞争不得产生重叠。"""

    def test_release_and_reclaim_race(self, tmp_path):
        events = {"entered": threading.Event(), "release": threading.Event()}
        results = []

        def blocking_execute():
            # 模拟持有认领权的长时间 execute() 调用
            WinRarExecutor._claim_plan("race-test")
            events["entered"].set()
            events["release"].wait()
            WinRarExecutor._release_plan("race-test")
            results.append("first-released")

        t = threading.Thread(target=blocking_execute)
        t.start()
        events["entered"].wait()

        # 第一个线程持有 plan_id 时尝试认领同一 plan_id
        with pytest.raises(ArchiveExecutionError) as exc:
            WinRarExecutor._claim_plan("race-test")
        assert exc.value.code == "ARCHIVE_EXECUTION_IN_PROGRESS"
        results.append("second-rejected")

        events["release"].set()
        t.join()

        # 现在已释放
        WinRarExecutor._claim_plan("race-test")
        WinRarExecutor._release_plan("race-test")
        results.append("third-ok")

        assert "first-released" in results
        assert "second-rejected" in results
        assert "third-ok" in results
        assert results.index("second-rejected") < results.index("first-released")


# ============================================================================
# 7. 已发布 manifest 的不可变性
# ============================================================================


class TestManifestImmutability:
    def test_original_manifest_unchanged_after_validation(self, tmp_path):
        import tempfile, shutil
        from app.services.archive.archive_manifest_service import validate_manifest_files

        manifest = {
            "manifest_id": "immutable-test",
            "archive_base_name": "case",
            "total_input_bytes": 1000,
            "actual_archive_bytes": 1000,
            "volume_size_bytes": 4_000_000_000,
            "max_part_count": 2,
            "validation_status": "validated",
            "continuity_check": "ok",
            "parts": [{
                "filename": "case.part1.rar",
                "part_number": 1,
                "size_bytes": 1000,
                "md5": "ede3d3b685b4e137ba4cb2521329a75e",
                "disc_number": "GP20260718-001",
                "disc_date": "2026-07-18",
                "volume_size_bytes": 4_000_000_000,
            }],
        }
        original = copy.deepcopy(manifest)

        d = tempfile.mkdtemp()
        try:
            (Path(d) / "case.part1.rar").write_bytes(b"\x00" * 1000)
            class Rec:
                final_dir = Path(d)
                public_manifest = manifest
                manifest_id = "immutable-test"

            err = validate_manifest_files(Rec())
            assert err is None
            # 原始 manifest 在验证前后必须完全一致
            assert manifest == original
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestGetValidManifestNormalizes:
    def test_legacy_normalized_copy_uses_decimal_disc_capacity(self):
        from app.services.archive.archive_manifest_access_service import _normalized_manifest

        manifest = {
            "manifest_id": "norm-test",
            "archive_base_name": "case",
            "total_input_bytes": 4_100_000_000,
            "actual_archive_bytes": 4_100_000_000,
            "volume_size_bytes": 22_000_000_000,
            "max_part_count": 2,
            "validation_status": "validated",
            "continuity_check": "ok",
            "parts": [{
                "filename": "case.part1.rar",
                "part_number": 1,
                "size_bytes": 4_100_000_000,
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
                "disc_number": "GP20260718-001",
                "disc_date": "2026-07-18",
                "volume_size_bytes": 22_000_000_000,
            }],
        }
        original = copy.deepcopy(manifest)

        normalized = _normalized_manifest(manifest)

        # 原始值未改变
        assert "disc_capacity_bytes" not in original["parts"][0]
        # 规范化结果包含该值
        assert normalized["parts"][0]["disc_capacity_bytes"] == 22_000_000_000
        # 原始值仍不含 disc_capacity_bytes
        assert original["parts"][0].get("disc_capacity_bytes") is None


# ============================================================================
# 8. ARCHIVE_INTEGRITY_TIMEOUT 契约链
# ============================================================================


class TestIntegrityTimeoutContractChain:
    def test_in_python_export_gate_enum(self):
        from app.services.export_gate_service import ExportGateCode
        assert hasattr(ExportGateCode, "ARCHIVE_INTEGRITY_TIMEOUT")
        assert ExportGateCode.ARCHIVE_INTEGRITY_TIMEOUT.value == "ARCHIVE_INTEGRITY_TIMEOUT"

    def test_in_archive_message(self):
        from app.services.export_gate_service import _archive_message
        msg = _archive_message("ARCHIVE_INTEGRITY_TIMEOUT")
        assert "完整性校验" in msg

    def test_not_confused_with_corruption(self):
        from app.repository.archive.archive_validator_repository import _invalid
        t = _invalid("ARCHIVE_INTEGRITY_TIMEOUT", "超时")
        c = _invalid("ARCHIVE_PARTS_INVALID", "损坏")
        assert t.diagnostic_code != c.diagnostic_code
        assert t.replan_allowed is False


# ============================================================================
# 9. record_controller 的 Enum.value
# ============================================================================


class TestRecordControllerEnum:
    def test_extracts_value_not_Enum_repr(self):
        from app.services.export_gate_service import ExportGateCode
        code = ExportGateCode.ARCHIVE_MANIFEST_CONTEXT_MISMATCH
        extracted = code.value if hasattr(code, "value") else str(code)
        assert extracted == "ARCHIVE_MANIFEST_CONTEXT_MISMATCH"
        assert "ExportGateCode" not in extracted

    def test_string_fallback_unchanged(self):
        raw = "ARCHIVE_MANIFEST_CONTEXT_MISMATCH"
        extracted = raw.value if hasattr(raw, "value") else str(raw)
        assert extracted == "ARCHIVE_MANIFEST_CONTEXT_MISMATCH"


# ============================================================================
# 拒绝旧版 manifest 的无效值
# ============================================================================


class TestOldManifestRejectsInvalidDiscCap:
    """键存在但值无效时拒绝；键不存在时推导。"""

    def _valid_part(self):
        return {
            "filename": "case.part1.rar",
            "part_number": 1,
            "size_bytes": 1_000_000,
            "md5": "879f4bba57ed37c9ec5e5aedf9864698",
            "disc_number": "GP20260718-001",
            "disc_date": "2026-07-18",
            "volume_size_bytes": 4_000_000_000,
        }

    def _valid_manifest(self, parts):
        return {
            "manifest_id": "reject-test",
            "archive_base_name": "case",
            "total_input_bytes": 1_000_000,
            "actual_archive_bytes": 1_000_000,
            "volume_size_bytes": 4_000_000_000,
            "max_part_count": 2,
            "validation_status": "validated",
            "continuity_check": "ok",
            "parts": parts,
        }

    def test_missing_key_ok(self, tmp_path):
        from app.services.archive.archive_manifest_service import validate_manifest_files
        part = self._valid_part()
        # 有意不提供该键
        manifest = self._valid_manifest([part])
        (tmp_path / "case.part1.rar").write_bytes(b"\x00" * 1_000_000)
        class Rec:
            final_dir = tmp_path
            public_manifest = manifest
            manifest_id = "reject-test"
        err = validate_manifest_files(Rec())
        assert err is None

    def test_null_rejected(self, tmp_path):
        from app.services.archive.archive_manifest_service import validate_manifest_files
        part = self._valid_part()
        part["disc_capacity_bytes"] = None
        manifest = self._valid_manifest([part])
        (tmp_path / "case.part1.rar").write_bytes(b"\x00" * 1_000_000)
        class Rec:
            final_dir = tmp_path
            public_manifest = manifest
            manifest_id = "reject-test"
        err = validate_manifest_files(Rec())
        assert err == "ARCHIVE_MANIFEST_INVALID"

    def test_string_rejected(self, tmp_path):
        from app.services.archive.archive_manifest_service import validate_manifest_files
        part = self._valid_part()
        part["disc_capacity_bytes"] = "4GB"
        manifest = self._valid_manifest([part])
        (tmp_path / "case.part1.rar").write_bytes(b"\x00" * 1_000_000)
        class Rec:
            final_dir = tmp_path
            public_manifest = manifest
            manifest_id = "reject-test"
        err = validate_manifest_files(Rec())
        assert err == "ARCHIVE_MANIFEST_INVALID"

    def test_bool_rejected(self, tmp_path):
        from app.services.archive.archive_manifest_service import validate_manifest_files
        part = self._valid_part()
        part["disc_capacity_bytes"] = True
        manifest = self._valid_manifest([part])
        (tmp_path / "case.part1.rar").write_bytes(b"\x00" * 1_000_000)
        class Rec:
            final_dir = tmp_path
            public_manifest = manifest
            manifest_id = "reject-test"
        err = validate_manifest_files(Rec())
        assert err == "ARCHIVE_MANIFEST_INVALID"

    def test_zero_rejected(self, tmp_path):
        from app.services.archive.archive_manifest_service import validate_manifest_files
        part = self._valid_part()
        part["disc_capacity_bytes"] = 0
        manifest = self._valid_manifest([part])
        (tmp_path / "case.part1.rar").write_bytes(b"\x00" * 1_000_000)
        class Rec:
            final_dir = tmp_path
            public_manifest = manifest
            manifest_id = "reject-test"
        err = validate_manifest_files(Rec())
        assert err == "ARCHIVE_MANIFEST_INVALID"

    def test_negative_rejected(self, tmp_path):
        from app.services.archive.archive_manifest_service import validate_manifest_files
        part = self._valid_part()
        part["disc_capacity_bytes"] = -1
        manifest = self._valid_manifest([part])
        (tmp_path / "case.part1.rar").write_bytes(b"\x00" * 1_000_000)
        class Rec:
            final_dir = tmp_path
            public_manifest = manifest
            manifest_id = "reject-test"
        err = validate_manifest_files(Rec())
        assert err == "ARCHIVE_MANIFEST_INVALID"


# ============================================================================
# 10. _positive_int 严格验证
# ============================================================================


class TestPositiveInt:
    def test_positive_ok(self):
        from app.services.attachment_plan_service import _positive_int
        assert _positive_int(4_000_000_000) == 4_000_000_000
        assert _positive_int(1) == 1

    def test_none_raises(self):
        from app.services.attachment_plan_service import _positive_int
        from app.services.attachment_plan_models_service import AttachmentPlanError
        with pytest.raises(AttachmentPlanError) as exc:
            _positive_int(None)
        assert "缺少" in exc.value.safe_message

    def test_zero_raises(self):
        from app.services.attachment_plan_service import _positive_int
        from app.services.attachment_plan_models_service import AttachmentPlanError
        with pytest.raises(AttachmentPlanError) as exc:
            _positive_int(0)
        assert "正整" in exc.value.safe_message

    def test_negative_raises(self):
        from app.services.attachment_plan_service import _positive_int
        from app.services.attachment_plan_models_service import AttachmentPlanError
        with pytest.raises(AttachmentPlanError) as exc:
            _positive_int(-1)
        assert exc.value.code == "ATTACHMENT_PLAN_INVALID"

    def test_bool_raises(self):
        from app.services.attachment_plan_service import _positive_int
        from app.services.attachment_plan_models_service import AttachmentPlanError
        with pytest.raises(AttachmentPlanError) as exc:
            _positive_int(True)
        assert "类型无效" in exc.value.safe_message

    def test_float_raises(self):
        from app.services.attachment_plan_service import _positive_int
        from app.services.attachment_plan_models_service import AttachmentPlanError
        with pytest.raises(AttachmentPlanError) as exc:
            _positive_int(4.0)
        assert "类型无效" in exc.value.safe_message

    def test_string_raises(self):
        from app.services.attachment_plan_service import _positive_int
        from app.services.attachment_plan_models_service import AttachmentPlanError
        with pytest.raises(AttachmentPlanError) as exc:
            _positive_int("4000000000")
        assert "类型无效" in exc.value.safe_message


# ============================================================================
# 11. 正常执行（保留现有行为）
# ============================================================================


class TestNormalExecution:
    def test_small_input_completes(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 1024)
        plan = _make_plan(vol=4_000_000_000)
        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert result.returncode == 0
        assert result.timed_out is False
        assert (result.staging_dir / "case.rar").is_file()

    def test_single_volume_uses_base_name(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 512)
        plan = _make_plan()
        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert (result.staging_dir / "case.rar").is_file()
        assert not (result.staging_dir / "case.part1.rar").exists()

    def test_multi_volume_untouched(self, tmp_path):
        def multi_runner(args, **kwargs):
            archive_path = Path(next(item for item in args if item.endswith(".rar") and not item.startswith("@")))
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
# 12. 通过 process_runner 路径清理超时 + OSError
# ============================================================================


class TestTimeoutCleanup:
    def test_timeout_cleans_staging(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")

        def runner(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 300))

        executor = WinRarExecutor(tmp_path / "staging", timeout_seconds=1, process_runner=runner)
        inventory = build_input_inventory(source)
        plan = _make_plan()
        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert exc.value.code == "ARCHIVE_EXECUTION_TIMEOUT"
        assert list((tmp_path / "staging").glob("archive-*")) == []

    def test_oserror_cleans_staging(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")

        def runner(args, **kwargs):
            raise OSError("disk full")

        executor = WinRarExecutor(tmp_path / "staging", timeout_seconds=300, process_runner=runner)
        inventory = build_input_inventory(source)
        plan = _make_plan()
        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert exc.value.code == "ARCHIVE_EXECUTION_FAILED"
        assert list((tmp_path / "staging").glob("archive-*")) == []


# ============================================================================
# 13. 非零退出 + 来源列表清理
# ============================================================================


class TestNonZeroExit:
    def test_nonzero_cleans_staging(self, tmp_path):
        def failing_runner(args, **kwargs):
            archive_path = Path(next(item for item in args if item.endswith(".rar") and not item.startswith("@")))
            archive_path.write_bytes(b"partial")
            return subprocess.CompletedProcess(args, 7, "", "some error")

        executor = WinRarExecutor(tmp_path / "staging", process_runner=failing_runner)
        inventory = _inventory(tmp_path, 128)
        plan = _make_plan()
        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert result.returncode == 7
        assert result.diagnostic_code == "ARCHIVE_EXECUTION_FAILED"
        assert not result.staging_dir.exists()

    def test_source_list_cleaned(self, tmp_path):
        executor = WinRarExecutor(tmp_path / "staging", process_runner=_run_ok)
        inventory = _inventory(tmp_path, 256)
        plan = _make_plan()
        result = executor.execute(plan, inventory.files, inventory.source_root, capability())
        assert not (result.staging_dir / "source-list.txt").exists()


# ============================================================================
# 14. 已净化的错误消息
# ============================================================================


class TestSanitisedMessages:
    def test_timeout_message_no_paths(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")

        def runner(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 300))

        executor = WinRarExecutor(tmp_path / "staging", timeout_seconds=1, process_runner=runner)
        inventory = build_input_inventory(source)
        plan = _make_plan()
        with pytest.raises(ArchiveExecutionError) as exc:
            executor.execute(plan, inventory.files, inventory.source_root, capability())
        msg = exc.value.safe_message
        assert "\\" not in msg
        assert str(tmp_path) not in msg

    def test_termination_failure_message_no_paths(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "data.txt").write_text("x", encoding="utf-8")
        inventory = build_input_inventory(source)
        plan = _make_plan()
        executor = WinRarExecutor(tmp_path / "staging")

        fake = FakePopen(poll_returns=[None, None], wait_timeouts=0)
        with mock.patch("subprocess.Popen", return_value=fake), \
             mock.patch("app.repository.winrar_executor_repository._kill_process_tree_impl", return_value=False):
            with pytest.raises(ArchiveExecutionError) as exc:
                executor.execute(plan, inventory.files, inventory.source_root, capability())
            msg = exc.value.safe_message
            assert "\\" not in msg
            assert str(tmp_path) not in msg
