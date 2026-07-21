"""Layer 21: BE_Services — 设备配置服务。

封装设备配置的持久化存取，提供输入校验和业务规则。
Controller 通过此服务访问设备数据，不直接依赖 Repository 实现。
"""
from __future__ import annotations
from ..repository.device_config import list_all, insert, update, delete


class DeviceConfigError(Exception):
    """设备配置操作错误。"""


def list_devices() -> list[dict]:
    """获取全部设备列表。"""
    return list_all()


def add_device(name: str, model: str, description: str = "") -> dict:
    """添加设备。

    规则：名称不可为空，同一名称不可重复。
    """
    name = name.strip()
    model = model.strip()
    description = description.strip() if description else ""
    if not name:
        raise DeviceConfigError("设备名称不能为空")
    if any(d["name"] == name for d in list_all()):
        raise DeviceConfigError(f"设备名称 '{name}' 已存在")
    return insert(name, model, description)


def update_device(device_id: str, name: str = "", model: str = "", description: str = "") -> dict:
    """更新设备。

    规则：如提供新名称，不可与其他设备重复。
    """
    name = name.strip() if name else ""
    model = model.strip() if model else ""
    description = description.strip() if description else ""
    if name:
        conflicts = [d for d in list_all() if d["name"] == name and d["id"] != device_id]
        if conflicts:
            raise DeviceConfigError(f"设备名称 '{name}' 已存在")
    result = update(device_id, name, model, description)
    if result is None:
        raise DeviceConfigError(f"设备 '{device_id}' 不存在")
    return result


def delete_device(device_id: str) -> bool:
    """删除设备。"""
    success = delete(device_id)
    if not success:
        raise DeviceConfigError(f"设备 '{device_id}' 不存在")
    return True
