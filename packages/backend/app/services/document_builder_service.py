"""
Layer 21: BE_Services — docx 文档构建器

将 InspectionReport 转换为 officecli batch JSON 命令数组。
通过 officecli create + batch 生成标准格式检查笔录 .docx。

> 文件行数超过 250 行上限：本文件是 Word 文档生成的核心编排入口，包含 build_record_document
  主流程（标题/绪论/检查/附件/签名/页码 6 大区块）及 _p/_heading/_build_table 等格式辅助函数。
  格式参数集中管理有利于与业务方 Word 标准保持一致，拆分会导致参数分散。

格式参照业务方认可的最终 Word 标准：
- 正文：16pt 仿宋_GB2312，26pt 固定行距，首行缩进 32pt
- 标题：22pt 仿宋_GB2312，居中
- 文号：18pt 仿宋，居中
- 一级标题（一、绪论）：16pt 加粗，首行缩进
- 二级标题（（一）检查方法）：16pt 加粗，缩进 21pt
"""

from .report_defaults_service import normalize_data_summary
from .legacy_report_projection_service import project_ordered_legacy_report
from .entrust_person_service import format_entrust_persons
from .material_policy_service import reviewed_material_display_name


DEFAULT_EXTRACT_COLUMNS = [
    {"key": "no", "title": "序号"},
    {"key": "electronic_data", "title": "电子数据"},
    {"key": "source", "title": "来源"},
    {"key": "extraction_method", "title": "提取方式"},
    {"key": "md5_hash", "title": "文件MD5哈希值"},
]
DEFAULT_EXTRACT_ROWS = [{"no": "1", "electronic_data": "", "source": "", "extraction_method": "", "md5_hash": ""}]


def build_record_document(report: dict, photo_paths: list[str] = None) -> list[dict]:
    """
    构建完整的检查笔录文档结构，返回 officecli batch 命令数组。
    """
    if photo_paths is None:
        photo_paths = []
    report = project_ordered_legacy_report(report)

    intro = report.get("introduction", {})
    insp = report.get("inspection", {})
    attach = report.get("attachments", {})

    commands = []

    # ─── 标题（22pt 仿宋_GB2312 居中）───
    commands.append(_p(
        report.get("title", "电子数据检查笔录"), bold=True,
        size=22, align="center",
    ))
    # ─── 文号（18pt 仿宋 居中）───
    commands.append(_p(report.get("document_number", "xx电检〔20xx〕xx号"), size=18, align="center", spacing_after=400, font_ea="仿宋"))

    # ═══ 一、绪论 ═══
    commands.append(_heading("一、绪论"))

    # (一)～(九)
    entrust_unit = (
        str(intro.get("entrust_unit_prefix", "")).strip()
        + str(intro.get("entrust_unit", "")).strip()
    )
    commands.append(_p(f"（一）委托单位：{entrust_unit}"))
    commands.append(_p(f"（二）委 托 人：{format_entrust_persons(intro.get('entrust_persons'))}"))
    commands.append(_p(f"（三）委托时间：{intro.get('entrust_time', '')}"))
    commands.append(_p(f"（四）案件简要情况：{intro.get('case_summary', '')}"))

    # (五) 检材情况
    commands.append(_p("（五）检材情况："))
    evidence_list = intro.get("evidence_list", [])
    for i, ev in enumerate(evidence_list, 1):
        reviewed_device = reviewed_material_display_name(ev, i - 1)
        device_type = str(ev.get("device_type", "")).strip()
        device = reviewed_device or (
            ev.get("device_name") or ev.get("model", "")
            if device_type.casefold() in {"手机", "智能手机", "phone", "smartphone", "平板", "平板电脑", "tablet"}
            else device_type or ev.get("device_name") or ev.get("model", "")
        )
        extractable = ev.get("extractable")
        if not isinstance(extractable, bool):
            extractable = any(str(ev.get(key, "")).strip() for key in ("imei1", "imei2", "serial_number"))
        details = []
        if extractable:
            for key, label in (("imei1", "IMEI1"), ("imei2", "IMEI2"), ("serial_number", "序列号")):
                if ev.get(key):
                    details.append(f"{label}：{ev[key]}")
        suffix = f"（{'；'.join(details)}）" if details else "" if extractable else "（无法提取）"
        commands.append(_p(f"{i}、{device}一部{suffix}。"))

    commands.append(_p(f"（六）检查要求：{intro.get('inspection_requirement', '')}"))
    commands.append(_p(f"（七）检查起止时间：{intro.get('inspection_time_range', '')}。"))

    # (八) 检查人员
    commands.append(_p("（八）检查人员："))
    for inspector in intro.get("inspectors", []):
        commands.append(_p(f"{inspector.get('name', '')}，{inspector.get('unit', '')}，警号：{inspector.get('badge_number', '')}"))

    commands.append(_p(f"（九）检查地点：{intro.get('inspection_place', '')}。"))

    # ═══ 二、检查 ═══
    commands.append(_heading("二、检查"))

    # (一) 检查方法
    commands.append(_heading_small("（一）检查方法"))
    commands.append(_p(insp.get("method", "")))

    # (二) 检查设备
    commands.append(_heading_small("（二）检查设备"))
    hardware = insp.get("hardware_device", "美亚FL-901手机取证塔")
    commands.append(_p(f"1、硬件设备：{hardware}。"))

    software_tools = insp.get("software_tools", [])
    for i, sw in enumerate(software_tools, 1):
        commands.append(_p(f"{i + 1}、{sw['name']}（版本号为{sw['version']}）。"))

    # (三) 检查过程
    commands.append(_heading_small("（三）检查过程"))
    for step in insp.get("process_steps", []):
        commands.append(_p(f"{step['step_number']}、{step.get('content', '')}"))

    # (四) 检查结果
    commands.append(_heading_small("（四）检查结果"))
    result = insp.get("result", {})
    evidence_numbers = [
        str(item.get("evidence_number")).strip()
        for item in evidence_list
        if item.get("evidence_number")
    ]
    evidence_label = "、".join(evidence_numbers) or result.get("evidence_number", "")
    disc = attach.get("disc_number", "")
    result_text = (
        "经对编号为" + evidence_label + "号检材使用"
        + result.get("software_name", "") + "（版本号为"
        + result.get("software_version", "") + "）进行检查，检出"
        + normalize_data_summary(result.get("data_summary")) + "等电子数据。"
        + "将检出结果生成为\"" + result.get("rar_filename", "") + "\"文件，"
        + "文件MD5哈希值为\"" + str(result.get("md5_hash", "")).upper() + "\"，"
        + "文件大小为\"" + result.get("file_size", "") + "\"字节。"
    )
    # 光盘记录句（参照最终 Word 标准）
    if disc:
        result_text += f"并以光盘方式记录在编号为{disc}的光盘中。"
    commands.append(_p(result_text))

    # ═══ 附件 ═══
    commands.append(_empty_line())
    commands.append(_p("附件：1、电子数据提取固定清单，共1页；"))
    commands.append(_p("2、检材图2张，共1页；"))
    commands.append(_p("3、本鉴定中心刻制的编号为\"" + str(disc) + "\"的光盘1张，共1页。"))

    # 签名区
    commands.append(_empty_line())
    commands.append(_empty_line())
    commands.append(_p("检查人签名：", align="right", first_line=None))
    commands.append(_empty_line())
    commands.append(_p("年  月  日", align="right", first_line=None))

    # ─── 附件1：电子数据提取固定清单 ───
    commands.append(_empty_line())
    commands.append(_p("附件1："))
    commands.append(_p("电子数据提取固定清单", bold=True, size=22, align="center"))

    extract_list = attach.get("extract_list", {})
    commands.extend(_build_table(extract_list))

    # ─── 附件2：检材照片 (REQ-008: officecli 嵌入原图) ───
    commands.append(_empty_line())
    commands.append(_p("附件2："))
    commands.append(_empty_line())
    for i, photo_path in enumerate(photo_paths):
        commands.append({
            "command": "add",
            "parent": "/body",
            "type": "image",
            "props": {
                "file": photo_path,
                "width": "480pt",
                "height": "360pt",
            },
        })
        commands.append(_p(f"检材照片{i + 1}", align="center", size=16, spacing_after=60))

    # ─── 附件3：光盘 ───
    commands.append(_empty_line())
    commands.append(_p("附件3："))
    commands.append(_empty_line())
    commands.append(_p("光盘粘贴处", align="center", first_line=None))
    commands.append(_empty_line())
    if disc:
        commands.append(_p(f"本鉴定中心刻制的{disc}号光盘", align="center", first_line=None))

    # ─── 页码（页脚） ───
    commands.append({
        "command": "add",
        "parent": "/body/sectPr[1]",
        "type": "footer",
        "props": {},
    })
    commands.append({
        "command": "add",
        "parent": "/footer[1]",
        "type": "paragraph",
        "props": {"text": "第 [PAGE] 页 共 [NUMPAGES] 页", "align": "center"},
    })

    return commands


# ═══════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════

def _p(text: str, bold: bool = False, size: int = 16, align: str = "left",
       spacing_after: int = 0, first_line: str | None = "32pt", indent: str | None = None,
       font_ea: str = "仿宋_GB2312") -> dict:
    """创建正文段落（默认 16pt 仿宋_GB2312，26pt 固定行距，首行缩进 32pt）"""
    props: dict = {
        "text": text,
        "bold": str(bold).lower(),
        "size": f"{size}pt",
        "align": align,
        "font.ea": font_ea,
        "spacing.line": "26pt",
        "lineRule": "exact",
    }
    if spacing_after:
        props["spacing.after"] = str(spacing_after)
    if first_line is not None:
        props["indent.firstLine"] = first_line
    if indent is not None:
        props["indent"] = indent
    # 标题附件等不需要首行缩进的段落须显式传 first_line=""
    return {
        "command": "add",
        "parent": "/body",
        "type": "paragraph",
        "props": props,
    }


def _heading(text: str) -> dict:
    """一级标题：16pt 加粗，首行缩进"""
    return _p(text, bold=True)


def _heading_small(text: str) -> dict:
    """二级标题：16pt 加粗，缩进 21pt（无首行缩进）"""
    return _p(text, bold=True, indent="21pt", first_line="")


def _empty_line() -> dict:
    """空行（无缩进）"""
    return _p("", spacing_after=0, first_line="")


def _build_table(table_data: dict) -> list[dict]:
    """构建附件1 表格（表头加粗，仿宋 16pt）"""
    cols = table_data.get("columns") or DEFAULT_EXTRACT_COLUMNS
    rows = table_data.get("rows") or DEFAULT_EXTRACT_ROWS
    all_rows = [[column.get("title", "") for column in cols]] + [
        [_table_cell_value(row, column.get("key", "")) for column in cols]
        for row in rows
    ]
    commands: list[dict] = [{
        "command": "add",
        "parent": "/body",
        "type": "table",
        "props": {
            "cols": str(len(cols)),
            "rows": str(len(all_rows)),
            "border.all": "single;4;000000",
        },
    }]
    for row_index, values in enumerate(all_rows, 1):
        for column_index, value in enumerate(values, 1):
            commands.append({
                "command": "set",
                "path": f"/body/tbl[1]/tr[{row_index}]/tc[{column_index}]",
                "props": {
                    "text": value,
                    "bold": "true" if row_index == 1 else "false",
                    "size": "16pt",
                    "font.ea": "仿宋_GB2312",
                    "align": "center" if row_index == 1 else "left",
                },
            })
    return commands


def _table_cell_value(row: dict, key: str) -> str:
    value = str(row.get(key, ""))
    if key == "md5_hash":
        return value.upper()
    if key == "source":
        source = value.strip()
        if source.endswith("内提取") and not source.endswith("检材内提取"):
            return source[:-3] + "检材内提取"
    return value
