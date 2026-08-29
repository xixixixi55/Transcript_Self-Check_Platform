"""第 21 层：规范化本地环境事实并投影处理步骤 3。"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

from ...repository.inspection.local_inspection_environment_repository import LocalInspectionEnvironmentRepository

_EDITION_LABELS = {
    "professional": "专业版",
    "enterprise": "企业版",
    "education": "教育版",
    "core": "家庭版",
    "home": "家庭版",
}


class InspectionEnvironmentService:
    def __init__(self, repository: LocalInspectionEnvironmentRepository | None = None) -> None:
        self.repository = repository or LocalInspectionEnvironmentRepository()

    def capture(self) -> dict[str, Any]:
        facts = self.repository.read()
        os_display = _operating_system_display(facts.get("operating_system"))
        huorong = facts.get("huorong") if isinstance(facts.get("huorong"), Mapping) else {}
        detected = bool(huorong.get("detected"))
        version = _text(huorong.get("version"))
        return {
            "operating_system": {
                "display_name": os_display,
                "status": "detected" if os_display else "unavailable",
            },
            "security_software": {
                "name": "火绒安全软件" if detected else "",
                "version": version,
                "status": "detected" if detected and version else (
                    "version_unknown" if detected else "not_found"
                ),
            },
        }

    def apply_to_report(self, report: Mapping[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(dict(report))
        inspection = value.setdefault("inspection", {})
        snapshot = self.capture()
        inspection["environment_snapshot"] = snapshot
        inspection["process_steps"] = project_environment_step(
            inspection.get("process_steps"), inspection.get("hardware_device"), snapshot,
        )
        return value


def project_environment_step(
    steps: Any, hardware_device: Any, snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source = steps if isinstance(steps, list) else []
    content = build_environment_step(hardware_device, snapshot)
    return [
        {**dict(step), "content": content}
        if isinstance(step, Mapping) and step.get("step_number") == 3
        else copy.deepcopy(dict(step))
        for step in source if isinstance(step, Mapping)
    ]


def build_environment_step(hardware_device: Any, snapshot: Mapping[str, Any]) -> str:
    hardware = _text(hardware_device) or "检查硬件设备待确认"
    os_info = snapshot.get("operating_system")
    security = snapshot.get("security_software")
    os_info = os_info if isinstance(os_info, Mapping) else {}
    security = security if isinstance(security, Mapping) else {}
    os_display = _text(os_info.get("display_name")) if os_info.get("status") == "detected" else ""
    operating_system = os_display or "操作系统信息待确认"
    operating_system_startup = (
        f"{operating_system}操作系统启动正常" if os_display
        else f"{operating_system}启动正常"
    )
    status = security.get("status")
    if status in {"detected", "version_unknown"}:
        name = _text(security.get("name")) or "火绒安全软件"
        version = _text(security.get("version"))
        version_text = f"版本号为{version}" if status == "detected" and version else "版本号待确认"
        return (
            f"启动{hardware}，{operating_system_startup}，使用{name}（{version_text}）"
            f"对{hardware}进行杀毒，未发现病毒，完毕后退出{name}。"
        )
    return (
        f"启动{hardware}，{operating_system_startup}，安全软件待确认（版本号待确认），"
        f"对{hardware}进行杀毒的结果待确认。"
    )


def _operating_system_display(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    product = _text(value.get("product_name"))
    build = _integer(value.get("build_number"))
    if not product:
        return ""
    if build >= 22000:
        product = re.sub(r"Windows\s+10", "Windows 11", product, flags=re.IGNORECASE)
    base_match = re.search(r"Windows\s+(?:10|11)", product, flags=re.IGNORECASE)
    base = base_match.group(0).replace("windows", "Windows") if base_match else product
    edition_id = _text(value.get("edition_id")).casefold()
    edition = next((label for key, label in _EDITION_LABELS.items() if key in edition_id), "")
    machine = _text(value.get("architecture")).casefold()
    bits = "64位" if any(item in machine for item in ("64", "amd64", "arm64")) else (
        "32位" if machine in {"x86", "i386", "i686"} else ""
    )
    variant = f"{bits}{edition}"
    return " ".join(item for item in (base, variant) if item)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _integer(value: Any) -> int:
    try:
        return int(_text(value))
    except ValueError:
        return 0
