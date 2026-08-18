# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "packages" / "backend"

a = Analysis(
    [str(BACKEND / "app" / "portable_entry.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("app"),
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="backend", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=True,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=False, name="backend",
)
