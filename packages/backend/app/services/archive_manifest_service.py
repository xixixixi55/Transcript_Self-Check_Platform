"""Build and revalidate immutable public ArchiveManifest data."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..repository.archive_hash_repository import compute_md5_streaming
from ..repository.archive_validator_repository import ArchiveValidationResult
from ..repository.winrar_discovery_repository import WinRarCapability
from .disc_sequence_service import (
    generate_disc_numbers,
    parse_disc_sequence,
    validate_disc_mapping,
)
from .archive_staging_security_service import OWNERSHIP_MARKER_NAME
from .archive_manifest_output_security_service import (
    assert_safe_output_file as _assert_safe_output_file,
    compute_disc_capacity,
    is_safe_output_file as _is_safe_output_file,
)

ArchiveFileIdentity = tuple[int, int, int, int, int]


def capture_archive_file_identities(
    root: Path, filenames: set[str],
) -> dict[str, ArchiveFileIdentity]:
    """Capture path-independent identities for already hashed, sealed parts."""

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
    else:  # REQ-030: empty first disc keeps part disc metadata empty until mapped
        disc_date = ""
        actual_disc_numbers = [""] * len(validation.parts)
    public_parts: list[dict[str, object]] = []
    internal_paths: dict[str, Path] = {}
    total_archive_bytes = 0
    for part, disc_number in zip(validation.parts, actual_disc_numbers, strict=True):
        md5 = (
            verified_md5s.get(part.filename)
            if verified_md5s is not None
            else compute_md5_streaming(part.path, validation.parts[0].path.parent)
        )
        if not isinstance(md5, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", md5):
            raise ValueError("ARCHIVE_PARTS_INVALID")
        disc_capacity = compute_disc_capacity(part.size_bytes)
        public_parts.append({
            "part_id": str(uuid4()),
            "part_number": part.part_number,
            "filename": part.filename,
            "size_bytes": part.size_bytes,
            "md5": md5,
            "disc_number": disc_number,
            "disc_date": disc_date,
            "disc_capacity_bytes": disc_capacity,
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


def validate_published_manifest(record, *, verified_md5s: dict[str, str] | None = None) -> bool:
    """Re-check the same-run files before DOCX generation or retry."""

    root = Path(record.final_dir).resolve(strict=False)
    if not root.is_dir():
        return False
    manifest = record.public_manifest
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
        if isinstance(volume_size, int) and (size > volume_size or volume_size <= 0):
            return False
        # Disc capacity must be the smallest tier ≥ actual size
        try:
            expected_cap = compute_disc_capacity(size)
        except ValueError:
            return False
        if "disc_capacity_bytes" not in item:
            # Old manifest — key absent, derive from trusted size_bytes
            actual_cap = expected_cap
        else:
            actual_cap = item["disc_capacity_bytes"]
            if (not isinstance(actual_cap, int) or isinstance(actual_cap, bool)
                    or actual_cap <= 0):
                return False
        if actual_cap != expected_cap:
            return False
        # volume_size_bytes invariant: if present on both part and manifest, must match
        part_vol = item.get("volume_size_bytes")
        if isinstance(part_vol, int) and not isinstance(part_vol, bool) and isinstance(volume_size, int) and not isinstance(volume_size, bool):
            if part_vol != volume_size:
                return False
        md5 = verified_md5s.get(filename) if verified_md5s is not None else compute_md5_streaming(path, root)
        if md5 != item.get("md5"):
            return False
        actual_total += size
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
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
    """Return a stable integrity error code for the published manifest files."""
    manifest = record.public_manifest
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
        if "disc_capacity_bytes" not in item:
            # Old manifest — key absent, derive from trusted size_bytes
            try:
                disc_cap = compute_disc_capacity(size_bytes)
            except ValueError:
                return "ARCHIVE_MANIFEST_INVALID"
        else:
            disc_cap = item["disc_capacity_bytes"]
            if (not isinstance(disc_cap, int) or isinstance(disc_cap, bool)
                    or disc_cap <= 0):
                return "ARCHIVE_MANIFEST_INVALID"
        try:
            expected_cap = compute_disc_capacity(size_bytes)
        except ValueError:
            return "ARCHIVE_MANIFEST_INVALID"
        if disc_cap != expected_cap:
            return "ARCHIVE_MANIFEST_INVALID"
        # volume_size_bytes invariant: if present on part, must match manifest level
        part_volume = item.get("volume_size_bytes")
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
    """Validate authenticated Manifest identity and physical metadata without content I/O.

    Callers must first authenticate the Manifest and its MD5 values against the
    durable publication digest.  Formal download/export/reuse paths continue to
    call ``validate_manifest_files`` without trusted hashes.
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
