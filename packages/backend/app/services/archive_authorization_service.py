"""Service boundary for fixed roots and future trusted local grants."""

from __future__ import annotations

from pathlib import Path

from ..repository.archive_authorization_repository import (
    ArchiveAuthorizationError,
    ArchiveAuthorizationStore,
    AuthorizedInputRoot,
)
from .archive_input_snapshot_layout_service import private_snapshot_root


class ArchiveAuthorizationService:
    def __init__(self, upload_base: str, output_base: str) -> None:
        self.store = ArchiveAuthorizationStore(upload_base)
        self.output_roots = (
            output_base,
            str(Path(output_base) / "compressed"),
            str(Path(output_base) / "parsed"),
            str(Path(output_base) / "exports"),
            str(Path(output_base) / "photos"),
            str(Path(output_base) / "cache"),
            str(Path(output_base) / "caches"),
            str(Path(output_base) / "temp"),
            str(Path(output_base) / "tmp"),
            str(private_snapshot_root()),
        )

    def authorize_report_directory(
        self,
        report_dir: str,
        grant_token: str | None = None,
    ) -> AuthorizedInputRoot:
        return self.store.authorize_directory(
            report_dir, grant_token=grant_token, output_roots=self.output_roots,
        )

    def authorize_server_source(
        self,
        source_root: str,
        cleanup_root: str,
    ) -> AuthorizedInputRoot:
        return self.store.authorize_server_source(
            source_root, cleanup_root, output_roots=self.output_roots,
        )

    def issue_exact_directory_grant(self, report_dir: str) -> str:
        """Reserved for a trusted desktop bridge; no ordinary HTTP route calls it."""
        return self.store.issue_exact_directory_grant(report_dir)


__all__ = [
    "ArchiveAuthorizationError",
    "ArchiveAuthorizationService",
    "AuthorizedInputRoot",
]
