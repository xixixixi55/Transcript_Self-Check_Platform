"""Pure validation and generation rules for the first disc number."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

_MAX_SAFE_INTEGER = 2**53 - 1


@dataclass(frozen=True)
class DiscSequence:
    prefix: str
    date: str
    start_number: int
    number_width: int
    first_disc_number: str


@dataclass(frozen=True)
class DiscSequenceParseResult:
    sequence: DiscSequence | None
    error_code: str | None = None

    @property
    def valid(self) -> bool:
        return self.sequence is not None


_PATTERN = re.compile(r"^([A-Za-z\u3400-\u9fff]{1,20})(\d{4})(\d{2})(\d{2})-(\d+)$", re.IGNORECASE)


def parse_disc_sequence(value: str | None) -> DiscSequenceParseResult:
    if not value:
        return DiscSequenceParseResult(None, "FIRST_DISC_NUMBER_MISSING")
    if not isinstance(value, str):
        return DiscSequenceParseResult(None, "FIRST_DISC_NUMBER_INVALID")
    if value != value.strip():
        return DiscSequenceParseResult(None, "FIRST_DISC_NUMBER_INVALID")
    match = _PATTERN.fullmatch(value)
    if not match:
        return DiscSequenceParseResult(None, "FIRST_DISC_NUMBER_INVALID")
    year, month, day = (int(match.group(index)) for index in (2, 3, 4))
    try:
        date(year, month, day)
    except ValueError:
        return DiscSequenceParseResult(None, "FIRST_DISC_DATE_INVALID")
    raw_number = match.group(5)
    start_number = int(raw_number)
    if start_number < 1 or start_number > _MAX_SAFE_INTEGER:
        return DiscSequenceParseResult(None, "FIRST_DISC_SEQUENCE_INVALID")
    prefix = match.group(1).upper() if match.group(1).isascii() else match.group(1)
    sequence = DiscSequence(
        prefix=prefix,
        date=f"{year:04d}-{month:02d}-{day:02d}",
        start_number=start_number,
        number_width=len(raw_number),
        first_disc_number=f"{prefix}{year:04d}{month:02d}{day:02d}-{raw_number}",
    )
    return DiscSequenceParseResult(sequence)


def apply_disc_sequence_to_attachments(attachments: dict[str, Any]) -> DiscSequenceParseResult:
    result = parse_disc_sequence(attachments.get("disc_number"))
    if result.valid and result.sequence is not None:
        year, month, day = result.sequence.date.split("-")
        attachments["burning_date"] = f"{year}年{int(month)}月{int(day)}日"
        attachments["disc_sequence"] = {
            "prefix": result.sequence.prefix,
            "date": result.sequence.date,
            "start_number": result.sequence.start_number,
            "number_width": result.sequence.number_width,
            "first_disc_number": result.sequence.first_disc_number,
        }
    else:
        attachments.pop("disc_sequence", None)
    return result


def generate_disc_numbers(
    first_disc_number: str | DiscSequence,
    count: int,
) -> list[str]:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("FIRST_DISC_SEQUENCE_INVALID")
    parsed = (
        parse_disc_sequence(first_disc_number)
        if isinstance(first_disc_number, str)
        else DiscSequenceParseResult(first_disc_number)
    )
    if not parsed.valid or parsed.sequence is None:
        raise ValueError(parsed.error_code or "FIRST_DISC_NUMBER_INVALID")
    sequence = parsed.sequence
    if sequence.start_number + max(count - 1, 0) > _MAX_SAFE_INTEGER:
        raise ValueError("FIRST_DISC_SEQUENCE_INVALID")
    return [
        f"{sequence.prefix}{sequence.date.replace('-', '')}-"
        f"{sequence.start_number + index:0{sequence.number_width}d}"
        for index in range(count)
    ]


def validate_disc_mapping(
    part_numbers: list[int], metadata: list[tuple[str, str]],
) -> bool:
    if not metadata:
        return True
    if len(metadata) != len(part_numbers):
        return False
    ordered = [item for _, item in sorted(zip(part_numbers, metadata), key=lambda pair: pair[0])]
    first_disc = parse_disc_sequence(ordered[0][0])
    if not first_disc.valid or first_disc.sequence is None:
        return True  # Preserve legacy synthetic opaque disc identifiers.
    return (
        [item[0] for item in ordered] == generate_disc_numbers(first_disc.sequence, len(ordered))
        and all(item[1] == first_disc.sequence.date for item in ordered)
    )
