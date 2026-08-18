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
