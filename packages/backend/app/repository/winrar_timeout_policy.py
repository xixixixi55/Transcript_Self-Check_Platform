"""Timeout policy for WinRAR archive execution and integrity checks.

Per-attempt execution timeout — each ``WinRarExecutor.execute()`` call gets
a fresh timeout computed from total input bytes.  The replan loop in
``execute_archive()`` is bounded by ``max_replan_attempts`` (≤ 3 attempts
total); no separate total-task timeout is needed.

Configurable via ``BIJI_ARCHIVE_TIMEOUT_SECONDS`` (overrides *per-attempt*
execution timeout).
"""

from __future__ import annotations

import logging
import math
import os
import subprocess

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Execution timeout — per-attempt WinRAR "a" process
#
# Throughput floor of 5 MB/s is supported by real D2 acceptance data:
#   4.5 GB input →  ~9 min wall time →  ~8.3 MB/s effective
#   8.5 GB input → ~12 min wall time → ~11.8 MB/s effective
# The 5 MB/s floor leaves ≥40 % headroom below the slowest observation.
#
#   worst-case input  135 GB  (ARCHIVE_TOO_LARGE blocks > 135 GB)
#   time @ 5 MB/s    = 27 000 s = 7.5 h
#   cap at 10 h        → 36 000 s (covers 135 GB with 33 % margin)
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SECONDS = 300
_MIN_THROUGHPUT_BYTES_PER_SEC = 5_000_000  # 5 MB/s (real-data-verified floor)
_COMPLETION_GRACE_SECONDS = 600  # HDD/WinRAR volume finalization margin
_MAX_COMPUTED_TIMEOUT = 36_000  # 10 hours
_MAX_ENV_TIMEOUT = 86_400  # 24 hours (operator override ceiling)

_ENV_KEY = "BIJI_ARCHIVE_TIMEOUT_SECONDS"

# ---------------------------------------------------------------------------
# Integrity-check timeout — per "rar t" invocation against part1.rar
#
# ``rar t part1.rar`` verifies every byte of the *entire* multi-volume set
# (read + decompress + checksum).  Throughput is dominated by disk read:
#   → HDD sequential read floor: 50 MB/s (conservative, allows OS contention)
#   → 135 GB ÷ 50 MB/s = 2 700 s ≈ 45 min
#   → cap at 2 h (7 200 s) gives >2.6× margin
# ---------------------------------------------------------------------------

_INTEGRITY_DEFAULT_TIMEOUT = 60
_INTEGRITY_THROUGHPUT = 50_000_000  # 50 MB/s conservative HDD read floor
_INTEGRITY_MAX_TIMEOUT = 7_200  # 2 hours


def compute_timeout(input_bytes: int) -> int:
    """Return a bounded per-attempt *execution* timeout in seconds.

    1. If ``BIJI_ARCHIVE_TIMEOUT_SECONDS`` is set to a positive integer
       ≤ 86 400, use it verbatim (operator override).
    2. Otherwise compute ``max(300, ceil(input_bytes / 5 MB/s) + 600)`` clamped to
       [300, 36 000].

    Invalid or out-of-range env values trigger exactly one sanitised
    warning per call and a safe fallback to the computed value.
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
            env_val = None  # sentinel — already warned
        if env_val is None:
            pass  # already logged
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
    """Return a bounded integrity-check timeout.

    ``total_archive_bytes`` is the sum of all validated part sizes
    (not just part1), because ``rar t part1.rar`` verifies the full set.

    Formula: ``max(60, total_bytes / 50 MB/s)`` clamped to [60, 7 200].
    """
    size_based = max(_INTEGRITY_DEFAULT_TIMEOUT, int(total_archive_bytes / _INTEGRITY_THROUGHPUT))
    return min(size_based, _INTEGRITY_MAX_TIMEOUT)


def timeout_bounds() -> tuple[int, int, int]:
    """Return (default_min, computed_max, env_override_max) in seconds."""
    return (_DEFAULT_TIMEOUT_SECONDS, _MAX_COMPUTED_TIMEOUT, _MAX_ENV_TIMEOUT)


def integrity_bounds() -> tuple[int, int]:
    """Return (default, max) for integrity-check timeout in seconds."""
    return (_INTEGRITY_DEFAULT_TIMEOUT, _INTEGRITY_MAX_TIMEOUT)


def _kill_process_tree_impl(pid: int) -> bool:
    """Best-effort tree kill on Windows; returns True if successful."""
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
