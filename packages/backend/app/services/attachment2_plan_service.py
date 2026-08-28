"""根据明确审核的检材照片组进行纯 Attachment2 规划。"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any, Mapping

from .attachment_plan_models_service import (
    AttachmentPlanError,
    Attachment2ImagePlan,
    Attachment2PagePlan,
    MaterialPhotoGroup,
)

ATTACHMENT2_PAIR_SIZE = 2
ATTACHMENT2_MAX_IMAGES_PER_PAGE = 4
ATTACHMENT2_MAX_GROUPS_PER_PAGE = 2
ATTACHMENT2_LAYOUT_TWO_CENTERED = "two_centered"
ATTACHMENT2_LAYOUT_FOUR_GRID = "four_grid"

_MAPPING_ERROR = "附件2图片必须明确归属检材并保持审核后的顺序。"
_COUNT_ERROR = "附件2每个检材必须恰好对应两张图片。"


@dataclass(frozen=True)
class MaterialPhotoGroupInput:
    material_id: str
    material_number: str
    display_text: str
    ordered_image_ids: tuple[str, str]
    source_order: int


def build_attachment2_pages(
    groups: tuple[MaterialPhotoGroupInput, ...],
) -> tuple[Attachment2PagePlan, ...]:
    """按检材组构建页面；渲染器绝不重新分组平铺照片。"""
    pages: list[Attachment2PagePlan] = []
    for page_number, start in enumerate(
        range(0, len(groups), ATTACHMENT2_MAX_GROUPS_PER_PAGE), 1,
    ):
        page_groups = groups[start:start + ATTACHMENT2_MAX_GROUPS_PER_PAGE]
        layout = (
            ATTACHMENT2_LAYOUT_TWO_CENTERED
            if len(page_groups) == 1
            else ATTACHMENT2_LAYOUT_FOUR_GRID
        )
        slots = (
            ("left", "right")
            if len(page_groups) == 1
            else ("top-left", "top-right", "bottom-left", "bottom-right")
        )
        planned_groups: list[MaterialPhotoGroup] = []
        planned_images: list[Attachment2ImagePlan] = []
        for group_index, group in enumerate(page_groups):
            group_images: list[Attachment2ImagePlan] = []
            for image_index, image_id in enumerate(group.ordered_image_ids):
                sequence_number = start * ATTACHMENT2_PAIR_SIZE + group_index * ATTACHMENT2_PAIR_SIZE + image_index + 1
                image = Attachment2ImagePlan(
                    source_image_id=_safe_photo_id(image_id, sequence_number),
                    sequence_number=sequence_number,
                    safe_display_name=_safe_photo_name(image_id, sequence_number),
                    slot=slots[group_index * ATTACHMENT2_PAIR_SIZE + image_index],
                    evidence_number=group.material_number,
                )
                group_images.append(image)
                planned_images.append(image)
            planned_groups.append(MaterialPhotoGroup(
                material_id=group.material_id,
                material_number=group.material_number,
                display_text=group.display_text,
                images=(group_images[0], group_images[1]),
                source_order=group.source_order,
            ))
        pages.append(Attachment2PagePlan(
            page_number=page_number,
            show_attachment_title=page_number == 1,
            layout=layout,
            images=tuple(planned_images),
            material_groups=tuple(planned_groups),
            inspection_result_material_numbers=tuple(
                group.material_number for group in planned_groups
            ),
        ))
    return tuple(pages)


def material_photo_groups(report: Mapping[str, Any]) -> tuple[MaterialPhotoGroupInput, ...]:
    """验证并规范化明确的报告级检材照片映射。"""
    attachments = report.get("attachments") or {}
    photo_ids = photo_values(report)
    raw_groups = attachments.get("photo_groups")
    if not photo_ids:
        if raw_groups not in (None, []):
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        return ()
    if not isinstance(raw_groups, list):
        raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
    if len(set(photo_ids)) != len(photo_ids):
        raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
    if len(raw_groups) != len(photo_ids) // ATTACHMENT2_PAIR_SIZE:
        raise AttachmentPlanError(
            "ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID", _COUNT_ERROR,
        )
    catalog = _material_catalog(report)
    if len(catalog) != len(raw_groups):
        raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
    normalized: list[MaterialPhotoGroupInput] = []
    flattened: list[str] = []
    for index, raw in enumerate(raw_groups, 1):
        if not isinstance(raw, Mapping):
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        expected_id, expected_number = catalog[index - 1]
        material_id = _text(raw.get("material_id"))
        material_number = _text(raw.get("material_number"))
        display_text = _text(raw.get("display_text"))
        if not material_id or not material_number or not display_text:
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        if (material_id, material_number) != (expected_id, expected_number):
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        if display_text != f"检材{material_number}照片":
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        source_order = raw.get("source_order")
        if source_order != index:
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        raw_image_ids = raw.get("ordered_image_ids")
        if not isinstance(raw_image_ids, list) or len(raw_image_ids) != ATTACHMENT2_PAIR_SIZE:
            raise AttachmentPlanError(
                "ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID", _COUNT_ERROR,
            )
        image_ids = tuple(_text(value) for value in raw_image_ids)
        if not all(image_ids) or len(set(image_ids)) != ATTACHMENT2_PAIR_SIZE:
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        if any(value not in photo_ids for value in image_ids):
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        flattened.extend(image_ids)
        normalized.append(MaterialPhotoGroupInput(
            material_id=material_id,
            material_number=material_number,
            display_text=display_text,
            ordered_image_ids=(image_ids[0], image_ids[1]),
            source_order=index,
        ))
    if flattened != photo_ids:
        raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
    return tuple(normalized)


def with_compatible_material_photo_groups(report: Mapping[str, Any]) -> dict[str, Any]:
    """仅根据有序检材和照片 ID 填充缺失的旧版映射。"""
    result = copy.deepcopy(dict(report))
    attachments = result.get("attachments")
    if not isinstance(attachments, dict):
        attachments = {}
        result["attachments"] = attachments
    photo_ids = photo_values(result)
    raw_groups = attachments.get("photo_groups")
    if not photo_ids or raw_groups not in (None, []):
        return result
    if len(photo_ids) % ATTACHMENT2_PAIR_SIZE or len(set(photo_ids)) != len(photo_ids):
        return result
    catalog = _material_catalog(result)
    if len(catalog) != len(photo_ids) // ATTACHMENT2_PAIR_SIZE:
        return result
    attachments["photo_groups"] = [
        {
            "material_id": material_id,
            "material_number": material_number,
            "display_text": f"检材{material_number}照片",
            "ordered_image_ids": photo_ids[index * 2:index * 2 + 2],
            "source_order": index + 1,
        }
        for index, (material_id, material_number) in enumerate(catalog)
    ]
    return result


def photo_values(report: Mapping[str, Any]) -> list[str]:
    value = (report.get("attachments") or {}).get("photo_ids") or []
    return [_text(item) for item in value] if isinstance(value, list) else []


def evidence_numbers(report: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(number for _, number in _material_catalog(report))


def _material_catalog(report: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for item in (report.get("introduction") or {}).get("evidence_list") or []:
        if not isinstance(item, Mapping):
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        material_id = _text(item.get("id"))
        material_number = _text(item.get("evidence_number"))
        if not material_id or not material_number:
            raise AttachmentPlanError("ATTACHMENT2_IMAGE_MAPPING_INVALID", _MAPPING_ERROR)
        values.append((material_id, material_number))
    return tuple(values)


def _safe_photo_id(value: Any, sequence_number: int) -> str:
    candidate = _text(value)
    if not candidate or "/" in candidate or "\\" in candidate or ":" in candidate:
        return f"photo-{sequence_number}"
    return candidate[:96]


def _safe_photo_name(value: Any, sequence_number: int) -> str:
    candidate = _text(value).replace("/", "\\")
    name = PureWindowsPath(candidate).name
    safe = "".join(
        char if char.isprintable() and char not in '<>:/\\|?*' else "_"
        for char in name
    )
    return safe[:160] or f"photo-{sequence_number}.image"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


__all__ = [
    "ATTACHMENT2_LAYOUT_FOUR_GRID", "ATTACHMENT2_LAYOUT_TWO_CENTERED",
    "ATTACHMENT2_MAX_GROUPS_PER_PAGE", "ATTACHMENT2_MAX_IMAGES_PER_PAGE",
    "ATTACHMENT2_PAIR_SIZE", "MaterialPhotoGroupInput", "build_attachment2_pages",
    "evidence_numbers", "material_photo_groups", "photo_values",
    "with_compatible_material_photo_groups",
]
