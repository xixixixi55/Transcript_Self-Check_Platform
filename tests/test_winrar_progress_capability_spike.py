"""Synthetic regression evidence for the Phase 3 WinRAR progress spike."""

from scripts.probe_winrar_progress import (
    assess_progress_runs,
    extract_percentages,
    find_regressions,
)


def test_extracts_backspace_percentages_without_localized_text_dependency():
    output = (
        b"SYNTHETIC_TEST_FIXTURE.bin"
        b"\b\b\b\b 10%\b\b\b\b 20%\b\b\b\b100%"
    )
    assert extract_percentages(output) == (10, 20, 100)


def test_rejects_current_console_shape_when_percentages_reset():
    first = (
        b"SYNTHETIC_A.bin\b\b\b\b 10%\b\b\b\b  2%\b\b\b\b 10%"
        b"\r\nSYNTHETIC_B.bin\b\b\b\b 20%\b\b\b\b 40%"
        b"\b\b\b\b 12%\b\b\b\b 40%"
        b"\r\nSYNTHETIC_C.bin\b\b\b\b100%\b\b\b\b 42%\b\b\b\b100%"
    )
    second = first

    assessment = assess_progress_runs((first, second))

    assert assessment["status"] == "unsupported"
    assert assessment["repeatable"] is True
    assert assessment["monotonic"] is False
    assert assessment["regressionSamples"] == [
        [[10, 2], [40, 12], [100, 42]],
        [[10, 2], [40, 12], [100, 42]],
    ]


def test_rejects_silent_legacy_output_as_progress_signal():
    assessment = assess_progress_runs((b"", b""))

    assert assessment["status"] == "unsupported"
    assert assessment["sampleCounts"] == [0, 0]
    assert assessment["monotonic"] is False


def test_accepts_only_repeatable_monotonic_terminal_sequences():
    supported = assess_progress_runs(
        (
            b"\b\b\b\b 10%\b\b\b\b 50%\b\b\b\b100%",
            b"\b\b\b\b 10%\b\b\b\b 50%\b\b\b\b100%",
        )
    )
    inconsistent = assess_progress_runs(
        (
            b"\b\b\b\b 10%\b\b\b\b100%",
            b"\b\b\b\b 20%\b\b\b\b100%",
        )
    )

    assert supported["status"] == "supported"
    assert inconsistent["status"] == "unsupported"


def test_reports_exact_regression_boundaries():
    assert find_regressions((10, 2, 5, 40, 12, 100, 42)) == (
        (10, 2),
        (40, 12),
        (100, 42),
    )
