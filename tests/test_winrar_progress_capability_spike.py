"""Synthetic regression evidence for the Phase 3 WinRAR progress spike."""

from scripts.probe_winrar_progress import (
    assess_progress_runs,
    decide_adapter,
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

    assert assessment["supported"] is False
    assert assessment["repeatable"] is True
    assert assessment["monotonic"] is False
    assert assessment["regressionSamples"] == [
        [[10, 2], [40, 12], [100, 42]],
        [[10, 2], [40, 12], [100, 42]],
    ]


def test_rejects_silent_legacy_output_as_progress_signal():
    assessment = assess_progress_runs((b"", b""))

    assert assessment["supported"] is False
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

    assert supported["supported"] is True
    assert inconsistent["supported"] is False


def test_reports_exact_regression_boundaries():
    assert find_regressions((10, 2, 5, 40, 12, 100, 42)) == (
        (10, 2),
        (40, 12),
        (100, 42),
    )


def test_723_idn_shape_remains_blocked_when_single_and_multi_regress():
    single = assess_progress_runs((
        b" 16% 33% 50% 66% 83%100% 22% 44% 66% 88%100%",
        b" 16% 33% 50% 66% 83%100% 22% 44% 66% 88%100%",
    ))
    multi = assess_progress_runs((
        b" 12% 24% 36% 48% 60% 72% 16% 32% 96% 88%100%",
        b" 12% 24% 36% 48% 60% 72% 16% 32% 96% 88%100%",
    ))
    volumes = assess_progress_runs((
        b" 12% 24% 36% 48% 60% 72% 84% 96%100%",
        b" 12% 24% 36% 48% 60% 72% 84% 96%100%",
    ))

    decision = decide_adapter(
        {"single": single, "multi": multi, "volumes": volumes},
        {"returnCode": 10, "reported100": False},
        {"returnCode": 1, "reported100": False},
        {"returnCode": 0, "stdoutBytes": 0, "stderrBytes": 0},
    )

    assert single["regressionSamples"] == [[[100, 22]], [[100, 22]]]
    assert multi["monotonic"] is False
    assert volumes["supported"] is True
    assert decision == "unsupported"


def test_adapter_requires_safe_failure_cancellation_and_legacy_silence():
    normal = assess_progress_runs((b" 10% 50%100%", b" 10% 50%100%"))
    normal_cases = {"single": normal, "multi": normal, "volumes": normal}
    safe_failure = {"returnCode": 10, "reported100": False}
    safe_cancel = {"returnCode": 1, "reported100": False}
    silent = {"returnCode": 0, "stdoutBytes": 0, "stderrBytes": 0}

    assert decide_adapter(normal_cases, safe_failure, safe_cancel, silent) == "supported"
    assert decide_adapter(
        normal_cases,
        {"returnCode": 10, "reported100": True},
        safe_cancel,
        silent,
    ) == "unsupported"
    assert decide_adapter(
        normal_cases,
        safe_failure,
        {"returnCode": 0, "reported100": False},
        silent,
    ) == "unsupported"
