"""不透明案件资产的受控二进制存储。"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from .workbench_serialization import validate_opaque_id


class CaseAssetStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def stage(self, case_id: str, suffix: str, content: bytes) -> Path:
        directory = self._case_directory(case_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f".upload-{secrets.token_hex(16)}{suffix}"
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def finalize(self, staged: Path, case_id: str, asset_id: str, suffix: str) -> None:
        target = self.path_for(case_id, asset_id, suffix)
        os.replace(staged, target)

    def discard(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def read(self, case_id: str, asset_id: str, suffix: str) -> bytes:
        return self.path_for(case_id, asset_id, suffix).read_bytes()

    def delete(self, case_id: str, asset_id: str, suffix: str) -> None:
        self.path_for(case_id, asset_id, suffix).unlink(missing_ok=True)

    def path_for(self, case_id: str, asset_id: str, suffix: str) -> Path:
        case_id = validate_opaque_id(case_id)
        asset_id = validate_opaque_id(asset_id)
        if suffix not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("unsupported asset suffix")
        path = (self.root / case_id / f"{asset_id}{suffix}").resolve()
        path.relative_to(self.root)
        return path

    def files_for_case(self, case_id: str) -> tuple[Path, ...]:
        directory = self._case_directory(case_id)
        if not directory.is_dir():
            return ()
        return tuple(path for path in directory.iterdir() if path.is_file())

    def case_ids(self) -> tuple[str, ...]:
        return tuple(path.name for path in self.root.iterdir() if path.is_dir())

    def _case_directory(self, case_id: str) -> Path:
        case_id = validate_opaque_id(case_id)
        directory = (self.root / case_id).resolve()
        directory.relative_to(self.root)
        return directory
