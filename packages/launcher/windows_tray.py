"""Native Windows notification-area lifecycle for the portable launcher."""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable
from ctypes import wintypes


class TrayError(RuntimeError):
    """Raised when Windows cannot create the notification-area icon."""


WM_APP = 0x8000
WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_NULL = 0x0000
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
IDI_APPLICATION = 32512
TRAY_MESSAGE = WM_APP + 1
TIMER_ID = 1
OPEN_COMMAND = 1001
EXIT_COMMAND = 1002


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
)


class WndClass(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


class NotifyIconData(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD), ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class TrayController:
    """Small testable state machine behind the native message loop."""

    def __init__(self, on_open: Callable[[], None], backend_alive: Callable[[], bool]) -> None:
        self.on_open = on_open
        self.backend_alive = backend_alive
        self.result = "exit"

    def open_application(self) -> None:
        self.on_open()

    def poll_backend(self) -> bool:
        if self.backend_alive():
            return True
        self.result = "backend_stopped"
        return False


class WindowsTray:
    """Own a hidden Win32 window and its notification-area icon."""

    def __init__(self, controller: TrayController) -> None:
        if os.name != "nt":
            raise TrayError("系统托盘仅支持 Windows 桌面环境。")
        self.controller = controller
        self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        self.kernel32 = ctypes.windll.kernel32
        self.class_name = f"WenshuTrayWindow-{os.getpid()}"
        self.hwnd = None
        self.hicon = None
        self.owns_icon = False
        self.icon_data = None
        self._wndproc = WNDPROC(self._window_proc)
        self._configure_api()

    def _configure_api(self) -> None:
        self.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self.user32.RegisterClassW.argtypes = [ctypes.POINTER(WndClass)]
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ]
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        ]
        self.user32.DefWindowProcW.restype = ctypes.c_ssize_t
        self.user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID]
        self.user32.SetTimer.restype = ctypes.c_size_t
        self.user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
        self.user32.DestroyWindow.argtypes = [wintypes.HWND]
        self.user32.DestroyIcon.argtypes = [wintypes.HICON]
        self.user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self.user32.CreatePopupMenu.restype = wintypes.HMENU
        self.user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, wintypes.HWND, wintypes.LPVOID,
        ]
        self.user32.TrackPopupMenu.restype = wintypes.UINT
        self.user32.PostMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        ]
        self.user32.DestroyMenu.argtypes = [wintypes.HMENU]
        self.user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
        self.user32.LoadIconW.restype = wintypes.HICON
        self.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NotifyIconData)]
        self.shell32.ExtractIconExW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON),
            ctypes.POINTER(wintypes.HICON), wintypes.UINT,
        ]
        self.shell32.ExtractIconExW.restype = wintypes.UINT

    def run(self) -> str:
        self._create_window()
        self._add_icon()
        self.user32.SetTimer(self.hwnd, TIMER_ID, 1000, None)
        message = wintypes.MSG()
        try:
            while True:
                status = self.user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if status == 0:
                    break
                if status == -1:
                    raise TrayError("无法读取系统托盘消息，请重新启动文枢。")
                self.user32.TranslateMessage(ctypes.byref(message))
                self.user32.DispatchMessageW(ctypes.byref(message))
        finally:
            self._remove_icon()
            if self.hicon and self.owns_icon:
                self.user32.DestroyIcon(self.hicon)
                self.hicon = None
        return self.controller.result

    def _create_window(self) -> None:
        instance = self.kernel32.GetModuleHandleW(None)
        window_class = WndClass()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = instance
        window_class.lpszClassName = self.class_name
        if not self.user32.RegisterClassW(ctypes.byref(window_class)):
            raise TrayError("无法注册系统托盘窗口，请重新启动文枢。")
        self.hwnd = self.user32.CreateWindowExW(
            0, self.class_name, "文枢", 0, 0, 0, 0, 0, None, None, instance, None,
        )
        if not self.hwnd:
            raise TrayError("无法创建系统托盘窗口，请重新启动文枢。")

    def _load_icon(self):
        large = wintypes.HICON()
        small = wintypes.HICON()
        if self.shell32.ExtractIconExW(sys.executable, 0, ctypes.byref(large), ctypes.byref(small), 1):
            chosen = small or large
            if large and chosen != large:
                self.user32.DestroyIcon(large)
            if small and chosen != small:
                self.user32.DestroyIcon(small)
            self.owns_icon = bool(chosen)
            return chosen
        self.owns_icon = False
        return self.user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def _add_icon(self) -> None:
        self.hicon = self._load_icon()
        data = NotifyIconData()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
        data.uCallbackMessage = TRAY_MESSAGE
        data.hIcon = self.hicon
        data.szTip = "文枢"
        data.szInfoTitle = "文枢正在运行"
        data.szInfo = "文枢已在后台运行，可通过托盘图标重新打开或退出。"
        data.dwInfoFlags = NIIF_INFO
        if not self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            raise TrayError("无法添加系统托盘图标，请重新启动文枢。")
        self.icon_data = data

    def _remove_icon(self) -> None:
        if self.icon_data is not None:
            self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.icon_data))
            self.icon_data = None

    def _show_menu(self) -> None:
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        menu = self.user32.CreatePopupMenu()
        if not menu:
            return
        try:
            self.user32.AppendMenuW(menu, MF_STRING, OPEN_COMMAND, "打开文枢")
            self.user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            self.user32.AppendMenuW(menu, MF_STRING, EXIT_COMMAND, "退出文枢")
            self.user32.SetForegroundWindow(self.hwnd)
            command = self.user32.TrackPopupMenu(
                menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                point.x, point.y, 0, self.hwnd, None,
            )
            if command == OPEN_COMMAND:
                self.controller.open_application()
            elif command == EXIT_COMMAND:
                self.user32.DestroyWindow(self.hwnd)
            self.user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        finally:
            self.user32.DestroyMenu(menu)

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == TRAY_MESSAGE:
            if lparam == WM_LBUTTONDBLCLK:
                self.controller.open_application()
            elif lparam == WM_RBUTTONUP:
                self._show_menu()
            return 0
        if message == WM_TIMER and wparam == TIMER_ID:
            if not self.controller.poll_backend():
                self.user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            self.user32.KillTimer(hwnd, TIMER_ID)
            self._remove_icon()
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, message, wparam, lparam)


def run_windows_tray(
    on_open: Callable[[], None], backend_alive: Callable[[], bool],
) -> str:
    """Run until the user exits or the owned backend stops."""
    return WindowsTray(TrayController(on_open, backend_alive)).run()


__all__ = ["TrayController", "TrayError", "WindowsTray", "run_windows_tray"]
