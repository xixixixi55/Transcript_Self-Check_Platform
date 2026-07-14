import os
import sys
import tempfile
import zipfile
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.repository.file_storage import (
    ensure_dir, save_json, read_json, compute_md5,
    create_rar, extract_archive, detect_winrar_version,
)


# ─── 原有测试 ───

def test_ensure_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "a", "b", "c")
        result = ensure_dir(path)
        assert os.path.exists(result)


def test_save_and_read_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.json")
        save_json({"key": "value"}, path)
        data = read_json(path)
        assert data["key"] == "value"


def test_read_json_missing():
    assert read_json("/nonexistent/path.json") == {}


def test_compute_md5():
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "test.txt")
    with open(path, "w") as f:
        f.write("test content")
    result = compute_md5(path)
    assert len(result) == 32
    assert result == "9473fdd0d880a43c21b7778d34872157"


# ─── T006: create_rar + extract_archive + detect_winrar_version ───

def test_create_rar_skip():
    """create_rar skip=True 返回空 rar_info"""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = create_rar(tmpdir, tmpdir, "test", skip=True)
        assert result["filename"] == ""
        assert result["md5"] == ""
        assert result["size_bytes"] == 0


def test_extract_archive_zip():
    """解压 .zip 文件，验证内容正确"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试 .zip
        zip_path = os.path.join(tmpdir, "test.zip")
        inner_dir = os.path.join(tmpdir, "inner")
        os.makedirs(os.path.join(inner_dir, "data"))
        with open(os.path.join(inner_dir, "data", "test.json"), "w") as f:
            f.write('{"key": "value"}')

        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, dirs, files in os.walk(inner_dir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    zf.write(fp, os.path.relpath(fp, tmpdir))

        # 解压
        out_dir = os.path.join(tmpdir, "out")
        extracted_root = extract_archive(zip_path, out_dir)
        assert os.path.exists(extracted_root)
        # 验证 JSON 文件存在
        data_path = os.path.join(extracted_root, "data", "test.json")
        assert os.path.exists(data_path)


def test_extract_archive_invalid_format():
    """不支持的格式抛出 ValueError"""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_path = os.path.join(tmpdir, "test.7z")
        with open(bad_path, "w") as f:
            f.write("dummy")
        with pytest.raises(ValueError, match="不支持的压缩格式"):
            extract_archive(bad_path, tmpdir)


def test_extract_archive_corrupted_zip():
    """损坏的 .zip 文件抛出异常"""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_zip = os.path.join(tmpdir, "corrupt.zip")
        with open(bad_zip, "wb") as f:
            f.write(b"not a valid zip file")
        with pytest.raises((zipfile.BadZipFile, ValueError)):
            extract_archive(bad_zip, tmpdir)


def test_detect_winrar_version():
    """检测 WinRAR 版本，返回字符串或 None（不抛异常）"""
    result = detect_winrar_version()
    assert result is None or isinstance(result, str)
