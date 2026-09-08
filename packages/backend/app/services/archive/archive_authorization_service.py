"""本机输入路径安全和导出目录授权的服务边界。"""

from __future__ import annotations

from pathlib import Path

from ...repository.archive.archive_authorization_repository import (
    ArchiveAuthorizationError,
    ArchiveAuthorizationStore,
    AuthorizedInputRoot,
)
from .archive_input_snapshot_layout_service import private_snapshot_root


class ArchiveAuthorizationService:
    def __init__(
        self, output_base: str,
        additional_output_roots: tuple[str, ...] = (),
    ) -> None:
        self.store = ArchiveAuthorizationStore()
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
            *additional_output_roots,
        )

    def authorize_report_directory(
        self,
        report_dir: str,
    ) -> AuthorizedInputRoot:
        return self.store.authorize_directory(
            report_dir,
            output_roots=self.output_roots,
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
        """为受控的案件导出目录签发一次性授权。"""
        return self.store.issue_exact_directory_grant(report_dir)

    def consume_exact_directory_grant(self, token: str, selected_path: str) -> bool:
        """使用原生导出目录选择器产生的一次性授权。

        对未知、过期、已使用或路径不匹配的令牌返回 False，使 export-bundle 始终仅写入
        选择器授权的路径。
        """
        try:
            self.store._consume_grant(token, Path(selected_path).resolve(strict=False))
            return True
        except ArchiveAuthorizationError:
            return False


__all__ = [
    "ArchiveAuthorizationError",
    "ArchiveAuthorizationService",
    "AuthorizedInputRoot",
]
