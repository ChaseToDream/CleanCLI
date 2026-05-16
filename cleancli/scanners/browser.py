"""
CleanCLI - 浏览器缓存扫描器
扫描 Chrome、Edge、Firefox、Brave、Vivaldi、Opera 等浏览器缓存
"""

import os
from cleancli.cleaner import CleanItem, ScanResult, _get_size
from cleancli.scanners import scanner, ScanContext


@scanner("浏览器缓存 - Chrome")
def scan_chrome_cache(ctx: ScanContext) -> ScanResult:
    chrome_base = os.path.join(ctx.local_appdata, "Google", "Chrome", "User Data")
    return _scan_chromium_profile_caches("Chrome", chrome_base)


@scanner("浏览器缓存 - Edge")
def scan_edge_cache(ctx: ScanContext) -> ScanResult:
    edge_base = os.path.join(ctx.local_appdata, "Microsoft", "Edge", "User Data")
    return _scan_chromium_profile_caches(
        "Edge", edge_base,
        cache_names=("Cache", "Code Cache", "GPUCache", "Service Worker")
    )


@scanner("浏览器缓存 - Firefox")
def scan_firefox_cache(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    profiles_dir = os.path.join(ctx.local_appdata, "Mozilla", "Firefox", "Profiles")
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


@scanner("浏览器缓存 - Chromium系")
def scan_chromium_browsers(ctx: ScanContext) -> ScanResult:
    result = ScanResult(category="")
    chromium_browsers = [
        ("Brave", os.path.join(ctx.local_appdata, "Brave Software", "Brave-Browser", "User Data"), False),
        ("Vivaldi", os.path.join(ctx.local_appdata, "Vivaldi", "User Data"), False),
        ("Opera", os.path.join(ctx.appdata, "Opera Software", "Opera Stable"), True),
        ("Opera GX", os.path.join(ctx.appdata, "Opera Software", "Opera GX Stable"), True),
        ("Arc", os.path.join(ctx.local_appdata, "Arc", "User Data"), False),
    ]
    for browser_name, user_data, scan_root in chromium_browsers:
        r = _scan_chromium_profile_caches(browser_name, user_data, scan_root_caches=scan_root)
        result.items.extend(r.items)
        result.total_size += r.total_size
    return result


def _scan_chromium_profile_caches(browser_name: str, user_data: str,
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
