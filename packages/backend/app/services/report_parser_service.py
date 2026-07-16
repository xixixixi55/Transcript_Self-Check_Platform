"""
Layer 21: BE_Services — 报告解析编排服务。
REQ-011 缓存 / REQ-012 跳过重复压缩 / REQ-013 压缩开关 / REQ-014 压缩包上传 / REQ-016 动态 software_tools。

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
    create_rar, extract_archive, compute_md5, detect_winrar_version,
)
from ..repository.html_parser import (
    parse_case_info, parse_device_lists, parse_report_info,
    parse_device_base,
    find_base_directories, format_time_chinese, format_time_range_chinese,
)
from .report_defaults_service import DEFAULT_DATA_SUMMARY
# 缓存版本号：解析逻辑变更时递增，自动淘汰旧缓存
_CACHE_VERSION = 4  # v4: data_summary no longer comes from navigation categories

def parse_report(source_dir: str, output_dir: str, compress: bool = True) -> dict:
    """解析报告目录。compress=False 时跳过 RAR 压缩，rar_info 返回 None。"""
    data_dir = os.path.join(source_dir, "data")
    # REQ-011: 检查解析缓存（含版本号，代码变更后自动失效）
    report_name = os.path.basename(source_dir.rstrip("/").rstrip("\\"))
    cache_dir = os.path.join(output_dir, "parsed")
    ensure_dir(cache_dir)
    cache_mode = "compress" if compress else "nocompress"
    cache_path = os.path.join(cache_dir, f"{report_name}.{cache_mode}.json")

    if is_cache_valid(cache_path, source_dir):
        cached = read_json(cache_path)
        if cached.get("report") and cached.get("cache_version") == _CACHE_VERSION:
            return cached

    # 1-7. 解析并构建 InspectionReport
    report = _build_report(data_dir, source_dir, output_dir, compress=compress)

    result = {
        "report": report,
        "cache_version": _CACHE_VERSION,
        "parsed_files": [
            "data_case_info.json", "data_device_lists.json",
            "data_report_info.json", "data_navigation.json",
        ],
        "rar_info": _build_rar_info(report),
    }

    save_json(result, cache_path)
    return result


def parse_from_archive(archive_path: str, output_dir: str) -> dict:
    """从上传的 .rar/.zip 压缩包解析。解压→解析→计算原始压缩包 MD5。REQ-014。"""
    ext = os.path.splitext(archive_path)[1].lower()
    archive_md5 = compute_md5(archive_path)
    archive_size = os.path.getsize(archive_path)

    # 解压到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="report_extract_")
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
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
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
        dev_name = base_info.get("device_name") or dev.get("device_name", "")
        model = base_info.get("model") or dev_name or dev.get("device_name", "")
        device_type = base_info.get("device_name") or base_info.get("model") or dev.get("device_name", "")
        evidence_items.append({
            "id": en,
            "device_type": device_type,
            "model": model,
            "imei1": base_info.get("imei1", ""),
            "imei2": base_info.get("imei2", ""),
            "serial_number": base_info.get("serial_number", ""),
            "evidence_number": en,
        })

    # Fallback: 若所有设备的 base_info 均为空白（Base 目录名不匹配），
    # 改用 find_base_directories 扫描包含 Base/ 子目录的任意目录重新解析
    all_blank = all(
        not ei["device_type"] and not ei["model"] and not ei["imei1"]
        for ei in evidence_items
    )
    if all_blank and evidence_items:
        dirs = find_base_directories(data_dir)
        if dirs:
            base_info = parse_device_base(data_dir, dirs[0])
            if base_info.get("model") or base_info.get("imei1"):
                for ei in evidence_items:
                    ei["device_type"] = base_info.get("device_name") or base_info.get("model", "")
                    ei["model"] = base_info.get("model") or base_info.get("device_name", "")
                    ei["imei1"] = base_info.get("imei1", "")
                    ei["imei2"] = base_info.get("imei2", "")
                    ei["serial_number"] = base_info.get("serial_number", "")

    # 6. 检查过程步骤
    first_device = evidence_items[0] if evidence_items else {
        "model": "", "imei1": "", "imei2": "", "evidence_number": ""}
    sv = _extract_version(versions)
    process_steps = [
        {"step_number": 1, "content": f"将{first_device.get('device_type') or first_device.get('model', '未知设备')}（IMEI1：{first_device.get('imei1', 'xx')}；IMEI2：{first_device.get('imei2', 'xx')}）编号为{first_device.get('evidence_number', 'xx')}。"},
        {"step_number": 2, "content": f"对检材{first_device.get('evidence_number', 'xx')}进行拍照。"},
        {"step_number": 3, "content": "启动美亚FL-901手机取证塔，Windows 10 64位企业版操作系统启动正常，使用火绒安全软件（版本号为6.0.6.1）对取证塔进行杀毒，未发现病毒，完毕后退出火绒安全软件。"},
        {"step_number": 4, "content": f"启动美亚手机大师-并行版V5软件（版本号为{sv}）使用美亚手机大师-并行版V5软件对检材{first_device.get('evidence_number', 'xx')}进行检查。"},
    ]

    # 7. 数据摘要是报告字段默认值，不从导航分类列表动态拼接。
    data_summary = DEFAULT_DATA_SUMMARY

    # 8. 动态 software_tools（REQ-016）
    software_tools = _build_software_tools(sv, compress=compress, is_rar_archive=is_rar_archive)

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
    time_range = devices_raw[0]["time_range"] if devices_raw else ""

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
            "inspection_time_range": format_time_range_chinese(time_range),
            "inspectors": [],
            "inspection_place": "合成检验鉴定中心",
        },
        "inspection": {
            "method": "采用 GA/T 1069-2021《法庭科学电子物证手机检验技术规范》进行检查。",
            "hardware_device": "美亚FL-901手机取证塔",
            "software_tools": software_tools,
            "process_steps": process_steps,
            "result": {
                "evidence_number": first_device.get("evidence_number", ""),
                "software_name": "美亚手机大师-并行版V5",
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


def _build_software_tools(sv: str, compress: bool = True, is_rar_archive: bool = False) -> list[dict]:
    """REQ-016: 动态生成 software_tools。美亚手机大师 + WinRAR（始终显示，默认版本 6.24 可修改）+ Python hashlib（实际版本）。"""
    tools = []
    if sv:
        tools.append({"name": "美亚手机大师-并行版V5", "version": sv})
    # WinRAR 始终显示，默认版本 6.24（用户可在预览中修改）
    version = detect_winrar_version() or "6.24"
    tools.append({"name": "WinRAR压缩管理软件", "version": version})
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    tools.append({"name": "Python hashlib", "version": py_ver})
    return tools


def _build_rar_info_from_compress(source_dir: str, output_dir: str,
                                   case_name: str, compress: bool) -> dict:
    """根据 compress 参数决定是否压缩，返回 rar_info"""
    compressed_dir = os.path.join(output_dir, "compressed")
    return create_rar(source_dir, compressed_dir, case_name, skip=not compress)


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
