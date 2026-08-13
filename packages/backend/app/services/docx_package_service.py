"""Safe DOCX package inspection and container-independent fingerprints."""

from __future__ import annotations

import hashlib
import re
import struct
import zipfile
from pathlib import Path

OOXML_PACKAGE_FINGERPRINT_ALGORITHM = "ooxml-package-sha256-v1"
_FINGERPRINT_MARKER = b"BIJI-OOXML-PACKAGE-FINGERPRINT-V1"
_MAX_U64 = (1 << 64) - 1


class DocxPackageError(ValueError):
    """Raised when a DOCX ZIP package is not safe to inspect."""

    code = "TEMPLATE_PACKAGE_INVALID"


def compute_ooxml_package_fingerprint(path: str | Path) -> str:
    """Hash sorted ZIP entry names and uncompressed bytes, ignoring ZIP metadata."""
    entries = _read_validated_entries(path)
    digest = hashlib.sha256()
    _update_frame(digest, _FINGERPRINT_MARKER)
    for name, content in entries:
        name_bytes = name.encode("utf-8")
        _update_length(digest, len(name_bytes))
        digest.update(name_bytes)
        _update_length(digest, len(content))
        digest.update(content)
    return digest.hexdigest().upper()


def read_validated_docx_entries(path: str | Path) -> list[tuple[str, bytes]]:
    """Read a DOCX after enforcing the same ZIP entry safety contract as hashing."""
    return _read_validated_entries(path)


def raw_docx_sha256(path: str | Path) -> str:
    """Return the raw DOCX hash for diagnostics only."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_validated_entries(path: str | Path) -> list[tuple[str, bytes]]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names: set[str] = set()
            folded_names: set[str] = set()
            entries: list[tuple[str, bytes]] = []
            for info in archive.infolist():
                entry_name = info.filename[:-1] if info.is_dir() and info.filename.endswith("/") else info.filename
                _validate_entry_name(entry_name, names, folded_names)
                if info.is_dir():
                    continue
                if info.flag_bits & 0x1:
                    raise DocxPackageError("DOCX package encryption is not supported")
                if _is_symlink(info):
                    raise DocxPackageError("DOCX package symbolic links are not supported")
                content = archive.read(info)
                if len(content) > _MAX_U64:
                    raise DocxPackageError("DOCX package entry is too large")
                entries.append((info.filename, content))
            return sorted(entries, key=lambda item: item[0])
    except DocxPackageError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise DocxPackageError("DOCX package is not a valid ZIP archive") from exc


def _validate_entry_name(name: str, names: set[str], folded_names: set[str]) -> None:
    if not name or "\x00" in name or "\\" in name:
        raise DocxPackageError("DOCX package contains an invalid entry name")
    if name.startswith("/") or name.startswith("//"):
        raise DocxPackageError("DOCX package contains an absolute entry name")
    if re.match(r"^[A-Za-z]:($|/)", name) or name.startswith("//?/"):
        raise DocxPackageError("DOCX package contains a device entry name")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise DocxPackageError("DOCX package contains a path traversal entry")
    if name in names or name.casefold() in folded_names:
        raise DocxPackageError("DOCX package contains duplicate entry names")
    names.add(name)
    folded_names.add(name.casefold())


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return (mode & 0o170000) == 0o120000


def _update_frame(digest: hashlib._Hash, value: bytes) -> None:
    _update_length(digest, len(value))
    digest.update(value)


def _update_length(digest: hashlib._Hash, value: int) -> None:
    digest.update(struct.pack(">Q", value))
