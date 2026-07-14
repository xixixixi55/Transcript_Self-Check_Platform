"""
Layer 21: BE_Services — docx 文档构建器

将 InspectionReport 转换为 officecli batch JSON 命令数组。
通过 officecli create + batch 生成标准格式检查笔录 .docx。
"""


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

    intro = report.get("introduction", {})
    insp = report.get("inspection", {})
    attach = report.get("attachments", {})

    commands = []

    # ─── 标题 ───
    commands.append(_p(report.get("title", "电子数据检查笔录"), bold=True, size=32, align="center"))
    commands.append(_p(report.get("document_number", "xx电检〔20xx〕xx号"), size=20, align="center", spacing_after=400))

    # ═══ 一、绪论 ═══
    commands.append(_heading("一、绪论"))

    # (一)
    commands.append(_p(f"（一）委托单位：{intro.get('entrust_unit', '')}"))
    commands.append(_p(f"（二）委 托 人：{intro.get('entrust_person', '')}"))
    commands.append(_p(f"（三）委托时间：{intro.get('entrust_time', '')}"))
    commands.append(_p(f"（四）案件简要情况：{intro.get('case_summary', '')}"))

    # (五) 检材情况
    commands.append(_p("（五）检材情况："))
    evidence_list = intro.get("evidence_list", [])
    for i, ev in enumerate(evidence_list, 1):
        parts = [f"{ev.get('device_type') or ev.get('model', '')}一部"]
        if ev.get("imei1"):
            parts.append(f"IMEI1：{ev['imei1']}")
        if ev.get("imei2"):
            parts.append(f"IMEI2：{ev['imei2']}")
        if ev.get("serial_number"):
            parts.append(f"序列号：{ev['serial_number']}")
        commands.append(_p(f"{i}、{'（'.join(parts)}）。" if "IMEI" in " ".join(parts) else f"{i}、{' '.join(parts)}。"))

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
    result_text = (
        "经对编号为" + result.get("evidence_number", "") + "号检材使用"
        + result.get("software_name", "") + "（版本号为"
        + result.get("software_version", "") + "）进行检查，检出"
        + result.get("data_summary", "") + "等电子数据。"
        + "将检出结果生成为\"" + result.get("rar_filename", "") + "\"文件，"
        + "文件MD5哈希值为\"" + result.get("md5_hash", "") + "\"，"
        + "文件大小为\"" + result.get("file_size", "") + "\"字节。"
    )
    commands.append(_p(result_text))

    # ═══ 附件 ═══
    commands.append(_empty_line())
    commands.append(_p("附件：1、电子数据提取固定清单，共1页；"))
    commands.append(_p("2、检材图2张，共1页；"))
    disc = attach.get("disc_number", "")
    commands.append(_p("3、本鉴定中心刻制的编号为\"" + str(disc) + "\"的光盘1张，共1页。"))

    # 签名区
    commands.append(_empty_line())
    commands.append(_empty_line())
    commands.append(_p("检查人签名：", align="right"))
    commands.append(_empty_line())
    commands.append(_p("年  月  日", align="right"))

    # ─── 附件1：电子数据提取固定清单 ───
    commands.append(_empty_line())
    commands.append(_p("附件1："))
    commands.append(_p("电子数据提取固定清单", bold=True, align="center"))

    extract_list = attach.get("extract_list", {})
    commands.extend(_build_table(extract_list))

    # ─── 附件2：检材照片 (REQ-008: officecli 嵌入原图) ───
    commands.append(_empty_line())
    commands.append(_p("附件2："))
    commands.append(_empty_line())
    for i, photo_path in enumerate(photo_paths):
        # 嵌入图片原图
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
        # 图片下方标签
        commands.append(_p(f"检材照片{i + 1}", align="center", size=20, spacing_after=60))

    # ─── 附件3：光盘 ───
    commands.append(_empty_line())
    commands.append(_p("附件3："))
    commands.append(_empty_line())
    commands.append(_p("光盘粘贴处", align="center"))
    commands.append(_empty_line())
    if disc:
        commands.append(_p(f"本鉴定中心刻制的{disc}号光盘", align="center"))

    # ─── 页码（页脚） ───
    # 空白 docx 没有预置 footer。需先通过 sectPr 创建 footer 部件（officecli
    # 会自动在 /footer 区域创建），再将页码段落写入 /footer[1]。
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


def _p(text: str, bold: bool = False, size: int = 24, align: str = "left",
       spacing_after: int = 120) -> dict:
    """创建段落命令"""
    return {
        "command": "add",
        "parent": "/body",
        "type": "paragraph",
        "props": {
            "text": text,
            "bold": str(bold).lower(),
            "size": f"{size}pt",
            "align": align,
            "spacing.after": str(spacing_after),
        },
    }


def _heading(text: str) -> dict:
    """一级标题"""
    return _p(text, bold=True, size=28, spacing_after=200)


def _heading_small(text: str) -> dict:
    """二级标题"""
    return _p(text, bold=True, size=24, spacing_after=100)


def _empty_line() -> dict:
    """空行"""
    return _p("", spacing_after=60)


def _add_image(path: str, caption: str) -> dict:
    """添加图片"""
    return {
        "command": "add",
        "parent": "/body",
        "type": "paragraph",
        "props": {
            "text": caption,
            "size": "20pt",
            "align": "center",
        },
    }


def _build_table(table_data: dict) -> list[dict]:
    """构建表格"""
    cols = table_data.get("columns") or DEFAULT_EXTRACT_COLUMNS
    rows = table_data.get("rows") or DEFAULT_EXTRACT_ROWS
    all_rows = [[column.get("title", "") for column in cols]] + [
        [str(row.get(column.get("key", ""), "")) for column in cols]
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
                },
            })
    return commands
