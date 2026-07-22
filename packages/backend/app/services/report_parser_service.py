"""
Layer 21: BE_Services — 报告解析编排服务。
REQ-011 缓存 / REQ-013 兼容压缩开关 / REQ-014 压缩包上传 / REQ-016 动态 software_tools。

> 文件行数超过 250 行上限：本文件是报告解析的核心编排入口，包含 _build_report（组装完整
  InspectionReport）、_build_software_tools（动态软件工具列表）、缓存判断、RAR 压缩编排、
  附件自动填充等多个紧密耦合的子流程。拆分会导致参数传递链过长，降低可维护性。
"""
import os
import shutil
import sys
import tempfile
from typing import Optional
from ..repository.file_storage import (
    is_cache_valid, save_json, read_json, ensure_dir,
    extract_archive, compute_md5, detect_winrar_version,
)
from ..repository.html_parser import (
    parse_case_info, parse_device_lists, parse_report_info,
    parse_device_base,
    format_time_chinese, format_inspection_time_range,
)
from ..repository.report_format_adapter import require_supported_report_format
from .report_defaults_service import DEFAULT_DATA_SUMMARY
from .material_policy_service import material_from_legacy_item, select_display_identifiers
from .report_parsing_cache_service import REPORT_PARSING_CACHE_SERVICE
# 缓存版本号：解析逻辑变更时递增，自动淘汰旧缓存
_CACHE_VERSION = 7  # v7: structured main-software and per-material device-name parsing

def parse_report(source_dir: str, output_dir: str, compress: bool = True) -> dict:
    """解析报告目录；compress 仅为兼容参数，解析阶段不执行压缩。"""
    data_dir = os.path.join(source_dir, "data")
    return REPORT_PARSING_CACHE_SERVICE.load_or_build(
        source_dir,
        os.path.join(output_dir, "parsed"),
        _CACHE_VERSION,
        lambda: _build_parse_result(source_dir, output_dir, compress),
        fingerprint_dir=data_dir if os.path.isdir(data_dir) else source_dir,
    )


def _build_parse_result(source_dir: str, output_dir: str, compress: bool) -> dict:
    """Build one uncached parse result; cache metadata stays outside the payload."""
    data_dir = os.path.join(source_dir, "data")
    report = _build_report(data_dir, source_dir, output_dir, compress=compress)
    return {
        "report": report,
        "cache_version": _CACHE_VERSION,
        "parsed_files": [
            "data_case_info.json", "data_device_lists.json",
            "data_report_info.json", "data_navigation.json",
        ],
        "rar_info": _build_rar_info(report),
    }


def parse_from_archive(
    archive_path: str,
    output_dir: str,
    *,
    retain_source: bool = False,
) -> dict:
    """解析上传压缩包；需要后续归档时由调用方保留受控源目录。"""
    ext = os.path.splitext(archive_path)[1].lower()
    archive_md5 = compute_md5(archive_path)
    archive_size = os.path.getsize(archive_path)

    # 解压到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="biji_archive_context_")
    extracted_root = ""
    succeeded = False
    try:
        extracted_root = extract_archive(archive_path, tmp_dir)
        # 构建 InspectionReport（compress=False 因为已是压缩包）
        report = _build_report(
            os.path.join(extracted_root, "data"),
            extracted_root, output_dir,
            compress=False,
            is_rar_archive=(ext == ".rar"),
        )
        # 结果中的文件信息来自原始上传的压缩包
        report["inspection"]["result"].update({
            "rar_filename": os.path.basename(archive_path),
            "md5_hash": archive_md5,
            "file_size": f"{archive_size}字节",
        })
        succeeded = True
    finally:
        if not retain_source or not succeeded:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    result = {
        "report": report,
        "parsed_files": [
            "data_case_info.json", "data_device_lists.json",
            "data_report_info.json", "data_navigation.json",
        ],
        "rar_info": {
            "filename": os.path.basename(archive_path),
            "md5": archive_md5,
            "size_bytes": archive_size,
            "size_display": _format_file_size(archive_size),
        },
    }
    if retain_source:
        result["_archive_source_root"] = extracted_root
        result["_archive_source_cleanup_root"] = tmp_dir
    return result


def _split_persons(collector: str) -> list[str]:
    """将采集人字符串按顿号拆分为数组，过滤空串"""
    if not collector:
        return []
    return [name.strip() for name in collector.replace("，", "、").split("、") if name.strip()]


def _format_case_summary(case_name: str) -> str:
    """格式化案件简要情况，避免双"案"（如'XX诈骗案'→'XX诈骗案'，不追加）"""
    if not case_name:
        return ""
    return f"{case_name}案" if not case_name.endswith("案") else case_name


def _build_report(data_dir: str, source_dir: str, output_dir: str,
                  compress: bool = True, is_rar_archive: bool = False) -> dict:
    """构建 InspectionReport（parse_report / parse_from_archive 共用）"""
    # 在解析案件字段前确认核心结构；缺少核心文件时由既有 parser 给出具体错误。
    require_supported_report_format(data_dir)
    # 1. 解析案件信息
    case = parse_case_info(data_dir)
    # 2. 解析设备列表
    devices_raw = parse_device_lists(data_dir)
    # 3. 解析取证工具版本
    versions = parse_report_info(data_dir)
    # 5. 解析每个设备的基本信息
    evidence_items = []
    for dev in devices_raw:
        en = dev["evidence_number"]
        # 尝试从 Base 目录解析设备详情
        base_info = parse_device_base(data_dir, en)
        # Base 解析失败时，回退到 data_device_lists 中的 device_name
        dev_name = str(base_info.get("device_name") or dev.get("device_name", "")).strip()
        brand = str(base_info.get("brand") or "").strip()
        raw_model = str(base_info.get("model") or dev_name or dev.get("device_name", "")).strip()
        model = _device_display_name(brand, raw_model, dev_name)
        explicit_device_type = base_info.get("device_type") or dev.get("device_type", "")
        device_type = explicit_device_type or base_info.get("device_name") or base_info.get("model") or dev.get("device_name", "")
        evidence_items.append({
            "id": en,
            "device_type": device_type,
            "device_type_source": "report_field" if explicit_device_type else "legacy_display",
            "device_name": model,
            "brand": brand,
            "model": model,
            "imei1": dev.get("imei1", "") or base_info.get("imei1", ""),
            "imei2": dev.get("imei2", "") or base_info.get("imei2", ""),
            "serial_number": base_info.get("serial_number", ""),
            "evidence_number": en,
        })

    # 6. 检查过程步骤
    # The standard model preserves every evidence item, while the existing
    # process/result sections remain single-primary-device fields.
    first_device = evidence_items[0] if evidence_items else {
        "model": "", "imei1": "", "imei2": "", "evidence_number": ""}
    main_software = versions.get("main_software") or {}
    main_name = str(main_software.get("name", "")).strip()
    main_version = str(main_software.get("version", "")).strip()
    main_status = main_software.get("status", "unconfirmed")
    main_candidates = main_software.get("candidates", [])
    sv = main_version or _extract_version(versions)
    main_display = " ".join(filter(None, [main_name, main_version]))
    first_identifiers = select_display_identifiers(material_from_legacy_item(first_device, 0))
    identifier_labels = {"imei1": "IMEI1", "imei2": "IMEI2", "serial_number": "序列号"}
    identifier_text = "；".join(
        f"{identifier_labels[item.type]}：{item.value}" for item in first_identifiers
    ) or "设备标识待确认"
    process_steps = [
        {"step_number": 1, "content": f"将{first_device.get('device_name') or first_device.get('model') or first_device.get('device_type', '未知设备')}（{identifier_text}）编号为{first_device.get('evidence_number', 'xx')}。"},
        {"step_number": 2, "content": f"对检材{first_device.get('evidence_number', 'xx')}进行拍照。"},
        {"step_number": 3, "content": "启动美亚FL-901手机取证塔，Windows 10 64位企业版操作系统启动正常，使用火绒安全软件（版本号为6.0.6.1）对取证塔进行杀毒，未发现病毒，完毕后退出火绒安全软件。"},
        {"step_number": 4, "content": f"启动{main_display or '待确认主取证软件'}（版本号为{main_version or '待确认'}）对检材{first_device.get('evidence_number', 'xx')}进行检查。"},
    ]

    # 7. 数据摘要是报告字段默认值，不从导航分类列表动态拼接。
    data_summary = DEFAULT_DATA_SUMMARY

    # 8. 动态 software_tools（REQ-016）
    software_tools = _build_software_tools(
        sv,
        compress=compress,
        is_rar_archive=is_rar_archive,
        main_name=main_name,
        main_status=main_status,
    )

    # 9. 条件压缩 RAR
    rar_info = _build_rar_info_from_compress(source_dir, output_dir, case.get("case_name", "report"), compress)

    # 附件1 电子数据提取固定清单 — 从 rar_info 自动填充
    extract_columns = [
        {"key": "no", "title": "序号", "width": "60"},
        {"key": "electronic_data", "title": "电子数据", "width": "220"},
        {"key": "source", "title": "来源", "width": "180"},
        {"key": "extraction_method", "title": "提取方式", "width": "180"},
        {"key": "md5_hash", "title": "文件MD5哈希值", "width": "260"},
    ]
    extract_rows = []
    en = first_device.get("evidence_number", "")
    if rar_info.get("filename"):
        extract_rows.append({
            "no": "1",
            "electronic_data": rar_info["filename"],
            "source": f"{en}检材内提取" if en else "",
            "extraction_method": "使用美亚手机取证塔对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值",
            "md5_hash": rar_info["md5"],
        })

    # 10. 构建 InspectionReport
    # 标准检查时间只来自案件 JSON 的创建时间和报告时间；设备表时间段不参与。
    time_range = format_inspection_time_range(
        case.get("create_time", ""), case.get("report_time", "")
    )

    # 用于前端生成文号的原始数据
    _case_number = case.get("case_number", "")

    return {
        "title": "电子数据检查笔录",
        "document_number": "SYN-TEST〔2026〕000号",
        "case_number": _case_number,  # 前端用此值生成文号
        "introduction": {
            "entrust_unit": case.get("submit_unit", ""),
            "entrust_persons": _split_persons(case.get("submit_person", "")),
            "entrust_time": format_time_chinese(case.get("create_time", "")),
            "case_summary": _format_case_summary(case.get("case_name", "")),
            "evidence_list": evidence_items,
            "inspection_requirement": "上述检材内电子数据的提取、固定和恢复",
            "inspection_time_range": time_range,
            "inspectors": [],
            "inspection_place": "合成检验鉴定中心",
        },
        "inspection": {
            "method": "采用 GA/T 1069-2021《法庭科学电子物证手机检验技术规范》进行检查。",
            "hardware_device": "美亚FL-901手机取证塔",
            "primary_software": {
                "name": main_name,
                "version": main_version,
                "display_name": main_display,
                "confirmation_status": main_status,
                "provenance": [{
                    "source_type": "report",
                    "source_file": "data_report_info.json",
                    "json_path": "contents",
                    "adapter": "legacy-report-adapter",
                    "confidence": 1 if main_status == "confirmed_by_report" else None,
                }],
                "candidates": main_candidates,
            },
            "software_tools": software_tools,
            "process_steps": process_steps,
            "result": {
                "evidence_number": first_device.get("evidence_number", ""),
                "software_name": main_name,
                "software_version": sv,
                "data_summary": data_summary,
                "rar_filename": rar_info["filename"],
                "md5_hash": rar_info["md5"],
                "file_size": str(rar_info.get("size_bytes", 0)),
            },
        },
        "attachments": {
            "extract_list": {"columns": extract_columns, "rows": extract_rows},
            "photo_ids": [],
            "disc_number": "",
            "burning_date": "",
        },
    }


def _device_display_name(brand: str, model: str, fallback_name: str = "") -> str:
    """Build one stable device display name without duplicating its brand."""
    brand_value = " ".join(str(brand).split())
    model_value = " ".join(str(model).split())
    fallback = " ".join(str(fallback_name).split())
    if model_value:
        if brand_value and brand_value.casefold() not in model_value.casefold():
            return f"{brand_value} {model_value}"
        return model_value
    return brand_value or fallback


def _build_software_tools(
    sv: str,
    compress: bool = True,
    is_rar_archive: bool = False,
    *,
    main_name: str | None = None,
    main_status: str = "unconfirmed",
) -> list[dict]:
    """Build only the report primary tool plus the two allowed runtime tools."""
    tools = []
    if main_name and sv:
        tools.append({
            "category": "main_forensic",
            "name": main_name or "",
            "version": sv,
            "display_name": " ".join(filter(None, [main_name or "", sv])),
            "confirmation_status": main_status,
        })
    # Keep the compatibility entry, but report the actual discovery result.
    detected_version = detect_winrar_version()
    version = detected_version or ""
    tools.append({
        "category": "winrar",
        "name": "WinRAR压缩管理软件",
        "version": version,
        "display_name": (
            f"WinRAR压缩管理软件 {version}"
            if detected_version else "WinRAR压缩管理软件（未检测到）"
        ),
        "confirmation_status": "confirmed" if detected_version else "unconfirmed",
    })
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    tools.append({
        "category": "python_hashlib",
        "name": "Python hashlib",
        "version": py_ver,
        "display_name": f"Python hashlib {py_ver}",
        "confirmation_status": "confirmed",
    })
    return tools


def _build_rar_info_from_compress(source_dir: str, output_dir: str,
                                   case_name: str, compress: bool) -> dict:
    """Deprecated compatibility hook: parsing no longer has compression side effects.

    The controller creates an opaque archive context; execute_archive performs the
    gated WinRAR run only after review supplies a valid first disc number.
    """
    return {
        "filename": "",
        "filepath": "",
        "md5": "",
        "size_bytes": 0,
        "size_display": "",
    }


def _build_rar_info(report: dict) -> Optional[dict]:
    """从 report 的 result 字段提取 rar_info，所有字段为空时返回 None"""
    r = report.get("inspection", {}).get("result", {})
    filename = r.get("rar_filename", "")
    md5 = r.get("md5_hash", "")
    size = r.get("file_size", "")
    if not filename and not md5 and not size:
        return None
    return {
        "filename": filename,
        "md5": md5,
        "size_bytes": 0,
        "size_display": size,
    }


def _format_file_size(bytes_val: int) -> str:
    """格式化文件大小（用于压缩包上传结果）"""
    if bytes_val < 1024:
        return f"{bytes_val} 字节"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.2f} MB"
    return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def _extract_version(versions: dict) -> str:
    """提取软件版本号字符串"""
    pv = versions.get("product_version", "")
    if pv:
        parts = pv.split()
        return parts[-1] if parts else pv
    return ""


def _filter_categories(categories: list[str]) -> list[str]:
    """过滤数据分类，保留大类"""
    big_cats = ["即时通讯", "手机信息", "通讯录", "通话记录", "短信",
                 "媒体文件", "微信", "抖音", "QQ", "支付宝", "日历",
                 "备忘录", "邮件", "录音", "图片", "视频", "文件"]
    result = []
    for cat in categories:
        for big in big_cats:
            if big in cat and big not in result:
                result.append(big)
                break
    return result if result else categories[:5]
