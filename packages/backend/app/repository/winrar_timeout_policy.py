"""WinRAR 归档执行和完整性检查的超时策略。

每次尝试的执行超时：每次 ``WinRarExecutor.execute()`` 调用都会根据输入总字节数
获得新的超时。``execute_archive()`` 中的重新规划循环受 ``max_replan_attempts``
限制（总计不超过 3 次尝试），因此无需单独设置任务总超时。

可通过 ``BIJI_ARCHIVE_TIMEOUT_SECONDS`` 配置（覆盖每次尝试的执行超时）。
"""

from __future__ import annotations

import logging
import math
import os
import subprocess

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 执行超时 — 每次尝试的 WinRAR "a" 进程
#
# 在多个磁盘密集任务并发运行的 HDD 竞争环境中，每个任务实测约 0.3 MB/s。
# 按 0.1 MB/s 预算，使超时可容纳实测墙钟时间的三倍，同时保持有界。
#
# 默认生产策略可将超过 225 GiB 的输入切换为不分卷 RAR，
# 因此该超时是执行安全边界，而非归档大小准入限制。
# 有限的 30 天边界可在竞争磁盘预算下覆盖标准的 225 GiB 阈值。
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SECONDS = 300
_MIN_THROUGHPUT_BYTES_PER_SEC = 100_000  # 竞争状态 HDD 的吞吐下限为 0.1 MB/s
_COMPLETION_GRACE_SECONDS = 600  # HDD/WinRAR 分卷收尾余量
_MAX_COMPUTED_TIMEOUT = 30 * 24 * 60 * 60
_MAX_ENV_TIMEOUT = _MAX_COMPUTED_TIMEOUT

_ENV_KEY = "BIJI_ARCHIVE_TIMEOUT_SECONDS"

# ---------------------------------------------------------------------------
# 完整性检查超时 — 每次针对 part1.rar 调用 "rar t"
#
# ``rar t part1.rar`` 会验证整个多分卷集合的每个字节
#（读取 + 解压 + 校验和）。部署环境主要使用 HDD，老旧磁盘、碎片、
# 杀毒软件和并发工作会使实际速率远低于标称顺序读取规格。
# 使用与归档执行相同的 0.1 MB/s 下限，并加上固定收尾余量。
# ---------------------------------------------------------------------------

_INTEGRITY_DEFAULT_TIMEOUT = 300
_INTEGRITY_THROUGHPUT = 100_000
_INTEGRITY_COMPLETION_GRACE_SECONDS = 600
_INTEGRITY_MAX_TIMEOUT = 30 * 24 * 60 * 60


def compute_timeout(input_bytes: int) -> int:
    """返回以秒为单位的有界单次尝试执行超时。

    1. 若 ``BIJI_ARCHIVE_TIMEOUT_SECONDS`` 是不超过 2 592 000 的正整数，
       则直接采用该值（运维人员覆盖）。
    2. 否则计算 ``max(300, ceil(input_bytes / 0.1 MB/s) + 600)``，
       并限制在 [300, 2 592 000] 范围内。

    无效或超出范围的环境变量值在每次调用中仅触发一次脱敏警告，
    并安全回退到计算值。
    """
    env_raw = os.environ.get(_ENV_KEY, "").strip()
    if env_raw:
        try:
            env_val = int(env_raw)
        except ValueError:
            _logger.warning(
                "%s 值无效（非数字），已回退到默认计算。"
                "允许范围：1–%d 秒。",
                _ENV_KEY, _MAX_ENV_TIMEOUT,
            )
            env_val = None  # 哨兵值——已发出警告
        if env_val is None:
            pass  # 已记录日志
        elif env_val == 0:
            _logger.warning(
                "%s=0，已回退到默认计算。"
                "允许范围：1–%d 秒。",
                _ENV_KEY, _MAX_ENV_TIMEOUT,
            )
        elif env_val < 0:
            _logger.warning(
                "%s=%d 超出允许范围，已回退到默认计算。"
                "允许范围：1–%d 秒。",
                _ENV_KEY, env_val, _MAX_ENV_TIMEOUT,
            )
        elif env_val <= _MAX_ENV_TIMEOUT:
            return env_val
        else:
            _logger.warning(
                "%s=%d 超出允许范围，已回退到默认计算。"
                "允许范围：1–%d 秒。",
                _ENV_KEY, env_val, _MAX_ENV_TIMEOUT,
            )

    size_based = max(
        _DEFAULT_TIMEOUT_SECONDS,
        math.ceil(input_bytes / _MIN_THROUGHPUT_BYTES_PER_SEC)
        + (_COMPLETION_GRACE_SECONDS if input_bytes > 0 else 0),
    )
    return min(size_based, _MAX_COMPUTED_TIMEOUT)


def compute_integrity_timeout(total_archive_bytes: int) -> int:
    """返回有界的完整性检查超时。

    ``total_archive_bytes`` 是所有已验证分卷大小的总和，而非仅 part1，
    因为 ``rar t part1.rar`` 会验证整个分卷集。

    对非空归档使用公式 ``max(300, ceil(total_bytes / 0.1 MB/s) + 600)``，
    并限制在 [300, 2,592,000] 范围内。
    """
    size_based = max(
        _INTEGRITY_DEFAULT_TIMEOUT,
        math.ceil(total_archive_bytes / _INTEGRITY_THROUGHPUT)
        + (_INTEGRITY_COMPLETION_GRACE_SECONDS if total_archive_bytes > 0 else 0),
    )
    return min(size_based, _INTEGRITY_MAX_TIMEOUT)


def timeout_bounds() -> tuple[int, int, int]:
    """返回以秒为单位的 (default_min, computed_max, env_override_max)。"""
    return (_DEFAULT_TIMEOUT_SECONDS, _MAX_COMPUTED_TIMEOUT, _MAX_ENV_TIMEOUT)


def integrity_bounds() -> tuple[int, int]:
    """返回完整性检查超时的 (default, max)，单位为秒。"""
    return (_INTEGRITY_DEFAULT_TIMEOUT, _INTEGRITY_MAX_TIMEOUT)


def _kill_process_tree_impl(pid: int) -> bool:
    """在 Windows 上尽力终止进程树；成功时返回 True。"""
    if os.name != "nt":
        return True
    try:
        result = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True, timeout=15, shell=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
