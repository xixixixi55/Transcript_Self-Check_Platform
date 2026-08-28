"""所有权标记和保守的暂存清理原语。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

OWNERSHIP_MARKER_NAME = ".workbench-staging-owner.json"


def controlled_staging_root_id(staging_root: Path, deployment_id: str) -> str:
    value = f"{deployment_id}\0{staging_root.resolve(strict=False)}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def write_ownership_marker(
    staging_dir: Path, attempt_id: str, deployment_id: str, staging_root_id: str,
    task_id: str | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    payload = {
        "marker_version": 1,
        "attempt_id": attempt_id,
        "deployment_instance_id": deployment_id,
        "staging_root_id": staging_root_id,
        "marker_token": token,
    }
    if task_id is not None:
        payload["task_id"] = task_id
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=staging_dir, prefix=".owner-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, separators=(",", ":"), ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, staging_dir / OWNERSHIP_MARKER_NAME)
    except (OSError, TypeError, ValueError):
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)
        raise
    return token


def remove_ownership_marker(staging_dir: Path) -> None:
    marker = staging_dir / OWNERSHIP_MARKER_NAME
    try:
        marker.chmod(stat.S_IRUSR | stat.S_IWUSR)
        staging_dir.chmod(
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
            | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IXOTH
        )
    except OSError:
        pass
    try:
        marker.unlink()
    except PermissionError:
        # 并发的合法发布者可能已删除标记，随后恢复目录只读状态。
        # 重试前再次检查，使调用方可将这一特定竞争视为幂等成功。
        if not marker.exists():
            raise FileNotFoundError(marker)
        marker.chmod(stat.S_IRUSR | stat.S_IWUSR)
        staging_dir.chmod(
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
            | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH
        )
        marker.unlink()


def cleanup_owned_staging(
    record: dict[str, Any], staging_root: Path, deployment_id: str,
) -> str:
    locator = record.get("staging_locator")
    if not isinstance(locator, str) or not locator:
        return "not_required"
    candidate = Path(locator)
    root = staging_root.resolve(strict=False)
    expected_root_id = controlled_staging_root_id(staging_root, deployment_id)
    if record.get("staging_root_id") != expected_root_id:
        return "unknown"
    try:
        resolved = candidate.resolve(strict=True)
        if resolved == root or resolved.parent != root:
            return "unknown"
    except FileNotFoundError:
        return "succeeded" if not candidate.exists() and record.get("cleanup_status") == "succeeded" else "unknown"
    except (OSError, RuntimeError, ValueError, TypeError):
        return "unknown"
    try:
        marker = _read_marker(resolved / OWNERSHIP_MARKER_NAME)
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        return "unknown"
    expected = {
        "marker_version": 1,
        "attempt_id": record.get("attempt_id"),
        "deployment_instance_id": deployment_id,
        "staging_root_id": record.get("staging_root_id"),
        "marker_token": record.get("ownership_marker_token"),
    }
    if record.get("task_id") is not None:
        expected["task_id"] = record.get("task_id")
    if marker != expected or _process_is_active(record.get("process_pid")):
        return "unknown"
    try:
        shutil.rmtree(resolved)
    except OSError:
        return "failed"
    return "succeeded"


def _read_marker(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("invalid ownership marker")
    return value


def _process_is_active(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
