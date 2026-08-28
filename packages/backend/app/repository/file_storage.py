"""
Layer 20: BE_Repository — 文件存取模块

处理报告上传、JSON 缓存读写、RAR 生成、压缩包解压。
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from typing import Optional

from .winrar_discovery_repository import discover_winrar

def _find_winrar() -> Optional[str]:
    """使用统一发现策略查找已验证的 WinRAR/RAR 可执行文件。"""
    capability = discover_winrar()
    return capability.executable_path if capability.available else None


def detect_winrar_version() -> Optional[str]:
    """检测已安装的 WinRAR 版本号（如 "6.24"），未找到返回 None"""
    capability = discover_winrar()
    return capability.version if capability.available else None


def ensure_dir(path: str) -> str:
    """确保目录存在，返回目录路径"""
    os.makedirs(path, exist_ok=True)
    return path


def save_upload_dir(source_dir: str, dest_root: str) -> str:
    """
    保存上传的报告目录到项目存储区。
    返回目标目录路径。
    """
    dirname = os.path.basename(source_dir)
    dest_dir = os.path.join(dest_root, dirname)

    # 如果目标已存在，加时间戳后缀
    if os.path.exists(dest_dir):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        dest_dir = os.path.join(dest_root, f"{dirname}_{timestamp}")

    ensure_dir(os.path.dirname(dest_dir))
    shutil.copytree(source_dir, dest_dir)
    return dest_dir


def save_json(data: dict, filepath: str) -> None:
    """保存 JSON 到文件"""
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(filepath: str) -> dict:
    """读取 JSON 文件，不存在时返回空 dict"""
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def is_cache_valid(cache_path: str, source_dir: str) -> bool:
    """检查缓存是否有效（缓存存在且比源文件新）"""
    if not os.path.exists(cache_path):
        return False
    cache_time = os.path.getmtime(cache_path)
    # 检查源目录中最新的 JSON 文件
    data_dir = os.path.join(source_dir, "data")
    if not os.path.exists(data_dir):
        return False
    latest_source = cache_time
    for root, _dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith(".json"):
                mtime = os.path.getmtime(os.path.join(root, f))
                if mtime > latest_source:
                    latest_source = mtime
    return cache_time >= latest_source


def file_exists_and_valid(filepath: str) -> bool:
    """检查文件是否存在且大小 > 0"""
    return os.path.exists(filepath) and os.path.getsize(filepath) > 0


def compute_md5(filepath: str) -> str:
    """计算文件的 MD5 哈希值"""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_rar(source_dir: str, output_dir: str, archive_name: str,
               force: bool = False, skip: bool = False) -> dict:
    """已弃用的单卷辅助函数；绝不回退到 ZIP。"""
    if skip:
        return {
            "filename": "",
            "filepath": "",
            "md5": "",
            "size_bytes": 0,
            "size_display": "",
        }
    raise ValueError("ARCHIVE_PLAN_INVALID")


def extract_archive(archive_path: str, output_dir: str) -> str:
    """解压 .rar/.zip 到指定目录，返回解压后的根目录路径。失败抛出 ValueError。"""
    ensure_dir(output_dir)
    ext = os.path.splitext(archive_path)[1].lower()
    if ext == ".zip":
        return _extract_zip(archive_path, output_dir)
    elif ext == ".rar":
        return _extract_rar(archive_path, output_dir)
    else:
        raise ValueError(f"不支持的压缩格式: {ext}，仅支持 .rar 和 .zip")


def _extract_zip(zip_path: str, output_dir: str) -> str:
    """解压 .zip 文件，返回根目录路径"""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        root_prefix = _common_prefix(names)
        zf.extractall(output_dir)
    return os.path.join(output_dir, root_prefix) if root_prefix else output_dir


def _extract_rar(rar_path: str, output_dir: str) -> str:
    """使用 WinRAR CLI 解压 .rar 文件，返回根目录路径"""
    winrar = _find_winrar()
    if not winrar:
        raise ValueError("WinRAR 未安装，无法解压 .rar 文件。请安装 WinRAR 或使用 .zip 格式。")
    # 列出内容以确定根目录
    list_result = subprocess.run(
        [winrar, "vb", rar_path], capture_output=True, text=True, timeout=30)
    root_prefix = _common_prefix(list_result.stdout.strip().split("\n"))
    # 解压
    result = subprocess.run(
        [winrar, "x", "-y", rar_path, output_dir],
        capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise ValueError(f"RAR 解压失败: {result.stderr or result.stdout}")
    return os.path.join(output_dir, root_prefix) if root_prefix else output_dir


def _common_prefix(paths: list[str]) -> str:
    """找到路径列表的公共根目录前缀（最外层文件夹名）"""
    paths = [p.replace("\\", "/").strip("/") for p in paths if p]
    if not paths:
        return ""
    top_dir = paths[0].split("/")[0]
    for p in paths:
        if not p.startswith(top_dir):
            return ""
    return top_dir


def _format_size(bytes_val: int) -> str:
    """格式化字节数"""
    if bytes_val < 1024:
        return f"{bytes_val} 字节"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"
