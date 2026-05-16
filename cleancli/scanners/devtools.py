"""
CleanCLI - 开发工具缓存扫描器
扫描 npm、pip、yarn、Go、Rust/Cargo、Conda、Docker、VS Code 等缓存
"""

import os
from cleancli.cleaner import CleanItem, ScanResult, _get_size
from cleancli.scanners import scanner, ScanContext


@scanner("Java缓存")
def scan_java_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    java_paths = [
        os.path.join(ctx.local_appdata, "Sun", "Java", "Deployment", "cache"),
        os.path.join(ctx.local_appdata, "Oracle", "Java", "cache"),
    ]
    for path in java_paths:
        r = _scan_dir_simple(ctx, path, "Java缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("npm缓存")
def scan_npm_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    npm_cache = os.path.join(ctx.local_appdata, "npm-cache")
    if os.path.isdir(npm_cache):
        size = _get_size(npm_cache)
        if size > 0:
            result.add_item(CleanItem(
                path=npm_cache, size=size, category="npm缓存",
                item_type="dir", description="npm cache",
            ))
    user_npm = os.path.join(ctx.user_profile, ".npm")
    if os.path.isdir(user_npm):
        size = _get_size(user_npm)
        if size > 0:
            result.add_item(CleanItem(
                path=user_npm, size=size, category="npm缓存",
                item_type="dir", description=".npm cache",
            ))
    return result


@scanner("pip缓存")
def scan_pip_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    pip_cache = os.path.join(ctx.local_appdata, "pip", "cache")
    if os.path.isdir(pip_cache):
        size = _get_size(pip_cache)
        if size > 0:
            result.add_item(CleanItem(
                path=pip_cache, size=size, category="pip缓存",
                item_type="dir", description="pip cache",
            ))
    user_pip = os.path.join(ctx.user_profile, "AppData", "Local", "pip", "cache")
    if os.path.isdir(user_pip) and user_pip != pip_cache:
        size = _get_size(user_pip)
        if size > 0:
            result.add_item(CleanItem(
                path=user_pip, size=size, category="pip缓存",
                item_type="dir", description="pip cache (user)",
            ))
    return result


@scanner("yarn缓存")
def scan_yarn_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    yarn_cache = os.path.join(ctx.local_appdata, "Yarn", "Cache")
    if os.path.isdir(yarn_cache):
        size = _get_size(yarn_cache)
        if size > 0:
            result.add_item(CleanItem(
                path=yarn_cache, size=size, category="yarn缓存",
                item_type="dir", description="yarn cache",
            ))
    return result


@scanner("Go模块缓存")
def scan_go_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    gopath = os.environ.get("GOPATH", os.path.join(ctx.user_profile, "go"))
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


@scanner("Rust/Cargo缓存")
def scan_cargo_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    cargo_home = os.environ.get("CARGO_HOME", os.path.join(ctx.user_profile, ".cargo"))
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


@scanner("Conda缓存")
def scan_conda_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    conda_cache_paths = [
        os.path.join(ctx.user_profile, ".conda", "pkgs"),
        os.path.join(ctx.user_profile, "miniconda3", "pkgs"),
        os.path.join(ctx.user_profile, "anaconda3", "pkgs"),
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


@scanner("Chocolatey缓存")
def scan_choco_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    choco_cache = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Chocolatey", "Cache")
    if os.path.isdir(choco_cache):
        r = _scan_dir_simple(ctx, choco_cache, "Chocolatey缓存", include_subdirs=True)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("Scoop缓存")
def scan_scoop_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    scoop_cache = os.path.join(ctx.user_profile, "scoop", "cache")
    if os.path.isdir(scoop_cache):
        r = _scan_dir_simple(ctx, scoop_cache, "Scoop缓存")
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


@scanner("Docker缓存")
def scan_docker_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    docker_paths = [
        os.path.join(ctx.local_appdata, "Docker", "log"),
        os.path.join(ctx.appdata, "Docker", "log"),
    ]
    for path in docker_paths:
        if os.path.isdir(path):
            r = _scan_dir_simple(ctx, path, "Docker缓存", {".log"}, include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
    return result


@scanner("VS Code缓存")
def scan_vscode_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    vscode_dirs = [
        (os.path.join(ctx.appdata, "Code", "Cache"), "VS Code缓存"),
        (os.path.join(ctx.appdata, "Code", "CachedData"), "VS Code缓存"),
        (os.path.join(ctx.appdata, "Code", "CachedExtensionVSIXs"), "VS Code缓存"),
        (os.path.join(ctx.appdata, "Code", "Logs"), "VS Code日志"),
        (os.path.join(ctx.appdata, "Code", "User", "workspaceStorage"), "VS Code工作区存储"),
        (os.path.join(ctx.local_appdata, "Programs", "Microsoft VS Code", "Cache"), "VS Code缓存"),
    ]
    for path, cat in vscode_dirs:
        if os.path.isdir(path):
            r = _scan_dir_simple(ctx, path, cat, include_subdirs=True)
            result.items.extend(r.items)
            result.total_size += r.total_size
    return result


def _scan_dir_simple(ctx: ScanContext, path: str, category: str, ext_filter: set = None,
                     include_subdirs: bool = False) -> ScanResult:
    """通用目录扫描辅助方法"""
    from cleancli.cleaner import _get_mtime
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
