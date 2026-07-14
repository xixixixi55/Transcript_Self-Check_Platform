"""
Layer 21: BE_Services — 报告解析编排服务。
REQ-011 缓存 / REQ-012 跳过重复压缩 / REQ-013 压缩开关 / REQ-014 压缩包上传 / REQ-016 动态 software_tools。
"""
import os
import shutil
import tempfile
from typing import Optional
from ..repository.file_storage import (
    is_cache_valid, save_json, read_json, ensure_dir,
    create_rar, extract_archive, compute_md5, detect_winrar_version,
)
from ..repository.html_parser import (
    parse_case_info, parse_device_lists, parse_report_info,
    parse_navigation, parse_device_base,
)
def parse_report(source_dir: str, output_dir: str, compress: bool = True) -> dict:
    """解析报告目录。compress=False 时跳过 RAR 压缩，rar_info 返回 None。"""
    data_dir = os.path.join(source_dir, "data")
    # REQ-011: 检查解析缓存
    report_name = os.path.basename(source_dir.rstrip("/").rstrip("\\"))
    cache_dir = os.path.join(output_dir, "parsed")
    ensure_dir(cache_dir)
    # 压缩结果和不压缩结果的 rar_info、software_tools 不同，必须隔离缓存。
    cache_mode = "compress" if compress else "nocompress"
    cache_path = os.path.join(cache_dir, f"{report_name}.{cache_mode}.json")

    if is_cache_valid(cache_path, source_dir):
        cached = read_json(cache_path)
        if cached.get("report"):
            return cached

    # 1-7. 解析并构建 InspectionReport
    report = _build_report(data_dir, source_dir, output_dir, compress=compress)

    result = {
        "report": report,
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
            "file_size": _format_file_size(archive_size),
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


def _build_report(data_dir: str, source_dir: str, output_dir: str,
                  compress: bool = True, is_rar_archive: bool = False) -> dict:
    """构建 InspectionReport（parse_report / parse_from_archive 共用）"""
    # 1. 解析案件信息
    case = parse_case_info(data_dir)
    # 2. 解析设备列表
    devices_raw = parse_device_lists(data_dir)
    # 3. 解析取证工具版本
    versions = parse_report_info(data_dir)
    # 4. 解析数据分类统计
    nav = parse_navigation(data_dir)

    # 5. 解析每个设备的基本信息
    evidence_items = []
    for dev in devices_raw:
        en = dev["evidence_number"]
        base_info = parse_device_base(data_dir, en)
        evidence_items.append({
            "id": en,
            "device_type": base_info.get("device_name") or base_info.get("model", ""),
            "model": base_info.get("model") or base_info.get("device_name", ""),
            "imei1": base_info.get("imei1", ""),
            "imei2": base_info.get("imei2", ""),
            "serial_number": base_info.get("serial_number", ""),
            "evidence_number": en,
        })

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

    # 7. 数据分类摘要
    categories = nav.get("categories", [])
    data_summary = "、".join(_filter_categories(categories)[:5]) or "电子数据"

    # 8. 动态 software_tools（REQ-016）
    software_tools = _build_software_tools(sv, compress=compress, is_rar_archive=is_rar_archive)

    # 9. 条件压缩 RAR
    rar_info = _build_rar_info_from_compress(source_dir, output_dir, case.get("case_name", "report"), compress)

    # 10. 构建 InspectionReport
    time_range = devices_raw[0]["time_range"] if devices_raw else ""

    # 用于前端生成文号的原始数据
    _case_number = case.get("case_number", "")
    _collect_unit = case.get("collect_unit", "")

    return {
        "title": "电子数据检查笔录",
        "document_number": "",
        "case_number": _case_number,  # 前端用此值生成文号
        "introduction": {
            "entrust_unit": _collect_unit,
            "entrust_person": case.get("collector", ""),
            "entrust_time": case.get("create_time", ""),
            "case_summary": f"{case.get('case_name', '')}案",
            "evidence_list": evidence_items,
            "inspection_requirement": "上述检材内电子数据的提取、固定和恢复",
            "inspection_time_range": time_range,
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
                "file_size": rar_info["size_display"],
            },
        },
        "attachments": {
            "extract_list": {"columns": [], "rows": []},
            "photo_ids": [],
            "disc_number": "",
        },
    }


def _build_software_tools(sv: str, compress: bool = True, is_rar_archive: bool = False) -> list[dict]:
    """REQ-016: 动态生成 software_tools。美亚手机大师（始终）+ WinRAR（仅当调用 CLI 时）。"""
    tools = []
    if sv:
        tools.append({"name": "美亚手机大师-并行版V5", "version": sv})
    if compress or is_rar_archive:
        version = detect_winrar_version() or "6.24"
        tools.append({"name": "WinRAR压缩管理软件", "version": version})
    tools.append({"name": "Python hashlib", "version": "标准库"})
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
