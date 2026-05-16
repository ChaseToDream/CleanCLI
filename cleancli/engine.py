"""
CleanCLI - 业务逻辑引擎
封装纯业务逻辑，不依赖 UI 模块
"""

import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from cleancli.cleaner import (
    JunkScanner, ScanResult, CleanItem, CleanItemResult,
    clean_items, get_disk_info, get_error_summary,
)
from cleancli.residual import (
    ResidualScanner, ResidualScanResult, ResidualItem,
    clean_residual_item, get_clean_action_description,
)


@dataclass
class CleanReport:
    """清理报告"""
    junk_files_cleaned: int = 0
    junk_space_freed: int = 0
    junk_failed: int = 0
    residual_files_cleaned: int = 0
    residual_space_freed: int = 0
    residual_failed: int = 0
    categories: dict = None
    dry_run: bool = False
    elapsed_seconds: float = 0.0

    def __post_init__(self):
        if self.categories is None:
            self.categories = {}

    @property
    def total_cleaned(self) -> int:
        return self.junk_files_cleaned + self.residual_files_cleaned

    @property
    def total_freed(self) -> int:
        return self.junk_space_freed + self.residual_space_freed

    @property
    def total_failed(self) -> int:
        return self.junk_failed + self.residual_failed


def build_scanner(older: int = 0, min_kb: int = 0) -> JunkScanner:
    """构建垃圾扫描器"""
    return JunkScanner(older_than_days=older, min_size_bytes=min_kb * 1024)


def scan_junk(older: int = 0, min_kb: int = 0) -> List[ScanResult]:
    """扫描垃圾文件"""
    scanner = build_scanner(older, min_kb)
    return scanner.scan_all()


def scan_residual() -> ResidualScanResult:
    """扫描残留文件"""
    scanner = ResidualScanner()
    return scanner.scan_all()


def select_junk_categories(results: List[ScanResult],
                           auto: bool = False) -> List[ScanResult]:
    """选择要清理的垃圾类别（纯逻辑）"""
    if auto:
        return [r for r in results if r.items and not r.error]
    # 非 auto 模式由 UI 层处理选择
    return []


def select_residual_items(result: ResidualScanResult,
                          auto: bool = False) -> List[ResidualItem]:
    """选择要清理的残留项（纯逻辑）"""
    if auto:
        return [i for i in result.residual_items if i.risk_level == "low"]
    # 非 auto 模式由 UI 层处理选择
    return []


def execute_clean_junk(selected: List[ScanResult], dry_run: bool = False,
                       on_error: Callable = None) -> Tuple[int, int, int, List[CleanItemResult], dict]:
    """执行垃圾清理，返回 (success, failed, freed, details, categories)"""
    all_items = []
    categories = {}
    for r in selected:
        all_items.extend(r.items)
        categories[r.category] = len(r.items)

    success, failed, freed, details = clean_items(all_items, dry_run=dry_run, on_error=on_error)
    return success, failed, freed, details, categories


def execute_clean_residual(selected: List[ResidualItem], dry_run: bool = False,
                           on_progress: Callable = None) -> Tuple[int, int, int]:
    """执行残留清理，返回 (success, failed, freed)"""
    success = failed = freed = 0
    total = len(selected)

    for i, item in enumerate(selected):
        if on_progress:
            on_progress(i, total)
        if dry_run:
            success += 1
            freed += item.size
        else:
            if clean_residual_item(item, dry_run=dry_run):
                success += 1
                freed += item.size
            else:
                failed += 1

    return success, failed, freed


def make_report(junk_result: Tuple = None, residual_result: Tuple = None,
                categories: dict = None, dry_run: bool = False,
                elapsed: float = 0.0) -> CleanReport:
    """构建清理报告"""
    report = CleanReport(dry_run=dry_run, elapsed_seconds=elapsed, categories=categories or {})

    if junk_result:
        report.junk_files_cleaned = junk_result[0]
        report.junk_failed = junk_result[1]
        report.junk_space_freed = junk_result[2]

    if residual_result:
        report.residual_files_cleaned = residual_result[0]
        report.residual_failed = residual_result[1]
        report.residual_space_freed = residual_result[2]

    return report


def check_admin() -> bool:
    """检查是否以管理员权限运行（仅 Windows）"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
