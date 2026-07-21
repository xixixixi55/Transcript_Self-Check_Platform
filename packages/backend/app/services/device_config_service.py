"""Layer 21: BE_Services — 设备配置服务。

封装设备配置的持久化存取，提供输入规范化和错误归一化。
Controller 通过此服务访问设备数据，不直接依赖 Repository 实现。

本模块不新增业务约束 — Pydantic 校验在 Controller 层完成，
数据完整性规则由 Repository 的存储实现保证。
"""
from __future__ import annotations
from ..repository.device_config import list_all, insert, update, delete


class DeviceConfigError(Exception):
    """设备配置操作错误。"""


def list_devices() -> list[dict]:
    """获取全部设备列表。"""
    return list_all()


def add_device(name: str, model: str, description: str = "") -> dict:
    """添加设备。输入规范化后委托 Repository。"""
    return insert(name.strip(), model.strip(), description.strip() if description else "")


def update_device(device_id: str, name: str = "", model: str = "", description: str = "") -> dict:
    """更新设备。输入规范化后委托 Repository。"""
    result = update(
        device_id,
        name.strip() if name else "",
        model.strip() if model else "",
        description.strip() if description else "",
    )
    if result is None:
        raise DeviceConfigError(f"设备 '{device_id}' 不存在")
    return result


def delete_device(device_id: str) -> bool:
    """删除设备。"""
    if not delete(device_id):
        raise DeviceConfigError(f"设备 '{device_id}' 不存在")
    return True
