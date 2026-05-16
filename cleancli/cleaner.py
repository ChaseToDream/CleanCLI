"""
CleanCLI - 核心清理引擎 v3.1
深度扫描和清理Windows系统垃圾文件
改进：重试机制、只读属性清除、详细错误追踪、批量处理、注册机制
"""

import os
import glob
import shutil
import tempfile
import ctypes
import stat
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from cleancli.config import SAFE_PATH_PREFIXES


@dataclass
class CleanItem:
    """待清理项目"""
    path: str
    size: int  # bytes
    category: str
    item_type: str  # file / dir / dns_cache / command
    description: str = ""
    modified_time: float = 0.0


@dataclass
class CleanItemResult:
    """单个项目的清理结果"""
    item: CleanItem
    success: bool
    error: str = ""  # locked / permission / not_found / unknown


@dataclass
class ScanResult:
    """扫描结果"""
    category: str
    items: List[CleanItem] = field(default_factory=list)
    total_size: int = 0
    error: str = ""

    def add_item(self, item: CleanItem):
        self.items.append(item)
        self.total_size += item.size


def _get_size(path: str) -> int:
    """获取文件或目录大小"""
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        elif os.path.isdir(path):
            total = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except (OSError, PermissionError):
                        pass
            return total
    except (OSError, PermissionError):
        pass
    return 0


def _get_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except (OSError, PermissionError):
        return 0.0


def _existing_drives() -> List[str]:
    """返回系统中存在的驱动器盘符列表"""
    return [d for d in "CDEFGHIJ" if os.path.isdir(f"{d}:\\")]


def _clear_readonly(func, path, exc):
    """shutil.rmtree 的 onerror 回调：清除只读属性后重试"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except (OSError, PermissionError):
        pass


def _safe_remove_file(path: str, retries: int = 2, delay: float = 0.3) -> Tuple[bool, str]:
    """
    安全删除文件，带重试机制
    返回 (成功, 错误原因)
    """
    for attempt in range(retries + 1):
        try:
            try:
                attrs = os.stat(path).st_mode
                if not (attrs & stat.S_IWRITE):
                    os.chmod(path, stat.S_IWRITE)
            except (OSError, PermissionError):
                pass
            os.remove(path)
            return True, ""
        except PermissionError:
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
                continue
            return False, "locked"
        except FileNotFoundError:
            return True, ""
        except OSError as e:
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
                continue
            return False, "unknown"
    return False, "unknown"


def _safe_remove_dir(path: str, retries: int = 2, delay: float = 0.3) -> Tuple[bool, str]:
    """
    安全删除目录，带重试和只读属性处理
    返回 (成功, 错误原因)
    """
    for attempt in range(retries + 1):
        try:
            shutil.rmtree(path, onerror=_clear_readonly)
            return True, ""
        except PermissionError:
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
                continue
            return False, "locked"
        except FileNotFoundError:
            return True, ""
        except OSError:
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
                continue
            return False, "unknown"
    return False, "unknown"


def _is_path_safe(path: str) -> bool:
    """检查路径是否安全（防止误删重要文件）"""
    path_lower = os.path.normcase(os.path.normpath(path)).lower()
    if not os.path.exists(path):
        return False
    for prefix in SAFE_PATH_PREFIXES:
        if not prefix:
            continue
        norm_prefix = os.path.normcase(os.path.normpath(prefix)).lower()
        if path_lower.startswith(norm_prefix):
            return True
    return False


class JunkScanner:
    """系统垃圾文件扫描器"""

    def __init__(self, older_than_days: int = 0, min_size_bytes: int = 0):
        self.user_profile = os.environ.get("USERPROFILE", "")
        self.local_appdata = os.environ.get("LOCALAPPDATA", "")
        self.appdata = os.environ.get("APPDATA", "")
        self.program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        self.windir = os.environ.get("SYSTEMROOT", os.environ.get("WINDIR", r"C:\Windows"))
        self.temp_dir = tempfile.gettempdir()
        self.older_than_days = older_than_days
        self.min_size_bytes = min_size_bytes
        self._now = time.time()

    def _passes_filters(self, size: int, mtime: float) -> bool:
        """检查是否通过年龄和大小过滤"""
        if self.min_size_bytes > 0 and size < self.min_size_bytes:
            return False
        if self.older_than_days > 0 and mtime > 0:
            cutoff = self._now - (self.older_than_days * 86400)
            if mtime > cutoff:
                return False
        return True

    def scan_all(self, max_workers: int = 4) -> List[ScanResult]:
        """执行全盘垃圾扫描（并行，使用注册机制）"""
        # 导入 scanners 包以触发注册
        from cleancli.scanners import get_all_scanners, ScanContext
        ctx = ScanContext.from_scanner(self)
        registered = get_all_scanners()

        results: List[ScanResult] = [None] * len(registered)

        def _run(idx_name_fn):
            idx, name, fn = idx_name_fn
            try:
                result = fn(ctx)
                result.category = name
                return idx, result
            except Exception as e:
                return idx, ScanResult(category=name, error=str(e))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run, (i, name, fn)): i
                for i, (name, fn) in enumerate(registered)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result

        return results


def clean_items(items: List[CleanItem], dry_run: bool = False,
                on_error=None) -> Tuple[int, int, int, List[CleanItemResult]]:
    """
    清理指定项目
    返回 (成功数, 失败数, 释放空间, 详细结果列表)
    on_error: 可选回调函数，签名 on_error(item: CleanItem, error: str)，每次失败时调用
    """
    success = 0
    failed = 0
    freed = 0
    details: List[CleanItemResult] = []

    seen_paths: Set[str] = set()
    deduped_items = []
    for item in items:
        if item.item_type in ("dns_cache", "command", "recycle_bin"):
            deduped_items.append(item)
            continue
        norm = os.path.normcase(os.path.normpath(item.path))
        if norm not in seen_paths:
            seen_paths.add(norm)
            deduped_items.append(item)

    for item in deduped_items:
        if dry_run:
            success += 1
            freed += item.size
            details.append(CleanItemResult(item=item, success=True))
            continue

        if item.item_type == "dns_cache":
            ret = os.system("ipconfig /flushdns >nul 2>&1")
            if ret == 0:
                success += 1
                freed += item.size
                details.append(CleanItemResult(item=item, success=True))
            else:
                failed += 1
                details.append(CleanItemResult(item=item, success=False, error="command_failed"))
                if on_error:
                    on_error(item, "command_failed")
            continue

        if not _is_path_safe(item.path):
            failed += 1
            details.append(CleanItemResult(item=item, success=False, error="unsafe_path"))
            if on_error:
                on_error(item, "unsafe_path")
            continue

        try:
            if item.item_type == "file":
                ok, err = _safe_remove_file(item.path)
                if ok:
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error=err or "unknown"))
                    if on_error:
                        on_error(item, err or "unknown")
            elif item.item_type == "dir":
                ok, err = _safe_remove_dir(item.path)
                if ok:
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error=err or "unknown"))
                    if on_error:
                        on_error(item, err or "unknown")
            elif item.item_type == "command":
                ret = os.system(item.path)
                if ret == 0:
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error="command_failed"))
                    if on_error:
                        on_error(item, "command_failed")
            elif item.item_type == "recycle_bin":
                if empty_recycle_bin():
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error="recycle_bin_failed"))
                    if on_error:
                        on_error(item, "recycle_bin_failed")
            else:
                failed += 1
                details.append(CleanItemResult(item=item, success=False, error="unknown_type"))
                if on_error:
                    on_error(item, "unknown_type")
        except Exception:
            failed += 1
            details.append(CleanItemResult(item=item, success=False, error="exception"))
            if on_error:
                on_error(item, "exception")

    return success, failed, freed, details


def get_error_summary(details: List[CleanItemResult]) -> dict:
    """从详细结果中汇总错误信息"""
    errors = {
        "locked": 0, "permission": 0, "not_found": 0,
        "unsafe_path": 0, "command_failed": 0, "recycle_bin_failed": 0,
        "unknown": 0, "other": 0,
    }
    for d in details:
        if not d.success:
            err = d.error
            if err in errors:
                errors[err] += 1
            else:
                errors["other"] += 1
    return {k: v for k, v in errors.items() if v > 0}


def empty_recycle_bin() -> bool:
    """清空回收站（使用Windows API）"""
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        return True
    except Exception:
        return False


def get_disk_info() -> List[dict]:
    """获取磁盘使用信息"""
    disks = []
    for drive in _existing_drives():
        try:
            usage = shutil.disk_usage(f"{drive}:\\")
            disks.append({
                "drive": drive,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
            })
        except (OSError, PermissionError):
            pass
    return disks
