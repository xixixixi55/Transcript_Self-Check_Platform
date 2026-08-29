"""不泄露路径的 WinRAR 发现和能力探测。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class WinRarCapability:
    available: bool
    executable_path: str | None
    executable_name: str | None
    version: str | None
    supports_rar_volumes: bool
    diagnostic_code: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "executable_name": self.executable_name if self.available else None,
            "version": self.version,
            "supports_rar_volumes": self.supports_rar_volumes,
        }


ProbeRunner = Callable[..., subprocess.CompletedProcess[str]]
_STANDARD_PATHS = (
    r"C:\Program Files\WinRAR\rar.exe",
    r"C:\Program Files\WinRAR\WinRAR.exe",
    r"C:\Program Files (x86)\WinRAR\rar.exe",
    r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
)


def _safe_probe_output(result: subprocess.CompletedProcess[str]) -> str:
    text = f"{result.stdout or ''}\n{result.stderr or ''}"
    return re.sub(r"[A-Za-z]:\\[^\r\n]*", "", text)


def _probe_candidate(candidate: Path, probe_runner: ProbeRunner) -> WinRarCapability | None:
    # WinRAR.exe 是 GUI 二进制文件：`-?` 会打开窗口且不提供控制台帮助。
    # 优先使用同一安装目录中的控制台版本，确保探测绝不启动 GUI 交互。
    if candidate.name.casefold() == "winrar.exe":
        console_sibling = candidate.with_name("rar.exe")
        if console_sibling.is_file():
            return _probe_candidate(console_sibling, probe_runner)
        return None
    if not candidate.is_file():
        return None
    try:
        result = probe_runner(
            [str(candidate), "-?"], capture_output=True, text=True,
            timeout=10, shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = _safe_probe_output(result)
    match = re.search(r"(?:WinRAR|RAR)\s+([0-9]+\.[0-9]+)", output, re.IGNORECASE)
    # WinRAR 与控制台 RAR 二进制文件对此开关的文档表述不同：
    # WinRAR 通常显示 `-v<bytes>b`，而 RAR 5.x 显示 `v<size>[k,b]`。
    # 两种形式都能证明该可执行文件公开了分卷开关。
    supports_volumes = bool(
        re.search(r"(?:-v(?:\d|<)|\bv\s*<size>|\bvolume)", output, re.IGNORECASE)
    )
    return WinRarCapability(
        True, str(candidate), candidate.name, match.group(1) if match else None,
        supports_volumes,
    )


def discover_winrar(
    configured_path: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    path_lookup: Callable[[str], str | None] = shutil.which,
    probe_runner: ProbeRunner = subprocess.run,
) -> WinRarCapability:
    """依次使用配置路径、环境变量、PATH 和标准安装位置。"""

    environment = os.environ if env is None else env
    seen: set[str] = set()

    def try_candidates(candidates: tuple[Path, ...]) -> WinRarCapability | None:
        for candidate in candidates:
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            capability = _probe_candidate(candidate, probe_runner)
            if capability and capability.supports_rar_volumes:
                return capability
        return None

    capability = try_candidates(tuple(Path(path) for path in (configured_path,))) if configured_path else None
    if capability:
        return capability
    env_path = environment.get("BIJI_WINRAR_PATH")
    capability = try_candidates(tuple(Path(path) for path in (env_path,))) if env_path else None
    if capability:
        return capability
    path_candidates = tuple(
        Path(found) for name in ("WinRAR.exe", "rar.exe")
        if (found := path_lookup(name))
    )
    capability = try_candidates(path_candidates)
    if capability:
        return capability
    capability = try_candidates(tuple(Path(path) for path in _STANDARD_PATHS))
    if capability:
        return capability
    return WinRarCapability(
        False, None, None, None, False, "WINRAR_UNAVAILABLE",
    )
