"""Bounded JSON serialization for business DTOs and opaque asset references."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .workbench_constants import MAX_CASE_DTO_BYTES
from .workbench_errors import ForbiddenPayloadError

_FORBIDDEN_KEYS = {
    "base64", "raw_html", "raw_json", "raw_sections", "binary", "image_data",
    "content_bytes", "blob", "photo_data", "photo_base64", "image_base64", "base64_data",
    "source_path", "template_path", "output_path",
    "absolute_path", "original_json",
}
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9._-]{1,160}$")
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")
_ABSOLUTE_PATH_FRAGMENT = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?<![A-Za-z0-9_])/[^/\\s])")
_ASSET_KINDS = {"image", "source_snapshot", "cache", "staging", "other"}
_FIELD_SOURCES = {"report", "user", "system_default"}
_FIELD_CONFIRMATIONS = {"confirmed", "pending"}


def dump_bounded_json(value: Any, *, max_bytes: int = MAX_CASE_DTO_BYTES) -> str:
    _validate_value(value)
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ForbiddenPayloadError() from error
    if len(serialized.encode("utf-8")) > max_bytes:
        raise ForbiddenPayloadError("PAYLOAD_TOO_LARGE")
    return serialized


def load_bounded_json(serialized: str, *, max_bytes: int = MAX_CASE_DTO_BYTES) -> Any:
    if not isinstance(serialized, str) or len(serialized.encode("utf-8")) > max_bytes:
        raise ForbiddenPayloadError("PAYLOAD_TOO_LARGE")
    try:
        value = json.loads(serialized, parse_constant=_reject_json_constant)
    except (TypeError, ValueError) as error:
        raise ForbiddenPayloadError() from error
    _validate_value(value)
    return value


def validate_opaque_asset_refs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ForbiddenPayloadError()
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ForbiddenPayloadError()
        if set(item) - {"asset_id", "asset_kind", "fingerprint", "metadata"}:
            raise ForbiddenPayloadError()
        asset_id = validate_opaque_id(item.get("asset_id"))
        if asset_id in seen:
            raise ForbiddenPayloadError("DUPLICATE_ASSET_REFERENCE")
        seen.add(asset_id)
        if item.get("asset_kind") not in _ASSET_KINDS:
            raise ForbiddenPayloadError()
        if item.get("fingerprint") is not None and not isinstance(item.get("fingerprint"), str):
            raise ForbiddenPayloadError()
        metadata = item.get("metadata", {})
        if not isinstance(metadata, Mapping) or any(
            not isinstance(key, str) or isinstance(child, (dict, list, tuple, bytes, bytearray))
            or not isinstance(child, (str, int, float, bool))
            for key, child in metadata.items()
        ):
            raise ForbiddenPayloadError()
        result.append(dict(item))
    dump_bounded_json(result)
    return result


def validate_opaque_id(value: Any) -> str:
    if not isinstance(value, str) or value in {".", ".."} or not _OPAQUE_ID.fullmatch(value):
        raise ForbiddenPayloadError("INVALID_OPAQUE_ID")
    return value


def validate_safe_string(value: Any, code: str = "FORBIDDEN_LARGE_OBJECT") -> str:
    if not isinstance(value, str):
        raise ForbiddenPayloadError(code)
    _validate_value(value)
    return value


def validate_field_states(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ForbiddenPayloadError()
    result: dict[str, dict[str, Any]] = {}
    for field_path, state in value.items():
        if not isinstance(field_path, str) or not field_path or not isinstance(state, Mapping):
            raise ForbiddenPayloadError()
        if _ABSOLUTE_PATH.match(field_path.lstrip()):
            raise ForbiddenPayloadError("ABSOLUTE_PATH_FORBIDDEN")
        if state.get("source") not in _FIELD_SOURCES or state.get("confirmation") not in _FIELD_CONFIRMATIONS:
            raise ForbiddenPayloadError()
        revision = state.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ForbiddenPayloadError()
        if not isinstance(state.get("last_changed_at"), str):
            raise ForbiddenPayloadError()
        if state.get("subject_id") is not None:
            validate_opaque_id(state["subject_id"])
        result[field_path] = dict(state)
    dump_bounded_json(result)
    return result


def _validate_value(value: Any, key: str | None = None) -> None:
    if isinstance(value, bytes) or isinstance(value, bytearray):
        raise ForbiddenPayloadError()
    if key and key.casefold() in _FORBIDDEN_KEYS:
        raise ForbiddenPayloadError()
    if isinstance(value, str):
        normalized = value.lstrip().casefold()
        if _ABSOLUTE_PATH.match(value.lstrip()) or _ABSOLUTE_PATH_FRAGMENT.search(value):
            raise ForbiddenPayloadError("ABSOLUTE_PATH_FORBIDDEN")
        if normalized.startswith("data:") or normalized.startswith("<html") or normalized.startswith("<!doctype"):
            raise ForbiddenPayloadError()
        return
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise ForbiddenPayloadError()
            _validate_value(child_value, child_key)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _validate_value(child)
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    raise ForbiddenPayloadError()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant: {value}")
