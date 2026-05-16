"""
CleanCLI - 应用程序缓存扫描器
扫描 OneDrive、Teams、Outlook、备份文件等应用缓存
"""

import os
from cleancli.cleaner import CleanItem, ScanResult, _get_size
from cleancli.scanners import scanner, ScanContext


@scanner("OneDrive缓存")
def scan_onedrive_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    onedrive_cache = os.path.join(ctx.local_appdata, "Microsoft", "OneDrive", "logs")
    r = _scan_dir_app(ctx, onedrive_cache, "OneDrive缓存", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    onedrive_settings = os.path.join(ctx.local_appdata, "Microsoft", "OneDrive", "settings")
    r2 = _scan_dir_app(ctx, onedrive_settings, "OneDrive缓存")
    result.items.extend(r2.items)
    result.total_size += r2.total_size
    return result


@scanner("Teams缓存")
def scan_teams_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    teams_new = os.path.join(ctx.local_appdata, "Packages", "MSTeams_8wekyb3d8bbwe", "LocalCache")
    r = _scan_dir_app(ctx, teams_new, "Teams缓存", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    teams_classic = os.path.join(ctx.appdata, "Microsoft", "Teams", "Cache")
    r2 = _scan_dir_app(ctx, teams_classic, "Teams缓存", include_subdirs=True)
    result.items.extend(r2.items)
    result.total_size += r2.total_size
    teams_gpucache = os.path.join(ctx.appdata, "Microsoft", "Teams", "GPUCache")
    r3 = _scan_dir_app(ctx, teams_gpucache, "Teams缓存")
    result.items.extend(r3.items)
    result.total_size += r3.total_size
    return result


@scanner("Outlook临时文件")
def scan_outlook_temp(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    outlook_temp = os.path.join(ctx.local_appdata, "Microsoft", "Outlook")
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


@scanner("备份文件")
def scan_backup_files(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    scan_roots = [
        os.path.join(ctx.user_profile, "Documents"),
        os.path.join(ctx.user_profile, "Desktop"),
        os.path.join(ctx.user_profile, "Downloads"),
    ]
    backup_exts = {".bak", ".old", ".orig"}
    for root_dir in scan_roots:
        if not os.path.isdir(root_dir):
            continue
        try:
            for root, _, files in os.walk(root_dir):
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
                            if size > 1024 and ctx.passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=fp, size=size, category="备份文件",
                                    item_type="file", description=f, modified_time=mtime,
                                ))
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
    return result


@scanner("日志压缩归档")
def scan_log_archives(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    log_dirs = [
        os.path.join(ctx.windir, "Logs"),
        os.path.join(ctx.windir, "Temp"),
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
                            if size > 0 and ctx.passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=fp, size=size, category="日志压缩归档",
                                    item_type="file", description=f, modified_time=mtime,
                                ))
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
    return result


@scanner("临时解压文件")
def scan_temp_extracted(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    temp_dirs = [ctx.temp_dir]
    if ctx.local_appdata:
        local_temp = os.path.join(ctx.local_appdata, "Temp")
        if os.path.isdir(local_temp):
            temp_dirs.append(local_temp)
    for temp_dir in temp_dirs:
        if not os.path.isdir(temp_dir):
            continue
        try:
            for entry in os.scandir(temp_dir):
                if entry.is_file(follow_symlinks=False):
                    name = entry.name
                    if name.startswith("~") or name.startswith("~$"):
                        try:
                            size = entry.stat().st_size
                            mtime = entry.stat().st_mtime
                            if size > 0 and ctx.passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=entry.path, size=size, category="临时解压文件",
                                    item_type="file", description=name, modified_time=mtime,
                                ))
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
    return result


def _scan_dir_app(ctx: ScanContext, path: str, category: str, ext_filter: set = None,
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
                        if size > 0 and ctx.passes_filters(size, mtime):
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
                        if size > 0 and ctx.passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category=category,
                                item_type="file", description=entry.name, modified_time=mtime,
                            ))
                    elif entry.is_dir(follow_symlinks=False):
                        size = _get_size(entry.path)
                        if size > 0:
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category=category,
                                item_type="dir",
                            ))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return result
