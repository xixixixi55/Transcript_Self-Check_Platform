"""Layer 21: BE_Services — 设备配置服务。

封装设备配置的持久化存取，提供输入规范化和错误归一化。
Controller 通过此服务访问设备数据，不直接依赖 Repository 实现。

所属公司由本服务统一清洗和校验；Controller 负责 HTTP 请求形状，Repository 只负责存取。
"""
from __future__ import annotations
from ..repository.device_config import list_all, insert, update, delete


class DeviceConfigError(Exception):
    """设备配置操作错误。"""


def list_devices() -> list[dict]:
    """获取全部设备列表。"""
    return list_all()


def add_device(name: str, model: str, company: str, description: str = "") -> dict:
    """添加设备。输入规范化后委托 Repository。"""
    company_value = _required_company(company)
    return insert(
        name.strip(), model.strip(), company_value,
        description.strip() if description else "",
    )


def update_device(
    device_id: str, name: str = "", model: str = "", description: str = "",
    company: str | None = None,
) -> dict:
    """更新设备。输入规范化后委托 Repository。"""
    company_value = _required_company(company) if company is not None else None
    result = update(
        device_id,
        name.strip() if name else "",
        model.strip() if model else "",
        description.strip() if description else "",
        company_value,
    )
    if result is None:
        raise DeviceConfigError(f"设备 '{device_id}' 不存在")
    return result


def delete_device(device_id: str) -> bool:
    """删除设备。"""
    if not delete(device_id):
        raise DeviceConfigError(f"设备 '{device_id}' 不存在")
    return True


def company_for_device_name(device_name: object) -> str:
    """Return one configured company only when the normalized device name is unique."""
    key = _device_name_key(device_name)
    if not key:
        return ""
    try:
        devices = list_all()
    except (OSError, TypeError, ValueError):
        return ""
    matches = [item for item in devices if _device_name_key(item.get("name")) == key]
    if len(matches) != 1:
        return ""
    return str(matches[0].get("company") or "").strip()


def _required_company(company: object) -> str:
    value = str(company or "").strip()
    if not value:
        raise DeviceConfigError("所属公司不能为空")
    return value


def _device_name_key(value: object) -> str:
    return "".join(str(value or "").split()).casefold()
