"""Validate attachment-two images and calculate deterministic contain geometry."""

from __future__ import annotations

from dataclasses import dataclass
import io
import struct
import zlib
from pathlib import Path, PureWindowsPath
from typing import Sequence

from docx.image.image import Image

EMU_PER_INCH = 914400
DEFAULT_DISPLAY_DPI = 96
ATTACHMENT2_SLOT_WIDTH_EMU = 2_030_400
ATTACHMENT2_SLOT_HEIGHT_EMU = 2_707_200
SUPPORTED_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


class Attachment2ImageError(ValueError):
    """Stable, path-free error for an image that cannot be rendered."""

    code = "ATTACHMENT2_IMAGE_INVALID"
    safe_message = "附件图片无法读取、解码或格式不受支持。"


@dataclass(frozen=True)
class Attachment2PhotoAsset:
    source_image_id: str
    safe_display_name: str
    path: str
    width_px: int
    height_px: int
    horz_dpi: int
    vert_dpi: int
    orientation: int = 1


@dataclass(frozen=True)
class Attachment2ImageGeometry:
    render_width_emu: int
    render_height_emu: int
    offset_x_emu: int
    offset_y_emu: int


def validate_attachment2_photos(
    photo_paths: Sequence[str], source_image_ids: Sequence[str] = (),
) -> tuple[Attachment2PhotoAsset, ...]:
    """Decode every uploaded image while retaining paths only in backend runtime state."""
    assets: list[Attachment2PhotoAsset] = []
    used_ids: set[str] = set()
    for sequence_number, raw_path in enumerate(photo_paths, 1):
        try:
            path = Path(raw_path)
            if not path.is_file() or path.stat().st_size <= 0:
                raise Attachment2ImageError
            if path.suffix.casefold() not in SUPPORTED_IMAGE_SUFFIXES:
                raise Attachment2ImageError
            with path.open("rb") as handle:
                blob = handle.read()
            _validate_image_blob(blob, path.suffix.casefold())
            image = Image.from_file(io.BytesIO(blob))
            width, height = int(image.px_width), int(image.px_height)
            orientation = _jpeg_orientation(blob) if path.suffix.casefold() in {".jpg", ".jpeg"} else 1
            if orientation in {5, 6, 7, 8}:
                width, height = height, width
            horz_dpi = _positive_dpi(getattr(image, "horz_dpi", 0))
            vert_dpi = _positive_dpi(getattr(image, "vert_dpi", 0))
        except Exception as error:
            raise Attachment2ImageError from error
        if width <= 0 or height <= 0:
            raise Attachment2ImageError
        candidate = _safe_source_id(
            source_image_ids[sequence_number - 1]
            if sequence_number <= len(source_image_ids) else "",
            sequence_number,
        )
        if candidate in used_ids:
            candidate = f"{candidate}-{sequence_number}"
        used_ids.add(candidate)
        assets.append(Attachment2PhotoAsset(
            candidate, _safe_display_name(path.name, sequence_number), str(path),
            width, height, horz_dpi, vert_dpi, orientation,
        ))
    return tuple(assets)


def calculate_contain_geometry(
    width_px: int,
    height_px: int,
    *,
    slot_width_emu: int = ATTACHMENT2_SLOT_WIDTH_EMU,
    slot_height_emu: int = ATTACHMENT2_SLOT_HEIGHT_EMU,
    display_dpi: int = DEFAULT_DISPLAY_DPI,
) -> Attachment2ImageGeometry:
    """Fit by pixel aspect ratio, cap at the slot, and never upscale a small image."""
    if width_px <= 0 or height_px <= 0 or display_dpi <= 0:
        raise ValueError("image dimensions must be positive")
    natural_width = width_px * EMU_PER_INCH / display_dpi
    natural_height = height_px * EMU_PER_INCH / display_dpi
    scale = min(slot_width_emu / natural_width, slot_height_emu / natural_height, 1.0)
    render_width = max(1, round(natural_width * scale))
    render_height = max(1, round(natural_height * scale))
    return Attachment2ImageGeometry(
        render_width, render_height,
        (slot_width_emu - render_width) // 2,
        (slot_height_emu - render_height) // 2,
    )


def _positive_dpi(value: object) -> int:
    try:
        dpi = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DISPLAY_DPI
    return dpi if dpi > 0 else DEFAULT_DISPLAY_DPI


def _jpeg_orientation(blob: bytes) -> int:
    if not blob.startswith(b"\xff\xd8"):
        return 1
    position = 2
    while position + 4 <= len(blob) and blob[position] == 0xFF:
        marker = blob[position + 1]
        if marker in {0xD8, 0xD9}:
            break
        segment_length = struct.unpack_from(">H", blob, position + 2)[0]
        segment_start = position + 4
        segment_end = position + 2 + segment_length
        segment = blob[segment_start:segment_end]
        if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
            return _tiff_orientation(segment[6:])
        position = segment_end
    return 1


def _validate_image_blob(blob: bytes, suffix: str) -> None:
    if suffix == ".png":
        _validate_png(blob)
        return
    if not blob.startswith(b"\xff\xd8") or b"\xff\xd9" not in blob[2:]:
        raise Attachment2ImageError


def _validate_png(blob: bytes) -> None:
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        raise Attachment2ImageError
    position = 8
    saw_header = False
    saw_data = False
    compressed = bytearray()
    while position + 12 <= len(blob):
        length = struct.unpack_from(">I", blob, position)[0]
        start = position + 8
        end = start + length
        if end + 4 > len(blob):
            raise Attachment2ImageError
        chunk_type = blob[position + 4:position + 8]
        data = blob[start:end]
        crc = struct.unpack_from(">I", blob, end)[0]
        if zlib.crc32(chunk_type + data) & 0xffffffff != crc:
            raise Attachment2ImageError
        if chunk_type == b"IHDR":
            saw_header = len(data) == 13
        elif chunk_type == b"IDAT":
            saw_data = True
            compressed.extend(data)
        elif chunk_type == b"IEND":
            if not saw_header or not saw_data or end + 4 != len(blob):
                raise Attachment2ImageError
            try:
                zlib.decompress(bytes(compressed))
            except zlib.error as error:
                raise Attachment2ImageError from error
            return
        position = end + 4
    raise Attachment2ImageError


def _tiff_orientation(tiff: bytes) -> int:
    if len(tiff) < 8 or tiff[:2] not in {b"II", b"MM"}:
        return 1
    endian = "<" if tiff[:2] == b"II" else ">"
    if struct.unpack_from(endian + "H", tiff, 2)[0] != 42:
        return 1
    ifd_offset = struct.unpack_from(endian + "I", tiff, 4)[0]
    if ifd_offset + 2 > len(tiff):
        return 1
    entry_count = struct.unpack_from(endian + "H", tiff, ifd_offset)[0]
    for index in range(entry_count):
        entry = ifd_offset + 2 + index * 12
        if entry + 12 > len(tiff):
            return 1
        tag, field_type, count = struct.unpack_from(endian + "HHI", tiff, entry)
        if tag != 0x0112 or field_type != 3 or count < 1:
            continue
        value = struct.unpack_from(endian + "H", tiff, entry + 8)[0]
        return value if value in range(1, 9) else 1
    return 1


def _safe_source_id(value: object, sequence_number: int) -> str:
    candidate = "" if value is None else str(value).strip()
    if not candidate or "/" in candidate or "\\" in candidate or ":" in candidate:
        return f"photo-{sequence_number}"
    return candidate[:96]


def _safe_display_name(value: str, sequence_number: int) -> str:
    name = PureWindowsPath(value.replace("/", "\\")).name
    safe = "".join(char if char.isprintable() and char not in '<>:/\\|?*' else "_" for char in name)
    return safe[:160] or f"photo-{sequence_number}.image"


__all__ = [
    "ATTACHMENT2_SLOT_HEIGHT_EMU", "ATTACHMENT2_SLOT_WIDTH_EMU",
    "Attachment2ImageError", "Attachment2ImageGeometry", "Attachment2PhotoAsset",
    "calculate_contain_geometry", "validate_attachment2_photos",
]
