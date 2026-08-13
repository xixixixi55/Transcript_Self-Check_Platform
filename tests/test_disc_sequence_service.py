import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.disc_sequence_service import generate_disc_numbers, parse_disc_sequence


def test_disc_sequence_parses_and_generates_with_width():
    parsed = parse_disc_sequence("gp20260718-09")
    assert parsed.valid
    assert parsed.sequence is not None
    assert parsed.sequence.date == "2026-07-18"
    assert parsed.sequence.number_width == 2
    assert generate_disc_numbers(parsed.sequence, 3) == [
        "GP20260718-09", "GP20260718-10", "GP20260718-11"
    ]
    assert generate_disc_numbers("GP20260718-99", 2)[1] == "GP20260718-100"
    assert generate_disc_numbers("GP20260718-09", 0) == []


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "FIRST_DISC_NUMBER_MISSING"),
        ("GP20260230-01", "FIRST_DISC_DATE_INVALID"),
        ("GP20260718-0", "FIRST_DISC_SEQUENCE_INVALID"),
        ("GP20260718 -01", "FIRST_DISC_NUMBER_INVALID"),
    ],
)
def test_disc_sequence_rejects_invalid_input(value, code):
    result = parse_disc_sequence(value)
    assert not result.valid
    assert result.error_code == code


def test_disc_sequence_rejects_negative_or_boolean_count():
    with pytest.raises(ValueError, match="FIRST_DISC_SEQUENCE_INVALID"):
        generate_disc_numbers("GP20260718-01", -1)
    with pytest.raises(ValueError, match="FIRST_DISC_SEQUENCE_INVALID"):
        generate_disc_numbers("GP20260718-01", True)


def test_disc_sequence_rejects_non_string_and_unsafe_numbers():
    assert parse_disc_sequence(123).error_code == "FIRST_DISC_NUMBER_INVALID"
    assert parse_disc_sequence("GP20260718-9007199254740992").error_code == "FIRST_DISC_SEQUENCE_INVALID"
    assert parse_disc_sequence(
        "ABCDEFGHIJKLMNOPQRSTU20260718-01",
    ).error_code == "FIRST_DISC_NUMBER_INVALID"
