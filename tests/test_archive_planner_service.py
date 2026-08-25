import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive_planner_service import (  # noqa: E402
    ArchivePolicy,
    ArchiveSourceEntry,
    ArchiveTier,
    PRODUCTION_ARCHIVE_POLICY,
    plan_archive,
    safe_archive_base_name,
)


GB = 1024**3


def entry(size: int) -> list[ArchiveSourceEntry]:
    return [ArchiveSourceEntry("data/file.bin", size, 1)]


@pytest.mark.parametrize(
    ("size", "tier", "expected", "status"),
    [
        (1, 4, 1, "planned"),
        (4 * GB, 4, 1, "planned"),
        (7 * GB, 4, 2, "planned"),
        (8 * GB, 4, 2, "planned"),
        (8 * GB + 1, 22, 1, "planned"),
        (22 * GB, 22, 1, "planned"),
        (44 * GB, 22, 2, "planned"),
        (44 * GB + 1, 45, 1, "planned"),
        (45 * GB, 45, 1, "planned"),
        (135 * GB, 45, 3, "planned"),
        (225 * GB, 45, 5, "planned"),
        (225 * GB + 1, None, 1, "planned"),
    ],
)
def test_production_binary_tier_boundaries(size, tier, expected, status):
    plan = plan_archive("合成案件", entry(size), first_disc_number="GP2026071802-01")
    assert plan.volume_tier_gb == tier
    assert plan.expected_part_count == expected
    assert plan.status == status
    if size > 225 * GB:
        assert plan.archive_mode == "oversized_single_volume"
        assert plan.volume_size_bytes is None
        assert plan.max_part_count == 1
        assert plan.diagnostics[0].code == "ARCHIVE_OVERSIZED_SINGLE_VOLUME"
        assert plan.first_disc_number is None
    else:
        assert plan.archive_mode == "standard_split"


@pytest.mark.parametrize(
    ("size", "tier", "expected"),
    [
        (9 * GB, 22, 1),
        (23 * GB, 22, 2),
        (43 * GB, 22, 2),
        (47 * GB, 45, 2),
        (91 * GB, 45, 3),
        (181 * GB, 45, 5),
    ],
)
def test_named_capacity_planning(size, tier, expected):
    """Planner selects tier and expected count from input bytes; no WinRAR call."""
    plan = plan_archive("合成案件", entry(size), first_disc_number="GP2026071802-01")
    assert plan.volume_tier_gb == tier
    assert plan.expected_part_count == expected
    assert plan.status == "planned"


def test_plan_records_selection_reason_and_disc_projection():
    plan = plan_archive("合成案件", entry(8 * GB), first_disc_number="GP2026071802-09")
    assert plan.diagnostics[0].code == "ARCHIVE_TIER_SELECTED"
    assert "4GB" in plan.diagnostics[0].message
    assert plan.expected_disc_numbers == ("GP2026071802-09", "GP2026071802-10")


def test_oversized_plan_keeps_only_a_user_hard_drive_number():
    plan = plan_archive(
        "合成案件", entry(225 * GB + 1), first_disc_number="YP2026041302-01",
    )
    assert plan.archive_mode == "oversized_single_volume"
    assert plan.first_disc_number == "YP2026041302-01"
    assert plan.expected_disc_numbers == ("YP2026041302-01",)


def test_legacy_number_remains_accepted_and_bound_to_a_new_plan():
    plan = plan_archive(
        "合成案件", entry(1), first_disc_number="GP20260718-01",
    )
    assert plan.status == "planned"
    assert plan.first_disc_number == "GP20260718-01"
    assert plan.expected_disc_numbers == ("GP20260718-01",)


def test_public_plan_projection_has_no_filesystem_paths():
    plan = plan_archive("合成案件", entry(1), first_disc_number="GP2026071802-01")
    public_plan = plan.public_dict()
    assert "output_directory" not in public_plan
    assert all("absolute_path" not in entry for entry in public_plan["source_entries"])
    assert not any(":" in str(value) for value in public_plan.values() if isinstance(value, str))


@pytest.mark.parametrize("bad_size", [-1, 1.5, True, 2**53])
def test_plan_rejects_invalid_sizes(bad_size):
    plan = plan_archive("合成案件", entry(bad_size))
    assert plan.status == "blocked"
    assert plan.diagnostics[0].code == "ARCHIVE_PLAN_INVALID"


def test_plan_rejects_empty_input_and_unsafe_total():
    assert plan_archive("合成案件", []).diagnostics[0].code == "ARCHIVE_INPUT_EMPTY"
    total_over_safe = [
        ArchiveSourceEntry("a", 2**53 - 1), ArchiveSourceEntry("b", 1)
    ]
    assert plan_archive("合成案件", total_over_safe).diagnostics[0].code == "ARCHIVE_PLAN_INVALID"


def test_plan_is_injectable_for_small_multi_volume_tests():
    policy = ArchivePolicy(
        (ArchiveTier(4, 4, 2), ArchiveTier(22, 22, 2), ArchiveTier(45, 45, 5))
    )
    plan = plan_archive("合成案件", entry(8), policy=policy)
    assert (plan.volume_size_bytes, plan.expected_part_count) == (4, 2)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("案件:名称", "案件_名称"), ("   ...", ""), ("CON", "_CON"), ("案件\\子目录", "案件_子目录")],
)
def test_archive_name_is_windows_safe_without_path_segments(name, expected):
    assert safe_archive_base_name(name) == expected
