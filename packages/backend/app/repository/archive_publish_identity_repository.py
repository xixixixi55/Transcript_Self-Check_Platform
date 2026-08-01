"""Serialization and immutable identity checks for publish intents."""

from __future__ import annotations

import json
from typing import Any


def intent_dict(row: Any) -> dict[str, Any]:
    value = dict(row)
    value["source_revision"] = int(value["source_revision"])
    value["draft_revision"] = int(value["draft_revision"])
    value["public_manifest"] = json.loads(value.pop("public_manifest_json"))
    raw_file_set = value.pop("publication_file_set_json", None)
    value["publication_file_set"] = None if raw_file_set is None else json.loads(raw_file_set)
    return value


def same_publish_identity(
    connection: Any, existing: Any, *, attempt_id: str, case_id: str,
    source_id: str, source_revision: int, draft_revision: int,
    report_fingerprint: str, source_key: str, input_fingerprint: str,
    archive_fingerprint: str, manifest_id: str, relative_final_dir: str,
    serialized_manifest: str, context_hash: str, task_id: str,
    deployment_instance_id: str, publication_id: str,
) -> bool:
    expected = {
        "attempt_id": attempt_id, "case_id": case_id, "source_id": source_id,
        "source_revision": source_revision, "draft_revision": draft_revision,
        "report_fingerprint": report_fingerprint, "source_key": source_key,
        "input_fingerprint": input_fingerprint, "archive_fingerprint": archive_fingerprint,
        "manifest_id": manifest_id, "relative_final_dir": relative_final_dir,
        "public_manifest_json": serialized_manifest, "task_id": task_id,
        "deployment_instance_id": deployment_instance_id, "publication_id": publication_id,
        "publication_relative_dir": relative_final_dir,
    }
    if any(existing[key] != value for key, value in expected.items()):
        return False
    fence = connection.execute(
        "SELECT * FROM archive_publish_fences WHERE fence_id=? AND attempt_id=? "
        "AND deployment_instance_id=?",
        (existing["fence_id"], attempt_id, deployment_instance_id),
    ).fetchone()
    return bool(
        fence is not None
        and fence["fence_id"] == f"fence-{attempt_id}"
        and fence["case_id"] == case_id
        and fence["attempt_id"] == attempt_id
        and fence["task_id"] == task_id
        and fence["deployment_instance_id"] == deployment_instance_id
        and fence["source_id"] == source_id
        and int(fence["source_revision"]) == source_revision
        and int(fence["draft_revision"]) == draft_revision
        and fence["report_fingerprint"] == report_fingerprint
        and fence["context_hash"] == context_hash
        and fence["status"] in {"active", "pending_verification", "consumed"}
    )
