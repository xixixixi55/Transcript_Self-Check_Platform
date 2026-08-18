# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

ROOT = Path(SPECPATH).parent
LAUNCHER = ROOT / "packages" / "launcher"
GENERATED = Path(os.environ["BIJI_LAUNCHER_GENERATED_DIR"])

a = Analysis(
    [str(LAUNCHER / "main.py")],
    pathex=[str(GENERATED), str(LAUNCHER)],
    binaries=[], datas=[], hiddenimports=[], hookspath=[], runtime_hooks=[],
    excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="文枢", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
