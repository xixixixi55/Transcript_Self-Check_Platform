"""Probe raw WinRAR progress with synthetic inputs and no installation."""

from __future__ import annotations
import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "backend"))
from app.repository.winrar_discovery_repository import discover_winrar  # noqa: E402
PERCENT_PATTERN = re.compile(rb"(?<!\d)(\d{1,3})%")
NORMAL_FILE_SIZES_MIB = (1, 6, 18)

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

def decide_adapter(
    normal_cases: dict[str, dict[str, object]],
    failure: dict[str, object],
    cancellation: dict[str, object],
    legacy_silent: dict[str, object],
) -> str:
    normal_supported = normal_cases and all(
        case.get("supported") is True for case in normal_cases.values()
    )
    failure_safe = (
        failure.get("returnCode") not in (None, 0)
        and failure.get("reported100") is False
    )
    cancellation_safe = (
        cancellation.get("returnCode") not in (None, 0)
        and cancellation.get("reported100") is False
    )
    silent_compatible = (
        legacy_silent.get("returnCode") == 0
        and legacy_silent.get("stdoutBytes") == 0
        and legacy_silent.get("stderrBytes") == 0
    )
    return (
        "supported"
        if normal_supported and failure_safe and cancellation_safe and silent_compatible
        else "unsupported"
    )

def _write_random_file(path: Path, size_mib: int, generator: random.Random) -> None:
    with path.open("wb") as stream:
        for _ in range(size_mib):
            stream.write(generator.randbytes(1024 * 1024))

def _write_synthetic_inputs(root: Path) -> tuple[Path, Path]:
    generator = random.Random(20260730)
    normal = root / "SYNTHETIC_TEST_FIXTURES"
    normal.mkdir()
    for index, size_mib in enumerate(NORMAL_FILE_SIZES_MIB, start=1):
        target = normal / f"SYNTHETIC_TEST_FIXTURE_{index}.bin"
        _write_random_file(target, size_mib, generator)
    cancellation = root / "SYNTHETIC_CANCEL_FIXTURE.bin"
    _write_random_file(cancellation, 128, generator)
    return normal, cancellation

def _run(executable: Path, args: Sequence[str], root: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable), *args],
        cwd=root,
        capture_output=True,
        check=False,
        timeout=60,
        shell=False,
    )

def _raw_summary(result: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
    output = result.stdout + result.stderr
    percentages = extract_percentages(output)
    return {
        "returnCode": result.returncode,
        "stdoutBytes": len(result.stdout),
        "stderrBytes": len(result.stderr),
        "stdoutSha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderrSha256": hashlib.sha256(result.stderr).hexdigest(),
        "encoding": "ASCII" if all(byte < 128 for byte in output) else "opaque-bytes",
        "reported100": 100 in percentages,
        "terminalPercentage": percentages[-1] if percentages else None,
    }

def _run_twice(
    executable: Path,
    root: Path,
    label: str,
    common_args: Sequence[str],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    results = []
    for run_number in (1, 2):
        args = [
            *common_args,
            f"SYNTHETIC_{label.upper()}_{run_number}.rar",
            "SYNTHETIC_TEST_FIXTURES",
        ]
        results.append(_run(executable, args, root))
    return (
        assess_progress_runs([result.stdout + result.stderr for result in results]),
        [_raw_summary(result) for result in results],
    )

def _cancel(executable: Path, root: Path, input_path: Path) -> dict[str, object]:
    args = [
        "a", "-r", "-y", "-idn", "-m5", "SYNTHETIC_CANCELLED.rar",
        input_path.name,
    ]
    process = subprocess.Popen(
        [str(executable), *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    time.sleep(0.5)
    process.kill()
    stdout, stderr = process.communicate(timeout=10)
    return _raw_summary(subprocess.CompletedProcess(args, process.returncode, stdout, stderr))

def run_probe(executable: Path) -> dict[str, object]:
    if not executable.is_file():
        return {"status": "unavailable", "diagnosticCode": "WINRAR_UNAVAILABLE"}

    with tempfile.TemporaryDirectory(prefix="SYNTHETIC-winrar-progress-") as temp:
        root = Path(temp)
        normal, cancellation_input = _write_synthetic_inputs(root)
        help_result = _run(executable, ["-?"], root)
        version_match = re.search(rb"\bRAR\s+(\d+\.\d+)\s+(x64|x86)", help_result.stdout)

        single_runs = []
        for run_number in (1, 2):
            args = [
                "a", "-r", "-y", "-idn",
                f"SYNTHETIC_SINGLE_{run_number}.rar",
                str(normal.relative_to(root) / "SYNTHETIC_TEST_FIXTURE_3.bin"),
            ]
            single_runs.append(_run(executable, args, root))
        single = assess_progress_runs([
            result.stdout + result.stderr for result in single_runs
        ])
        multi, multi_raw = _run_twice(
            executable, root, "multi", ["a", "-r", "-y", "-idn"],
        )
        volumes, volumes_raw = _run_twice(
            executable, root, "volumes",
            ["a", "-r", "-y", "-idn", "-v8388608b"],
        )

        failure_result = _run(
            executable,
            ["a", "-r", "-y", "-idn", "SYNTHETIC_FAILURE.rar", "SYNTHETIC_MISSING_*"],
            root,
        )
        failure = _raw_summary(failure_result)
        cancellation = _cancel(executable, root, cancellation_input)
        legacy_silent = _raw_summary(_run(
            executable,
            ["a", "-r", "-y", "-inul", "SYNTHETIC_LEGACY.rar", normal.name],
            root,
        ))

    normal_cases = {"single": single, "multi": multi, "volumes": volumes}
    return {
        "status": decide_adapter(normal_cases, failure, cancellation, legacy_silent),
        "executableName": executable.name,
        "version": version_match.group(1).decode() if version_match else None,
        "architecture": version_match.group(2).decode() if version_match else None,
        "captureMethod": "ordinary-pipe",
        "signalSource": "raw-stdout-ascii-percent-token",
        "commands": {
            "single": ["a", "-r", "-y", "-idn", "<archive>", "<single-file>"],
            "multi": ["a", "-r", "-y", "-idn", "<archive>", "<input-root>"],
            "volumes": [
                "a", "-r", "-y", "-idn", "-v8388608b", "<archive>", "<input-root>",
            ],
            "legacy": ["a", "-r", "-y", "-inul", "<archive>", "<input-root>"],
        },
        "normalCases": normal_cases,
        "rawEvidence": {
            "single": [_raw_summary(result) for result in single_runs],
            "multi": multi_raw,
            "volumes": volumes_raw,
        },
        "failure": failure,
        "cancellation": cancellation,
        "legacySilent": legacy_silent,
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
                "diagnosticCode": capability.diagnostic_code,
            }, indent=2))
            return 0
        executable = Path(capability.executable_path)
    print(json.dumps(run_probe(executable), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
