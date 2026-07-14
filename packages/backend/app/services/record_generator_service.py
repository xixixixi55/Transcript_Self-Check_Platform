"""
Layer 21: BE_Services — 笔录文档生成服务

负责：
1. 构建文档结构 (document_builder_service)
2. 创建 .docx (officecli create)
3. 应用 batch 命令写入内容 (officecli batch)
4. 返回文件路径供下载
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from .document_builder_service import build_record_document

# 查找 officecli 完整路径（Windows: .cmd, Unix: 无扩展名）
_OFFICECLI = shutil.which("officecli") or shutil.which("officecli.cmd")
if not _OFFICECLI:
    raise RuntimeError("officecli 未安装或不在 PATH 中。请运行: npm install -g officecli")

# subprocess 公共参数
# encoding='utf-8': 中文 Windows 默认 GBK，officecli 输出 UTF-8
_SUBPROCESS_KWARGS = dict(capture_output=True, encoding="utf-8")

def _run_officecli(*args: str) -> subprocess.CompletedProcess:
    """调用 officecli。uvicorn 子进程的 PATH 可能不完整（缺少 npm 全局目录
    和 System32），因此：
    1. 使用 shutil.which 查找 officecli 绝对路径（含 .CMD 扩展名）
    2. 在子进程 env 中显式注入 System32 路径，确保 Windows 能通过 cmd.exe
       执行 .CMD 批处理文件
    3. encoding='utf-8' 处理 officecli 的 UTF-8 输出
    """
    env = os.environ.copy()
    # 确保 cmd.exe 所在目录在 PATH 中（.CMD 文件依赖 cmd.exe 执行）
    system32 = r"C:\Windows\System32"
    if system32 not in env.get("PATH", ""):
        env["PATH"] = system32 + ";" + env.get("PATH", "")
    return subprocess.run(
        [_OFFICECLI, *args],
        env=env,
        **_SUBPROCESS_KWARGS,
    )


def generate_docx(report: dict, photo_paths: list[str] = None, output_dir: str = None) -> str:
    """
    生成检查笔录 .docx 文件。
    返回生成的 .docx 文件路径。
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()

    os.makedirs(output_dir, exist_ok=True)

    # 生成安全的文件名（移除文件名不支持的特殊字符）
    doc_number = report.get("document_number", "").replace("/", "-").replace("\\", "-")
    safe_doc_number = doc_number.replace("〔", "[").replace("〕", "]") if doc_number else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_doc_number or '检查笔录'}_{timestamp}.docx"
    filepath = os.path.join(output_dir, filename)

    # 1. 构建文档命令
    commands = build_record_document(report, photo_paths or [])

    # 2. 创建空白 docx
    result = _run_officecli("create", filepath)
    if result.returncode != 0:
        raise RuntimeError(f"officecli create 失败: stdout={result.stdout} stderr={result.stderr}")

    # 3. 批量写入内容 — 通过临时文件传入命令
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(commands, tmp, ensure_ascii=False)
        tmp_path = tmp.name

    try:
        result = _run_officecli("batch", filepath, "--input", tmp_path)
        if result.returncode != 0:
            raise RuntimeError(f"officecli batch 失败: {result.stderr}")
    finally:
        os.unlink(tmp_path)

    save_result = _run_officecli("save", filepath)
    if save_result.returncode != 0:
        raise RuntimeError(f"officecli save failed: {save_result.stderr}")

    if not os.path.isfile(filepath) or os.path.getsize(filepath) == 0:
        raise RuntimeError("officecli 生成的 Word 文档为空")

    return filepath
