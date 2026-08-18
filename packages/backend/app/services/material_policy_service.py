"""Stage-one material classification and display policy."""

from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from .canonical_models_service import (
    FieldProvenance,
    Material,
    MaterialClassification,
    MaterialIdentifier,
)

MATERIAL_TYPE_RULE_ID = "device_type_controlled_v1"
_PHONE_WORDS = ("手机", "智能手机", "phone", "smartphone", "iphone")
_TABLET_WORDS = ("平板", "平板电脑", "tablet", "ipad")
_PHONE_DISPLAY_TYPE_WORDS = ("手机", "智能手机", "phone", "smartphone")
_TABLET_DISPLAY_TYPE_WORDS = ("平板", "平板电脑", "tablet")
_CONFIRMED_STATUSES = {"confirmed_by_report", "confirmed_by_user"}


def _normalise_device_type(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _contains_word(value: str, word: str) -> bool:
    if any("\u4e00" <= char <= "\u9fff" for char in word):
        return word in value
    return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", value) is not None


def classify_material_type(device_type: Any) -> MaterialClassification:
    """Classify only an explicit report device_type field."""

    value = _normalise_device_type(device_type)
    if not value:
        return MaterialClassification(
            source="none",
            rule_id=MATERIAL_TYPE_RULE_ID,
            diagnostic_code="MATERIAL_TYPE_DEVICE_TYPE_MISSING",
        )

    phone_hit = any(_contains_word(value, word) for word in _PHONE_WORDS)
    tablet_hit = any(_contains_word(value, word) for word in _TABLET_WORDS)
    if phone_hit and tablet_hit:
        diagnostic = "MATERIAL_TYPE_CONFLICT"
        material_kind = "unconfirmed"
    elif phone_hit:
        diagnostic = None
        material_kind = "phone"
    elif tablet_hit:
        diagnostic = None
        material_kind = "tablet"
    else:
        diagnostic = "MATERIAL_TYPE_DEVICE_TYPE_UNRECOGNIZED"
        material_kind = "unconfirmed"

    return MaterialClassification(
        status=("confirmed_by_report" if material_kind != "unconfirmed" else "unconfirmed"),
        source="report",
        rule_id=MATERIAL_TYPE_RULE_ID,
        diagnostic_code=diagnostic,
    )


def _safe_text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set, bool)):
        return ""
    return str(value).strip()


def _legacy_provenance(path: str) -> FieldProvenance:
    return FieldProvenance(
        source_type="legacy_migration",
        adapter="legacy-report-input",
        json_path=path,
    )


def _classification_from_report_item(item: Mapping[str, Any]) -> tuple[str, MaterialClassification]:
    if (
        item.get("device_type_source") not in {None, "report_field"}
        and item.get("material_type_source") != "user"
    ):
        return "unconfirmed", MaterialClassification(
            status="unconfirmed",
            source="none",
            rule_id=MATERIAL_TYPE_RULE_ID,
            diagnostic_code="MATERIAL_TYPE_DEVICE_TYPE_NOT_EXPLICIT",
        )
    if "material_type" not in item:
        candidate = classify_material_type(item.get("device_type"))
        value = _normalise_device_type(item.get("device_type"))
        phone_hit = any(_contains_word(value, word) for word in _PHONE_WORDS)
        tablet_hit = any(_contains_word(value, word) for word in _TABLET_WORDS)
        kind = "phone" if phone_hit and not tablet_hit else "tablet" if tablet_hit and not phone_hit else "unconfirmed"
        return kind, candidate

    kind = item.get("material_type")
    status = item.get("material_type_status")
    source = item.get("material_type_source")
    if kind in {"phone", "tablet"} and status in _CONFIRMED_STATUSES and source in {"report", "user"}:
        return kind, MaterialClassification(
            status=status,
            source=source,
            rule_id=MATERIAL_TYPE_RULE_ID,
            diagnostic_code=item.get("material_type_diagnostic"),
        )
    return "unconfirmed", MaterialClassification(
        status="unconfirmed",
        source=source if source in {"report", "user"} else "none",
        rule_id=MATERIAL_TYPE_RULE_ID,
        diagnostic_code="MATERIAL_TYPE_STATUS_MISSING",
    )


def material_from_legacy_item(item: Mapping[str, Any], index: int) -> Material:
    """Build canonical material while retaining every source identifier."""

    kind, classification = _classification_from_report_item(item)
    identifiers: list[MaterialIdentifier] = []
    for identifier_type in ("imei1", "imei2", "serial_number"):
        value = _safe_text(item.get(identifier_type))
        if value:
            path = f"introduction.evidence_list[{index}].{identifier_type}"
            identifiers.append(
                MaterialIdentifier(
                    type=identifier_type,
                    value=value,
                    provenance=[_legacy_provenance(path)],
                )
            )
    extractable = item.get("extractable")
    if not isinstance(extractable, bool):
        extractable = bool(identifiers)
    return Material(
        id=_safe_text(item.get("id")) or f"legacy-material-{index + 1}",
        evidence_number=_safe_text(item.get("evidence_number")),
        type=kind,
        name=_safe_text(item.get("device_type")),
        model=_safe_text(item.get("model")),
        extractable=extractable,
        identifiers=identifiers,
        provenance=[_legacy_provenance(f"introduction.evidence_list[{index}].device_type")],
        classification=classification,
    )


def select_display_identifiers(material: Material) -> tuple[MaterialIdentifier, ...]:
    """Return only identifiers allowed by the already-confirmed material type."""

    if (
        material.classification.status not in _CONFIRMED_STATUSES
        or material.classification.source not in {"report", "user"}
    ):
        return ()

    def clean(identifier: MaterialIdentifier) -> MaterialIdentifier | None:
        value = identifier.value.strip()
        if not value or any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F for char in value):
            return None
        if identifier.type in {"imei1", "imei2"} and not re.fullmatch(r"\d{15}", value):
            return None
        return identifier.model_copy(update={"value": value})

    selected: list[MaterialIdentifier] = []
    allowed = ("imei1", "imei2") if material.type == "phone" else ("serial_number",) if material.type == "tablet" else ()
    for identifier_type in allowed:
        identifier = next((item for item in material.identifiers if item.type == identifier_type), None)
        if identifier is not None:
            cleaned = clean(identifier)
            if cleaned is not None:
                selected.append(cleaned)
    return tuple(selected)


def reviewed_material_display_name(item: Mapping[str, Any], index: int = 0) -> str | None:
    """Return a reviewed device name with its confirmed material type appended."""

    material = material_from_legacy_item(item, index)
    type_label = "手机" if material.type == "phone" else "平板" if material.type == "tablet" else ""
    if not type_label:
        return None
    base_name = next(
        (
            _safe_text(item.get(key))
            for key in ("device_name", "model", "device_type")
            if _safe_text(item.get(key))
        ),
        "",
    )
    if _contains_material_type(base_name, material.type):
        return base_name
    return f"{base_name}{type_label}"


def _contains_material_type(value: str, material_type: str) -> bool:
    normalized = _normalise_device_type(value)
    words = (
        _PHONE_DISPLAY_TYPE_WORDS
        if material_type == "phone"
        else _TABLET_DISPLAY_TYPE_WORDS
    )
    for word in sorted(words, key=len, reverse=True):
        normalized_word = _normalise_device_type(word)
        if any("\u4e00" <= char <= "\u9fff" for char in normalized_word):
            if re.search(rf"{re.escape(normalized_word)}(?![\u4e00-\u9fff])", normalized):
                return True
        elif _contains_word(normalized, normalized_word):
            return True
    return False


def enrich_report_material_types(report: Mapping[str, Any]) -> dict[str, Any]:
    """Add optional classification fields without changing legacy parser logic."""

    enriched = copy.deepcopy(dict(report))
    introduction = enriched.setdefault("introduction", {})
    for item in introduction.get("evidence_list") or []:
        if not isinstance(item, dict) or "material_type_status" in item:
            continue
        kind, classification = _classification_from_report_item(item)
        item.update(
            {
                "material_type": kind,
                "material_type_status": classification.status,
                "material_type_source": classification.source,
                "material_type_diagnostic": classification.diagnostic_code,
            }
        )
    return enriched


def unconfirmed_material_fields(report: Mapping[str, Any]) -> tuple[str, ...]:
    def field_path(index: int, item: Mapping[str, Any] | None = None) -> str:
        item_id = _safe_text(item.get("id")) if item is not None else ""
        if item_id:
            if re.fullmatch(r"material-[A-Za-z0-9_-]+", item_id):
                locator = f"id={item_id}"
            else:
                digest = hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:12]
                locator = f"id_hash={digest}"
            return f"introduction.evidence_list[{locator}].material_type"
        return f"introduction.evidence_list[{index}].material_type"

    def report_candidate_matches(item: Mapping[str, Any], kind: Any) -> bool:
        derived_kind, candidate = _classification_from_report_item({
            "device_type": item.get("device_type"),
            "device_type_source": item.get("device_type_source"),
        })
        return (
            kind == derived_kind
            and candidate.status == "confirmed_by_report"
            and candidate.source == "report"
        )

    fields: list[str] = []
    items = (report.get("introduction") or {}).get("evidence_list") or []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            fields.append(field_path(index))
            continue
        kind = item.get("material_type")
        status = item.get("material_type_status")
        source = item.get("material_type_source")
        is_confirmed = (
            kind in {"phone", "tablet"}
            and status in _CONFIRMED_STATUSES
            and source in {"report", "user"}
        )
        if is_confirmed and source == "report":
            is_confirmed = report_candidate_matches(item, kind)
        if not is_confirmed:
            fields.append(field_path(index, item))
    return tuple(fields)
