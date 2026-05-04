"""
CleanCLI - 核心清理引擎 v2.0
深度扫描和清理Windows系统垃圾文件：临时文件、回收站、浏览器缓存、
系统日志、崩溃转储、.NET/Java/npm/pip缓存、Windows Store、Installer缓存等
支持年龄过滤和大小阈值
"""

import os
import glob
import shutil
import tempfile
import ctypes
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class CleanItem:
    """待清理项目"""
    path: str
    size: int  # bytes
    category: str
    item_type: str  # file / dir / dns_cache / command
    description: str = ""
    modified_time: float = 0.0  # 最后修改时间戳


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
    """获取文件最后修改时间"""
    try:
        return os.path.getmtime(path)
    except (OSError, PermissionError):
        return 0.0


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
    safe_prefixes = [
        os.environ.get("TEMP", "").lower(),
        os.environ.get("TMP", "").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "temp").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "inetcache").lower(),
        os.environ.get("SYSTEMROOT", "").lower() + "\\temp",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "explorer").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "wer").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "logs").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "panther").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "debug").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "prefetch").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "softwaredistribution").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "minidump").lower(),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "livekernelreports").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "google").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "edge").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "mozilla").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "crashdumps").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "notifications").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "d3dscache").lower(),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "explorer").lower(),
    ]
    for prefix in safe_prefixes:
        if prefix and path_lower.startswith(prefix):
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
            ("崩溃转储文件", self._scan_crash_dumps),
            ("预取文件", self._scan_prefetch),
            ("字体缓存", self._scan_font_cache),
            ("图标缓存", self._scan_icon_cache),
            ("浏览器缓存 - Chrome", self._scan_chrome_cache),
            ("浏览器缓存 - Edge", self._scan_edge_cache),
            ("浏览器缓存 - Firefox", self._scan_firefox_cache),
            ("Windows Store缓存", self._scan_store_cache),
            ("Windows Installer缓存", self._scan_installer_cache),
            ("Delivery Optimization", self._scan_delivery_optimization),
            (".NET临时文件", self._scan_dotnet_temp),
            ("Java缓存", self._scan_java_cache),
            ("npm缓存", self._scan_npm_cache),
            ("pip缓存", self._scan_pip_cache),
            ("yarn缓存", self._scan_yarn_cache),
            ("D3D着色器缓存", self._scan_d3d_cache),
            ("最近文件记录", self._scan_recent_files),
            ("Windows Defender扫描历史", self._scan_defender_history),
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

    def _scan_dir(self, path: str, category: str, ext_filter: set = None,
                  include_subdirs: bool = False) -> ScanResult:
        """通用目录扫描辅助方法"""
        result = ScanResult(category="")
        if not os.path.isdir(path):
            return result
        try:
            if include_subdirs:
                for root, _, files in os.walk(path):
                    for f in files:
                        if ext_filter and not f.lower().endswith(tuple(ext_filter)):
                            continue
                        fp = os.path.join(root, f)
                        try:
                            size = os.path.getsize(fp)
                            mtime = os.path.getmtime(fp)
                            if size > 0 and self._passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=fp, size=size, category=category,
                                    item_type="file", description=f, modified_time=mtime,
                                ))
                        except (OSError, PermissionError):
                            pass
            else:
                for entry in os.scandir(path):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            if ext_filter and not entry.name.lower().endswith(tuple(ext_filter)):
                                continue
                            size = entry.stat().st_size
                            mtime = entry.stat().st_mtime
                            if size > 0 and self._passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=entry.path, size=size, category=category,
                                    item_type="file", description=entry.name, modified_time=mtime,
                                ))
                        elif entry.is_dir(follow_symlinks=False):
                            size = _get_size(entry.path)
                            mtime = _get_mtime(entry.path)
                            if size > 0 and self._passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=entry.path, size=size, category=category,
                                    item_type="dir", modified_time=mtime,
                                ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_user_temp(self) -> ScanResult:
        """扫描用户临时文件"""
        result = ScanResult(category="")
        temp_dirs = [self.temp_dir]
        if self.local_appdata:
            local_temp = os.path.join(self.local_appdata, "Temp")
            if os.path.isdir(local_temp):
                temp_dirs.append(local_temp)
        for temp_dir in temp_dirs:
            r = self._scan_dir(temp_dir, "用户临时文件")
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_system_temp(self) -> ScanResult:
        """扫描系统临时文件"""
        return self._scan_dir(os.path.join(self.windir, "Temp"), "系统临时文件")

    def _scan_windows_update(self) -> ScanResult:
        """扫描Windows更新缓存"""
        return self._scan_dir(
            os.path.join(self.windir, "SoftwareDistribution", "Download"),
            "Windows更新缓存"
        )

    def _scan_system_logs(self) -> ScanResult:
        """扫描系统日志文件"""
        result = ScanResult(category="")
        log_dirs = [
            os.path.join(self.windir, "Logs"),
            os.path.join(self.windir, "Panther"),
            os.path.join(self.windir, "debug"),
        ]
        for log_dir in log_dirs:
            r = self._scan_dir(log_dir, "系统日志文件", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_thumbnails(self) -> ScanResult:
        """扫描缩略图缓存"""
        result = ScanResult(category="")
        thumb_dir = os.path.join(self.local_appdata, "Microsoft", "Windows", "Explorer")
        if not os.path.isdir(thumb_dir):
            return result
        try:
            for entry in os.scandir(thumb_dir):
                if entry.is_file(follow_symlinks=False) and entry.name.lower().startswith("thumbcache"):
                    try:
                        size = entry.stat().st_size
                        mtime = entry.stat().st_mtime
                        if size > 0 and self._passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category="缩略图缓存",
                                item_type="file", description=entry.name, modified_time=mtime,
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
            r = self._scan_dir(report_dir, "错误报告", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_crash_dumps(self) -> ScanResult:
        """扫描崩溃转储文件"""
        result = ScanResult(category="")
        dump_paths = [
            os.path.join(self.windir, "MEMORY.DMP"),
            os.path.join(self.windir, "Minidump"),
            os.path.join(self.local_appdata, "CrashDumps"),
        ]
        for path in dump_paths:
            if os.path.isfile(path):
                try:
                    size = os.path.getsize(path)
                    mtime = os.path.getmtime(path)
                    if size > 0 and self._passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=path, size=size, category="崩溃转储文件",
                            item_type="file", description=os.path.basename(path), modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
            elif os.path.isdir(path):
                r = self._scan_dir(path, "崩溃转储文件", {".dmp", ".mdmp", ".hdmp"}, include_subdirs=True)
                result.items.extend(r.items)
                result.total_size += r.total_size
        # 用户目录下的 .dmp 文件
        for dmp in glob.glob(os.path.join(self.user_profile, "*.dmp")):
            try:
                size = os.path.getsize(dmp)
                mtime = os.path.getmtime(dmp)
                if size > 0 and self._passes_filters(size, mtime):
                    result.add_item(CleanItem(
                        path=dmp, size=size, category="崩溃转储文件",
                        item_type="file", description=os.path.basename(dmp), modified_time=mtime,
                    ))
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
                        mtime = entry.stat().st_mtime
                        if size > 0 and self._passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category="预取文件",
                                item_type="file", description=entry.name, modified_time=mtime,
                            ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_font_cache(self) -> ScanResult:
        """扫描字体缓存"""
        result = ScanResult(category="")
        cache_path = os.path.join(
            self.local_appdata, "Microsoft", "Windows", "FontCache"
        )
        r = self._scan_dir(cache_path, "字体缓存")
        result.items.extend(r.items)
        result.total_size += r.total_size
        return result

    def _scan_icon_cache(self) -> ScanResult:
        """扫描图标缓存"""
        result = ScanResult(category="")
        icon_dir = os.path.join(self.local_appdata, "Microsoft", "Windows", "Explorer")
        if not os.path.isdir(icon_dir):
            return result
        try:
            for entry in os.scandir(icon_dir):
                if entry.is_file(follow_symlinks=False) and entry.name.lower().startswith("iconcache"):
                    try:
                        size = entry.stat().st_size
                        mtime = entry.stat().st_mtime
                        if size > 0 and self._passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category="图标缓存",
                                item_type="file", description=entry.name, modified_time=mtime,
                            ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_chrome_cache(self) -> ScanResult:
        """扫描Chrome浏览器缓存"""
        result = ScanResult(category="")
        chrome_base = os.path.join(self.local_appdata, "Google", "Chrome", "User Data")
        if not os.path.isdir(chrome_base):
            return result
        # 扫描所有 Profile
        try:
            for entry in os.scandir(chrome_base):
                if entry.is_dir(follow_symlinks=False) and (
                    entry.name == "Default" or entry.name.startswith("Profile")
                ):
                    for cache_name in ("Cache", "Code Cache", "GPUCache", "Service Worker", "ScriptCache"):
                        cache_path = os.path.join(entry.path, cache_name)
                        if os.path.isdir(cache_path):
                            size = _get_size(cache_path)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=cache_path, size=size, category="Chrome缓存",
                                    item_type="dir", description=f"{entry.name}/{cache_name}",
                                ))
        except (OSError, PermissionError):
            pass
        return result

    def _scan_edge_cache(self) -> ScanResult:
        """扫描Edge浏览器缓存"""
        result = ScanResult(category="")
        edge_base = os.path.join(self.local_appdata, "Microsoft", "Edge", "User Data")
        if not os.path.isdir(edge_base):
            return result
        try:
            for entry in os.scandir(edge_base):
                if entry.is_dir(follow_symlinks=False) and (
                    entry.name == "Default" or entry.name.startswith("Profile")
                ):
                    for cache_name in ("Cache", "Code Cache", "GPUCache", "Service Worker"):
                        cache_path = os.path.join(entry.path, cache_name)
                        if os.path.isdir(cache_path):
                            size = _get_size(cache_path)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=cache_path, size=size, category="Edge缓存",
                                    item_type="dir", description=f"{entry.name}/{cache_name}",
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
                    for cache_name in ("cache2", "startupCache", "shader-cache"):
                        cache_path = os.path.join(profile.path, cache_name)
                        if os.path.isdir(cache_path):
                            size = _get_size(cache_path)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=cache_path, size=size, category="Firefox缓存",
                                    item_type="dir", description=f"{profile.name}/{cache_name}",
                                ))
        except (OSError, PermissionError):
            pass
        return result

    def _scan_store_cache(self) -> ScanResult:
        """扫描Windows Store缓存"""
        result = ScanResult(category="")
        store_cache = os.path.join(
            self.local_appdata, "Packages", "Microsoft.WindowsStore_8wekyb3d8bbwe", "LocalCache"
        )
        r = self._scan_dir(store_cache, "Windows Store缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        return result

    def _scan_installer_cache(self) -> ScanResult:
        """扫描Windows Installer孤立补丁缓存"""
        result = ScanResult(category="")
        installer_dir = os.path.join(self.windir, "Installer")
        if not os.path.isdir(installer_dir):
            return result
        # 只扫描 $PatchCache$ 和孤立 .msp 文件
        patch_cache = os.path.join(installer_dir, "$PatchCache$")
        if os.path.isdir(patch_cache):
            r = self._scan_dir(patch_cache, "Installer缓存", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        # Chk 文件碎片
        for entry in os.scandir(installer_dir):
            if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".msp"):
                # .msp 补丁文件，如果对应产品已卸载则是孤立的
                try:
                    size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    if size > 5 * 1024 * 1024 and self._passes_filters(size, mtime):  # > 5MB
                        result.add_item(CleanItem(
                            path=entry.path, size=size, category="Installer缓存",
                            item_type="file", description=entry.name, modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
        return result

    def _scan_delivery_optimization(self) -> ScanResult:
        """扫描Delivery Optimization缓存"""
        result = ScanResult(category="")
        do_path = os.path.join(
            self.local_appdata, "Packages",
            "Microsoft.WindowsDeliveryOptimization_8wekyb3d8bbwe", "LocalState"
        )
        if os.path.isdir(do_path):
            r = self._scan_dir(do_path, "Delivery Optimization", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_dotnet_temp(self) -> ScanResult:
        """扫描.NET临时文件"""
        result = ScanResult(category="")
        dotnet_paths = [
            os.path.join(self.windir, "Microsoft.NET", "Framework", "v4.0.30319", "Temporary ASP.NET Files"),
            os.path.join(self.windir, "Microsoft.NET", "Framework64", "v4.0.30319", "Temporary ASP.NET Files"),
        ]
        for path in dotnet_paths:
            r = self._scan_dir(path, ".NET临时文件", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_java_cache(self) -> ScanResult:
        """扫描Java缓存"""
        result = ScanResult(category="")
        java_paths = [
            os.path.join(self.local_appdata, "Sun", "Java", "Deployment", "cache"),
            os.path.join(self.local_appdata, "Oracle", "Java", "cache"),
        ]
        for path in java_paths:
            r = self._scan_dir(path, "Java缓存", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_npm_cache(self) -> ScanResult:
        """扫描npm缓存"""
        result = ScanResult(category="")
        npm_cache = os.path.join(self.local_appdata, "npm-cache")
        if os.path.isdir(npm_cache):
            size = _get_size(npm_cache)
            if size > 0:
                result.add_item(CleanItem(
                    path=npm_cache, size=size, category="npm缓存",
                    item_type="dir", description="npm cache",
                ))
        # 用户目录下的 npm cache
        user_npm = os.path.join(self.user_profile, ".npm")
        if os.path.isdir(user_npm):
            size = _get_size(user_npm)
            if size > 0:
                result.add_item(CleanItem(
                    path=user_npm, size=size, category="npm缓存",
                    item_type="dir", description=".npm cache",
                ))
        return result

    def _scan_pip_cache(self) -> ScanResult:
        """扫描pip缓存"""
        result = ScanResult(category="")
        pip_cache = os.path.join(self.local_appdata, "pip", "cache")
        if os.path.isdir(pip_cache):
            size = _get_size(pip_cache)
            if size > 0:
                result.add_item(CleanItem(
                    path=pip_cache, size=size, category="pip缓存",
                    item_type="dir", description="pip cache",
                ))
        user_pip = os.path.join(self.user_profile, "AppData", "Local", "pip", "cache")
        if os.path.isdir(user_pip) and user_pip != pip_cache:
            size = _get_size(user_pip)
            if size > 0:
                result.add_item(CleanItem(
                    path=user_pip, size=size, category="pip缓存",
                    item_type="dir", description="pip cache (user)",
                ))
        return result

    def _scan_yarn_cache(self) -> ScanResult:
        """扫描yarn缓存"""
        result = ScanResult(category="")
        yarn_cache = os.path.join(self.local_appdata, "Yarn", "Cache")
        if os.path.isdir(yarn_cache):
            size = _get_size(yarn_cache)
            if size > 0:
                result.add_item(CleanItem(
                    path=yarn_cache, size=size, category="yarn缓存",
                    item_type="dir", description="yarn cache",
                ))
        return result

    def _scan_d3d_cache(self) -> ScanResult:
        """扫描D3D着色器缓存"""
        result = ScanResult(category="")
        d3d_cache = os.path.join(self.local_appdata, "D3DSCache")
        r = self._scan_dir(d3d_cache, "D3D着色器缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        return result

    def _scan_recent_files(self) -> ScanResult:
        """扫描最近文件访问记录"""
        result = ScanResult(category="")
        recent_dir = os.path.join(self.appdata, "Microsoft", "Windows", "Recent")
        if not os.path.isdir(recent_dir):
            return result
        try:
            for entry in os.scandir(recent_dir):
                if entry.is_file(follow_symlinks=False):
                    try:
                        size = entry.stat().st_size
                        mtime = entry.stat().st_mtime
                        if size > 0 and self._passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category="最近文件记录",
                                item_type="file", description=entry.name, modified_time=mtime,
                            ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_defender_history(self) -> ScanResult:
        """扫描Windows Defender扫描历史"""
        result = ScanResult(category="")
        defender_path = os.path.join(
            self.program_data, "Microsoft", "Windows Defender", "Scans", "History"
        )
        r = self._scan_dir(defender_path, "Defender扫描历史", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        return result

    def _scan_recycle_bin(self) -> ScanResult:
        """扫描回收站"""
        result = ScanResult(category="")
        for drive in "CDEFGHIJ":
            recycle_path = f"{drive}:\\$Recycle.Bin"
            if os.path.isdir(recycle_path):
                r = self._scan_dir(recycle_path, "回收站", include_subdirs=True)
                result.items.extend(r.items)
                result.total_size += r.total_size
        return result

    def _scan_dns_cache(self) -> ScanResult:
        """DNS缓存（标记为可清理项，实际通过命令清理）"""
        result = ScanResult(category="")
        result.add_item(CleanItem(
            path="[DNS Cache - Memory]",
            size=0,
            category="DNS缓存",
            item_type="dns_cache",
            description="系统DNS解析缓存",
        ))
        return result


def clean_items(items: List[CleanItem], dry_run: bool = False) -> tuple:
    """
    清理指定项目
    返回 (成功数, 失败数, 释放空间)
    """
    success = 0
    failed = 0
    freed = 0

    for item in items:
        if dry_run:
            success += 1
            freed += item.size
            continue

        if item.item_type == "dns_cache":
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


def get_disk_info() -> List[dict]:
    """获取磁盘使用信息"""
    disks = []
    for drive in "CDEFGHIJ":
        path = f"{drive}:\\"
        try:
            usage = shutil.disk_usage(path)
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
