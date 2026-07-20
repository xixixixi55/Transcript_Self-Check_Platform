"""Stable errors shared by attachment planning helpers."""

from __future__ import annotations


class AttachmentPlanError(ValueError):
    """Stable error raised when a final manifest cannot produce a plan."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


__all__ = ["AttachmentPlanError"]
