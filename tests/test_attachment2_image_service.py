"""Precise attachment-two image validation and contain geometry tests."""

import os
import base64
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.attachment2_image_service import (  # noqa: E402
    ATTACHMENT2_SLOT_HEIGHT_EMU,
    ATTACHMENT2_SLOT_WIDTH_EMU,
    Attachment2ImageError,
    calculate_contain_geometry,
    validate_attachment2_photos,
)

MINIMAL_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AX//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AX//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8Qf//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8Qf//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8Qf//Z"
)


def png_bytes(width: int, height: int) -> bytes:
    rows = b"".join(b"\x00" + b"\x30\x80\xc0\xff" * width for _ in range(height))

    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def test_validate_supported_oriented_shapes_and_keeps_runtime_paths_internal(tmp_path):
    paths = []
    for index, (width, height) in enumerate(((1600, 900), (900, 1600), (1000, 1000)), 1):
        path = tmp_path / f"shape-{index}.png"
        path.write_bytes(png_bytes(width, height))
        paths.append(str(path))

    assets = validate_attachment2_photos(paths, ("reviewed-1", "reviewed-2", "reviewed-3"))

    assert [(asset.width_px, asset.height_px) for asset in assets] == [
        (1600, 900), (900, 1600), (1000, 1000),
    ]
    assert [asset.source_image_id for asset in assets] == [
        "reviewed-1", "reviewed-2", "reviewed-3",
    ]
    assert all(str(tmp_path) in asset.path for asset in assets)
    assert all("photo" not in asset.source_image_id for asset in assets)


def test_validate_jpeg_and_reads_exif_orientation_marker(tmp_path):
    tiff = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    tiff += struct.pack("<H", 1)
    tiff += struct.pack("<HHI", 0x0112, 3, 1) + struct.pack("<H", 6) + b"\x00\x00"
    tiff += struct.pack("<I", 0)
    exif = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    path = tmp_path / "oriented.jpg"
    path.write_bytes(MINIMAL_JPEG[:2] + app1 + MINIMAL_JPEG[2:])

    asset = validate_attachment2_photos([str(path)])[0]

    assert asset.width_px == 1 and asset.height_px == 1
    assert asset.orientation == 6


@pytest.mark.parametrize("dimensions", [(4000, 1000), (1000, 4000), (2000, 2000)])
def test_contain_geometry_preserves_ratio_and_stays_inside_slot(dimensions):
    width, height = dimensions
    geometry = calculate_contain_geometry(width, height)

    assert geometry.render_width_emu <= ATTACHMENT2_SLOT_WIDTH_EMU
    assert geometry.render_height_emu <= ATTACHMENT2_SLOT_HEIGHT_EMU
    assert geometry.offset_x_emu >= 0 and geometry.offset_y_emu >= 0
    assert abs(
        geometry.render_width_emu * height - geometry.render_height_emu * width
    ) <= max(width, height)
    assert geometry.offset_x_emu * 2 + geometry.render_width_emu <= ATTACHMENT2_SLOT_WIDTH_EMU
    assert geometry.offset_y_emu * 2 + geometry.render_height_emu <= ATTACHMENT2_SLOT_HEIGHT_EMU


def test_small_images_are_not_upscaled_and_are_centered():
    geometry = calculate_contain_geometry(96, 96)
    assert geometry.render_width_emu == 914400
    assert geometry.render_height_emu == 914400
    assert geometry.offset_x_emu == (ATTACHMENT2_SLOT_WIDTH_EMU - 914400) // 2
    assert geometry.offset_y_emu == (ATTACHMENT2_SLOT_HEIGHT_EMU - 914400) // 2


@pytest.mark.parametrize("filename,content", [
    ("missing.png", None),
    ("empty.png", b""),
    ("broken.jpg", b"not-a-jpeg"),
    ("broken.png", b"not-a-png"),
    ("unsupported.gif", png_bytes(2, 2)),
])
def test_invalid_images_are_rejected_without_paths_in_error(tmp_path, filename, content):
    path = tmp_path / filename
    if content is not None:
        path.write_bytes(content)

    with pytest.raises(Attachment2ImageError) as error:
        validate_attachment2_photos([str(path)])

    assert error.value.code == "ATTACHMENT2_IMAGE_INVALID"
    assert str(tmp_path) not in error.value.safe_message
    assert str(path) not in error.value.safe_message


def test_duplicate_source_ids_are_made_unique_without_reordering(tmp_path):
    paths = []
    for index in range(2):
        path = tmp_path / f"ordered-{index}.png"
        path.write_bytes(png_bytes(2 + index, 3))
        paths.append(str(path))

    assets = validate_attachment2_photos(paths, ("same", "same"))
    assert [asset.source_image_id for asset in assets] == ["same", "same-2"]
