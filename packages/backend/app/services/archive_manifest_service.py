"""Build and revalidate immutable public ArchiveManifest data."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..repository.archive_hash_repository import compute_md5_streaming
from ..repository.archive_validator_repository import ArchiveValidationResult
from ..repository.winrar_discovery_repository import WinRarCapability
from .disc_sequence_service import generate_disc_numbers


def _disc_date(first_disc_number: str) -> str:
    return f"{first_disc_number[2:6]}-{first_disc_number[6:8]}-{first_disc_number[8:10]}"


def assemble_archive_manifest(
    plan,
    validation: ArchiveValidationResult,
    capability: WinRarCapability,
    *,
    retry_count: int,
) -> tuple[dict[str, object], dict[str, Path]]:
    if not validation.valid or not validation.parts:
        raise ValueError("ARCHIVE_PARTS_INVALID")
    if not plan.first_disc_number:
        raise ValueError("FIRST_DISC_NUMBER_INVALID")
    manifest_id = str(uuid4())
    disc_date = _disc_date(plan.first_disc_number)
    actual_disc_numbers = generate_disc_numbers(plan.first_disc_number, len(validation.parts))
    public_parts: list[dict[str, object]] = []
    internal_paths: dict[str, Path] = {}
    total_archive_bytes = 0
    for part, disc_number in zip(validation.parts, actual_disc_numbers, strict=True):
        md5 = compute_md5_streaming(part.path, validation.parts[0].path.parent)
        public_parts.append({
            "part_id": str(uuid4()),
            "part_number": part.part_number,
            "filename": part.filename,
            "size_bytes": part.size_bytes,
            "md5": md5,
            "disc_number": disc_number,
            "disc_date": disc_date,
            "volume_size_bytes": plan.volume_size_bytes,
            "continuity_check": "passed",
        })
        internal_paths[part.filename] = part.path
        total_archive_bytes += part.size_bytes
    manifest = {
        "manifest_id": manifest_id,
        "plan_id": plan.plan_id,
        "archive_base_name": plan.archive_base_name,
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


def validate_published_manifest(record) -> bool:
    """Re-check the same-run files before DOCX generation or retry."""

    root = Path(record.final_dir).resolve(strict=False)
    if not root.is_dir():
        return False
    manifest = record.public_manifest
    parts = manifest.get("parts")
    if not isinstance(parts, list):
        return False
    filenames: set[str] = set()
    numbers: list[int] = []
    base_name = manifest.get("archive_base_name")
    volume_size = manifest.get("volume_size_bytes")
    max_part_count = manifest.get("max_part_count")
    actual_total = 0
    for item in parts:
        if not isinstance(item, dict):
            return False
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
        if isinstance(base_name, str) and not re.fullmatch(
            rf"{re.escape(base_name)}\.part{number}\.rar", filename,
        ):
            return False
        path = (root / filename).resolve(strict=False)
        try:
            path.relative_to(root)
            size = path.stat().st_size
        except (OSError, ValueError):
            return False
        if size != item.get("size_bytes") or size <= 0:
            return False
        if isinstance(volume_size, int) and (size > volume_size or volume_size <= 0):
            return False
        if compute_md5_streaming(path, root) != item.get("md5"):
            return False
        actual_total += size
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        return False
    if isinstance(max_part_count, int) and len(parts) > max_part_count:
        return False
    archive_names = {
        entry.name for entry in root.iterdir()
        if entry.is_file() and (
            entry.suffix.casefold() == ".rar"
            or re.search(r"\.r\d+$", entry.name, re.IGNORECASE)
        )
    }
    if archive_names != filenames:
        return False
    return actual_total == manifest.get("actual_archive_bytes")
