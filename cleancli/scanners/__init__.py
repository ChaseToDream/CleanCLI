"""
CleanCLI - 扫描器注册机制
提供 ScanContext（扫描上下文）和 scanner 注册装饰器
"""

import os
import time
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Tuple

from cleancli.cleaner import ScanResult


@dataclass
class ScanContext:
    """扫描上下文，包含所有扫描器共用的路径和过滤配置"""
    user_profile: str
    local_appdata: str
    appdata: str
    program_data: str
    windir: str
    temp_dir: str
    older_than_days: int
    min_size_bytes: int
    _now: float

    @classmethod
    def from_scanner(cls, scanner) -> "ScanContext":
        """从 JunkScanner 实例创建上下文"""
        return cls(
            user_profile=scanner.user_profile,
            local_appdata=scanner.local_appdata,
            appdata=scanner.appdata,
            program_data=scanner.program_data,
            windir=scanner.windir,
            temp_dir=scanner.temp_dir,
            older_than_days=scanner.older_than_days,
            min_size_bytes=scanner.min_size_bytes,
            _now=scanner._now,
        )

    def passes_filters(self, size: int, mtime: float) -> bool:
        """检查是否通过年龄和大小过滤"""
        if self.min_size_bytes > 0 and size < self.min_size_bytes:
            return False
        if self.older_than_days > 0 and mtime > 0:
            cutoff = self._now - (self.older_than_days * 86400)
            if mtime > cutoff:
                return False
        return True


# ── 扫描器注册表 ──────────────────────────────────────────

_REGISTRY: List[Tuple[str, Callable]] = []


def scanner(name: str):
    """注册扫描器装饰器

    用法:
        @scanner("用户临时文件")
        def scan_user_temp(ctx: ScanContext) -> ScanResult:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        _REGISTRY.append((name, fn))
        return fn
    return decorator


def get_all_scanners() -> List[Tuple[str, Callable]]:
    """获取所有已注册的扫描器"""
    return list(_REGISTRY)


def clear_registry():
    """清空注册表（用于测试）"""
    _REGISTRY.clear()
