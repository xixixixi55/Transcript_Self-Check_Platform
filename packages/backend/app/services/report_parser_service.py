"""
Layer 21: BE_Services — 报告解析编排服务。
REQ-011 缓存 / REQ-013 兼容压缩开关 / REQ-014 压缩包上传 / REQ-016 动态 software_tools。

> 本文件处于 400–600 行高内聚允许区间，是报告解析的核心编排入口，包含 _build_report（组装完整
  InspectionReport）、_build_software_tools（动态软件工具列表）、缓存判断、RAR 压缩编排、
  附件自动填充等多个紧密耦合的子流程。拆分会导致参数传递链过长，降低可维护性。
"""
import os
import re
import shutil
import tempfile
from typing import Optional
from ..repository.file_storage import (
    is_cache_valid, save_json, read_json, ensure_dir,
    extract_archive, compute_md5, detect_winrar_version,
)
from ..repository.html_parser import (
    _resolve_evidence_directory,
    parse_case_info, parse_device_lists, parse_report_info,
    parse_device_base,
    format_inspection_time_range,
)
from ..repository.device_field_parser import is_generic_device_label
from ..repository.report_format_adapter import require_supported_report_format
from ..repository.filesystem_identity_repository import (
    normalized_directory_key,
    selected_files_content_fingerprint,
)
from ..repository.report_parse_input_repository import (
    ReportParseInputSnapshot,
    build_report_parse_input_snapshot,
)
from ..repository.hashmyfiles_repository import HASHMYFILES_DISPLAY_VERSION
from .report_defaults_service import (
    DEFAULT_DATA_SUMMARY,
    DEFAULT_DOCUMENT_NUMBER,
    DEFAULT_HARDWARE_DEVICE,
    DEFAULT_INSPECTION_METHOD,
    DEFAULT_INSPECTION_PLACE,
    DEFAULT_INSPECTION_REQUIREMENT,
)
from .material_policy_service import material_from_legacy_item, select_display_identifiers
from .report_parsing_cache_service import REPORT_PARSING_CACHE_SERVICE
from .report_parse_inflight_service import REPORT_PARSE_INFLIGHT_REGISTRY
from .entrust_person_service import normalize_entrust_persons
# 缓存版本号：解析逻辑变更时递增，自动淘汰旧缓存
_CACHE_VERSION = 23  # v23: stop deriving entrust time from report creation time
_TRAILING_CASE_NAME_MARK_RE = re.compile(r"(案)\s*(?:（[^（）]*）|\([^()]*\))\s*$")

def parse_report(source_dir: str, output_dir: str, compress: bool = True) -> dict:
    """解析报告目录；compress 仅为兼容参数，解析阶段不执行压缩。"""
    source_key = normalized_directory_key(source_dir)
    generation = REPORT_PARSING_CACHE_SERVICE.current_generation()
    operation_key = f"{source_key}:{_CACHE_VERSION}:{generation}"
    return REPORT_PARSE_INFLIGHT_REGISTRY.run(
        operation_key,
        lambda: _parse_report_task(
            source_dir, output_dir, compress, generation,
        ),
    )


def _parse_report_task(
    source_dir: str, output_dir: str, compress: bool, generation: int,
) -> dict:
    """Run cache validation and Parser work inside one shared task."""
    data_dir = os.path.join(source_dir, "data")
    has_core_files = all(
        os.path.isfile(os.path.join(data_dir, name))
        for name in (
            "data_case_info.json", "data_device_lists.json", "data_report_info.json",
        )
    )
    snapshot: ReportParseInputSnapshot | None = None

    def get_snapshot() -> ReportParseInputSnapshot:
        nonlocal snapshot
        if snapshot is None:
            snapshot = build_report_parse_input_snapshot(source_dir)
        return snapshot

    fingerprint = (
        (lambda _data_dir: get_snapshot().dependency_fingerprint)
        if has_core_files else _report_parser_dependency_fingerprint
    )
    return REPORT_PARSING_CACHE_SERVICE.load_or_build(
        source_dir,
        os.path.join(output_dir, "parsed"),
        _CACHE_VERSION,
        lambda: _build_parse_result(
            source_dir, output_dir, compress,
            input_snapshot=get_snapshot() if has_core_files else None,
        ),
        fingerprint_dir=data_dir if os.path.isdir(data_dir) else source_dir,
        fingerprint=fingerprint,
        snapshot_builder=get_snapshot if has_core_files else None,
        generation_token=generation,
    )


def _report_parser_dependency_fingerprint(data_dir: str) -> str:
    """Fingerprint the JSON paths reached by the current Legacy parser.

    Core report files are always read. Device-base JSON paths are discovered
    from the report's device rows, matching ``parse_device_base`` instead of
    hashing unrelated attachment and media JSON files.
    """
    dependency_files = [
        "data_case_info.json",
        "data_device_lists.json",
        "data_report_info.json",
    ]
    existing_core_files = [
        name for name in dependency_files
        if os.path.isfile(os.path.join(data_dir, name))
    ]
    if len(existing_core_files) != len(dependency_files):
        return selected_files_content_fingerprint(data_dir, existing_core_files)
    for device in parse_device_lists(data_dir):
        resolved_dir = _resolve_evidence_directory(
            data_dir, device.get("evidence_number", ""),
        )
        if not resolved_dir:
            continue
        for name in sorted(os.listdir(resolved_dir)):
            sub_dir = os.path.join(resolved_dir, name)
            if not os.path.isdir(sub_dir):
                continue
            for filename in sorted(os.listdir(sub_dir)):
                if filename.casefold().endswith(".json"):
                    dependency_files.append(
                        os.path.relpath(
                            os.path.join(sub_dir, filename), data_dir,
                        ),
                    )
    return selected_files_content_fingerprint(data_dir, dependency_files)


def _build_parse_result(
    source_dir: str, output_dir: str, compress: bool,
    *, input_snapshot: ReportParseInputSnapshot | None = None,
) -> dict:
    """Build one uncached parse result; cache metadata stays outside the payload."""
    data_dir = os.path.join(source_dir, "data")
    report = _build_report(
        data_dir, source_dir, output_dir, compress=compress,
        input_snapshot=input_snapshot,
    )
    return {
        "report": report,
        "_case_metadata": _case_metadata(data_dir, input_snapshot, report),
        "cache_version": _CACHE_VERSION,
        "parsed_files": [
            "data_case_info.json", "data_device_lists.json",
            "data_report_info.json", "data_navigation.json",
        ],
        "rar_info": _build_rar_info(report),
    }


def _case_metadata(
    data_dir: str, input_snapshot: ReportParseInputSnapshot | None,
    report: dict,
) -> dict[str, str]:
    case = input_snapshot.case_info if input_snapshot is not None else {}
    if input_snapshot is None and os.path.isfile(os.path.join(data_dir, "data_case_info.json")):
        case = parse_case_info(data_dir)
    introduction = report.get("introduction") if isinstance(report, dict) else None
    summary = introduction.get("case_summary", "") if isinstance(introduction, dict) else ""
    return {
        "case_name": _normalize_case_name(case.get("case_name")),
        "case_number": str(case.get("case_number") or "").strip(),
        "case_summary": str(summary or "").strip(),
    }


def parse_from_archive(
    archive_path: str,
    output_dir: str,
    *,
    retain_source: bool = False,
    archive_md5: str | None = None,
) -> dict:
    """解析上传压缩包；需要后续归档时由调用方保留受控源目录。"""
    ext = os.path.splitext(archive_path)[1].lower()
    archive_md5 = (archive_md5 or compute_md5(archive_path)).upper()
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
    """兼容旧调用名，将委托人文本规范化为数组。"""
    return normalize_entrust_persons(collector)


def _normalize_case_name(case_name: object) -> str:
    """Normalize the parser case name without inventing a case suffix."""
    value = str(case_name or "").strip()
    return _TRAILING_CASE_NAME_MARK_RE.sub(r"\1", value).strip()


def _format_case_summary(case_name: object) -> str:
    """Use the normalized report case name as the editable case summary seed."""
    return _normalize_case_name(case_name)


def _build_report(data_dir: str, source_dir: str, output_dir: str,
                  compress: bool = True, is_rar_archive: bool = False,
                  input_snapshot: ReportParseInputSnapshot | None = None) -> dict:
    """构建 InspectionReport（parse_report / parse_from_archive 共用）"""
    if input_snapshot is None:
        # 在解析案件字段前确认核心结构；缺少核心文件时由既有 parser 给出具体错误。
        require_supported_report_format(data_dir)
        # 1. 解析案件信息
        case = parse_case_info(data_dir)
        # 2. 解析设备列表
        devices_raw = parse_device_lists(data_dir)
        # 3. 解析取证工具版本
        versions = parse_report_info(data_dir)
        device_base_info = {}
    else:
        case = input_snapshot.case_info
        devices_raw = input_snapshot.device_rows
        versions = input_snapshot.report_info
        device_base_info = input_snapshot.device_base_info
    # 5. 解析每个设备的基本信息
    evidence_items = []
    for dev in devices_raw:
        en = dev["evidence_number"]
        # 尝试从 Base 目录解析设备详情
        base_info = device_base_info.get(en) if input_snapshot else parse_device_base(data_dir, en)
        # Base 解析失败时，回退到 data_device_lists 中的 device_name
        dev_name = str(base_info.get("device_name") or dev.get("device_name", "")).strip()
        brand = str(base_info.get("brand") or "").strip()
        raw_model = _first_concrete_device_value(
            base_info.get("model"), base_info.get("device_name"),
            dev.get("device_name", ""),
        )
        display_name = _device_display_name(brand, raw_model, "")
        explicit_device_type = base_info.get("device_type") or dev.get("device_type", "")
        device_type = explicit_device_type or base_info.get("device_name") or base_info.get("model") or dev.get("device_name", "")
        imei1 = dev.get("imei1", "") or base_info.get("imei1", "")
        imei2 = dev.get("imei2", "") or base_info.get("imei2", "")
        serial_number = base_info.get("serial_number", "")
        evidence_items.append({
            "id": en,
            "device_type": device_type,
            "device_type_source": "report_field" if explicit_device_type else "legacy_display",
            "device_name": display_name,
            "brand": brand,
            "model": raw_model,
            "imei1": imei1,
            "imei2": imei2,
            "serial_number": serial_number,
            "extractable": bool(str(imei1).strip() or str(imei2).strip() or str(serial_number).strip()),
            "evidence_number": en,
        })

    evidence_items = _natural_evidence_order(evidence_items)

    # 6. 检查过程步骤
    # Keep the legacy scalar DTO fields, but project all evidence items into
    # their display text.  The evidence list remains the structured source of
    # truth; process/result strings must not silently fall back to item zero.
    first_device = evidence_items[0] if evidence_items else {
        "model": "", "imei1": "", "imei2": "", "evidence_number": ""}
    process_devices = evidence_items or [first_device]
    evidence_numbers = []
    material_descriptions = []
    identifier_labels = {"imei1": "IMEI1", "imei2": "IMEI2", "serial_number": "序列号"}
    for index, device in enumerate(process_devices):
        evidence_number = str(device.get("evidence_number", "")).strip()
        if evidence_number and evidence_number not in evidence_numbers:
            evidence_numbers.append(evidence_number)
        extractable = bool(device.get("extractable", any(
            str(device.get(key, "")).strip() for key in ("imei1", "imei2", "serial_number")
        )))
        identifiers = select_display_identifiers(material_from_legacy_item(device, index)) if extractable else ()
        identifier_text = "；".join(
            f"{identifier_labels[item.type]}：{item.value}" for item in identifiers
        ) or ("设备标识待确认" if extractable else "无法提取")
        device_name = (
            device.get("device_name")
            or device.get("model")
            or device.get("device_type", "未知设备")
        )
        material_descriptions.append(
            f"{device_name}（{identifier_text}）编号为{evidence_number or 'xx'}"
        )
    evidence_label = "、".join(evidence_numbers) or "xx"
    main_software = versions.get("main_software") or {}
    main_name = str(main_software.get("name", "")).strip()
    main_version = str(main_software.get("version", "")).strip()
    main_status = main_software.get("status", "unconfirmed")
    main_candidates = main_software.get("candidates", [])
    sv = main_version or _extract_version(versions)
    main_display = main_name
    main_action_name = _software_action_name(main_display)
    process_steps = [
        {"step_number": 1, "content": f"将{'；'.join(material_descriptions)}。"},
        {"step_number": 2, "content": f"对检材{evidence_label}进行拍照。"},
        {"step_number": 3, "content": "检查环境将在案件初始化时自动识别。"},
        {"step_number": 4, "content": f"启动{main_action_name}（版本号为{main_version or '待确认'}）使用{main_action_name}对检材{evidence_label}进行检查。"},
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

    normalized_case_name = _normalize_case_name(case.get("case_name", ""))

    # 9. 条件压缩 RAR
    rar_info = _build_rar_info_from_compress(source_dir, output_dir, normalized_case_name or "report", compress)

    # 附件1 电子数据提取固定清单 — 从 rar_info 自动填充
    extract_columns = [
        {"key": "no", "title": "序号", "width": "60"},
        {"key": "electronic_data", "title": "电子数据", "width": "220"},
        {"key": "source", "title": "来源", "width": "180"},
        {"key": "extraction_method", "title": "提取方式", "width": "180"},
        {"key": "md5_hash", "title": "文件MD5哈希值", "width": "260"},
    ]
    extract_rows = []
    if rar_info.get("filename"):
        extract_rows.append({
            "no": "1",
            "electronic_data": rar_info["filename"],
            "source": f"{evidence_label}检材内提取" if evidence_numbers else "",
            "extraction_method": "使用美亚手机取证塔对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值",
            "md5_hash": str(rar_info["md5"]).upper(),
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
        "document_number": DEFAULT_DOCUMENT_NUMBER,
        "case_number": _case_number,  # 前端用此值生成文号
        "introduction": {
            "entrust_unit": case.get("submit_unit", ""),
            "entrust_persons": _split_persons(case.get("submit_person", "")),
            "entrust_time": "",
            "case_summary": _format_case_summary(normalized_case_name),
            "evidence_list": evidence_items,
            "inspection_requirement": DEFAULT_INSPECTION_REQUIREMENT,
            "inspection_time_range": time_range,
            "inspectors": [],
            "inspection_place": DEFAULT_INSPECTION_PLACE,
        },
        "inspection": {
            "method": DEFAULT_INSPECTION_METHOD,
            "hardware_device": DEFAULT_HARDWARE_DEVICE,
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
                "evidence_number": "、".join(evidence_numbers),
                "software_name": main_name,
                "software_version": sv,
                "data_summary": data_summary,
                "rar_filename": rar_info["filename"],
                "md5_hash": str(rar_info["md5"]).upper(),
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


def _software_action_name(value: object) -> str:
    name = str(value or "").strip() or "待确认主取证软件"
    return name if name.endswith("软件") else f"{name}软件"


def _natural_evidence_order(items: list[dict]) -> list[dict]:
    """Sort whole material records when all numeric keys are safe and unique."""
    keyed = [(_evidence_order_key(item.get("evidence_number")), item) for item in items]
    keys = [key for key, _ in keyed]
    if any(key is None for key in keys) or len(set(keys)) != len(keys):
        return items
    return [item for _, item in sorted(keyed, key=lambda pair: pair[0])]


def _evidence_order_key(value: object) -> tuple[int, ...] | None:
    groups = re.findall(r"\d+", str(value or ""))
    if not groups:
        return None
    numbers = tuple(int(group) for group in groups)
    return numbers if all(number <= 9_007_199_254_740_991 for number in numbers) else None


def _device_display_name(brand: str, model: str, fallback_name: str = "") -> str:
    """Build one stable device display name without duplicating its brand."""
    brand_value = " ".join(str(brand).split())
    model_value = " ".join(str(model).split())
    fallback = " ".join(str(fallback_name).split())
    if model_value:
        if brand_value and brand_value.casefold() not in model_value.casefold():
            return f"{brand_value} {model_value}"
        return model_value
    if fallback and not is_generic_device_label(fallback):
        return fallback
    return brand_value


def _first_concrete_device_value(*values: object) -> str:
    for value in values:
        normalized = " ".join(str(value or "").split())
        if normalized and not is_generic_device_label(normalized):
            return normalized
    return ""


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
    # MD5 校验由 HashMyFiles.exe 执行，工具条目显示 HashMyFiles 2.51；
    # 存量案件仍持久化旧值 Python hashlib，识别逻辑同时兼容两者。
    tools.append({
        "category": "hashmyfiles",
        "name": "HashMyFiles",
        "version": HASHMYFILES_DISPLAY_VERSION,
        "display_name": f"HashMyFiles {HASHMYFILES_DISPLAY_VERSION}",
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
