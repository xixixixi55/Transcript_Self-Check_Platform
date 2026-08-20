"""SYNTHETIC tests for user-visible launcher startup failures."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


LAUNCHER_MAIN = Path(__file__).parents[1] / "packages" / "launcher" / "main.py"
sys.path.insert(0, str(LAUNCHER_MAIN.parent))
SPEC = importlib.util.spec_from_file_location("portable_launcher_main", LAUNCHER_MAIN)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_integrity_failure_is_shown_to_user(monkeypatch) -> None:
    messages: list[tuple[str, str, int]] = []
    monkeypatch.setattr(
        module, "resolve_launcher_paths",
        lambda **_kwargs: type("Paths", (), {"lock_file": Path("SYNTHETIC.lock")})(),
    )
    monkeypatch.setattr(
        module, "validate_program_integrity",
        lambda _paths: (_ for _ in ()).throw(module.LauncherError("SYNTHETIC integrity failure")),
    )
    monkeypatch.setattr(module, "show_message", lambda title, message, flags: messages.append((title, message, flags)))
    assert module.main() == 1
    assert messages == [("文枢启动失败", "SYNTHETIC integrity failure", module.MB_ICONERROR)]


def test_successful_start_uses_tray_and_reopens_existing_application(tmp_path: Path, monkeypatch) -> None:
    class Process:
        pid = 43210

        def poll(self):
            return None

    class Lock:
        def __init__(self, _path):
            self.released = False

        def acquire(self):
            return True

        def release(self):
            self.released = True

    class Job:
        def close(self):
            return None

    paths = type("Paths", (), {
        "lock_file": tmp_path / "launcher.lock",
        "log_root": tmp_path / "logs",
    })()
    process = Process()
    log_path = tmp_path / "backend.log"
    log_path.write_bytes(b"")
    log_handle = log_path.open("ab")
    events: list[object] = []
    monkeypatch.setattr(module, "resolve_launcher_paths", lambda **_kwargs: paths)
    monkeypatch.setattr(module, "validate_program_integrity", lambda _paths: None)
    monkeypatch.setattr(module, "SingleInstance", Lock)
    monkeypatch.setattr(module, "new_secret", lambda: "SYNTHETIC-SECRET")
    monkeypatch.setattr(module, "start_backend", lambda *_args: (process, log_handle))
    monkeypatch.setattr(module, "attach_kill_on_close_job", lambda _process: Job())
    monkeypatch.setattr(module, "wait_until_ready", lambda *_args: 32123)
    monkeypatch.setattr(module, "open_desktop_browser", lambda port, secret: events.append(("bootstrap", port, secret)))
    monkeypatch.setattr(module, "open_application_browser", lambda port: events.append(("open", port)))
    monkeypatch.setattr(module, "terminate_process_tree", lambda target: events.append(("terminate", target)))

    def run_tray(on_open, backend_alive):
        assert backend_alive() is True
        on_open()
        return "exit"

    monkeypatch.setattr(module, "run_windows_tray", run_tray)
    assert module.main() == 0
    assert events == [
        ("bootstrap", 32123, "SYNTHETIC-SECRET"),
        ("open", 32123),
        ("terminate", process),
    ]
