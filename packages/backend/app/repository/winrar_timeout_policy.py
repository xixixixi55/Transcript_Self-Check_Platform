"""Timeout policy for WinRAR archive execution.

Per-attempt timeout — each call to ``WinRarExecutor.execute()`` gets a
fresh timeout computed from the total input bytes.  The replan loop in
``execute_archive()`` is bounded by ``max_replan_attempts`` (≤ 3 attempts
total); no separate total-task timeout is needed.

Configurable via ``BIJI_ARCHIVE_TIMEOUT_SECONDS`` (overrides *per-attempt*),
size-aware, with separate caps for automatic computation and operator override.
"""

from __future__ import annotations

import logging
import os
import subprocess

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Throughput floor — 10 MiB/s covers low-end SATA HDD under system load.
#
#   worst-case input  135 GB  (ARCHIVE_TOO_LARGE blocks > 135 GB)
#   time @ 10 MiB/s  ≈ 3.58 h
#   with ~12% margin  → 4 h cap
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SECONDS = 300
_MIN_THROUGHPUT_BYTES_PER_SEC = 10 * 1024 * 1024  # 10 MiB/s conservative floor

# Per-attempt computed ceiling: covers the planner's 135 GB maximum.
_MAX_COMPUTED_TIMEOUT = 14_400  # 4 hours

# Operator override ceiling — one day is the practical sanity limit.
_MAX_ENV_TIMEOUT = 86_400  # 24 hours

_ENV_KEY = "BIJI_ARCHIVE_TIMEOUT_SECONDS"


def compute_timeout(input_bytes: int) -> int:
    """Return a bounded per-attempt timeout in seconds.

    1. If ``BIJI_ARCHIVE_TIMEOUT_SECONDS`` is set to a positive integer
       ≤ 86 400, use it verbatim (operator override).
    2. Otherwise compute ``max(300, input_bytes / 10 MiB/s)`` clamped to
       [300, 14 400].

    Invalid or out-of-range env values trigger a sanitised warning and
    a safe fallback to the computed value.
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
            env_val = 0
        if 0 < env_val <= _MAX_ENV_TIMEOUT:
            return env_val
        if env_val != 0:
            _logger.warning(
                "%s=%d 超出允许范围，已回退到默认计算。"
                "允许范围：1–%d 秒。",
                _ENV_KEY, env_val, _MAX_ENV_TIMEOUT,
            )

    size_based = max(
        _DEFAULT_TIMEOUT_SECONDS,
        int(input_bytes / _MIN_THROUGHPUT_BYTES_PER_SEC),
    )
    return min(size_based, _MAX_COMPUTED_TIMEOUT)


def timeout_bounds() -> tuple[int, int, int]:
    """Return (default_min, computed_max, env_override_max) in seconds."""
    return (_DEFAULT_TIMEOUT_SECONDS, _MAX_COMPUTED_TIMEOUT, _MAX_ENV_TIMEOUT)


def kill_process_tree(pid: int) -> None:
    """Best-effort tree kill on Windows as a last resort."""
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True, timeout=15, shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass
