"""
CleanCLI - 单元测试
测试核心功能：工具函数、路径安全检查、格式化、数据结构
"""

import os
import sys
import tempfile
import unittest

# 确保可以导入 cleancli
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cleancli.cleaner import (
    _get_size, _get_mtime, _is_path_safe,
    _safe_remove_file, _safe_remove_dir, _existing_drives,
    CleanItem, ScanResult,
)
from cleancli.ui import fmt_size, fmt_age


class TestFmtSize(unittest.TestCase):
    """测试文件大小格式化"""

    def test_zero(self):
        self.assertEqual(fmt_size(0), "0 B")

    def test_bytes(self):
        self.assertEqual(fmt_size(512), "512 B")

    def test_kilobytes(self):
        result = fmt_size(1024)
        self.assertIn("KB", result)
        self.assertIn("1.0", result)

    def test_megabytes(self):
        result = fmt_size(1024 * 1024)
        self.assertIn("MB", result)

    def test_gigabytes(self):
        result = fmt_size(1024 * 1024 * 1024)
        self.assertIn("GB", result)

    def test_negative(self):
        self.assertEqual(fmt_size(-100), "0 B")

    def test_ui_fmt_size_consistency(self):
        """fmt_size 应一致处理各种大小"""
        for size in [0, 512, 1024, 1024**2, 1024**3]:
            result = fmt_size(size)
            self.assertIsInstance(result, str)


class TestFmtAge(unittest.TestCase):
    """测试年龄格式化"""

    def test_zero(self):
        self.assertEqual(fmt_age(0), "不限")

    def test_days(self):
        self.assertEqual(fmt_age(15), "15天+")

    def test_months(self):
        self.assertEqual(fmt_age(60), "2个月+")

    def test_years(self):
        self.assertEqual(fmt_age(400), "1年+")


class TestExistingDrives(unittest.TestCase):
    """测试驱动器检测"""

    def test_returns_list(self):
        drives = _existing_drives()
        self.assertIsInstance(drives, list)

    def test_c_drive_exists(self):
        drives = _existing_drives()
        self.assertIn("C", drives)

    def test_no_invalid_drives(self):
        drives = _existing_drives()
        for d in drives:
            self.assertTrue(os.path.isdir(f"{d}:\\"))


class TestGetSize(unittest.TestCase):
    """测试文件/目录大小计算"""

    def test_nonexistent_path(self):
        self.assertEqual(_get_size("/nonexistent/path/abc123"), 0)

    def test_file_size(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            f.write(b"hello world")
            path = f.name
        try:
            size = _get_size(path)
            self.assertEqual(size, 11)
        finally:
            os.unlink(path)

    def test_directory_size(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "test.txt")
            with open(fp, "w") as f:
                f.write("test data")
            size = _get_size(d)
            self.assertEqual(size, 9)


class TestGetMtime(unittest.TestCase):
    """测试修改时间获取"""

    def test_nonexistent_path(self):
        self.assertEqual(_get_mtime("/nonexistent/path/abc123"), 0.0)

    def test_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            f.write(b"test")
            path = f.name
        try:
            mtime = _get_mtime(path)
            self.assertGreater(mtime, 0)
        finally:
            os.unlink(path)


class TestIsPathSafe(unittest.TestCase):
    """测试路径安全检查"""

    def test_nonexistent_path(self):
        self.assertFalse(_is_path_safe("/nonexistent/path/abc123"))

    def test_temp_dir_is_safe(self):
        temp_dir = tempfile.gettempdir()
        # 创建一个临时文件来测试
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            path = f.name
        try:
            self.assertTrue(_is_path_safe(path))
        finally:
            os.unlink(path)

    def test_system32_not_safe(self):
        system32 = os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "System32")
        self.assertFalse(_is_path_safe(system32))

    def test_config_has_entries(self):
        from cleancli.config import SAFE_PATH_PREFIXES
        self.assertGreater(len(SAFE_PATH_PREFIXES), 0)


class TestScanResult(unittest.TestCase):
    """测试 ScanResult 数据结构"""

    def test_empty_result(self):
        r = ScanResult(category="test")
        self.assertEqual(r.category, "test")
        self.assertEqual(len(r.items), 0)
        self.assertEqual(r.total_size, 0)
        self.assertEqual(r.error, "")

    def test_add_item(self):
        r = ScanResult(category="test")
        item = CleanItem(
            path="/tmp/test.txt",
            size=1024,
            category="test",
            item_type="file",
        )
        r.add_item(item)
        self.assertEqual(len(r.items), 1)
        self.assertEqual(r.total_size, 1024)

    def test_add_multiple_items(self):
        r = ScanResult(category="test")
        for i in range(5):
            r.add_item(CleanItem(
                path=f"/tmp/test{i}.txt",
                size=100,
                category="test",
                item_type="file",
            ))
        self.assertEqual(len(r.items), 5)
        self.assertEqual(r.total_size, 500)


class TestCleanItem(unittest.TestCase):
    """测试 CleanItem 数据结构"""

    def test_creation(self):
        item = CleanItem(
            path="/tmp/test.txt",
            size=1024,
            category="temp",
            item_type="file",
            description="test file",
            modified_time=1234567890.0,
        )
        self.assertEqual(item.path, "/tmp/test.txt")
        self.assertEqual(item.size, 1024)
        self.assertEqual(item.category, "temp")
        self.assertEqual(item.item_type, "file")
        self.assertEqual(item.description, "test file")
        self.assertEqual(item.modified_time, 1234567890.0)


class TestSafeRemove(unittest.TestCase):
    """测试安全删除功能"""

    def test_remove_nonexistent_file(self):
        ok, err = _safe_remove_file("/nonexistent/path/abc123.txt")
        # 不存在的文件应该返回成功（已经删除了）
        self.assertTrue(ok)

    def test_remove_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            f.write(b"test")
            path = f.name
        ok, err = _safe_remove_file(path)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertFalse(os.path.exists(path))

    def test_remove_nonexistent_dir(self):
        ok, err = _safe_remove_dir("/nonexistent/path/abc123_dir")
        self.assertTrue(ok)

    def test_remove_dir(self):
        d = tempfile.mkdtemp()
        fp = os.path.join(d, "test.txt")
        with open(fp, "w") as f:
            f.write("test")
        ok, err = _safe_remove_dir(d)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertFalse(os.path.exists(d))


class TestConfig(unittest.TestCase):
    """测试配置模块"""

    def test_system_dirs_is_set(self):
        from cleancli.config import SYSTEM_DIRS
        self.assertIsInstance(SYSTEM_DIRS, set)
        self.assertIn("microsoft", SYSTEM_DIRS)
        self.assertIn("windows", SYSTEM_DIRS)

    def test_safe_prefixes_filtered(self):
        from cleancli.config import SAFE_PATH_PREFIXES
        for p in SAFE_PATH_PREFIXES:
            self.assertTrue(p, "白名单中不应有空字符串")


if __name__ == "__main__":
    unittest.main()
