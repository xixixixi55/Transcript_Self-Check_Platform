"""Shared synthetic setup for case cleanup repository tests."""

from app.repository import (
    CaseDraftRepository,
    CaseRetentionRepository,
    CaseShellRepository,
    CleanupRunRepository,
    FormalWordArtifactRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
)

CASE_ID = "SYNTHETIC-CASE-TOMBSTONE"
SOURCE_ID = "SYNTHETIC-SOURCE-TOMBSTONE"
TASK_ID = "SYNTHETIC-TASK-TOMBSTONE"
RUN_ID = "SYNTHETIC-RUN-TOMBSTONE"
OWNER_ID = "SYNTHETIC-OWNER-TOMBSTONE"
CLAIM_TOKEN = "SYNTHETIC-CLAIM-TOMBSTONE"
PUBLICATION_ID = "SYNTHETIC-PUBLICATION-TOMBSTONE"
WORD_ID = "SYNTHETIC-WORD-TOMBSTONE"
TIME = "2026-08-02T00:00:00Z"
REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport",
    "document_number": "SYNTHETIC-DOC-001",
    "introduction": {
        "entrust_unit": "SYNTHETIC-UNIT",
        "entrust_persons": [],
        "entrust_time": "",
        "case_summary": "SYNTHETIC",
        "evidence_list": [],
        "inspection_requirement": "",
        "inspection_time_range": "",
        "inspectors": [],
        "inspection_place": "SYNTHETIC-PLACE",
    },
    "inspection": {
        "method": "SYNTHETIC-METHOD",
        "hardware_device": "SYNTHETIC-HARDWARE",
        "software_tools": [],
        "process_steps": [],
        "result": {
            "evidence_number": "",
            "software_name": "SYNTHETIC-TOOL",
            "software_version": "1",
            "data_summary": "SYNTHETIC",
            "rar_filename": "SYNTHETIC.rar",
            "md5_hash": "SYNTHETIC-MD5",
            "file_size": "0",
        },
    },
    "attachments": {
        "extract_list": {"columns": [], "rows": []},
        "photo_ids": [],
        "disc_number": "",
    },
}


def prepare_tombstone_case(database: WorkbenchDatabase) -> dict[str, object]:
    CaseShellRepository(database).create({
        "case_id": CASE_ID,
        "case_name": "SYNTHETIC/TEST/Case",
        "case_summary": "SYNTHETIC/TEST/Editable summary",
        "source_id": SOURCE_ID,
        "parse_task_id": TASK_ID,
    })
    TaskRecordRepository(database).create({
        "task_id": TASK_ID,
        "case_id": CASE_ID,
        "kind": "archive",
        "status": "succeeded",
        "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": SOURCE_ID,
        "case_id": CASE_ID,
        "task_id": TASK_ID,
        "source_type": "report_directory",
        "internal_path": "SYNTHETIC/TEST/source",
        "allowed_root": "SYNTHETIC/TEST",
        "allowed_root_id": "SYNTHETIC-ROOT",
        "fingerprint": "SYNTHETIC-FINGERPRINT",
        "metadata": {},
    })
    shells = CaseShellRepository(database)
    shells.update_lifecycle(CASE_ID, "parsing", 0)
    CaseDraftRepository(database).save({
        "case_id": CASE_ID,
        "report": REPORT,
        "asset_refs": [],
        "field_states": {},
    })
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET lifecycle='record_retention_expired',revision=revision+1 "
            "WHERE case_id=? AND revision=2",
            (CASE_ID,),
        )
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,source_revision,draft_revision,report_fingerprint,status,cleanup_status,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            (
                "SYNTHETIC-ATTEMPT-TOMBSTONE", 1, CASE_ID, TASK_ID,
                database.deployment_instance_id, SOURCE_ID, 0, 0, 1,
                "SYNTHETIC-REPORT", "succeeded", TIME,
            ),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,archive_fingerprint,manifest_id,"
            "relative_final_dir,public_manifest_json,publication_id,publication_relative_dir,publication_digest,"
            "publication_file_set_json,publication_status,fence_id,phase,publication_verified_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "SYNTHETIC-INTENT-TOMBSTONE", "SYNTHETIC-ATTEMPT-TOMBSTONE",
                TASK_ID, database.deployment_instance_id, CASE_ID, SOURCE_ID,
                0, 1, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY",
                "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE", "SYNTHETIC-MANIFEST",
                "formal", "{}", PUBLICATION_ID, "formal", "c" * 64, "[]",
                "verified", "SYNTHETIC-FENCE-TOMBSTONE", "verified", TIME, TIME, TIME,
            ),
        )
    FormalWordArtifactRepository(database).create({
        "word_artifact_id": WORD_ID,
        "case_id": CASE_ID,
        "publication_id": PUBLICATION_ID,
        "internal_relative_path": "formal/SYNTHETIC.docx",
        "file_digest": "a" * 64,
        "file_size": 12,
        "source_manifest_digest": "b" * 64,
        "template_identity": "legacy",
        "template_version": "v1",
        "generated_at": TIME,
        "status": "verified",
        "verified_at": TIME,
    })
    CaseRetentionRepository(database).upsert({
        "retention_record_id": "SYNTHETIC-RETENTION-TOMBSTONE",
        "case_id": CASE_ID,
        "eligibility": "eligible",
        "status": "processing",
        "last_meaningful_mutation_at": TIME,
        "latest_verified_formal_publication_at": TIME,
        "latest_successful_word_export_at": TIME,
        "retention_anchor_utc": TIME,
        "expires_at_utc": "2026-09-01T00:00:00Z",
        "policy_revision": 1,
        "case_revision": 3,
        "cleanup_revision": 0,
        "created_at": TIME,
        "updated_at": TIME,
    })
    runs = CleanupRunRepository(database)
    runs.create_planned({
        "cleanup_run_id": RUN_ID,
        "case_id": CASE_ID,
        "policy_revision": 1,
        "case_revision_at_plan": 3,
    })
    claimed = runs.claim(
        RUN_ID,
        owner_instance_id=OWNER_ID,
        claim_token=CLAIM_TOKEN,
        lease_expires_at="2026-08-03T00:00:00Z",
        expected_case_revision=3,
        expected_policy_revision=1,
        now=TIME,
    )
    runs.transition(
        RUN_ID,
        from_phase="claimed",
        to_phase="preflighted",
        owner_instance_id=OWNER_ID,
        claim_token=CLAIM_TOKEN,
        expected_fence_epoch=claimed["fence_epoch"],
        expected_case_revision=3,
        now=TIME,
    )
    runs.transition(
        RUN_ID,
        from_phase="preflighted",
        to_phase="work_files_cleaned",
        owner_instance_id=OWNER_ID,
        claim_token=CLAIM_TOKEN,
        expected_fence_epoch=claimed["fence_epoch"],
        expected_case_revision=3,
        now=TIME,
    )
    return {"run": claimed, "fence_epoch": claimed["fence_epoch"]}
