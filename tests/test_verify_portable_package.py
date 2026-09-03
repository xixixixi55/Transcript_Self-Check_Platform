"""便携发布白名单与哈希的 SYNTHETIC 测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "verify-portable-package.py"
BUILD_SCRIPT = Path(__file__).parents[1] / "scripts" / "build-portable.ps1"
SPEC = importlib.util.spec_from_file_location("verify_portable_package", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def manifest() -> dict:
    return {
        "schema_version": 1,
        "version": "TEST",
        "required_paths": [
            "文枢.exe", "runtime/backend/backend.exe", "runtime/node/node.exe", "runtime/node/LICENSE",
            "tools/officecli/officecli.js", "tools/hashmyfiles/HashMyFiles.exe",
            "tools/hashmyfiles/readme.txt", "resources/word_templates/template.docx",
            "web/index.html", "THIRD-PARTY-NOTICES.txt", "VERSION",
        ],
        "allowed_globs": [
            "文枢.exe", "runtime/backend/**", "runtime/node/*",
            "tools/officecli/officecli.js", "tools/hashmyfiles/*",
            "resources/word_templates/template*.docx", "web/index.html",
            "THIRD-PARTY-NOTICES.txt", "VERSION", "PORTABLE-FILES.json",
        ],
        "forbidden_globs": ["**/*.rar", "**/.env*"],
    }


def create_valid_staging(root: Path) -> Path:
    staging = root / "文枢-vTEST"
    for relative in manifest()["required_paths"]:
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"SYNTHETIC/{relative}".encode("utf-8"))
    return staging


def test_valid_staging_generates_deterministic_file_hashes(tmp_path: Path) -> None:
    staging = create_valid_staging(tmp_path)
    files = module.validate_staging(staging, manifest())
    output = module.write_hash_manifest(staging, files, "TEST")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == "TEST"
    assert len(payload["files"]) == len(manifest()["required_paths"])
    assert all(len(item["sha256"]) == 64 for item in payload["files"])


@pytest.mark.parametrize("relative", [
    "data/workbench.sqlite3",
    "tools/rar.exe",
    "workspace/output/SYNTHETIC.rar",
    "logs/backend.log",
    "generated/SYNTHETIC.docx",
    ".env",
])
def test_forbidden_assets_fail_closed(tmp_path: Path, relative: str) -> None:
    staging = create_valid_staging(tmp_path)
    target = staging / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"SYNTHETIC/FORBIDDEN")
    with pytest.raises(module.PortablePackageError, match="PORTABLE_"):
        module.validate_staging(staging, manifest())


def test_unexpected_top_level_fails_closed(tmp_path: Path) -> None:
    staging = create_valid_staging(tmp_path)
    (staging / "SYNTHETIC-extra").mkdir()
    with pytest.raises(module.PortablePackageError, match="TOP_LEVEL"):
        module.validate_staging(staging, manifest())


def test_unknown_file_inside_allowed_top_level_fails_closed(tmp_path: Path) -> None:
    staging = create_valid_staging(tmp_path)
    unknown = staging / "tools" / "officecli" / "SYNTHETIC-secret.json"
    unknown.write_text("SYNTHETIC", encoding="utf-8")
    with pytest.raises(module.PortablePackageError, match="PATH_NOT_ALLOWED"):
        module.validate_staging(staging, manifest())


def test_missing_required_file_fails_closed(tmp_path: Path) -> None:
    staging = create_valid_staging(tmp_path)
    (staging / "runtime" / "node" / "node.exe").unlink()
    with pytest.raises(module.PortablePackageError, match="REQUIRED_PATH_MISSING"):
        module.validate_staging(staging, manifest())


def test_portable_build_prefers_versioned_local_toolchain_before_system_fallback() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    node_override = script.index("$env:BIJI_NODE_DIST_DIR")
    node_local = script.index('"node-v$($manifest.node_version)-win-x64"')
    node_system = script.index("Get-Command node.exe")
    assert node_override < node_local < node_system

    office_override = script.index("$env:BIJI_OFFICECLI_PACKAGE_DIR")
    office_local = script.index('"officecli-$($manifest.officecli_version)"')
    office_system = script.index('"npm/node_modules/@officecli/officecli"')
    assert office_override < office_local < office_system
    assert 'Join-Path $projectRoot "dist/toolchain"' in script


def test_portable_build_disables_officecli_auto_resident_for_smoke() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    smoke_start = script.index('$officeSmokeRoot = Join-Path $buildRoot "officecli-smoke"')
    smoke_end = script.index("python scripts/verify-portable-package.py", smoke_start)
    smoke_script = script[smoke_start:smoke_end]
    assert '$env:OFFICECLI_NO_AUTO_RESIDENT = "1"' in smoke_script
