"""第 22 层：报告解析和 DOCX 导出控制器。"""
import os, shutil, tempfile
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from ..services.report.report_parser_service import parse_report
from ..services.archive_parse_runtime_service import parse_archive_with_reuse as parse_from_archive
from ..services.record_generator_service import generate_docx
from ..services.export_gate_service import ExportGateInput, evaluate_export_gate
from ..services.legacy_report_projection_service import project_ordered_legacy_report
from ..services.material_policy_service import enrich_report_material_types, unconfirmed_material_fields
from ..services.software_policy_service import (
    is_primary_software_confirmed,
    normalize_primary_software_projection,
)
from ..services.disc_sequence_service import apply_disc_sequence_to_attachments
from ..services.archive.archive_execution_service import (
    ArchiveGateError,
    get_valid_manifest,
)
from ..services.archive.archive_manifest_projection_service import project_manifest_to_legacy_report_with_plan
from ..services.archive.archive_export_service import validate_export_directory
from ..repository.workbench_errors import WorkbenchPersistenceError
from ..services.attachment_plan_service import AttachmentPlanError
from ..services.attachment2_plan_service import material_photo_groups
from ..services.attachment2_image_service import (
    Attachment2ImageError,
    validate_attachment2_photos,
)
from ..services.template_profile_service import TemplateProfileError
from ..services.archive.archive_runtime_service import ArchiveRuntimeError
from ..services.archive.archive_source_runtime_service import (
    create_preview_source,
    get_preview_source_summary,
    resolve_archive_context_id,
)
from ..services.archive.archive_authorization_service import ArchiveAuthorizationService
from ..services.report.report_parse_error_service import report_parse_http_error
from .pipeline_controller import (
    record_shadow_export_failure_at_controller,
    observe_shadow_export,
    observe_shadow_parse,
    pipeline_settings_for_request,
)
from .record_template_context_controller import (
    resolve_case_archive_manifest,
    resolve_case_disc_mapping,
    resolve_case_template_context,
)
from ..services.workbench_factory_service import get_workbench_services
from ..config import OUTPUT_BASE, UPLOAD_BASE, ARCHIVE_MAX_SIZE
router = APIRouter()
ARCHIVE_AUTHORIZATION_SERVICE = ArchiveAuthorizationService(UPLOAD_BASE, OUTPUT_BASE)
ATTACHMENT2_SKIPPED_MESSAGE = "当前图片不完整或无效，本次 Word 未生成附件2。"


def _clear_optional_attachment2(report: dict) -> None:
    attachments = report.setdefault("attachments", {})
    attachments["photo_ids"] = []
    attachments["photo_groups"] = []


def _attachment2_warning(code: str | None) -> dict[str, str]:
    return {
        "code": code or "ATTACHMENT2_IMAGE_INVALID",
        "message": ATTACHMENT2_SKIPPED_MESSAGE,
    }


@router.post("/reports/parse")
async def parse_report_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    report_dir: str = Form(""),
    archive_file: Optional[UploadFile] = File(None),
    compress: bool = Form(True),
    directory_grant_token: str = Form(""), source_authorization_enabled: bool = Form(True),
):
    """解析文件夹或压缩包中的 HTML 报告。"""
    settings = pipeline_settings_for_request(request)
    has_dir = bool(report_dir)
    has_file = archive_file is not None and archive_file.filename
    if has_dir and has_file:
        raise HTTPException(status_code=400, detail="不能同时提供 report_dir 和 archive_file")
    if not has_dir and not has_file:
        uploads = []
        if os.path.exists(UPLOAD_BASE):
            uploads = sorted(os.listdir(UPLOAD_BASE))
        if uploads:
            report_dir = os.path.join(UPLOAD_BASE, uploads[-1])
            has_dir = True
        else:
            raise HTTPException(status_code=400, detail="请提供 report_dir 或上传压缩包文件")
    try:
        authorized_input = None
        if has_file:
            filename = archive_file.filename or ""
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".rar", ".zip"):
                raise HTTPException(status_code=400, detail="仅支持 .rar 和 .zip 格式的压缩包")
            tmp_path = os.path.join(tempfile.gettempdir(), f"biji_upload_{os.urandom(8).hex()}{ext}")
            content = await archive_file.read()
            if len(content) > ARCHIVE_MAX_SIZE:
                os.unlink(tmp_path)
                raise HTTPException(status_code=400, detail=f"文件大小超过限制（{ARCHIVE_MAX_SIZE // 1024 // 1024}MB）")
            with open(tmp_path, "wb") as f:
                f.write(content)
            try:
                result = await run_in_threadpool(parse_from_archive, tmp_path, OUTPUT_BASE, retain_source=True)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            authorized_input = await run_in_threadpool(ARCHIVE_AUTHORIZATION_SERVICE.authorize_report_directory, report_dir, directory_grant_token or None, source_authorization_enabled=source_authorization_enabled)
            result = await run_in_threadpool(parse_report, str(authorized_input.resolved_input_root), OUTPUT_BASE, compress=compress)
        result.pop("_case_metadata", None)
        result["report"] = enrich_report_material_types(result["report"])
        result["archive_context_id"] = None
        source_root = result.pop("_archive_source_root", None)
        cleanup_root = result.pop("_archive_source_cleanup_root", None)
        if source_root:
            authorized_input = await run_in_threadpool(ARCHIVE_AUTHORIZATION_SERVICE.authorize_server_source, source_root, cleanup_root or source_root)
        if authorized_input:
            result["archive_context_id"] = await run_in_threadpool(
                create_preview_source, authorized_input, cleanup_root=cleanup_root,
            )
            result["archive_context"] = await run_in_threadpool(
                get_preview_source_summary, result["archive_context_id"],
            )
            result["archive_context_kind"] = "preview_source"
        result["archive_preparation_status"] = "not_prepared"
        result["archive_context_deprecated_compress"] = True
        result["archive_status"] = "not_prepared"
        observe_shadow_parse(
            result["report"], settings, result["archive_context_id"], background_tasks,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as error:
        # 将本地路径、案件数据和解析器堆栈详情保留在服务器内部。
        raise report_parse_http_error(error) from error
@router.post("/records/export")
async def export_record_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    report_json: str = Form(""),
    archive_context_id: str = Form(""),
    manifest_id: str = Form(""),
    case_id: str = Form(""), case_revision: int | None = Form(None),
    export_path: str = Form(""), directory_token: str = Form(""),
    word_filename: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
):
    """接收 InspectionReport JSON 和图片，生成唯一正式 DOCX。"""
    settings = pipeline_settings_for_request(request)
    import json
    if not report_json:
        raise HTTPException(status_code=400, detail="请提供笔录数据")
    try:
        report = json.loads(report_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="笔录数据 JSON 格式无效")
    template_context = resolve_case_template_context(
        case_id,
        case_revision,
        allow_attachment2_revision_drift=True,
        submitted_report=report,
    )
    directory_export_requested = bool(export_path or directory_token or word_filename)
    report = normalize_primary_software_projection(report)
    attachments = report.setdefault("attachments", {})
    disc_mapping = resolve_case_disc_mapping(case_id)
    if disc_mapping.plan_exists:
        # 持久化计划是权威来源。不完整/待处理的映射必须清除旧客户端字段，
        # 以免绕过导出门禁。
        attachments["disc_number"] = disc_mapping.first_disc_number or ""
    disc_result = apply_disc_sequence_to_attachments(attachments)
    uploaded_photos = [photo for photo in photos if photo.filename]
    had_attachment2_state = bool(
        attachments.get("photo_ids") or attachments.get("photo_groups")
    )
    attachments["photo_ids"] = [f"photo-{index}" for index in range(1, len(uploaded_photos) + 1)]
    photo_warning_code = None
    if uploaded_photos:
        if len(uploaded_photos) % 2:
            photo_warning_code = "ATTACHMENT2_IMAGE_COUNT_ODD"
        else:
            try:
                material_photo_groups(report)
            except AttachmentPlanError as error:
                photo_warning_code = error.code
    elif had_attachment2_state or report.get("introduction", {}).get("evidence_list"):
        photo_warning_code = "ATTACHMENT2_IMAGE_MISSING"
    if photo_warning_code:
        uploaded_photos = []
        _clear_optional_attachment2(report)
    material_fields = unconfirmed_material_fields(report)
    manifest_valid = False
    manifest_blocker_code = None
    validated_manifest = None
    formal_context_id = None
    formal_archive_requested = bool(archive_context_id or manifest_id)
    if archive_context_id and manifest_id:
        try:
            formal_context_id = resolve_archive_context_id(archive_context_id)
            validated_manifest = get_valid_manifest(formal_context_id, manifest_id, report)
            manifest_valid = True
        except ArchiveGateError as error:
            first_code = error.blockers[0].code if error.blockers else "ARCHIVE_PARTS_INVALID"
            manifest_blocker_code = first_code.value if hasattr(first_code, "value") else str(first_code)
            manifest_valid = False
        except ArchiveRuntimeError as error:
            manifest_blocker_code = error.code
    if validated_manifest is None and case_id and directory_export_requested:
        validated_manifest = resolve_case_archive_manifest(case_id)
    gate = evaluate_export_gate(
        ExportGateInput(
            material_types_confirmed=not material_fields,
            material_type_fields=material_fields,
            primary_software_confirmed=is_primary_software_confirmed(report),
            photo_count_valid=True,
            photo_mapping_valid=True,
            disc_sequence_valid=disc_result.valid,
            disc_sequence_error_code=disc_result.error_code,
            archive_manifest_required=formal_archive_requested,
            archive_manifest_present=bool(archive_context_id and manifest_id and not manifest_blocker_code),
            archive_manifest_valid=manifest_valid,
            archive_blocker_code=manifest_blocker_code,
        )
    )
    if not gate.allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "EXPORT_BLOCKED",
                "blockers": [
                    {
                        "code": issue.code.value if hasattr(issue.code, "value") else issue.code,
                        "field": issue.field,
                        "message": issue.message,
                    }
                    for issue in gate.blockers
                ],
            },
        )
    if formal_archive_requested and validated_manifest is None:
        raise HTTPException(status_code=422, detail={"code": "ARCHIVE_MANIFEST_MISSING"})
    if directory_export_requested:
        if not export_path or not directory_token or not word_filename:
            raise HTTPException(
                status_code=422,
                detail={"code": "EXPORT_PATH_NOT_AUTHORIZED", "message": "导出目录授权已失效，请重新选择导出目录。"},
            )
        try:
            validated_export_path = validate_export_directory(export_path)
        except WorkbenchPersistenceError as error:
            raise HTTPException(
                status_code=422,
                detail={"code": error.code, "message": str(error)},
            ) from error
        if not get_workbench_services().sources.authorization.consume_exact_directory_grant(
            directory_token, str(validated_export_path),
        ):
            raise HTTPException(
                status_code=422,
                detail={"code": "EXPORT_PATH_NOT_AUTHORIZED", "message": "导出目录授权已失效，请重新选择导出目录。"},
            )
    canonical_source = report
    legacy_plan = None
    if validated_manifest is not None:
        report, legacy_plan = project_manifest_to_legacy_report_with_plan(
            report, validated_manifest,
        )
    report = project_ordered_legacy_report(report)
    try:
        output_dir = os.path.join(OUTPUT_BASE, "exports")
        os.makedirs(output_dir, exist_ok=True)
        selected_output = str(validated_export_path) if directory_export_requested else output_dir
        staging_parent = str(validated_export_path) if directory_export_requested else None
        with tempfile.TemporaryDirectory(prefix=".biji-word-export-", dir=staging_parent) as staging_dir, \
             tempfile.TemporaryDirectory(prefix="attachment2-images-") as photo_dir:
            photo_paths = []
            for index, photo in enumerate(uploaded_photos, 1):
                suffix = os.path.splitext(photo.filename or "")[1].lower()
                photo_path = os.path.join(photo_dir, f"photo-{index:04d}{suffix}")
                try:
                    photo_content = await photo.read()
                except (OSError, ValueError):
                    photo_warning_code = "ATTACHMENT2_IMAGE_READ_FAILED"
                    photo_paths = []
                    _clear_optional_attachment2(report)
                    break
                with open(photo_path, "wb") as handle:
                    handle.write(photo_content)
                photo_paths.append(photo_path)
            if photo_paths:
                try:
                    validate_attachment2_photos(photo_paths, attachments["photo_ids"])
                except Attachment2ImageError as error:
                    photo_warning_code = error.code
                    photo_paths = []
                    _clear_optional_attachment2(report)
            generate_kwargs = {
                "photo_paths": photo_paths,
                "output_dir": staging_dir if directory_export_requested else selected_output,
                "archive_manifest": validated_manifest,
                "output_filename": word_filename or None,
                **template_context,
            }
            try:
                docx_path = generate_docx(report, **generate_kwargs)
            except (Attachment2ImageError, AttachmentPlanError) as error:
                if not str(error.code).startswith("ATTACHMENT2_"):
                    raise
                photo_warning_code = error.code
                _clear_optional_attachment2(report)
                docx_path = generate_docx(report, **{
                    **generate_kwargs, "photo_paths": [],
                })
            filename = os.path.basename(docx_path)
            if directory_export_requested:
                os.replace(docx_path, os.path.join(selected_output, filename))
        if validated_manifest is not None and formal_context_id is not None:
            observe_shadow_export(
                formal_context_id, report, validated_manifest, settings, background_tasks,
                legacy_plan=legacy_plan, canonical_source=canonical_source,
            )
        if directory_export_requested:
            warnings = (
                [_attachment2_warning(photo_warning_code)]
                if photo_warning_code else []
            )
            response_data = {
                "export_path": selected_output,
                "word_filename": filename,
            }
            if warnings:
                response_data["warnings"] = warnings
            return {
                "api_version": "v1", "schema_version": 1,
                "data": response_data,
            }
        headers = (
            {"X-Wenshu-Word-Warning": str(photo_warning_code)}
            if photo_warning_code else None
        )
        return FileResponse(
            path=docx_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )
    except (Attachment2ImageError, AttachmentPlanError, TemplateProfileError) as error:
        if validated_manifest is not None and formal_context_id is not None:
            record_shadow_export_failure_at_controller(settings, archive_context_id)
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.safe_message},
        ) from error
    except Exception:
        if validated_manifest is not None and formal_context_id is not None:
            record_shadow_export_failure_at_controller(settings, archive_context_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DOCX_RENDER_FAILED",
                "message": "文档生成失败，请检查模板后重试。",
            },
        )
