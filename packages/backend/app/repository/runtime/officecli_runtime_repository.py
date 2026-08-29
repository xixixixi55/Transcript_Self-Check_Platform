"""解析并执行私有 OfficeCLI 运行时，不进行 shell 插值。"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .runtime_paths import RuntimePaths, get_runtime_paths


class OfficeCliRuntimeError(RuntimeError):
    """配置的 OfficeCLI 运行时不可用时引发的稳定错误。"""


@dataclass(frozen=True)
class OfficeCliCommand:
    prefix: tuple[str, ...]

    def arguments(self, args: Sequence[str]) -> list[str]:
        return [*self.prefix, *args]


PathLookup = Callable[[str], str | None]
Runner = Callable[..., subprocess.CompletedProcess[str]]


def resolve_officecli_command(
    paths: RuntimePaths | None = None,
    *,
    env: Mapping[str, str] | None = None,
    path_lookup: PathLookup = shutil.which,
) -> OfficeCliCommand:
    runtime_paths = paths or get_runtime_paths()
    values = os.environ if env is None else env
    if runtime_paths.portable:
        if runtime_paths.node_executable.is_file() and runtime_paths.officecli_entry.is_file():
            return OfficeCliCommand((
                str(runtime_paths.node_executable), str(runtime_paths.officecli_entry),
            ))
        raise OfficeCliRuntimeError("OFFICECLI_RUNTIME_UNAVAILABLE")
    node_override = values.get("BIJI_NODE_PATH", "").strip()
    entry_override = values.get("BIJI_OFFICECLI_ENTRY", "").strip()
    node_path = Path(node_override) if node_override else runtime_paths.node_executable
    entry_path = Path(entry_override) if entry_override else runtime_paths.officecli_entry
    if node_path.is_file() and entry_path.is_file():
        return OfficeCliCommand((str(node_path), str(entry_path)))
    global_command = path_lookup("officecli") or path_lookup("officecli.cmd")
    if global_command:
        return OfficeCliCommand((global_command,))
    raise OfficeCliRuntimeError("OFFICECLI_RUNTIME_UNAVAILABLE")


def run_officecli(
    *args: str,
    paths: RuntimePaths | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    values = dict(os.environ if env is None else env)
    system32 = str(Path(values.get("SystemRoot", r"C:\Windows")) / "System32")
    path_parts = values.get("PATH", "").split(os.pathsep)
    if system32.casefold() not in {part.casefold() for part in path_parts if part}:
        values["PATH"] = system32 + os.pathsep + values.get("PATH", "")
    command = resolve_officecli_command(paths, env=values)
    return runner(
        command.arguments(args), env=values, capture_output=True,
        encoding="utf-8", errors="replace", shell=False,
    )


__all__ = [
    "OfficeCliCommand", "OfficeCliRuntimeError",
    "resolve_officecli_command", "run_officecli",
]
