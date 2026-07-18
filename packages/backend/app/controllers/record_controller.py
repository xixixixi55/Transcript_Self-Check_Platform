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
from ..services.disc_sequence_service import parse_disc_sequence

router = APIRouter()

# 存储路径（项目根目录）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
UPLOAD_BASE = os.path.join(_PROJECT_ROOT, "uploads")
OUTPUT_BASE = os.path.join(_PROJECT_ROOT, "output")
ARCHIVE_MAX_SIZE = 500 * 1024 * 1024  # 500MB


@router.post("/reports/parse")
async def parse_report_endpoint(
    report_dir: str = Form(""),
    archive_file: Optional[UploadFile] = File(None),
    compress: bool = Form(True),
):
    """
    解析 HTML 报告（文件夹模式或压缩包模式）。
    - 文件夹模式：提供 report_dir，compress 控制是否生成 RAR
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
                result = parse_from_archive(tmp_path, OUTPUT_BASE)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            # ─── 文件夹模式 ───
            if not os.path.exists(report_dir):
                raise HTTPException(status_code=404, detail=f"报告目录不存在: {report_dir}")
            result = parse_report(report_dir, OUTPUT_BASE, compress=compress)

        result["report"] = enrich_report_material_types(result["report"])
        return {"success": True, "data": result}
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
    disc_result = parse_disc_sequence(attachments.get("disc_number"))
    if disc_result.valid and disc_result.sequence is not None:
        year, month, day = disc_result.sequence.date.split("-")
        attachments["burning_date"] = f"{year}年{int(month)}月{int(day)}日"
        attachments["disc_sequence"] = {
            "prefix": disc_result.sequence.prefix,
            "date": disc_result.sequence.date,
            "start_number": disc_result.sequence.start_number,
            "number_width": disc_result.sequence.number_width,
            "first_disc_number": disc_result.sequence.first_disc_number,
        }
    else:
        attachments.pop("disc_sequence", None)
    material_fields = unconfirmed_material_fields(report)
    gate = evaluate_export_gate(
        ExportGateInput(
            material_types_confirmed=not material_fields,
            material_type_fields=material_fields,
            primary_software_confirmed=is_primary_software_confirmed(report),
            disc_sequence_valid=disc_result.valid,
            disc_sequence_error_code=disc_result.error_code,
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

    report = apply_inspector_snapshot_compatibility(report)

    # 保存上传的图片到临时目录
    photo_paths = []
    if photos:
        photo_dir = os.path.join(OUTPUT_BASE, "photos")
        os.makedirs(photo_dir, exist_ok=True)
        for photo in photos:
            if photo.filename:
                safe_name = os.path.basename(photo.filename)
                photo_path = os.path.join(photo_dir, safe_name)
                with open(photo_path, "wb") as f:
                    content = await photo.read()
                    f.write(content)
                photo_paths.append(photo_path)

    try:
        output_dir = os.path.join(OUTPUT_BASE, "exports")
        os.makedirs(output_dir, exist_ok=True)
        docx_path = generate_docx(report, photo_paths=photo_paths, output_dir=output_dir)

        filename = os.path.basename(docx_path)
        return FileResponse(
            path=docx_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档生成失败: {str(e)}")
