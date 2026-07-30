"""Synthetic regression evidence for the Phase 3 WinRAR progress spike."""

import os
from pathlib import Path

import pytest

from scripts.probe_winrar_conpty_progress import assess_visible_runs
from scripts.probe_winrar_progress import (
    assess_progress_runs,
    decide_adapter,
    extract_percentages,
    find_regressions,
)
from scripts.win32_conpty import ConPtyResult, run_conpty
from scripts.win32_terminal_progress import visible_percentages


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


def test_conpty_visible_state_preserves_real_overwrite_regressions():
    output = (
        b"\x1b[2J\x1b[H 16%\b\b\b\b 33%\b\b\b\b100%"
        b"\r 22%\x1b[4D 44%\r\n"
    )

    percentages, controls = visible_percentages(output)
    results = (
        ConPtyResult(0, output, False, False, 10),
        ConPtyResult(0, output, False, False, 10),
    )

    assert percentages == (16, 33, 100, 22, 44)
    assert controls == {
        "backspace": 8,
        "carriageReturn": 2,
        "lineFeed": 1,
        "csi": 3,
        "osc": 0,
    }
    assert assess_visible_runs(results)["regressionSamples"] == [
        [[100, 22]],
        [[100, 22]],
    ]


@pytest.mark.skipif(os.name != "nt", reason="ConPTY is Windows-only")
def test_native_conpty_captures_current_terminal_state():
    result = run_conpty(
        Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe",
        ["/d", "/c", "echo SYNTHETIC_TEST_FIXTURE 10%"],
        Path.cwd(),
    )

    assert result.return_code == 0
    assert b"SYNTHETIC_TEST_FIXTURE" in result.output
    assert visible_percentages(result.output)[0] == (10,)


@pytest.mark.skipif(os.name != "nt", reason="ConPTY is Windows-only")
def test_native_conpty_terminates_a_synthetic_child_process_tree():
    result = run_conpty(
        Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe",
        ["/d", "/c", "ping -n 30 127.0.0.1 > nul"],
        Path.cwd(),
        cancel_after_seconds=0.2,
    )

    assert result.cancelled is True
    assert result.tree_termination_succeeded is True
    assert result.return_code != 0
