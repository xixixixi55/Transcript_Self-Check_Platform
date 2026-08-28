"""第 20 层：读取本地 Windows 和火绒安装元数据。"""

from __future__ import annotations

import os
import platform
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

SystemReader = Callable[[], Mapping[str, Any]]
SoftwareReader = Callable[[], Iterable[Mapping[str, Any]]]
FileVersionReader = Callable[[Path], str | None]
PathExists = Callable[[Path], bool]

_HUORONG_SECURITY_MARKERS = (
    "火绒安全软件",
    "huorong internet security",
    "huorong security",
)


class LocalInspectionEnvironmentRepository:
    def __init__(
        self,
        system_reader: SystemReader | None = None,
        software_reader: SoftwareReader | None = None,
        file_version_reader: FileVersionReader | None = None,
        path_exists: PathExists | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._system_reader = system_reader or _read_windows_system
        self._software_reader = software_reader or _read_installed_software
        self._file_version_reader = file_version_reader or _read_windows_file_version
        self._path_exists = path_exists or Path.is_file
        self._platform_name = platform_name or os.name

    def read(self) -> dict[str, Any]:
        if self._platform_name != "nt":
            return {"operating_system": {}, "huorong": {"detected": False, "version": ""}}
        try:
            system = dict(self._system_reader())
        except (OSError, ValueError, TypeError):
            system = {}
        try:
            software = [dict(item) for item in self._software_reader()]
        except (OSError, ValueError, TypeError):
            software = []
        return {"operating_system": system, "huorong": self._find_huorong(software)}

    def _find_huorong(self, software: list[dict[str, Any]]) -> dict[str, Any]:
        match = next(
            (item for item in software if _is_huorong_security_software(item.get("display_name"))),
            None,
        )
        candidates = _huorong_executable_candidates(match)
        version = _clean(match.get("display_version")) if match else ""
        detected = match is not None
        for candidate in candidates:
            try:
                if not self._path_exists(candidate):
                    continue
                detected = True
                version = version or _clean(self._file_version_reader(candidate))
                if version:
                    break
            except (OSError, ValueError, TypeError):
                continue
        return {"detected": detected, "version": version}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_huorong_security_software(value: Any) -> bool:
    name = _clean(value).casefold()
    return any(marker in name for marker in _HUORONG_SECURITY_MARKERS)


def _read_windows_system() -> Mapping[str, Any]:
    import winreg

    key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        values = {}
        for source, target in (
            ("ProductName", "product_name"),
            ("EditionID", "edition_id"),
            ("DisplayVersion", "display_version"),
            ("CurrentBuildNumber", "build_number"),
        ):
            try:
                values[target] = winreg.QueryValueEx(key, source)[0]
            except OSError:
                values[target] = ""
    values["architecture"] = platform.machine()
    return values


def _read_installed_software() -> Iterable[Mapping[str, Any]]:
    import winreg

    uninstall = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in views:
            try:
                with winreg.OpenKey(root, uninstall, 0, winreg.KEY_READ | view) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for index in range(count):
                        yield _read_uninstall_entry(parent, winreg.EnumKey(parent, index))
            except OSError:
                continue


def _read_uninstall_entry(parent: Any, name: str) -> Mapping[str, str]:
    import winreg

    try:
        with winreg.OpenKey(parent, name) as key:
            result = {}
            for source, target in (
                ("DisplayName", "display_name"),
                ("DisplayVersion", "display_version"),
                ("InstallLocation", "install_location"),
                ("DisplayIcon", "display_icon"),
            ):
                try:
                    result[target] = _clean(winreg.QueryValueEx(key, source)[0])
                except OSError:
                    result[target] = ""
            return result
    except OSError:
        return {}


def _huorong_executable_candidates(entry: Mapping[str, Any] | None) -> list[Path]:
    candidates: list[Path] = []
    if entry:
        icon = _clean(entry.get("display_icon")).strip('"').split(",", 1)[0]
        if icon:
            candidates.append(Path(icon))
        location = _clean(entry.get("install_location"))
        if location:
            candidates.extend((
                Path(location) / "Sysdiag" / "bin" / "HipsMain.exe",
                Path(location) / "bin" / "HipsMain.exe",
            ))
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root = _clean(os.environ.get(env_name))
        if root:
            candidates.append(Path(root) / "Huorong" / "Sysdiag" / "bin" / "HipsMain.exe")
    return list(dict.fromkeys(candidates))


def _read_windows_file_version(path: Path) -> str | None:
    import ctypes
    from ctypes import wintypes

    size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not ctypes.windll.version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None
    values = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD * 13)).contents
    ms, ls = int(values[2]), int(values[3])
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
