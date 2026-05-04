"""
CleanCLI - 核心清理引擎
负责扫描和清理Windows系统垃圾文件：临时文件、回收站、浏览器缓存、系统日志等
"""

import os
import glob
import shutil
import tempfile
import ctypes
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CleanItem:
    """待清理项目"""
    path: str
    size: int  # bytes
    category: str
    item_type: str  # file / dir
    description: str = ""


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


def _safe_remove_file(path: str) -> bool:
    """安全删除文件"""
    try:
        os.remove(path)
        return True
    except (OSError, PermissionError):
        return False


def _safe_remove_dir(path: str) -> bool:
    """安全删除目录"""
    try:
        shutil.rmtree(path, ignore_errors=True)
        return True
    except (OSError, PermissionError):
        return False


def _is_path_safe(path: str) -> bool:
    """检查路径是否安全（防止误删重要文件）"""
    path_lower = path.lower()
    # 永远不删除的关键路径
    dangerous_patterns = [
        "\\windows\\system32",
        "\\windows\\syswow64",
        "\\program files",
        "\\program files (x86)",
        "\\users\\*\\documents",
        "\\users\\*\\desktop",
        "\\users\\*\\pictures",
        "\\users\\*\\videos",
        "\\users\\*\\music",
    ]
    # 允许清理的安全路径前缀
    safe_prefixes = [
        os.environ.get("TEMP", "").lower(),
        os.environ.get("TMP", "").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "temp").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "inetcache").lower(),
        os.environ.get("SYSTEMROOT", "").lower() + "\\temp",
    ]

    for prefix in safe_prefixes:
        if prefix and path_lower.startswith(prefix):
            return True

    for pattern in dangerous_patterns:
        if pattern.replace("*", "") in path_lower:
            return False

    return True


class JunkScanner:
    """系统垃圾文件扫描器"""

    def __init__(self):
        self.user_profile = os.environ.get("USERPROFILE", "")
        self.local_appdata = os.environ.get("LOCALAPPDATA", "")
        self.appdata = os.environ.get("APPDATA", "")
        self.windir = os.environ.get("SYSTEMROOT", os.environ.get("WINDIR", r"C:\Windows"))
        self.temp_dir = tempfile.gettempdir()

    def scan_all(self) -> List[ScanResult]:
        """执行全盘垃圾扫描"""
        results = []
        scanners = [
            ("用户临时文件", self._scan_user_temp),
            ("系统临时文件", self._scan_system_temp),
            ("Windows更新缓存", self._scan_windows_update),
            ("系统日志文件", self._scan_system_logs),
            ("缩略图缓存", self._scan_thumbnails),
            ("Windows错误报告", self._scan_error_reports),
            ("预取文件", self._scan_prefetch),
            ("浏览器缓存 - Chrome", self._scan_chrome_cache),
            ("浏览器缓存 - Edge", self._scan_edge_cache),
            ("浏览器缓存 - Firefox", self._scan_firefox_cache),
            ("回收站", self._scan_recycle_bin),
            ("DNS缓存", self._scan_dns_cache),
        ]
        for name, scanner in scanners:
            try:
                result = scanner()
                result.category = name
                results.append(result)
            except Exception as e:
                r = ScanResult(category=name, error=str(e))
                results.append(r)
        return results

    def _scan_user_temp(self) -> ScanResult:
        """扫描用户临时文件"""
        result = ScanResult(category="")
        temp_dirs = [self.temp_dir]
        if self.local_appdata:
            local_temp = os.path.join(self.local_appdata, "Temp")
            if os.path.isdir(local_temp):
                temp_dirs.append(local_temp)

        for temp_dir in temp_dirs:
            if not os.path.isdir(temp_dir):
                continue
            try:
                for entry in os.scandir(temp_dir):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat().st_size
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=entry.path,
                                    size=size,
                                    category="用户临时文件",
                                    item_type="file",
                                ))
                        elif entry.is_dir(follow_symlinks=False):
                            size = _get_size(entry.path)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=entry.path,
                                    size=size,
                                    category="用户临时文件",
                                    item_type="dir",
                                ))
                    except (OSError, PermissionError):
                        pass
            except (OSError, PermissionError):
                pass
        return result

    def _scan_system_temp(self) -> ScanResult:
        """扫描系统临时文件"""
        result = ScanResult(category="")
        system_temp = os.path.join(self.windir, "Temp")
        if not os.path.isdir(system_temp):
            return result
        try:
            for entry in os.scandir(system_temp):
                try:
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path,
                                size=size,
                                category="系统临时文件",
                                item_type="file",
                            ))
                    elif entry.is_dir(follow_symlinks=False):
                        size = _get_size(entry.path)
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path,
                                size=size,
                                category="系统临时文件",
                                item_type="dir",
                            ))
                except (OSError, PermissionError):
                    pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_windows_update(self) -> ScanResult:
        """扫描Windows更新缓存"""
        result = ScanResult(category="")
        update_path = os.path.join(self.windir, "SoftwareDistribution", "Download")
        if not os.path.isdir(update_path):
            return result
        try:
            for entry in os.scandir(update_path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path,
                                size=size,
                                category="Windows更新缓存",
                                item_type="file",
                            ))
                    elif entry.is_dir(follow_symlinks=False):
                        size = _get_size(entry.path)
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path,
                                size=size,
                                category="Windows更新缓存",
                                item_type="dir",
                            ))
                except (OSError, PermissionError):
                    pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_system_logs(self) -> ScanResult:
        """扫描系统日志文件"""
        result = ScanResult(category="")
        log_dirs = [
            os.path.join(self.windir, "Logs"),
            os.path.join(self.windir, "Panther"),
            os.path.join(self.windir, "debug"),
        ]
        for log_dir in log_dirs:
            if not os.path.isdir(log_dir):
                continue
            try:
                for root, _, files in os.walk(log_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            size = os.path.getsize(fp)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=fp,
                                    size=size,
                                    category="系统日志文件",
                                    item_type="file",
                                    description=f,
                                ))
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
        # CBS.log
        cbs_log = os.path.join(self.windir, "Logs", "CBS", "CBS.log")
        if os.path.isfile(cbs_log):
            try:
                size = os.path.getsize(cbs_log)
                if size > 0:
                    result.add_item(CleanItem(
                        path=cbs_log,
                        size=size,
                        category="系统日志文件",
                        item_type="file",
                        description="CBS.log",
                    ))
            except (OSError, PermissionError):
                pass
        return result

    def _scan_thumbnails(self) -> ScanResult:
        """扫描缩略图缓存"""
        result = ScanResult(category="")
        thumb_dir = os.path.join(
            self.local_appdata, "Microsoft", "Windows", "Explorer"
        )
        if not os.path.isdir(thumb_dir):
            return result
        try:
            for entry in os.scandir(thumb_dir):
                if entry.is_file(follow_symlinks=False) and entry.name.lower().startswith("thumbcache"):
                    try:
                        size = entry.stat().st_size
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path,
                                size=size,
                                category="缩略图缓存",
                                item_type="file",
                                description=entry.name,
                            ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_error_reports(self) -> ScanResult:
        """扫描Windows错误报告"""
        result = ScanResult(category="")
        report_dirs = [
            os.path.join(self.local_appdata, "Microsoft", "Windows", "WER"),
            os.path.join(self.windir, "Minidump"),
            os.path.join(self.windir, "LiveKernelReports"),
        ]
        for report_dir in report_dirs:
            if not os.path.isdir(report_dir):
                continue
            try:
                for root, _, files in os.walk(report_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            size = os.path.getsize(fp)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=fp,
                                    size=size,
                                    category="错误报告",
                                    item_type="file",
                                    description=f,
                                ))
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
        return result

    def _scan_prefetch(self) -> ScanResult:
        """扫描预取文件"""
        result = ScanResult(category="")
        prefetch_dir = os.path.join(self.windir, "Prefetch")
        if not os.path.isdir(prefetch_dir):
            return result
        try:
            for entry in os.scandir(prefetch_dir):
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".pf"):
                    try:
                        size = entry.stat().st_size
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path,
                                size=size,
                                category="预取文件",
                                item_type="file",
                                description=entry.name,
                            ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_chrome_cache(self) -> ScanResult:
        """扫描Chrome浏览器缓存"""
        result = ScanResult(category="")
        cache_paths = [
            os.path.join(self.local_appdata, "Google", "Chrome", "User Data", "Default", "Cache"),
            os.path.join(self.local_appdata, "Google", "Chrome", "User Data", "Default", "Code Cache"),
        ]
        for cache_path in cache_paths:
            if not os.path.isdir(cache_path):
                continue
            try:
                size = _get_size(cache_path)
                if size > 0:
                    result.add_item(CleanItem(
                        path=cache_path,
                        size=size,
                        category="Chrome缓存",
                        item_type="dir",
                        description=os.path.basename(cache_path),
                    ))
            except (OSError, PermissionError):
                pass
        # GPU Cache
        gpu_cache = os.path.join(self.local_appdata, "Google", "Chrome", "User Data", "Default", "GPUCache")
        if os.path.isdir(gpu_cache):
            try:
                size = _get_size(gpu_cache)
                if size > 0:
                    result.add_item(CleanItem(
                        path=gpu_cache,
                        size=size,
                        category="Chrome缓存",
                        item_type="dir",
                        description="GPUCache",
                    ))
            except (OSError, PermissionError):
                pass
        return result

    def _scan_edge_cache(self) -> ScanResult:
        """扫描Edge浏览器缓存"""
        result = ScanResult(category="")
        cache_paths = [
            os.path.join(self.local_appdata, "Microsoft", "Edge", "User Data", "Default", "Cache"),
            os.path.join(self.local_appdata, "Microsoft", "Edge", "User Data", "Default", "Code Cache"),
        ]
        for cache_path in cache_paths:
            if not os.path.isdir(cache_path):
                continue
            try:
                size = _get_size(cache_path)
                if size > 0:
                    result.add_item(CleanItem(
                        path=cache_path,
                        size=size,
                        category="Edge缓存",
                        item_type="dir",
                        description=os.path.basename(cache_path),
                    ))
            except (OSError, PermissionError):
                pass
        return result

    def _scan_firefox_cache(self) -> ScanResult:
        """扫描Firefox浏览器缓存"""
        result = ScanResult(category="")
        profiles_dir = os.path.join(self.local_appdata, "Mozilla", "Firefox", "Profiles")
        if not os.path.isdir(profiles_dir):
            return result
        try:
            for profile in os.scandir(profiles_dir):
                if profile.is_dir(follow_symlinks=False):
                    cache_path = os.path.join(profile.path, "cache2")
                    if os.path.isdir(cache_path):
                        size = _get_size(cache_path)
                        if size > 0:
                            result.add_item(CleanItem(
                                path=cache_path,
                                size=size,
                                category="Firefox缓存",
                                item_type="dir",
                                description=f"{profile.name}/cache2",
                            ))
        except (OSError, PermissionError):
            pass
        return result

    def _scan_recycle_bin(self) -> ScanResult:
        """扫描回收站"""
        result = ScanResult(category="")
        recycle_paths = []
        # 每个驱动器的回收站
        for drive in "CDEFGH":
            recycle_path = f"{drive}:\\$Recycle.Bin"
            if os.path.isdir(recycle_path):
                recycle_paths.append(recycle_path)

        for recycle_path in recycle_paths:
            try:
                for root, _, files in os.walk(recycle_path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            size = os.path.getsize(fp)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=fp,
                                    size=size,
                                    category="回收站",
                                    item_type="file",
                                ))
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
        return result

    def _scan_dns_cache(self) -> ScanResult:
        """DNS缓存（标记为可清理项，实际通过命令清理）"""
        result = ScanResult(category="")
        # DNS缓存不对应文件，标记一个虚拟项
        result.add_item(CleanItem(
            path="[DNS Cache - Memory]",
            size=0,
            category="DNS缓存",
            item_type="dns_cache",
            description="系统DNS解析缓存",
        ))
        return result


def clean_items(items: List[CleanItem]) -> tuple:
    """
    清理指定项目
    返回 (成功数, 失败数, 释放空间)
    """
    success = 0
    failed = 0
    freed = 0

    for item in items:
        if item.item_type == "dns_cache":
            # DNS缓存通过命令清理
            ret = os.system("ipconfig /flushdns >nul 2>&1")
            if ret == 0:
                success += 1
                freed += item.size
            else:
                failed += 1
            continue

        if not _is_path_safe(item.path):
            failed += 1
            continue

        try:
            if item.item_type == "file":
                if _safe_remove_file(item.path):
                    success += 1
                    freed += item.size
                else:
                    failed += 1
            elif item.item_type == "dir":
                if _safe_remove_dir(item.path):
                    success += 1
                    freed += item.size
                else:
                    failed += 1
        except Exception:
            failed += 1

    return success, failed, freed


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
