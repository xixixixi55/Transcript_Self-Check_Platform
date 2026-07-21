"""
Layer 22: BE_Controllers — 检查笔录 Controller

处理笔录相关的 HTTP 请求：上传解析（文件夹/压缩包）、导出 docx。
REQ-001/013/014: 支持文件夹上传（含压缩开关）+ 压缩包直接上传。
"""
import os
import shutil
import tempfile
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from ..services.report_parser_service import parse_report, parse_from_archive
from ..services.record_generator_service import generate_docx
from ..services.export_gate_service import ExportGateInput, evaluate_export_gate
from ..services.inspector_service import apply_inspector_snapshot_compatibility
from ..services.material_policy_service import enrich_report_material_types, unconfirmed_material_fields
from ..services.software_policy_service import (
    is_primary_software_confirmed,
    normalize_primary_software_projection,
)
from ..services.disc_sequence_service import apply_disc_sequence_to_attachments
from ..services.archive_execution_service import (
    ArchiveGateError,
    create_archive_context,
    get_valid_manifest,
)
from ..services.archive_manifest_projection_service import project_manifest_to_legacy_report
from ..services.attachment_plan_service import AttachmentPlanError
from ..services.attachment2_plan_service import material_photo_groups
from ..services.attachment2_image_service import Attachment2ImageError
from ..services.template_profile_service import TemplateProfileError
from ..services.archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveRuntimeError
from ..services.archive_authorization_service import ArchiveAuthorizationError, ArchiveAuthorizationService
from ..config import OUTPUT_BASE, UPLOAD_BASE, ARCHIVE_MAX_SIZE
router = APIRouter()
ARCHIVE_AUTHORIZATION_SERVICE = ArchiveAuthorizationService(UPLOAD_BASE, OUTPUT_BASE)
@router.post("/reports/parse")
async def parse_report_endpoint(
    report_dir: str = Form(""),
    archive_file: Optional[UploadFile] = File(None),
    compress: bool = Form(True),
    directory_grant_token: str = Form(""),
):
    """
    解析 HTML 报告（文件夹模式或压缩包模式）。
    - 文件夹模式：提供 report_dir；compress 保留兼容但仅控制是否建立归档上下文，解析阶段不压缩
    - 压缩包模式：提供 archive_file（.rar/.zip），自动解压解析
    """
    # 校验：两种模式不能同时提供或同时为空
    has_dir = bool(report_dir)
    has_file = archive_file is not None and archive_file.filename
    if has_dir and has_file:
        raise HTTPException(status_code=400, detail="不能同时提供 report_dir 和 archive_file")
    if not has_dir and not has_file:
        # 兼容旧行为：无参数时尝试使用最新上传目录
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
            # ─── 压缩包模式（REQ-014） ───
            # 校验文件格式
            filename = archive_file.filename or ""
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".rar", ".zip"):
                raise HTTPException(status_code=400, detail="仅支持 .rar 和 .zip 格式的压缩包")
            # 保存到临时文件
            tmp_path = os.path.join(tempfile.gettempdir(), f"biji_upload_{os.urandom(8).hex()}{ext}")
            content = await archive_file.read()
            if len(content) > ARCHIVE_MAX_SIZE:
                os.unlink(tmp_path)
                raise HTTPException(status_code=400, detail=f"文件大小超过限制（{ARCHIVE_MAX_SIZE // 1024 // 1024}MB）")
            with open(tmp_path, "wb") as f:
                f.write(content)
            try:
                result = parse_from_archive(tmp_path, OUTPUT_BASE, retain_source=True)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            # ─── 文件夹模式 ───
            authorized_input = ARCHIVE_AUTHORIZATION_SERVICE.authorize_report_directory(
                report_dir, directory_grant_token or None,
            )
            result = parse_report(
                str(authorized_input.resolved_input_root), OUTPUT_BASE, compress=compress,
            )
        result["report"] = enrich_report_material_types(result["report"])
        result["archive_context_id"] = None
        source_root = result.pop("_archive_source_root", None)
        cleanup_root = result.pop("_archive_source_cleanup_root", None)
        if source_root:
            authorized_input = ARCHIVE_AUTHORIZATION_SERVICE.authorize_server_source(
                source_root, cleanup_root or source_root,
            )
        if not has_file or source_root:
            result["archive_context_id"] = create_archive_context(
                authorized_input,
                result["report"],
                output_root=OUTPUT_BASE,
                cleanup_root=cleanup_root,
            )
            result["archive_context"] = ARCHIVE_RUNTIME_STORE.get_context_summary(
                result["archive_context_id"],
            )
        result["archive_context_deprecated_compress"] = True
        result["archive_status"] = "idle"
        return {"success": True, "data": result}
    except ArchiveAuthorizationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.safe_message},
        )
    except HTTPException:
        raise
    except Exception:
        # Do not expose local paths, case data, or parser stack details to the
        # client; keep this boundary safe for both folder and archive inputs.
        raise HTTPException(
            status_code=422,
            detail="报告解析失败：报告结构缺失、格式不受支持或字段无效，请检查后重试。",
        )
@router.post("/records/export")
async def export_record_endpoint(
    report_json: str = Form(""),
    archive_context_id: str = Form(""),
    manifest_id: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
):
    """
    接收 InspectionReport JSON + 附件图片，生成 .docx 并返回下载。
    REQ-008: 图片嵌入 .docx 附件区域。
    """
    import json
    if not report_json:
        raise HTTPException(status_code=400, detail="请提供笔录数据")
    try:
        report = json.loads(report_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="笔录数据 JSON 格式无效")
    report = normalize_primary_software_projection(report)
    attachments = report.setdefault("attachments", {})
    disc_result = apply_disc_sequence_to_attachments(attachments)
    uploaded_photos = [photo for photo in photos if photo.filename]
    attachments["photo_ids"] = [f"photo-{index}" for index in range(1, len(uploaded_photos) + 1)]
    photo_mapping_valid = True
    photo_mapping_error_code = None
    if uploaded_photos:
        try:
            material_photo_groups(report)
        except AttachmentPlanError as error:
            photo_mapping_valid = False
            photo_mapping_error_code = error.code
    material_fields = unconfirmed_material_fields(report)
    manifest_valid = False
    manifest_blocker_code = None
    validated_manifest = None
    if archive_context_id and manifest_id:
        try:
            validated_manifest = get_valid_manifest(archive_context_id, manifest_id, report)
            manifest_valid = True
        except ArchiveGateError as error:
            first_code = error.blockers[0].code if error.blockers else "ARCHIVE_PARTS_INVALID"
            manifest_blocker_code = first_code.value if hasattr(first_code, "value") else str(first_code)
            manifest_valid = False
        except ArchiveRuntimeError as error:
            manifest_blocker_code = error.code
    gate = evaluate_export_gate(
        ExportGateInput(
            material_types_confirmed=not material_fields,
            material_type_fields=material_fields,
            primary_software_confirmed=is_primary_software_confirmed(report),
            photo_count_valid=len(uploaded_photos) % 2 == 0,
            photo_mapping_valid=photo_mapping_valid,
            photo_mapping_error_code=photo_mapping_error_code,
            disc_sequence_valid=disc_result.valid,
            disc_sequence_error_code=disc_result.error_code,
            archive_manifest_required=True,
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
    if validated_manifest is None:
        raise HTTPException(status_code=422, detail={"code": "ARCHIVE_MANIFEST_MISSING"})
    report = project_manifest_to_legacy_report(report, validated_manifest)
    report = apply_inspector_snapshot_compatibility(report)
    # 保存上传的图片到临时目录
    try:
        output_dir = os.path.join(OUTPUT_BASE, "exports")
        os.makedirs(output_dir, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="attachment2-images-") as photo_dir:
            photo_paths = []
            for index, photo in enumerate(uploaded_photos, 1):
                suffix = os.path.splitext(photo.filename or "")[1].lower()
                photo_path = os.path.join(photo_dir, f"photo-{index:04d}{suffix}")
                with open(photo_path, "wb") as handle:
                    handle.write(await photo.read())
                photo_paths.append(photo_path)
            docx_path = generate_docx(
                report, photo_paths=photo_paths, output_dir=output_dir,
                archive_manifest=validated_manifest,
            )
        filename = os.path.basename(docx_path)
        return FileResponse(
            path=docx_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except (Attachment2ImageError, AttachmentPlanError, TemplateProfileError) as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.safe_message},
        ) from error
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DOCX_RENDER_FAILED",
                "message": "文档生成失败，请检查模板后重试。",
            },
        )
