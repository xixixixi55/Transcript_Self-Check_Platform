"""使用合成数据，通过原生 Windows ConPTY 探测 WinRAR 进度。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.probe_winrar_progress import (  # noqa: E402
    _raw_summary,
    _run,
    _write_synthetic_inputs,
    find_regressions,
)
from scripts.win32_conpty import (  # noqa: E402
    ConPtyResult,
    run_conpty,
)
from scripts.win32_terminal_progress import visible_percentages  # noqa: E402


def assess_visible_runs(results: Sequence[ConPtyResult]) -> dict[str, object]:
    sequences = tuple(visible_percentages(result.output)[0] for result in results)
    regressions = tuple(find_regressions(sequence) for sequence in sequences)
    has_signal = bool(sequences) and all(sequences)
    repeatable = len(sequences) > 1 and all(
        sequence == sequences[0] for sequence in sequences[1:]
    )
    monotonic = has_signal and all(not items for items in regressions)
    terminal_100 = has_signal and all(sequence[-1] == 100 for sequence in sequences)
    return {
        "supported": monotonic and repeatable and terminal_100,
        "sampleCounts": [len(sequence) for sequence in sequences],
        "regressionCounts": [len(items) for items in regressions],
        "regressionSamples": [
            [list(pair) for pair in items[:3]] for items in regressions
        ],
        "terminalPercentages": [
            sequence[-1] if sequence else None for sequence in sequences
        ],
        "repeatable": repeatable,
        "monotonic": monotonic,
        "terminal100": terminal_100,
    }


def _summary(result: ConPtyResult) -> dict[str, object]:
    percentages, controls = visible_percentages(result.output)
    try:
        result.output.decode("utf-8")
        encoding = "UTF-8"
    except UnicodeDecodeError:
        encoding = "non-UTF-8"
    return {
        "returnCode": result.return_code,
        "rawTerminalBytes": len(result.output),
        "rawTerminalSha256": hashlib.sha256(result.output).hexdigest(),
        "encoding": encoding,
        "controlCounts": controls,
        "reported100": 100 in percentages,
        "terminalPercentage": percentages[-1] if percentages else None,
        "cancelled": result.cancelled,
        "treeTerminationSucceeded": result.tree_termination_succeeded,
        "durationMs": result.duration_ms,
    }


def _run_twice(
    executable: Path,
    root: Path,
    label: str,
    input_name: str,
    switches: Sequence[str] = (),
) -> tuple[dict[str, object], list[dict[str, object]]]:
    results = [
        run_conpty(
            executable,
            ["a", "-r", "-y", "-idn", *switches,
             f"SYNTHETIC_{label.upper()}_{run_number}.rar", input_name],
            root,
        )
        for run_number in (1, 2)
    ]
    return assess_visible_runs(results), [_summary(result) for result in results]


def _decision(
    normal: dict[str, dict[str, object]],
    failure: dict[str, object],
    cancellation: dict[str, object],
    legacy: dict[str, object],
) -> str:
    safe_failure = failure["returnCode"] != 0 and failure["reported100"] is False
    safe_cancel = (
        cancellation["cancelled"] is True
        and cancellation["treeTerminationSucceeded"] is True
        and cancellation["returnCode"] != 0
        and cancellation["reported100"] is False
    )
    legacy_safe = (
        legacy["returnCode"] == 0
        and legacy["stdoutBytes"] == 0
        and legacy["stderrBytes"] == 0
    )
    return "supported" if (
        all(case["supported"] is True for case in normal.values())
        and safe_failure and safe_cancel and legacy_safe
    ) else "unsupported"


def run_probe(executable: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="SYNTHETIC-winrar-conpty-") as temp:
        root = Path(temp)
        normal_input, cancellation_input = _write_synthetic_inputs(root)
        help_result = _run(executable, ["-?"], root)
        version = re.search(rb"\bRAR\s+(\d+\.\d+)\s+(x64|x86)", help_result.stdout)
        single, single_raw = _run_twice(
            executable, root, "single",
            str(normal_input.relative_to(root) / "SYNTHETIC_TEST_FIXTURE_3.bin"),
        )
        multi, multi_raw = _run_twice(
            executable, root, "multi", normal_input.name,
        )
        volumes, volumes_raw = _run_twice(
            executable, root, "volumes", normal_input.name, ("-v8388608b",),
        )
        failure_result = run_conpty(
            executable,
            ["a", "-r", "-y", "-idn", "SYNTHETIC_FAILURE.rar",
             "SYNTHETIC_MISSING_*"],
            root,
        )
        cancellation_result = run_conpty(
            executable,
            ["a", "-r", "-y", "-idn", "-m5", "SYNTHETIC_CANCELLED.rar",
             cancellation_input.name],
            root,
            cancel_after_seconds=0.5,
        )
        legacy = _raw_summary(_run(
            executable,
            ["a", "-r", "-y", "-inul", "SYNTHETIC_LEGACY.rar", normal_input.name],
            root,
        ))

    normal = {"single": single, "multi": multi, "volumes": volumes}
    failure = _summary(failure_result)
    cancellation = _summary(cancellation_result)
    return {
        "status": _decision(normal, failure, cancellation, legacy),
        "executableName": executable.name,
        "version": version.group(1).decode() if version else None,
        "architecture": version.group(2).decode() if version else None,
        "captureMethod": "Windows-ConPTY-native-ctypes",
        "processControl": "suspended-child-assigned-to-kill-on-close-job-object",
        "signalSource": "parsed-current-visible-terminal-state",
        "commands": {
            "normal": ["a", "-r", "-y", "-idn", "<archive>", "<input>"],
            "volumes": [
                "a", "-r", "-y", "-idn", "-v8388608b", "<archive>", "<input>",
            ],
            "legacy": ["a", "-r", "-y", "-inul", "<archive>", "<input>"],
        },
        "normalCases": normal,
        "rawEvidence": {
            "single": single_raw, "multi": multi_raw, "volumes": volumes_raw,
        },
        "failure": failure,
        "cancellation": cancellation,
        "legacySilentOrdinaryPipe": legacy,
        "containsRawOutput": False,
        "containsAbsolutePath": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run_probe(arguments.executable), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
