"""验证并打包便携式 Windows 暂存目录。"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePosixPath

ALLOWED_TOP_LEVEL = {
    "文枢.exe", "runtime", "web", "resources", "tools", "licenses",
    "THIRD-PARTY-NOTICES.txt", "portable-manifest.json", "VERSION",
    "使用说明.txt", "PORTABLE-FILES.json",
}
FORBIDDEN_DIRECTORY_NAMES = {
    "uploads", "output", "logs", "__pycache__", ".pytest_cache", ".git",
}
FORBIDDEN_FILE_NAMES = {"winrar.exe", "rar.exe", ".env", "workbench.sqlite3"}
PYTHON_DOCX_DEFAULT_TEMPLATE = PurePosixPath(
    "runtime/backend/_internal/docx/templates/default.docx",
)


class PortablePackageError(RuntimeError):
    pass


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PortablePackageError("PORTABLE_MANIFEST_INVALID") from error
    required = {
        "schema_version", "product", "version", "platform",
        "required_paths", "allowed_globs", "forbidden_globs",
    }
    if not required.issubset(manifest) or manifest["schema_version"] != 1:
        raise PortablePackageError("PORTABLE_MANIFEST_INVALID")
    if not all(isinstance(manifest[key], list) for key in (
        "required_paths", "allowed_globs", "forbidden_globs",
    )):
        raise PortablePackageError("PORTABLE_MANIFEST_INVALID")
    return manifest


def validate_staging(staging: Path, manifest: dict) -> list[Path]:
    if not staging.is_dir():
        raise PortablePackageError("PORTABLE_STAGING_MISSING")
    top_level = {path.name for path in staging.iterdir()}
    unexpected = top_level - ALLOWED_TOP_LEVEL
    if unexpected:
        raise PortablePackageError("PORTABLE_TOP_LEVEL_NOT_ALLOWED")
    for relative in manifest["required_paths"]:
        if not (staging / Path(relative)).is_file():
            raise PortablePackageError(f"PORTABLE_REQUIRED_PATH_MISSING:{relative}")
    if "portable-manifest.json" in manifest["required_paths"]:
        try:
            packaged_manifest = json.loads(
                (staging / "portable-manifest.json").read_text(encoding="utf-8"),
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PortablePackageError("PORTABLE_PACKAGED_MANIFEST_INVALID") from error
        if packaged_manifest != manifest:
            raise PortablePackageError("PORTABLE_PACKAGED_MANIFEST_MISMATCH")
    entries = sorted(staging.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise PortablePackageError("PORTABLE_LINK_NOT_ALLOWED")
    files = [path for path in entries if path.is_file()]
    for path in files:
        relative = PurePosixPath(path.relative_to(staging).as_posix())
        if not any(fnmatch.fnmatchcase(relative.as_posix(), pattern) for pattern in manifest["allowed_globs"]):
            raise PortablePackageError(f"PORTABLE_PATH_NOT_ALLOWED:{relative}")
        lowered_parts = {part.casefold() for part in relative.parts}
        if lowered_parts & FORBIDDEN_DIRECTORY_NAMES:
            raise PortablePackageError(f"PORTABLE_FORBIDDEN_ASSET:{relative}")
        if path.name.casefold() in FORBIDDEN_FILE_NAMES or path.name.casefold().startswith("workbench.sqlite3-"):
            raise PortablePackageError(f"PORTABLE_FORBIDDEN_ASSET:{relative}")
        if path.suffix.casefold() == ".rar" or path.suffix.casefold() == ".log":
            raise PortablePackageError(f"PORTABLE_FORBIDDEN_ASSET:{relative}")
        if (
            path.suffix.casefold() == ".docx"
            and relative.parts[:2] != ("resources", "word_templates")
            and relative != PYTHON_DOCX_DEFAULT_TEMPLATE
        ):
            raise PortablePackageError(f"PORTABLE_GENERATED_DOCX:{relative}")
        if any(relative.match(pattern) for pattern in manifest["forbidden_globs"]):
            raise PortablePackageError(f"PORTABLE_FORBIDDEN_ASSET:{relative}")
    return files


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_hash_manifest(staging: Path, files: list[Path], version: str) -> Path:
    payload = {
        "schema_version": 1,
        "version": version,
        "files": [
            {
                "path": path.relative_to(staging).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in files
        ],
    }
    output = staging / "PORTABLE-FILES.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def build_zip(staging: Path, output_dir: Path, version: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_base = output_dir / f"文枢-v{version}-portable-x64"
    archive_path = Path(str(archive_base) + ".zip")
    archive_path.unlink(missing_ok=True)
    generated = Path(shutil.make_archive(
        str(archive_base), "zip", root_dir=staging.parent, base_dir=staging.name,
    ))
    Path(str(archive_path) + ".sha256").write_text(
        f"{file_sha256(generated)}  {generated.name}\n", encoding="utf-8",
    )
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("packaging/portable-manifest.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        files = validate_staging(args.staging, manifest)
        hash_manifest = write_hash_manifest(args.staging, files, str(manifest["version"]))
        if args.output is not None:
            archive = build_zip(args.staging, args.output, str(manifest["version"]))
            print(json.dumps({
                "status": "ok", "files": len(files) + 1,
                "manifest": str(hash_manifest), "archive": str(archive),
            }, ensure_ascii=False))
        else:
            print(json.dumps({"status": "ok", "files": len(files) + 1}, ensure_ascii=False))
        return 0
    except PortablePackageError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
