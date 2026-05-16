"""
CleanCLI - 配置模块
集中管理白名单、系统目录、风险等级等配置
"""

import os
import logging


# ── 日志配置 ──────────────────────────────────────────

def setup_logging(level: int = logging.WARNING, log_file: str = None):
    """配置日志系统"""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format=fmt, handlers=handlers)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── 安全路径白名单 ──────────────────────────────────────────
# 仅清理以这些前缀开头的路径

SAFE_PATH_PREFIXES = [
    # 系统临时目录
    _env("TEMP"),
    _env("TMP"),
    os.path.join(_env("LOCALAPPDATA"), "temp"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "inetcache"),
    _env("SYSTEMROOT") + "\\temp" if _env("SYSTEMROOT") else "",

    # 系统缓存与日志
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "explorer"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "wer"),
    os.path.join(_env("SYSTEMROOT"), "logs"),
    os.path.join(_env("SYSTEMROOT"), "panther"),
    os.path.join(_env("SYSTEMROOT"), "debug"),
    os.path.join(_env("SYSTEMROOT"), "prefetch"),
    os.path.join(_env("SYSTEMROOT"), "softwaredistribution"),
    os.path.join(_env("SYSTEMROOT"), "minidump"),
    os.path.join(_env("SYSTEMROOT"), "livekernelreports"),
    os.path.join(_env("LOCALAPPDATA"), "crashdumps"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "notifications"),
    os.path.join(_env("LOCALAPPDATA"), "d3dscache"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "fontcache"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "recent"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "windows", "clipboard"),

    # 浏览器
    os.path.join(_env("LOCALAPPDATA"), "google"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "edge"),
    os.path.join(_env("LOCALAPPDATA"), "mozilla"),
    os.path.join(_env("LOCALAPPDATA"), "brave software"),
    os.path.join(_env("LOCALAPPDATA"), "vivaldi"),
    os.path.join(_env("APPDATA"), "opera software"),

    # 开发工具
    os.path.join(_env("LOCALAPPDATA"), "npm-cache"),
    os.path.join(_env("LOCALAPPDATA"), "pip", "cache"),
    os.path.join(_env("LOCALAPPDATA"), "yarn", "cache"),
    os.path.join(_env("LOCALAPPDATA"), "go"),
    os.path.join(_env("USERPROFILE"), ".cache"),
    os.path.join(_env("USERPROFILE"), ".cargo", "registry"),
    os.path.join(_env("USERPROFILE"), ".cargo", "git"),
    os.path.join(_env("USERPROFILE"), ".conda", "pkgs"),
    os.path.join(_env("LOCALAPPDATA"), "chocolatey"),
    os.path.join(_env("USERPROFILE"), "scoop", "cache"),
    os.path.join(_env("LOCALAPPDATA"), "docker"),
    os.path.join(_env("APPDATA"), "code", "cache"),
    os.path.join(_env("APPDATA"), "code", "cacheddata"),
    os.path.join(_env("APPDATA"), "code", "cachedextensionvsixs"),
    os.path.join(_env("APPDATA"), "code", "logs"),
    os.path.join(_env("APPDATA"), "code", "user", "workspacestorage"),
    os.path.join(_env("LOCALAPPDATA"), "programs", "microsoft vs code"),

    # Java
    os.path.join(_env("LOCALAPPDATA"), "sun", "java"),
    os.path.join(_env("LOCALAPPDATA"), "oracle", "java"),

    # 系统安全
    os.path.join(_env("ProgramData"), "microsoft", "windows defender", "scans"),
    os.path.join(_env("SYSTEMROOT"), "serviceprofiles", "localservice", "appdata", "local", "microsoft", "windows", "deliveryoptimization"),
    os.path.join(_env("SYSTEMROOT"), "serviceprofiles", "networkservice", "appdata", "local", "microsoft", "windows", "deliveryoptimization"),
    os.path.join(_env("SYSTEMROOT"), "performance", "winsat"),
    os.path.join(_env("LOCALAPPDATA"), "packages"),
    os.path.join(_env("SYSTEMROOT"), "installer", "$patchcache$"),
    os.path.join(_env("PROGRAMDATA"), "microsoft", "diagnosis", "etllogs"),

    # Microsoft 应用
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "onenote"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "outlook"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "teams"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "onedrive"),
    os.path.join(_env("APPDATA"), "microsoft", "teams", "cache"),
    os.path.join(_env("APPDATA"), "microsoft", "teams", "gpucache"),
    os.path.join(_env("LOCALAPPDATA"), "packages", "msteams_8wekyb3d8bbwe", "localcache"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "onedrive", "logs"),
    os.path.join(_env("LOCALAPPDATA"), "microsoft", "onedrive", "settings"),
]

# 过滤空字符串
SAFE_PATH_PREFIXES = [p for p in SAFE_PATH_PREFIXES if p]


# ── 系统目录（残留扫描时跳过）──────────────────────────────────

SYSTEM_DIRS = {
    "microsoft", "windows", "google", "mozilla", "intel", "nvidia",
    "amd", "realtek", "common files", "internet explorer",
    "windows defender", "windows mail", "windows media player",
    "windows nt", "windows photo viewer", "windows portable devices",
    "windows sidebar", "windowspowershell", "packages", "connecteddevicesplatform",
    "temp", "temporary internet files", "crashdumps", "thumb",
}


# ── 系统发布者（残留扫描时跳过）──────────────────────────────────

SYSTEM_PUBLISHERS = {
    "microsoft corporation", "microsoft", "windows",
}


# ── 错误类型标签 ──────────────────────────────────────────

ERROR_LABELS = {
    "locked": ("文件被占用", ),
    "permission": ("权限不足", ),
    "not_found": ("文件不存在", ),
    "unsafe_path": ("路径不安全", ),
    "command_failed": ("命令执行失败", ),
    "recycle_bin_failed": ("回收站清理失败", ),
    "unknown": ("未知错误", ),
    "other": ("其他错误", ),
}
