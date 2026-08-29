"""构建并重新验证不可变的公开 ArchiveManifest 数据。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ...repository.archive_hash_repository import compute_md5_streaming
from ...repository.hash_algorithm_repository import manifest_part_business_hash, normalize_hash_algorithm
from ...repository.archive_validator_repository import ArchiveValidationResult
from ...repository.winrar_discovery_repository import WinRarCapability
from ..disc_sequence_service import generate_disc_numbers, parse_disc_sequence, validate_disc_mapping
from .archive_staging_security_service import OWNERSHIP_MARKER_NAME
from ..hash_algorithm_service import archive_business_hash
from .archive_manifest_output_security_service import (
    assert_safe_output_file as _assert_safe_output_file, compute_disc_capacity,
    compute_manifest_disc_capacity as _expected_disc_capacity,
    is_safe_output_file as _is_safe_output_file,
)

ArchiveFileIdentity = tuple[int, int, int, int, int]
_STANDARD_SPLIT_MODE = "standard_split"
_OVERSIZED_SINGLE_VOLUME_MODE = "oversized_single_volume"
def _manifest_mode(manifest: dict) -> str:
    mode = manifest.get("archive_mode")
    return "legacy_standard_split" if mode is None else str(mode)

def capture_archive_file_identities(
    root: Path, filenames: set[str],
) -> dict[str, ArchiveFileIdentity]:
    """为已计算哈希并密封的分卷捕获与路径无关的标识。"""

    resolved_root = root.resolve(strict=False)
    identities: dict[str, ArchiveFileIdentity] = {}
    for filename in filenames:
        path = (resolved_root / filename).resolve(strict=False)
        path.relative_to(resolved_root)
        _assert_safe_output_file(path)
        stat = path.stat()
        identities[filename] = (
            stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns,
            stat.st_dev, stat.st_ino,
        )
    return identities


def archive_file_identities_match(
    root: Path, expected: dict[str, ArchiveFileIdentity],
) -> bool:
    try:
        return capture_archive_file_identities(root, set(expected)) == expected
    except (OSError, ValueError):
        return False


def assemble_archive_manifest(
    plan,
    validation: ArchiveValidationResult,
    capability: WinRarCapability,
    *,
    retry_count: int,
    verified_md5s: dict[str, str] | None = None,
    business_hash_algorithm: str = "md5",
    verified_business_hashes: dict[str, str] | None = None,
) -> tuple[dict[str, object], dict[str, Path]]:
    if not validation.valid or not validation.parts:
        raise ValueError("ARCHIVE_PARTS_INVALID")
    manifest_id = str(uuid4())
    first_disc_number = plan.first_disc_number
    if first_disc_number:
        parsed_disc = parse_disc_sequence(first_disc_number)
        if not parsed_disc.valid or parsed_disc.sequence is None:
            raise ValueError(parsed_disc.error_code or "FIRST_DISC_NUMBER_INVALID")
        sequence = parsed_disc.sequence
        disc_date = sequence.date
        actual_disc_numbers = generate_disc_numbers(sequence, len(validation.parts))
    else:  # REQ-030：首张光盘为空时，分卷光盘元数据在映射前保持为空
        disc_date = ""
        actual_disc_numbers = [""] * len(validation.parts)
    archive_mode = getattr(plan, "archive_mode", _STANDARD_SPLIT_MODE)
    if archive_mode not in {_STANDARD_SPLIT_MODE, _OVERSIZED_SINGLE_VOLUME_MODE}:
        raise ValueError("ARCHIVE_PLAN_INVALID")
    public_parts: list[dict[str, object]] = []
    internal_paths: dict[str, Path] = {}
    total_archive_bytes = 0
    try:
        business_algorithm = normalize_hash_algorithm(business_hash_algorithm)
    except ValueError as error:
        raise ValueError("ARCHIVE_HASH_ALGORITHM_INVALID") from error
    for part, disc_number in zip(validation.parts, actual_disc_numbers, strict=True):
        md5 = (
            verified_md5s.get(part.filename)
            if verified_md5s is not None
            else compute_md5_streaming(part.path, validation.parts[0].path.parent)
        )
        if not isinstance(md5, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", md5):
            raise ValueError("ARCHIVE_PARTS_INVALID")
        business_hash = archive_business_hash(
            part.path, validation.parts[0].path.parent, business_algorithm,
            md5, verified_business_hashes,
        )
        disc_capacity = _expected_disc_capacity(part.size_bytes, archive_mode)
        public_part = {
            "part_id": str(uuid4()),
            "part_number": part.part_number,
            "filename": part.filename,
            "size_bytes": part.size_bytes,
            "md5": md5,
            "hash_algorithm": business_algorithm,
            "hash_value": business_hash,
            "disc_number": disc_number,
            "disc_date": disc_date,
            "volume_size_bytes": plan.volume_size_bytes,
            "continuity_check": "passed",
        }
        if disc_capacity is not None:
            public_part["disc_capacity_bytes"] = disc_capacity
        public_parts.append(public_part)
        internal_paths[part.filename] = part.path
        total_archive_bytes += part.size_bytes
    manifest = {
        "manifest_id": manifest_id,
        "plan_id": plan.plan_id,
        "archive_base_name": plan.archive_base_name,
        "archive_mode": archive_mode,
        "volume_size_bytes": plan.volume_size_bytes,
        "volume_tier_gb": plan.volume_tier_gb,
        "max_part_count": plan.max_part_count,
        "total_input_bytes": plan.total_input_bytes,
        "actual_archive_bytes": total_archive_bytes,
        "retry_count": retry_count,
        "parts": public_parts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "winrar_capability": capability.public_dict(),
        "validation_status": "validated",
        "continuity_check": "passed",
    }
    return manifest, internal_paths


def validate_published_manifest(record, *, verified_md5s: dict[str, str] | None = None) -> bool:
    """在生成 DOCX 或重试前重新检查同次运行的文件。"""

    root = Path(record.final_dir).resolve(strict=False)
    if not root.is_dir():
        return False
    manifest = record.public_manifest
    mode = _manifest_mode(manifest)
    if mode not in {
        "legacy_standard_split", _STANDARD_SPLIT_MODE,
        _OVERSIZED_SINGLE_VOLUME_MODE,
    }:
        return False
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        return False
    filenames: set[str] = set()
    numbers: list[int] = []
    disc_metadata: list[tuple[str, str]] = []
    base_name = manifest.get("archive_base_name")
    volume_size = manifest.get("volume_size_bytes")
    max_part_count = manifest.get("max_part_count")
    actual_total = 0
    for item in parts:
        if not isinstance(item, dict):
            return False
        try:
            manifest_part_business_hash(item)
        except ValueError:
            return False
        disc_number = item.get("disc_number")
        disc_date = item.get("disc_date")
        if disc_number is not None or disc_date is not None:
            if not isinstance(disc_number, str) or not isinstance(disc_date, str):
                return False
            disc_metadata.append((disc_number, disc_date))
        filename = item.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            return False
        if filename in filenames:
            return False
        filenames.add(filename)
        number = item.get("part_number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            return False
        numbers.append(number)
        if isinstance(base_name, str):
            expected_names = (
                {f"{base_name}.rar", f"{base_name}.part1.rar"}
                if len(parts) == 1 and number == 1
                else {f"{base_name}.part{number}.rar"}
            )
            if filename not in expected_names:
                return False
        path = (root / filename).resolve(strict=False)
        try:
            path.relative_to(root)
            if not path.exists():
                return False
            _assert_safe_output_file(path)
            size = path.stat().st_size
        except (OSError, ValueError):
            return False
        if size != item.get("size_bytes") or size <= 0:
            return False
        if mode == _OVERSIZED_SINGLE_VOLUME_MODE:
            if volume_size is not None:
                return False
        elif mode == _STANDARD_SPLIT_MODE and (
            not isinstance(volume_size, int) or size > volume_size or volume_size <= 0
        ):
            return False
        elif (mode == "legacy_standard_split" and isinstance(volume_size, int)
              and (size > volume_size or volume_size <= 0)):
            return False
        # 光盘容量必须是大于等于实际大小的最小档位
        try:
            expected_cap = _expected_disc_capacity(size, mode)
        except ValueError:
            return False
        if mode == _OVERSIZED_SINGLE_VOLUME_MODE:
            if item.get("disc_capacity_bytes") is not None:
                return False
            actual_cap = None
        elif "disc_capacity_bytes" not in item:
            # 旧版 manifest — 键缺失，根据可信的 size_bytes 推导
            actual_cap = expected_cap
        else:
            actual_cap = item["disc_capacity_bytes"]
            if (not isinstance(actual_cap, int) or isinstance(actual_cap, bool)
                    or actual_cap <= 0):
                return False
        if actual_cap != expected_cap:
            return False
        # volume_size_bytes 不变量：若分卷和 manifest 中均存在，则必须一致
        part_vol = item.get("volume_size_bytes")
        if mode == _OVERSIZED_SINGLE_VOLUME_MODE and part_vol is not None:
            return False
        if isinstance(part_vol, int) and not isinstance(part_vol, bool) and isinstance(volume_size, int) and not isinstance(volume_size, bool):
            if part_vol != volume_size:
                return False
        md5 = verified_md5s.get(filename) if verified_md5s is not None else compute_md5_streaming(path, root)
        if md5 != item.get("md5"):
            return False
        actual_total += size
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        return False
    if mode == _OVERSIZED_SINGLE_VOLUME_MODE and (
        len(parts) != 1
        or not isinstance(base_name, str)
        or parts[0].get("filename") != f"{base_name}.rar"
        or max_part_count != 1
    ):
        return False
    if not validate_disc_mapping(numbers, disc_metadata):
        return False
    if isinstance(max_part_count, int) and len(parts) > max_part_count:
        return False
    if verified_md5s is not None and set(verified_md5s) != filenames:
        return False
    entries = [entry for entry in root.iterdir() if entry.name != OWNERSHIP_MARKER_NAME]
    if any(not _is_safe_output_file(entry) for entry in entries):
        return False
    if {entry.name for entry in entries} != filenames:
        return False
    return actual_total == manifest.get("actual_archive_bytes")


def validate_manifest_files(
    record, *, verified_md5s: dict[str, str] | None = None,
    verified_file_identities: dict[str, ArchiveFileIdentity] | None = None,
) -> str | None:
    """为已发布的 Manifest 文件返回稳定的完整性错误码。"""
    manifest = record.public_manifest
    mode = _manifest_mode(manifest)
    if mode not in {
        "legacy_standard_split", _STANDARD_SPLIT_MODE,
        _OVERSIZED_SINGLE_VOLUME_MODE,
    }:
        return "ARCHIVE_MANIFEST_INVALID"
    if manifest.get("manifest_id") != record.manifest_id or manifest.get("validation_status") != "validated":
        return "ARCHIVE_MANIFEST_INVALID"
    parts = manifest.get("parts")
    root = Path(record.final_dir).resolve(strict=False)
    if not isinstance(parts, list) or not parts or not root.is_dir():
        return "ARCHIVE_MANIFEST_PART_MISSING"
    observed_md5s: dict[str, str] = {}
    for item in parts:
        if not isinstance(item, dict):
            return "ARCHIVE_MANIFEST_INVALID"
        filename = item.get("filename")
        md5 = item.get("md5")
        size_bytes = item.get("size_bytes")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not isinstance(md5, str)
            or not re.fullmatch(r"[0-9a-fA-F]{32}", md5)
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes <= 0
            or not isinstance(item.get("disc_number"), str)
            or not isinstance(item.get("disc_date"), str)
            or (bool(item.get("disc_number")) != bool(item.get("disc_date")))
        ):
            return "ARCHIVE_MANIFEST_INVALID"
        if mode == _OVERSIZED_SINGLE_VOLUME_MODE:
            if item.get("disc_capacity_bytes") is not None:
                return "ARCHIVE_MANIFEST_INVALID"
            disc_cap = None
        elif "disc_capacity_bytes" not in item:
            # 旧版 manifest — 键缺失，根据可信的 size_bytes 推导
            try:
                disc_cap = _expected_disc_capacity(size_bytes, mode)
            except ValueError:
                return "ARCHIVE_MANIFEST_INVALID"
        else:
            disc_cap = item["disc_capacity_bytes"]
            if (not isinstance(disc_cap, int) or isinstance(disc_cap, bool)
                    or disc_cap <= 0):
                return "ARCHIVE_MANIFEST_INVALID"
        try:
            expected_cap = _expected_disc_capacity(size_bytes, mode)
        except ValueError:
            return "ARCHIVE_MANIFEST_INVALID"
        if disc_cap != expected_cap:
            return "ARCHIVE_MANIFEST_INVALID"
        # volume_size_bytes 不变量：若分卷中存在，则必须与 manifest 层级一致
        part_volume = item.get("volume_size_bytes")
        if mode == _OVERSIZED_SINGLE_VOLUME_MODE and part_volume is not None:
            return "ARCHIVE_MANIFEST_INVALID"
        if isinstance(part_volume, int) and not isinstance(part_volume, bool):
            manifest_vol = manifest.get("volume_size_bytes")
            if isinstance(manifest_vol, int) and not isinstance(manifest_vol, bool):
                if part_volume != manifest_vol:
                    return "ARCHIVE_MANIFEST_INVALID"
        path = (root / filename).resolve(strict=False)
        try:
            path.relative_to(root)
            if not path.exists():
                return "ARCHIVE_MANIFEST_PART_MISSING"
            _assert_safe_output_file(path)
        except ValueError:
            return "ARCHIVE_MANIFEST_INVALID"
        except OSError:
            return "ARCHIVE_MANIFEST_PART_CHANGED"
        try:
            size = path.stat().st_size
        except OSError:
            return "ARCHIVE_MANIFEST_PART_MISSING"
        if size != size_bytes:
            return "ARCHIVE_MANIFEST_PART_CHANGED"
        observed_md5s[filename] = (
            verified_md5s.get(filename)
            if verified_md5s is not None
            else compute_md5_streaming(path, root)
        )
        if observed_md5s[filename] != md5:
            return "ARCHIVE_MANIFEST_PART_CHANGED"
    if verified_md5s is not None and set(verified_md5s) != set(observed_md5s):
        return "ARCHIVE_MANIFEST_INVALID"
    if verified_file_identities is not None and (
        set(verified_file_identities) != set(observed_md5s)
        or not archive_file_identities_match(root, verified_file_identities)
    ):
        return "ARCHIVE_MANIFEST_PART_CHANGED"
    return None if validate_published_manifest(
        record, verified_md5s=observed_md5s,
    ) else "ARCHIVE_MANIFEST_INVALID"


def validate_manifest_metadata(record) -> str | None:
    """验证已认证的 Manifest 标识和物理元数据，不执行内容 I/O。

    调用方必须先根据持久发布摘要认证 Manifest 及其 MD5 值。正式下载、导出和复用
    路径仍在不提供可信哈希的情况下调用 `validate_manifest_files`。
    """

    parts = record.public_manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        return "ARCHIVE_MANIFEST_INVALID"
    trusted_md5s: dict[str, str] = {}
    for item in parts:
        if not isinstance(item, dict):
            return "ARCHIVE_MANIFEST_INVALID"
        filename = item.get("filename")
        md5 = item.get("md5")
        if (
            not isinstance(filename, str)
            or filename in trusted_md5s
            or not isinstance(md5, str)
            or not re.fullmatch(r"[0-9a-fA-F]{32}", md5)
        ):
            return "ARCHIVE_MANIFEST_INVALID"
        trusted_md5s[filename] = md5
    return validate_manifest_files(record, verified_md5s=trusted_md5s)
