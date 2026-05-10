"""
CleanCLI - 核心清理引擎 v3.0
深度扫描和清理Windows系统垃圾文件
改进：重试机制、只读属性清除、详细错误追踪、批量处理
"""

import os
import glob
import shutil
import tempfile
import ctypes
import stat
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple


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
    safe_prefixes = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "temp"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "inetcache"),
        os.environ.get("SYSTEMROOT", "") + "\\temp",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "explorer"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "wer"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "logs"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "panther"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "debug"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "prefetch"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "softwaredistribution"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "minidump"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "livekernelreports"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "google"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "edge"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "mozilla"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "crashdumps"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "notifications"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "d3dscache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "fontcache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "recent"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm-cache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "pip", "cache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "yarn", "cache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "sun", "java"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "oracle", "java"),
        os.path.join(os.environ.get("ProgramData", ""), "microsoft", "windows defender", "scans"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "brave software"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "vivaldi"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "opera software"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "programs", "microsoft vs code"),
        os.path.join(os.environ.get("APPDATA", ""), "code", "cache"),
        os.path.join(os.environ.get("APPDATA", ""), "code", "cacheddata"),
        os.path.join(os.environ.get("APPDATA", ""), "code", "cachedextensionvsixs"),
        os.path.join(os.environ.get("APPDATA", ""), "code", "logs"),
        os.path.join(os.environ.get("APPDATA", ""), "code", "user", "workspacestorage"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "docker"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "go"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".cache"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".cargo", "registry"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".cargo", "git"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".conda", "pkgs"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "chocolatey"),
        os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "cache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "onenote"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "outlook"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "teams"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "onedrive"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "packages"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "serviceprofiles", "localservice", "appdata", "local", "microsoft", "windows", "deliveryoptimization"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "serviceprofiles", "networkservice", "appdata", "local", "microsoft", "windows", "deliveryoptimization"),
        os.path.join(os.environ.get("SYSTEMROOT", ""), "performance", "winsat"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "windows", "clipboard"),
        os.path.join(os.environ.get("APPDATA", ""), "microsoft", "teams", "cache"),
        os.path.join(os.environ.get("APPDATA", ""), "microsoft", "teams", "gpucache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "packages", "msteams_8wekyb3d8bbwe", "localcache"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "onedrive", "logs"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "microsoft", "onedrive", "settings"),
        os.path.join(os.environ.get("WINDIR", ""), "installer", "$patchcache$"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "microsoft", "diagnosis", "etllogs"),
    ]
    for prefix in safe_prefixes:
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

    def scan_all(self) -> List[ScanResult]:
        """执行全盘垃圾扫描"""
        results = []
        scanners = [
            ("用户临时文件", self._scan_user_temp),
            ("系统临时文件", self._scan_system_temp),
            ("Windows更新缓存", self._scan_windows_update),
            ("系统日志文件", self._scan_system_logs),
            ("事件日志压缩备份", self._scan_event_log_archives),
            ("缩略图缓存", self._scan_thumbnails),
            ("图标缓存", self._scan_icon_cache),
            ("字体缓存", self._scan_font_cache),
            ("Windows错误报告", self._scan_error_reports),
            ("崩溃转储文件", self._scan_crash_dumps),
            ("预取文件", self._scan_prefetch),
            ("Windows.old旧系统", self._scan_windows_old),
            ("ChkDsk碎片文件", self._scan_chk_files),
            ("浏览器缓存 - Chrome", self._scan_chrome_cache),
            ("浏览器缓存 - Edge", self._scan_edge_cache),
            ("浏览器缓存 - Firefox", self._scan_firefox_cache),
            ("浏览器缓存 - Chromium系", self._scan_chromium_browsers),
            ("Windows Store缓存", self._scan_store_cache),
            ("Windows Installer缓存", self._scan_installer_cache),
            ("Delivery Optimization", self._scan_delivery_optimization),
            ("Windows Spotlight缓存", self._scan_spotlight_cache),
            ("Windows性能日志", self._scan_performance_logs),
            ("Windows遥测诊断数据", self._scan_telemetry),
            (".NET临时文件", self._scan_dotnet_temp),
            ("Java缓存", self._scan_java_cache),
            ("npm缓存", self._scan_npm_cache),
            ("pip缓存", self._scan_pip_cache),
            ("yarn缓存", self._scan_yarn_cache),
            ("Go模块缓存", self._scan_go_cache),
            ("Rust/Cargo缓存", self._scan_cargo_cache),
            ("Conda缓存", self._scan_conda_cache),
            ("Chocolatey缓存", self._scan_choco_cache),
            ("Scoop缓存", self._scan_scoop_cache),
            ("Docker缓存", self._scan_docker_cache),
            ("VS Code缓存", self._scan_vscode_cache),
            ("D3D着色器缓存", self._scan_d3d_cache),
            ("最近文件记录", self._scan_recent_files),
            ("剪贴板历史", self._scan_clipboard_history),
            ("Windows Defender扫描历史", self._scan_defender_history),
            ("OneDrive缓存", self._scan_onedrive_cache),
            ("Teams缓存", self._scan_teams_cache),
            ("Outlook临时文件", self._scan_outlook_temp),
            ("备份文件", self._scan_backup_files),
            ("日志压缩归档", self._scan_log_archives),
            ("临时解压文件", self._scan_temp_extracted),
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

    def _scan_chromium_profile_caches(self, browser_name: str, user_data: str,
                                       cache_names: tuple = ("Cache", "Code Cache", "GPUCache", "Service Worker", "ScriptCache"),
                                       scan_root_caches: bool = False) -> ScanResult:
        """通用 Chromium 系浏览器缓存扫描"""
        result = ScanResult(category="")
        if not os.path.isdir(user_data):
            return result
        try:
            for entry in os.scandir(user_data):
                if entry.is_dir(follow_symlinks=False) and (
                    entry.name == "Default" or entry.name.startswith("Profile")
                ):
                    for cache_name in cache_names:
                        cache_path = os.path.join(entry.path, cache_name)
                        if os.path.isdir(cache_path):
                            size = _get_size(cache_path)
                            if size > 0:
                                result.add_item(CleanItem(
                                    path=cache_path, size=size, category=f"{browser_name}缓存",
                                    item_type="dir", description=f"{entry.name}/{cache_name}",
                                ))
            if scan_root_caches:
                for cache_name in cache_names[:3]:
                    cache_path = os.path.join(user_data, cache_name)
                    if os.path.isdir(cache_path):
                        size = _get_size(cache_path)
                        if size > 0:
                            result.add_item(CleanItem(
                                path=cache_path, size=size, category=f"{browser_name}缓存",
                                item_type="dir", description=cache_name,
                            ))
        except (OSError, PermissionError):
            pass
        return result

    def _scan_chrome_cache(self) -> ScanResult:
        """扫描Chrome浏览器缓存"""
        chrome_base = os.path.join(self.local_appdata, "Google", "Chrome", "User Data")
        return self._scan_chromium_profile_caches("Chrome", chrome_base)

    def _scan_edge_cache(self) -> ScanResult:
        """扫描Edge浏览器缓存"""
        edge_base = os.path.join(self.local_appdata, "Microsoft", "Edge", "User Data")
        return self._scan_chromium_profile_caches("Edge", edge_base,
                                                   cache_names=("Cache", "Code Cache", "GPUCache", "Service Worker"))

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
        total_size = 0
        for drive in "CDEFGHIJ":
            recycle_path = f"{drive}:\\$Recycle.Bin"
            if os.path.isdir(recycle_path):
                total_size += _get_size(recycle_path)
        if total_size > 0:
            result.add_item(CleanItem(
                path="[Recycle Bin - All Drives]",
                size=total_size,
                category="回收站",
                item_type="recycle_bin",
                description="所有驱动器回收站内容",
            ))
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

    # ── v2.1 新增扫描器 ──────────────────────────────────────

    def _scan_event_log_archives(self) -> ScanResult:
        """扫描事件日志压缩备份"""
        result = ScanResult(category="")
        # Windows事件日志归档 (.evtx.old, .etl.old, .etl.zip)
        log_dir = os.path.join(self.windir, "System32", "winevt", "Logs")
        if os.path.isdir(log_dir):
            try:
                for entry in os.scandir(log_dir):
                    if entry.is_file(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        if name_lower.endswith((".old", ".bak")) or (
                            name_lower.endswith(".etl") and entry.stat().st_size > 10 * 1024 * 1024
                        ):
                            try:
                                size = entry.stat().st_size
                                mtime = entry.stat().st_mtime
                                if size > 0 and self._passes_filters(size, mtime):
                                    result.add_item(CleanItem(
                                        path=entry.path, size=size, category="事件日志压缩备份",
                                        item_type="file", description=entry.name, modified_time=mtime,
                                    ))
                            except (OSError, PermissionError):
                                pass
            except (OSError, PermissionError):
                pass
        return result

    def _scan_windows_old(self) -> ScanResult:
        """扫描Windows.old旧系统备份"""
        result = ScanResult(category="")
        for drive in "CDEFGH":
            old_path = f"{drive}:\\Windows.old"
            if os.path.isdir(old_path):
                size = _get_size(old_path)
                if size > 0:
                    result.add_item(CleanItem(
                        path=old_path, size=size, category="Windows.old旧系统",
                        item_type="dir", description=f"{drive}:\\Windows.old",
                    ))
        return result

    def _scan_chk_files(self) -> ScanResult:
        """扫描ChkDsk碎片文件"""
        result = ScanResult(category="")
        for drive in "CDEFGH":
            found_path = f"{drive}:\\FOUND.{{????}}"
            for match_dir in glob.glob(found_path):
                if os.path.isdir(match_dir):
                    try:
                        size = _get_size(match_dir)
                        mtime = _get_mtime(match_dir)
                        if size > 0 and self._passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=match_dir, size=size, category="ChkDsk碎片文件",
                                item_type="dir", description=os.path.basename(match_dir),
                                modified_time=mtime,
                            ))
                    except (OSError, PermissionError):
                        pass
            # 也扫描根目录下的 .chk 文件
            for chk in glob.glob(f"{drive}:\\*.chk"):
                try:
                    size = os.path.getsize(chk)
                    mtime = os.path.getmtime(chk)
                    if size > 0 and self._passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=chk, size=size, category="ChkDsk碎片文件",
                            item_type="file", description=os.path.basename(chk),
                            modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
        return result

    def _scan_chromium_browsers(self) -> ScanResult:
        """扫描其他Chromium系浏览器（Brave, Vivaldi, Opera, Arc等）"""
        result = ScanResult(category="")
        chromium_browsers = [
            ("Brave", os.path.join(self.local_appdata, "Brave Software", "Brave-Browser", "User Data"), False),
            ("Vivaldi", os.path.join(self.local_appdata, "Vivaldi", "User Data"), False),
            ("Opera", os.path.join(self.appdata, "Opera Software", "Opera Stable"), True),
            ("Opera GX", os.path.join(self.appdata, "Opera Software", "Opera GX Stable"), True),
            ("Arc", os.path.join(self.local_appdata, "Arc", "User Data"), False),
        ]
        for browser_name, user_data, scan_root in chromium_browsers:
            r = self._scan_chromium_profile_caches(browser_name, user_data, scan_root_caches=scan_root)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_spotlight_cache(self) -> ScanResult:
        """扫描Windows Spotlight缓存"""
        result = ScanResult(category="")
        spotlight_path = os.path.join(
            self.local_appdata, "Packages",
            "Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy", "LocalState", "Assets"
        )
        r = self._scan_dir(spotlight_path, "Windows Spotlight缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        # 第二个位置
        spotlight_path2 = os.path.join(
            self.local_appdata, "Packages",
            "Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy", "LocalState", "TargetedContentCache"
        )
        r2 = self._scan_dir(spotlight_path2, "Windows Spotlight缓存", include_subdirs=True)
        result.items.extend(r2.items)
        result.total_size += r2.total_size
        return result

    def _scan_performance_logs(self) -> ScanResult:
        """扫描Windows性能日志"""
        result = ScanResult(category="")
        perf_paths = [
            os.path.join(self.windir, "Performance", "WinSAT"),
            os.path.join(self.windir, "System32", "LogFiles", "WMI"),
        ]
        for path in perf_paths:
            r = self._scan_dir(path, "Windows性能日志", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_telemetry(self) -> ScanResult:
        """扫描Windows遥测诊断数据"""
        result = ScanResult(category="")
        telemetry_path = os.path.join(
            self.program_data, "Microsoft", "Diagnosis", "ETLLogs"
        )
        r = self._scan_dir(telemetry_path, "Windows遥测诊断数据", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        # diagerr.xml
        diag_dir = os.path.join(self.program_data, "Microsoft", "Diagnosis")
        if os.path.isdir(diag_dir):
            for name in ("diagerr.xml", "diagwrn.xml"):
                fp = os.path.join(diag_dir, name)
                if os.path.isfile(fp):
                    try:
                        size = os.path.getsize(fp)
                        mtime = os.path.getmtime(fp)
                        if size > 0 and self._passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=fp, size=size, category="Windows遥测诊断数据",
                                item_type="file", description=name, modified_time=mtime,
                            ))
                    except (OSError, PermissionError):
                        pass
        return result

    def _scan_go_cache(self) -> ScanResult:
        """扫描Go模块缓存"""
        result = ScanResult(category="")
        gopath = os.environ.get("GOPATH", os.path.join(self.user_profile, "go"))
        go_cache = os.path.join(gopath, "pkg", "mod", "cache")
        if os.path.isdir(go_cache):
            size = _get_size(go_cache)
            if size > 0:
                result.add_item(CleanItem(
                    path=go_cache, size=size, category="Go模块缓存",
                    item_type="dir", description="go/pkg/mod/cache",
                ))
        go_build_cache = os.path.join(os.environ.get("LOCALAPPDATA", ""), "go-build")
        if os.path.isdir(go_build_cache):
            size = _get_size(go_build_cache)
            if size > 0:
                result.add_item(CleanItem(
                    path=go_build_cache, size=size, category="Go模块缓存",
                    item_type="dir", description="go-build cache",
                ))
        return result

    def _scan_cargo_cache(self) -> ScanResult:
        """扫描Rust/Cargo缓存"""
        result = ScanResult(category="")
        cargo_home = os.environ.get("CARGO_HOME", os.path.join(self.user_profile, ".cargo"))
        for subdir in ("registry", "git"):
            cache_path = os.path.join(cargo_home, subdir)
            if os.path.isdir(cache_path):
                size = _get_size(cache_path)
                if size > 0:
                    result.add_item(CleanItem(
                        path=cache_path, size=size, category="Rust/Cargo缓存",
                        item_type="dir", description=f".cargo/{subdir}",
                    ))
        return result

    def _scan_conda_cache(self) -> ScanResult:
        """扫描Conda缓存"""
        result = ScanResult(category="")
        conda_cache_paths = [
            os.path.join(self.user_profile, ".conda", "pkgs"),
            os.path.join(self.user_profile, "miniconda3", "pkgs"),
            os.path.join(self.user_profile, "anaconda3", "pkgs"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "conda", "conda", "pkgs"),
        ]
        for path in conda_cache_paths:
            if os.path.isdir(path):
                size = _get_size(path)
                if size > 0:
                    result.add_item(CleanItem(
                        path=path, size=size, category="Conda缓存",
                        item_type="dir", description=os.path.basename(os.path.dirname(path)) + "/pkgs",
                    ))
        return result

    def _scan_choco_cache(self) -> ScanResult:
        """扫描Chocolatey缓存"""
        result = ScanResult(category="")
        choco_cache = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Chocolatey", "Cache")
        if os.path.isdir(choco_cache):
            r = self._scan_dir(choco_cache, "Chocolatey缓存", include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_scoop_cache(self) -> ScanResult:
        """扫描Scoop缓存"""
        result = ScanResult(category="")
        scoop_cache = os.path.join(self.user_profile, "scoop", "cache")
        if os.path.isdir(scoop_cache):
            r = self._scan_dir(scoop_cache, "Scoop缓存")
            result.items.extend(r.items)
            result.total_size += r.total_size
        return result

    def _scan_docker_cache(self) -> ScanResult:
        """扫描Docker Desktop缓存"""
        result = ScanResult(category="")
        docker_paths = [
            os.path.join(self.local_appdata, "Docker", "log"),
            os.path.join(self.appdata, "Docker", "log"),
        ]
        for path in docker_paths:
            if os.path.isdir(path):
                r = self._scan_dir(path, "Docker缓存", {".log"}, include_subdirs=True)
                result.items.extend(r.items)
                result.total_size += r.total_size
        return result

    def _scan_vscode_cache(self) -> ScanResult:
        """扫描VS Code缓存"""
        result = ScanResult(category="")
        vscode_dirs = [
            (os.path.join(self.appdata, "Code", "Cache"), "VS Code缓存"),
            (os.path.join(self.appdata, "Code", "CachedData"), "VS Code缓存"),
            (os.path.join(self.appdata, "Code", "CachedExtensionVSIXs"), "VS Code缓存"),
            (os.path.join(self.appdata, "Code", "Logs"), "VS Code日志"),
            (os.path.join(self.appdata, "Code", "User", "workspaceStorage"), "VS Code工作区存储"),
            (os.path.join(self.local_appdata, "Programs", "Microsoft VS Code", "Cache"), "VS Code缓存"),
        ]
        for path, cat in vscode_dirs:
            if os.path.isdir(path):
                r = self._scan_dir(path, cat, include_subdirs=True)
                result.items.extend(r.items)
                result.total_size += r.total_size
        return result

    def _scan_clipboard_history(self) -> ScanResult:
        """扫描剪贴板历史"""
        result = ScanResult(category="")
        clipboard_path = os.path.join(
            self.local_appdata, "Microsoft", "Windows", "Clipboard"
        )
        r = self._scan_dir(clipboard_path, "剪贴板历史", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        return result

    def _scan_onedrive_cache(self) -> ScanResult:
        """扫描OneDrive缓存"""
        result = ScanResult(category="")
        onedrive_cache = os.path.join(self.local_appdata, "Microsoft", "OneDrive", "logs")
        r = self._scan_dir(onedrive_cache, "OneDrive缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        # OneDrive设置缓存
        onedrive_settings = os.path.join(self.local_appdata, "Microsoft", "OneDrive", "settings")
        r2 = self._scan_dir(onedrive_settings, "OneDrive缓存")
        result.items.extend(r2.items)
        result.total_size += r2.total_size
        return result

    def _scan_teams_cache(self) -> ScanResult:
        """扫描Microsoft Teams缓存"""
        result = ScanResult(category="")
        # 新版 Teams
        teams_new = os.path.join(self.local_appdata, "Packages", "MSTeams_8wekyb3d8bbwe", "LocalCache")
        r = self._scan_dir(teams_new, "Teams缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
        # 经典版 Teams
        teams_classic = os.path.join(self.appdata, "Microsoft", "Teams", "Cache")
        r2 = self._scan_dir(teams_classic, "Teams缓存", include_subdirs=True)
        result.items.extend(r2.items)
        result.total_size += r2.total_size
        teams_gpucache = os.path.join(self.appdata, "Microsoft", "Teams", "GPUCache")
        r3 = self._scan_dir(teams_gpucache, "Teams缓存")
        result.items.extend(r3.items)
        result.total_size += r3.total_size
        return result

    def _scan_outlook_temp(self) -> ScanResult:
        """扫描Outlook临时文件"""
        result = ScanResult(category="")
        outlook_temp = os.path.join(self.local_appdata, "Microsoft", "Outlook")
        if not os.path.isdir(outlook_temp):
            return result
        try:
            for entry in os.scandir(outlook_temp):
                if entry.is_dir(follow_symlinks=False) and "RoamCache" in entry.name:
                    size = _get_size(entry.path)
                    if size > 0:
                        result.add_item(CleanItem(
                            path=entry.path, size=size, category="Outlook临时文件",
                            item_type="dir", description=entry.name,
                        ))
                elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith((".ost.tmp", ".pst.tmp")):
                    try:
                        size = entry.stat().st_size
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category="Outlook临时文件",
                                item_type="file", description=entry.name,
                            ))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return result

    def _scan_backup_files(self) -> ScanResult:
        """扫描常见备份文件（.bak, .old, .orig, .tmp~）"""
        result = ScanResult(category="")
        scan_roots = [
            os.path.join(self.user_profile, "Documents"),
            os.path.join(self.user_profile, "Desktop"),
            os.path.join(self.user_profile, "Downloads"),
        ]
        backup_exts = {".bak", ".old", ".orig"}
        for root_dir in scan_roots:
            if not os.path.isdir(root_dir):
                continue
            try:
                for root, _, files in os.walk(root_dir):
                    # 只扫描前两层目录，避免太深
                    depth = root.replace(root_dir, "").count(os.sep)
                    if depth > 2:
                        continue
                    for f in files:
                        f_lower = f.lower()
                        if f_lower.endswith(tuple(backup_exts)) or f_lower.endswith(".tmp~"):
                            fp = os.path.join(root, f)
                            try:
                                size = os.path.getsize(fp)
                                mtime = os.path.getmtime(fp)
                                if size > 1024 and self._passes_filters(size, mtime):
                                    result.add_item(CleanItem(
                                        path=fp, size=size, category="备份文件",
                                        item_type="file", description=f, modified_time=mtime,
                                    ))
                            except (OSError, PermissionError):
                                pass
            except (OSError, PermissionError):
                pass
        return result

    def _scan_log_archives(self) -> ScanResult:
        """扫描日志压缩归档（.log.gz, .cab, .etl.zip）"""
        result = ScanResult(category="")
        log_dirs = [
            os.path.join(self.windir, "Logs"),
            os.path.join(self.windir, "Temp"),
        ]
        archive_exts = {".cab", ".gz", ".zip", ".log_old", ".etl_old"}
        for log_dir in log_dirs:
            if not os.path.isdir(log_dir):
                continue
            try:
                for root, _, files in os.walk(log_dir):
                    for f in files:
                        if f.lower().endswith(tuple(archive_exts)):
                            fp = os.path.join(root, f)
                            try:
                                size = os.path.getsize(fp)
                                mtime = os.path.getmtime(fp)
                                if size > 0 and self._passes_filters(size, mtime):
                                    result.add_item(CleanItem(
                                        path=fp, size=size, category="日志压缩归档",
                                        item_type="file", description=f, modified_time=mtime,
                                    ))
                            except (OSError, PermissionError):
                                pass
            except (OSError, PermissionError):
                pass
        return result

    def _scan_temp_extracted(self) -> ScanResult:
        """扫描临时解压文件（~*.tmp, ~WPL*.tmp, ~$*开头的Office临时文件）"""
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
                    if entry.is_file(follow_symlinks=False):
                        name = entry.name
                        # ~开头的临时解压文件、~WPL临时文件、~$Office临时文件
                        if name.startswith("~") or name.startswith("~$"):
                            try:
                                size = entry.stat().st_size
                                mtime = entry.stat().st_mtime
                                if size > 0 and self._passes_filters(size, mtime):
                                    result.add_item(CleanItem(
                                        path=entry.path, size=size, category="临时解压文件",
                                        item_type="file", description=name, modified_time=mtime,
                                    ))
                            except (OSError, PermissionError):
                                pass
            except (OSError, PermissionError):
                pass
        return result


def clean_items(items: List[CleanItem], dry_run: bool = False) -> Tuple[int, int, int, List[CleanItemResult]]:
    """
    清理指定项目
    返回 (成功数, 失败数, 释放空间, 详细结果列表)
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
            continue

        if not _is_path_safe(item.path):
            failed += 1
            details.append(CleanItemResult(item=item, success=False, error="unsafe_path"))
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
            elif item.item_type == "dir":
                ok, err = _safe_remove_dir(item.path)
                if ok:
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error=err or "unknown"))
            elif item.item_type == "command":
                ret = os.system(item.path)
                if ret == 0:
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error="command_failed"))
            elif item.item_type == "recycle_bin":
                if empty_recycle_bin():
                    success += 1
                    freed += item.size
                    details.append(CleanItemResult(item=item, success=True))
                else:
                    failed += 1
                    details.append(CleanItemResult(item=item, success=False, error="recycle_bin_failed"))
            else:
                failed += 1
                details.append(CleanItemResult(item=item, success=False, error="unknown_type"))
        except Exception:
            failed += 1
            details.append(CleanItemResult(item=item, success=False, error="exception"))

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
