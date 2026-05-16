"""
CleanCLI - 系统垃圾扫描器
扫描 Windows 系统临时文件、日志、缓存、更新文件等
"""

import os
import glob
from cleancli.cleaner import CleanItem, ScanResult, _get_size, _get_mtime, _existing_drives
from cleancli.scanners import scanner, ScanContext


@scanner("用户临时文件")
def scan_user_temp(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    temp_dirs = [ctx.temp_dir]
    if ctx.local_appdata:
        local_temp = os.path.join(ctx.local_appdata, "Temp")
        if os.path.isdir(local_temp):
            temp_dirs.append(local_temp)
    for temp_dir in temp_dirs:
        r = _scan_dir(ctx, temp_dir, "用户临时文件")
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("系统临时文件")
def scan_system_temp(ctx: ScanContext) -> ScanResult:
    return _scan_dir(ctx, os.path.join(ctx.windir, "Temp"), "系统临时文件")


@scanner("Windows更新缓存")
def scan_windows_update(ctx: ScanContext) -> ScanResult:
    return _scan_dir(ctx, os.path.join(ctx.windir, "SoftwareDistribution", "Download"), "Windows更新缓存")


@scanner("系统日志文件")
def scan_system_logs(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    log_dirs = [
        os.path.join(ctx.windir, "Logs"),
        os.path.join(ctx.windir, "Panther"),
        os.path.join(ctx.windir, "debug"),
    ]
    for log_dir in log_dirs:
        r = _scan_dir(ctx, log_dir, "系统日志文件", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("事件日志压缩备份")
def scan_event_log_archives(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    log_dir = os.path.join(ctx.windir, "System32", "winevt", "Logs")
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
                            if size > 0 and ctx.passes_filters(size, mtime):
                                result.add_item(CleanItem(
                                    path=entry.path, size=size, category="事件日志压缩备份",
                                    item_type="file", description=entry.name, modified_time=mtime,
                                ))
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
    return result


@scanner("缩略图缓存")
def scan_thumbnails(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    thumb_dir = os.path.join(ctx.local_appdata, "Microsoft", "Windows", "Explorer")
    if not os.path.isdir(thumb_dir):
        return result
    try:
        for entry in os.scandir(thumb_dir):
            if entry.is_file(follow_symlinks=False) and entry.name.lower().startswith("thumbcache"):
                try:
                    size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    if size > 0 and ctx.passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=entry.path, size=size, category="缩略图缓存",
                            item_type="file", description=entry.name, modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return result


@scanner("图标缓存")
def scan_icon_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    icon_dir = os.path.join(ctx.local_appdata, "Microsoft", "Windows", "Explorer")
    if not os.path.isdir(icon_dir):
        return result
    try:
        for entry in os.scandir(icon_dir):
            if entry.is_file(follow_symlinks=False) and entry.name.lower().startswith("iconcache"):
                try:
                    size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    if size > 0 and ctx.passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=entry.path, size=size, category="图标缓存",
                            item_type="file", description=entry.name, modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return result


@scanner("字体缓存")
def scan_font_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    cache_path = os.path.join(ctx.local_appdata, "Microsoft", "Windows", "FontCache")
    r = _scan_dir(ctx, cache_path, "字体缓存")
    result.items.extend(r.items)
    result.total_size += r.total_size
    return result


@scanner("Windows错误报告")
def scan_error_reports(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    report_dirs = [
        os.path.join(ctx.local_appdata, "Microsoft", "Windows", "WER"),
        os.path.join(ctx.windir, "Minidump"),
        os.path.join(ctx.windir, "LiveKernelReports"),
    ]
    for report_dir in report_dirs:
        r = _scan_dir(ctx, report_dir, "错误报告", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("崩溃转储文件")
def scan_crash_dumps(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    dump_paths = [
        os.path.join(ctx.windir, "MEMORY.DMP"),
        os.path.join(ctx.windir, "Minidump"),
        os.path.join(ctx.local_appdata, "CrashDumps"),
    ]
    for path in dump_paths:
        if os.path.isfile(path):
            try:
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                if size > 0 and ctx.passes_filters(size, mtime):
                    result.add_item(CleanItem(
                        path=path, size=size, category="崩溃转储文件",
                        item_type="file", description=os.path.basename(path), modified_time=mtime,
                    ))
            except (OSError, PermissionError):
                pass
        elif os.path.isdir(path):
            r = _scan_dir(ctx, path, "崩溃转储文件", {".dmp", ".mdmp", ".hdmp"}, include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
    for dmp in glob.glob(os.path.join(ctx.user_profile, "*.dmp")):
        try:
            size = os.path.getsize(dmp)
            mtime = os.path.getmtime(dmp)
            if size > 0 and ctx.passes_filters(size, mtime):
                result.add_item(CleanItem(
                    path=dmp, size=size, category="崩溃转储文件",
                    item_type="file", description=os.path.basename(dmp), modified_time=mtime,
                ))
        except (OSError, PermissionError):
            pass
    return result


@scanner("预取文件")
def scan_prefetch(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    prefetch_dir = os.path.join(ctx.windir, "Prefetch")
    if not os.path.isdir(prefetch_dir):
        return result
    try:
        for entry in os.scandir(prefetch_dir):
            if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".pf"):
                try:
                    size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    if size > 0 and ctx.passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=entry.path, size=size, category="预取文件",
                            item_type="file", description=entry.name, modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return result


@scanner("Windows.old旧系统")
def scan_windows_old(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    for drive in _existing_drives():
        old_path = f"{drive}:\\Windows.old"
        if os.path.isdir(old_path):
            size = _get_size(old_path)
            if size > 0:
                result.add_item(CleanItem(
                    path=old_path, size=size, category="Windows.old旧系统",
                    item_type="dir", description=f"{drive}:\\Windows.old",
                ))
    return result


@scanner("ChkDsk碎片文件")
def scan_chk_files(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    for drive in _existing_drives():
        found_path = f"{drive}:\\FOUND.{{????}}"
        for match_dir in glob.glob(found_path):
            if os.path.isdir(match_dir):
                try:
                    size = _get_size(match_dir)
                    mtime = _get_mtime(match_dir)
                    if size > 0 and ctx.passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=match_dir, size=size, category="ChkDsk碎片文件",
                            item_type="dir", description=os.path.basename(match_dir),
                            modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
        for chk in glob.glob(f"{drive}:\\*.chk"):
            try:
                size = os.path.getsize(chk)
                mtime = os.path.getmtime(chk)
                if size > 0 and ctx.passes_filters(size, mtime):
                    result.add_item(CleanItem(
                        path=chk, size=size, category="ChkDsk碎片文件",
                        item_type="file", description=os.path.basename(chk),
                        modified_time=mtime,
                    ))
            except (OSError, PermissionError):
                pass
    return result


@scanner("Windows Store缓存")
def scan_store_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    store_cache = os.path.join(
        ctx.local_appdata, "Packages", "Microsoft.WindowsStore_8wekyb3d8bbwe", "LocalCache"
    )
    r = _scan_dir(ctx, store_cache, "Windows Store缓存", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    return result


@scanner("Windows Installer缓存")
def scan_installer_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    installer_dir = os.path.join(ctx.windir, "Installer")
    if not os.path.isdir(installer_dir):
        return result
    patch_cache = os.path.join(installer_dir, "$PatchCache$")
    if os.path.isdir(patch_cache):
        r = _scan_dir(ctx, patch_cache, "Installer缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    for entry in os.scandir(installer_dir):
        if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".msp"):
            try:
                size = entry.stat().st_size
                mtime = entry.stat().st_mtime
                if size > 5 * 1024 * 1024 and ctx.passes_filters(size, mtime):
                    result.add_item(CleanItem(
                        path=entry.path, size=size, category="Installer缓存",
                        item_type="file", description=entry.name, modified_time=mtime,
                    ))
            except (OSError, PermissionError):
                pass
    return result


@scanner("Delivery Optimization")
def scan_delivery_optimization(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    do_path = os.path.join(
        ctx.local_appdata, "Packages",
        "Microsoft.WindowsDeliveryOptimization_8wekyb3d8bbwe", "LocalState"
    )
    if os.path.isdir(do_path):
        r = _scan_dir(ctx, do_path, "Delivery Optimization", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("Windows Spotlight缓存")
def scan_spotlight_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    spotlight_path = os.path.join(
        ctx.local_appdata, "Packages",
        "Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy", "LocalState", "Assets"
    )
    r = _scan_dir(ctx, spotlight_path, "Windows Spotlight缓存", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    spotlight_path2 = os.path.join(
        ctx.local_appdata, "Packages",
        "Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy", "LocalState", "TargetedContentCache"
    )
    r2 = _scan_dir(ctx, spotlight_path2, "Windows Spotlight缓存", include_subdirs=True)
    result.items.extend(r2.items)
    result.total_size += r2.total_size
    return result


@scanner("Windows性能日志")
def scan_performance_logs(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    perf_paths = [
        os.path.join(ctx.windir, "Performance", "WinSAT"),
        os.path.join(ctx.windir, "System32", "LogFiles", "WMI"),
    ]
    for path in perf_paths:
        r = _scan_dir(ctx, path, "Windows性能日志", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("Windows遥测诊断数据")
def scan_telemetry(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    telemetry_path = os.path.join(ctx.program_data, "Microsoft", "Diagnosis", "ETLLogs")
    r = _scan_dir(ctx, telemetry_path, "Windows遥测诊断数据", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    diag_dir = os.path.join(ctx.program_data, "Microsoft", "Diagnosis")
    if os.path.isdir(diag_dir):
        for name in ("diagerr.xml", "diagwrn.xml"):
            fp = os.path.join(diag_dir, name)
            if os.path.isfile(fp):
                try:
                    size = os.path.getsize(fp)
                    mtime = os.path.getmtime(fp)
                    if size > 0 and ctx.passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=fp, size=size, category="Windows遥测诊断数据",
                            item_type="file", description=name, modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
    return result


@scanner(".NET临时文件")
def scan_dotnet_temp(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    dotnet_paths = [
        os.path.join(ctx.windir, "Microsoft.NET", "Framework", "v4.0.30319", "Temporary ASP.NET Files"),
        os.path.join(ctx.windir, "Microsoft.NET", "Framework64", "v4.0.30319", "Temporary ASP.NET Files"),
    ]
    for path in dotnet_paths:
        r = _scan_dir(ctx, path, ".NET临时文件", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("D3D着色器缓存")
def scan_d3d_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    d3d_cache = os.path.join(ctx.local_appdata, "D3DSCache")
    r = _scan_dir(ctx, d3d_cache, "D3D着色器缓存", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    return result


@scanner("最近文件记录")
def scan_recent_files(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    recent_dir = os.path.join(ctx.appdata, "Microsoft", "Windows", "Recent")
    if not os.path.isdir(recent_dir):
        return result
    try:
        for entry in os.scandir(recent_dir):
            if entry.is_file(follow_symlinks=False):
                try:
                    size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    if size > 0 and ctx.passes_filters(size, mtime):
                        result.add_item(CleanItem(
                            path=entry.path, size=size, category="最近文件记录",
                            item_type="file", description=entry.name, modified_time=mtime,
                        ))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return result


@scanner("剪贴板历史")
def scan_clipboard_history(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    clipboard_path = os.path.join(ctx.local_appdata, "Microsoft", "Windows", "Clipboard")
    r = _scan_dir(ctx, clipboard_path, "剪贴板历史", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    return result


@scanner("Windows Defender扫描历史")
def scan_defender_history(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    defender_path = os.path.join(ctx.program_data, "Microsoft", "Windows Defender", "Scans", "History")
    r = _scan_dir(ctx, defender_path, "Defender扫描历史", include_subdirs=True)
    result.items.extend(r.items)
    result.total_size += r.total_size
    return result


@scanner("回收站")
def scan_recycle_bin(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    total_size = 0
    for drive in _existing_drives():
        recycle_path = f"{drive}:\\$Recycle.Bin"
        try:
            total_size += _get_size(recycle_path)
        except (OSError, PermissionError):
            pass
    if total_size > 0:
        result.add_item(CleanItem(
            path="[Recycle Bin - All Drives]",
            size=total_size,
            category="回收站",
            item_type="recycle_bin",
            description="所有驱动器回收站内容",
        ))
    return result


@scanner("DNS缓存")
def scan_dns_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    result.add_item(CleanItem(
        path="[DNS Cache - Memory]",
        size=0,
        category="DNS缓存",
        item_type="dns_cache",
        description="系统DNS解析缓存",
    ))
    return result


# ── 通用目录扫描辅助 ──────────────────────────────────────────

def _scan_dir(ctx: ScanContext, path: str, category: str, ext_filter: set = None,
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
                        mtime = _get_mtime(entry.path)
                        if size > 0 and ctx.passes_filters(size, mtime):
                            result.add_item(CleanItem(
                                path=entry.path, size=size, category=category,
                                item_type="dir", modified_time=mtime,
                            ))
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return result
