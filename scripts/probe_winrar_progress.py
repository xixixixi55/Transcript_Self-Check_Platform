"""Probe WinRAR console progress with synthetic inputs only."""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "backend"))

from app.repository.winrar_discovery_repository import discover_winrar  # noqa: E402

PERCENT_PATTERN = re.compile(rb"(?<!\d)(\d{1,3})%")
SYNTHETIC_FILE_SIZES_MIB = (4, 12, 24)


def extract_percentages(output: bytes) -> tuple[int, ...]:
    return tuple(int(match.group(1)) for match in PERCENT_PATTERN.finditer(output))


def find_regressions(percentages: Sequence[int]) -> tuple[tuple[int, int], ...]:
    return tuple(
        (previous, current)
        for previous, current in zip(percentages, percentages[1:])
        if current < previous
    )


def assess_progress_runs(outputs: Sequence[bytes]) -> dict[str, object]:
    sequences = tuple(extract_percentages(output) for output in outputs)
    regressions = tuple(find_regressions(sequence) for sequence in sequences)
    has_signal = bool(sequences) and all(sequences)
    monotonic = has_signal and all(not items for items in regressions)
    repeatable = len(sequences) > 1 and all(
        sequence == sequences[0] for sequence in sequences[1:]
    )
    supported = monotonic and repeatable and all(
        sequence[-1] == 100 for sequence in sequences
    )
    return {
        "status": "supported" if supported else "unsupported",
        "signalSource": "rar-console-stdout-backspace-percent",
        "runCount": len(sequences),
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
    }


def _write_synthetic_inputs(root: Path) -> None:
    generator = random.Random(20260730)
    for index, size_mib in enumerate(SYNTHETIC_FILE_SIZES_MIB, start=1):
        target = root / f"SYNTHETIC_TEST_FIXTURE_{index}.bin"
        with target.open("wb") as stream:
            for _ in range(size_mib):
                stream.write(generator.randbytes(1024 * 1024))


def _run(
    executable: Path,
    arguments: Sequence[str],
    working_directory: Path,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable), *arguments],
        cwd=working_directory,
        capture_output=True,
        check=False,
        timeout=60,
        shell=False,
    )


def run_probe(executable: Path) -> dict[str, object]:
    if not executable.is_file():
        return {
            "status": "unavailable",
            "executableName": executable.name,
            "diagnosticCode": "WINRAR_UNAVAILABLE",
        }

    with tempfile.TemporaryDirectory(prefix="SYNTHETIC-winrar-progress-") as temp:
        root = Path(temp)
        _write_synthetic_inputs(root)
        visible_runs = []
        for run_number in (1, 2):
            result = _run(
                executable,
                [
                    "a",
                    "-y",
                    "-m3",
                    f"SYNTHETIC_PROGRESS_{run_number}.rar",
                    "SYNTHETIC_TEST_FIXTURE_*.bin",
                ],
                root,
            )
            visible_runs.append(result.stdout + result.stderr)

        silent = _run(
            executable,
            [
                "a",
                "-y",
                "-m0",
                "-inul",
                "SYNTHETIC_LEGACY_SILENT.rar",
                "SYNTHETIC_TEST_FIXTURE_*.bin",
            ],
            root,
        )
        failure = _run(
            executable,
            [
                "a",
                "-y",
                "SYNTHETIC_FAILURE.rar",
                "SYNTHETIC_MISSING_FIXTURE_*.bin",
            ],
            root,
        )

    assessment = assess_progress_runs(visible_runs)
    version_match = re.search(rb"\bRAR\s+(\d+\.\d+)", visible_runs[0])
    return {
        **assessment,
        "executableName": executable.name,
        "version": version_match.group(1).decode("ascii") if version_match else None,
        "legacySilentCompatible": (
            silent.returncode == 0
            and not silent.stdout
            and not silent.stderr
        ),
        "failureBehavior": {
            "returnCode": failure.returncode,
            "percentageCount": len(
                extract_percentages(failure.stdout + failure.stderr)
            ),
        },
        "containsRawOutput": False,
        "containsAbsolutePath": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path)
    arguments = parser.parse_args()
    executable = arguments.executable
    if executable is None:
        capability = discover_winrar()
        if not capability.executable_path:
            print(json.dumps({
                "status": "unavailable",
                "executableName": None,
                "diagnosticCode": capability.diagnostic_code,
            }, ensure_ascii=False, indent=2))
            return 0
        executable = Path(capability.executable_path)
    print(json.dumps(run_probe(executable), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
