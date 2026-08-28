"""最小化的 Windows ConPTY 捕获与可见终端进度模型。"""

from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_SUSPENDED = 0x00000004
STARTF_USESTDHANDLES = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
WAIT_TIMEOUT = 0x00000102


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


@dataclass(frozen=True)
class ConPtyResult:
    return_code: int
    output: bytes
    cancelled: bool
    tree_termination_succeeded: bool
    duration_ms: int


def _check(result: object, operation: str) -> object:
    if not result:
        raise ctypes.WinError(ctypes.get_last_error(), operation)
    return result


def _configure_kernel32(kernel32: object) -> None:
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreatePseudoConsole.restype = ctypes.c_long
    kernel32.ClosePseudoConsole.argtypes = [ctypes.c_void_p]
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
    ]


def _read_pipe(kernel32: object, handle: wintypes.HANDLE, chunks: list[bytes]) -> None:
    while True:
        buffer = ctypes.create_string_buffer(4096)
        count = wintypes.DWORD()
        if not kernel32.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
            break
        if count.value:
            chunks.append(buffer.raw[:count.value])


def run_conpty(
    executable: Path,
    args: Sequence[str],
    cwd: Path,
    *,
    cancel_after_seconds: float | None = None,
) -> ConPtyResult:
    if os.name != "nt":
        raise OSError("ConPTY is available only on Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _configure_kernel32(kernel32)
    input_read, input_write = wintypes.HANDLE(), wintypes.HANDLE()
    output_read, output_write = wintypes.HANDLE(), wintypes.HANDLE()
    _check(kernel32.CreatePipe(
        ctypes.byref(input_read), ctypes.byref(input_write), None, 0,
    ), "CreatePipe(input)")
    _check(kernel32.CreatePipe(
        ctypes.byref(output_read), ctypes.byref(output_write), None, 0,
    ), "CreatePipe(output)")
    pseudo_console = ctypes.c_void_p()
    _check(kernel32.CreatePseudoConsole(
        COORD(160, 40), input_read, output_write, 0, ctypes.byref(pseudo_console),
    ) == 0, "CreatePseudoConsole")
    kernel32.CloseHandle(input_read)
    kernel32.CloseHandle(output_write)

    attribute_size = ctypes.c_size_t()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attribute_size))
    attribute_buffer = ctypes.create_string_buffer(attribute_size.value)
    attribute_list = ctypes.cast(attribute_buffer, ctypes.c_void_p)
    _check(kernel32.InitializeProcThreadAttributeList(
        attribute_list, 1, 0, ctypes.byref(attribute_size),
    ), "InitializeProcThreadAttributeList")
    _check(kernel32.UpdateProcThreadAttribute(
        attribute_list, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
        pseudo_console, ctypes.sizeof(ctypes.c_void_p), None, None,
    ), "UpdateProcThreadAttribute")

    startup = STARTUPINFOEXW()
    startup.StartupInfo.cb = ctypes.sizeof(startup)
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
    startup.StartupInfo.hStdInput = None
    startup.StartupInfo.hStdOutput = None
    startup.StartupInfo.hStdError = None
    startup.lpAttributeList = attribute_list
    process = PROCESS_INFORMATION()
    command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(executable), *args]))
    flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | CREATE_SUSPENDED
    _check(kernel32.CreateProcessW(
        None, command, None, None, False, flags, None, str(cwd),
        ctypes.byref(startup), ctypes.byref(process),
    ), "CreateProcessW")

    job = kernel32.CreateJobObjectW(None, None)
    _check(job, "CreateJobObjectW")
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    _check(kernel32.SetInformationJobObject(
        job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits),
        ctypes.sizeof(limits),
    ), "SetInformationJobObject")
    _check(kernel32.AssignProcessToJobObject(job, process.hProcess), "AssignProcessToJobObject")
    _check(kernel32.ResumeThread(process.hThread) != 0xFFFFFFFF, "ResumeThread")
    kernel32.CloseHandle(process.hThread)
    kernel32.CloseHandle(input_write)

    chunks: list[bytes] = []
    reader = threading.Thread(
        target=_read_pipe, args=(kernel32, output_read, chunks), daemon=True,
    )
    started = time.monotonic()
    reader.start()
    timeout_ms = (
        int(cancel_after_seconds * 1000) if cancel_after_seconds is not None else 60000
    )
    wait_result = kernel32.WaitForSingleObject(process.hProcess, timeout_ms)
    cancelled = wait_result == WAIT_TIMEOUT and cancel_after_seconds is not None
    terminated = False
    if cancelled:
        terminated = bool(kernel32.TerminateJobObject(job, 1))
        kernel32.WaitForSingleObject(process.hProcess, 10000)
    exit_code = wintypes.DWORD()
    _check(kernel32.GetExitCodeProcess(process.hProcess, ctypes.byref(exit_code)), "GetExitCodeProcess")
    kernel32.ClosePseudoConsole(pseudo_console)
    reader.join(timeout=10)
    duration_ms = round((time.monotonic() - started) * 1000)

    kernel32.DeleteProcThreadAttributeList(attribute_list)
    kernel32.CloseHandle(output_read)
    kernel32.CloseHandle(process.hProcess)
    kernel32.CloseHandle(job)
    return ConPtyResult(exit_code.value, b"".join(chunks), cancelled, terminated, duration_ms)
