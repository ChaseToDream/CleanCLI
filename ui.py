"""
CleanCLI - 交互式CLI界面模块 v2.0
提供彩色终端输出、交互式选择、进度展示、清理报告、磁盘信息、报告导出
"""

import os
import sys
import json
import time
from typing import List, Optional, Tuple
from dataclasses import dataclass, asdict

from cleaner import ScanResult, CleanItem
from residual import ResidualItem, ResidualScanResult


# ── ANSI 颜色码 ──────────────────────────────────────────────

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def _enable_ansi():
    """启用Windows终端ANSI颜色支持和UTF-8编码"""
    if sys.platform == "win32":
        import ctypes
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
        try:
            os.system("")
        except Exception:
            pass
        try:
            if sys.stdout.encoding != "utf-8":
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        try:
            if sys.stderr.encoding != "utf-8":
                sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


_enable_ansi()


# ── 输出工具函数 ──────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    if i == 0:
        return f"{int(size)} B"
    return f"{size:.2f} {units[i]}"


def format_age(days: int) -> str:
    """格式化时间年龄"""
    if days <= 0:
        return "不限"
    if days == 1:
        return "1天以上"
    if days < 30:
        return f"{days}天以上"
    if days < 365:
        return f"{days // 30}个月以上"
    return f"{days // 365}年以上"


def print_banner():
    """打印程序横幅"""
    banner = f"""
{Color.CYAN}{Color.BOLD}
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║        ██████╗██╗     ███████╗ █████╗ ███╗   ██╗        ║
  ║       ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║        ║
  ║       ██║     ██║     █████╗  ███████║██╔██╗ ██║        ║
  ║       ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║        ║
  ║       ╚██████╗███████╗███████╗██║  ██║██║ ╚████║        ║
  ║        ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝        ║
  ║                                                          ║
  ║            Windows 系统垃圾清理工具 v2.1                  ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
{Color.RESET}"""
    print(banner)


def print_separator(char: str = "─", width: int = 60, color: str = ""):
    """打印分隔线"""
    c = color or Color.DIM
    print(f"{c}{char * width}{Color.RESET}")


def print_header(title: str):
    """打印带装饰的标题"""
    print()
    print_separator("═", 60, Color.CYAN)
    print(f"{Color.CYAN}{Color.BOLD}  ◆ {title}{Color.RESET}")
    print_separator("═", 60, Color.CYAN)


def print_subheader(title: str):
    """打印子标题"""
    print(f"\n{Color.YELLOW}{Color.BOLD}  ▸ {title}{Color.RESET}")
    print_separator("─", 50, Color.DIM)


def print_info(label: str, value: str, indent: int = 4):
    """打印信息行"""
    spaces = " " * indent
    print(f"{spaces}{Color.DIM}{label}:{Color.RESET} {value}")


def print_success(msg: str, indent: int = 4):
    """打印成功消息"""
    spaces = " " * indent
    print(f"{spaces}{Color.GREEN}[OK] {msg}{Color.RESET}")


def print_warning(msg: str, indent: int = 4):
    """打印警告消息"""
    spaces = " " * indent
    print(f"{spaces}{Color.YELLOW}[!] {msg}{Color.RESET}")


def print_error(msg: str, indent: int = 4):
    """打印错误消息"""
    spaces = " " * indent
    print(f"{spaces}{Color.RED}[X] {msg}{Color.RESET}")


def print_progress_bar(current: int, total: int, width: int = 40, prefix: str = ""):
    """打印进度条"""
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r{prefix} [{Color.GREEN}{bar}{Color.RESET}] {pct*100:.0f}% ({current}/{total})", end="", flush=True)
    if current == total:
        print()


# ── 系统信息展示 ──────────────────────────────────────────────

def display_system_info(disk_info: List[dict], older_than: int = 0, min_size: int = 0):
    """展示系统信息和过滤条件"""
    print_header("系统信息")

    import platform
    print_info("操作系统", f"Windows {platform.version()}")
    print_info("计算机名", platform.node())
    print_info("处理器", platform.processor()[:50] if platform.processor() else "N/A")

    if disk_info:
        print_subheader("磁盘使用情况")
        for disk in disk_info:
            bar_width = 20
            filled = int(bar_width * disk["percent"] / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            color = Color.RED if disk["percent"] > 90 else Color.YELLOW if disk["percent"] > 75 else Color.GREEN
            print(f"    {Color.BOLD}{disk['drive']}:{Color.RESET} "
                  f"[{color}{bar}{Color.RESET}] {disk['percent']}% "
                  f"{Color.DIM}已用 {format_size(disk['used'])} / "
                  f"可用 {format_size(disk['free'])} / "
                  f"总计 {format_size(disk['total'])}{Color.RESET}")

    if older_than > 0 or min_size > 0:
        print_subheader("过滤条件")
        if older_than > 0:
            print_info("文件年龄", f"仅清理 {format_age(older_than)} 的文件")
        if min_size > 0:
            print_info("最小大小", f"仅清理 >= {format_size(min_size)} 的文件")


# ── 扫描结果展示 ──────────────────────────────────────────────

def display_scan_results(results: List[ScanResult], show_detail: bool = True) -> Tuple[int, int]:
    """展示垃圾扫描结果，返回 (总项目数, 总大小)"""
    total_items = 0
    total_size = 0

    print_header("垃圾文件扫描结果")

    for result in results:
        if result.error:
            print_warning(f"{result.category}: 扫描失败 - {result.error}")
            continue

        if not result.items:
            if show_detail:
                print(f"  {Color.DIM}{result.category}: 未发现垃圾文件{Color.RESET}")
            continue

        item_count = len(result.items)
        category_size = result.total_size
        total_items += item_count
        total_size += category_size

        print(f"\n  {Color.CYAN}{Color.BOLD}{result.category}{Color.RESET}"
              f"  {Color.DIM}({item_count} 项, {format_size(category_size)}){Color.RESET}")

        if show_detail:
            for item in result.items[:5]:
                name = os.path.basename(item.path) if item.path else "Unknown"
                desc = f" ({item.description})" if item.description else ""
                print(f"    {Color.DIM}  {name}{desc} - {format_size(item.size)}{Color.RESET}")
            if item_count > 5:
                print(f"    {Color.DIM}  ... 还有 {item_count - 5} 项{Color.RESET}")

    print()
    print_separator("═", 60, Color.CYAN)
    print(f"  {Color.BOLD}总计: {Color.GREEN}{total_items}{Color.RESET} {Color.BOLD}个文件, "
          f"占用 {Color.YELLOW}{format_size(total_size)}{Color.RESET}")
    print_separator("═", 60, Color.CYAN)

    return total_items, total_size


def display_residual_results(result: ResidualScanResult, show_detail: bool = True):
    """展示残留文件扫描结果"""
    print_header("残留文件扫描结果")

    print_info("已安装程序数量", str(len(result.installed_programs)))

    if not result.residual_items:
        print_success("未发现残留文件，系统很干净！")
        return

    by_type = {}
    for item in result.residual_items:
        by_type.setdefault(item.residual_type, []).append(item)

    type_labels = {
        "dir": "残留目录",
        "file": "残留文件",
        "registry": "残留注册表项",
        "shortcut": "孤立快捷方式",
        "service": "孤儿服务",
        "task": "孤儿计划任务",
        "startup": "孤儿启动项",
    }

    risk_colors = {"low": Color.GREEN, "medium": Color.YELLOW, "high": Color.RED}

    for rtype, items in by_type.items():
        label = type_labels.get(rtype, rtype)
        print_subheader(f"{label} ({len(items)} 项)")

        display_items = items if show_detail else items[:10]
        for item in display_items:
            risk_color = risk_colors.get(item.risk_level, Color.WHITE)
            risk_label = {"low": "低", "medium": "中", "high": "高"}.get(item.risk_level, "?")
            size_str = format_size(item.size) if item.size > 0 else "N/A"
            print(f"    {Color.WHITE}{item.path}{Color.RESET}")
            print(f"      {Color.DIM}关联: {item.associated_program} | "
                  f"大小: {size_str} | "
                  f"风险: {risk_color}[{risk_label}]{Color.RESET}")
        if not show_detail and len(items) > 10:
            print(f"    {Color.DIM}  ... 还有 {len(items) - 10} 项{Color.RESET}")

    print()
    print_separator("═", 60, Color.CYAN)
    print(f"  {Color.BOLD}残留项目总计: {Color.YELLOW}{len(result.residual_items)}{Color.RESET} 项, "
          f"占用 {Color.YELLOW}{format_size(result.total_size)}{Color.RESET}")
    print_separator("═", 60, Color.CYAN)

    if result.errors:
        print_warning(f"扫描过程中有 {len(result.errors)} 个错误")


# ── 交互式选择 ──────────────────────────────────────────────

def prompt_yes_no(question: str, default: bool = True) -> bool:
    """提示用户确认 (Y/N)"""
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            answer = input(f"  {Color.YELLOW}? {question} [{hint}]: {Color.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if not answer:
            return default
        if answer in ("y", "yes", "是"):
            return True
        if answer in ("n", "no", "否"):
            return False
        print(f"    {Color.DIM}请输入 y 或 n{Color.RESET}")


def prompt_category_select(results: List[ScanResult]) -> List[ScanResult]:
    """让用户选择要清理的垃圾类别"""
    print_header("选择清理类别")

    available = [(i, r) for i, r in enumerate(results) if r.items and not r.error]
    if not available:
        print_info("提示", "没有可清理的类别")
        return []

    for idx, (i, r) in enumerate(available, 1):
        size_str = format_size(r.total_size)
        print(f"  {Color.GREEN}{Color.BOLD}[{idx:>2}]{Color.RESET} {r.category}"
              f"  {Color.DIM}({len(r.items)} 项, {size_str}){Color.RESET}")

    print()
    print(f"  {Color.DIM}输入序号选择类别，多个用逗号分隔 (如: 1,3,5)")
    print(f"  输入 'a' 或 'all' 选择全部，直接回车跳过{Color.RESET}")

    while True:
        try:
            answer = input(f"\n  {Color.YELLOW}? 请选择要清理的类别: {Color.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return []

        if not answer:
            return []
        if answer in ("a", "all", "全部"):
            return [r for _, r in available]

        try:
            indices = []
            for part in answer.split(","):
                part = part.strip()
                if part:
                    n = int(part)
                    if 1 <= n <= len(available):
                        indices.append(n - 1)
            if indices:
                return [available[i][1] for i in indices]
        except ValueError:
            pass

        print(f"    {Color.RED}无效输入，请重新选择{Color.RESET}")


def prompt_residual_select(result: ResidualScanResult) -> List[ResidualItem]:
    """让用户选择要清理的残留项目"""
    print_header("选择清理残留项目")

    if not result.residual_items:
        print_info("提示", "没有发现残留项目")
        return []

    type_labels = {
        "dir": "目录", "file": "文件", "registry": "注册表",
        "shortcut": "快捷方式", "service": "服务", "task": "任务", "startup": "启动项",
    }
    risk_colors = {"low": Color.GREEN, "medium": Color.YELLOW, "high": Color.RED}

    for idx, item in enumerate(result.residual_items, 1):
        risk_color = risk_colors.get(item.risk_level, Color.WHITE)
        risk_label = {"low": "低", "medium": "中", "high": "高"}.get(item.risk_level, "?")
        type_label = type_labels.get(item.residual_type, item.residual_type)
        size_str = format_size(item.size) if item.size > 0 else "N/A"

        print(f"  {Color.GREEN}{Color.BOLD}[{idx:>2}]{Color.RESET} [{type_label}] {item.path}")
        print(f"      {Color.DIM}关联: {item.associated_program} | "
              f"大小: {size_str} | "
              f"风险: {risk_color}[{risk_label}]{Color.RESET}")

    print()
    print(f"  {Color.DIM}输入序号选择项目，多个用逗号分隔 (如: 1,3,5)")
    print(f"  输入 'a' 选择全部低风险项，'all' 选择全部，直接回车跳过{Color.RESET}")

    while True:
        try:
            answer = input(f"\n  {Color.YELLOW}? 请选择要清理的残留项: {Color.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return []

        if not answer:
            return []
        if answer == "a":
            return [item for item in result.residual_items if item.risk_level == "low"]
        if answer in ("all", "全部"):
            return list(result.residual_items)

        try:
            indices = []
            for part in answer.split(","):
                part = part.strip()
                if part:
                    n = int(part)
                    if 1 <= n <= len(result.residual_items):
                        indices.append(n - 1)
            if indices:
                return [result.residual_items[i] for i in indices]
        except ValueError:
            pass

        print(f"    {Color.RED}无效输入，请重新选择{Color.RESET}")


# ── 清理报告 ──────────────────────────────────────────────

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


def display_clean_report(report: CleanReport):
    """展示清理报告"""
    title = "清理报告（模拟模式）" if report.dry_run else "清理报告"
    print_header(title)

    total_cleaned = report.junk_files_cleaned + report.residual_files_cleaned
    total_freed = report.junk_space_freed + report.residual_space_freed
    total_failed = report.junk_failed + report.residual_failed

    print_subheader("垃圾文件清理")
    print_info("清理文件数", f"{Color.GREEN}{report.junk_files_cleaned}{Color.RESET} 个")
    print_info("释放空间", f"{Color.GREEN}{format_size(report.junk_space_freed)}{Color.RESET}")
    if report.junk_failed > 0:
        print_info("失败项目", f"{Color.RED}{report.junk_failed}{Color.RESET} 个")

    if report.categories:
        print()
        for cat, count in report.categories.items():
            print(f"      {Color.DIM}  {cat}: {count} 项{Color.RESET}")

    if report.residual_files_cleaned > 0 or report.residual_failed > 0:
        print_subheader("残留文件清理")
        print_info("清理项目数", f"{Color.GREEN}{report.residual_files_cleaned}{Color.RESET} 个")
        print_info("释放空间", f"{Color.GREEN}{format_size(report.residual_space_freed)}{Color.RESET}")
        if report.residual_failed > 0:
            print_info("失败项目", f"{Color.RED}{report.residual_failed}{Color.RESET} 个")

    print()
    print_separator("═", 60, Color.GREEN)
    print(f"  {Color.BOLD}清理总计:{Color.RESET}")
    print(f"    [OK] 共清理 {Color.GREEN}{Color.BOLD}{total_cleaned}{Color.RESET} 个项目")
    print(f"    [OK] 释放空间 {Color.GREEN}{Color.BOLD}{format_size(total_freed)}{Color.RESET}")
    if total_failed > 0:
        print(f"    [!] {total_failed} 个项目清理失败（可能被占用或权限不足）")
    if report.elapsed_seconds > 0:
        print(f"    {Color.DIM}耗时: {report.elapsed_seconds:.1f} 秒{Color.RESET}")
    print_separator("═", 60, Color.GREEN)

    if report.dry_run:
        print(f"\n  {Color.YELLOW}[!] 模拟模式 - 未实际删除任何文件{Color.RESET}\n")
    else:
        print(f"\n  {Color.DIM}提示: 部分清理可能需要重启系统才能完全生效{Color.RESET}\n")


def export_report(report: CleanReport, filepath: str,
                  junk_results: List[ScanResult] = None,
                  residual_result: ResidualScanResult = None):
    """导出清理报告到JSON文件"""
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run": report.dry_run,
        "summary": {
            "junk_files_cleaned": report.junk_files_cleaned,
            "junk_space_freed": report.junk_space_freed,
            "junk_space_freed_human": format_size(report.junk_space_freed),
            "junk_failed": report.junk_failed,
            "residual_files_cleaned": report.residual_files_cleaned,
            "residual_space_freed": report.residual_space_freed,
            "residual_space_freed_human": format_size(report.residual_space_freed),
            "residual_failed": report.residual_failed,
            "total_cleaned": report.junk_files_cleaned + report.residual_files_cleaned,
            "total_freed": report.junk_space_freed + report.residual_space_freed,
            "total_freed_human": format_size(report.junk_space_freed + report.residual_space_freed),
            "elapsed_seconds": report.elapsed_seconds,
        },
        "categories": report.categories,
    }

    if junk_results:
        data["junk_details"] = []
        for r in junk_results:
            if r.items:
                data["junk_details"].append({
                    "category": r.category,
                    "item_count": len(r.items),
                    "total_size": r.total_size,
                    "total_size_human": format_size(r.total_size),
                    "items": [{"path": i.path, "size": i.size, "description": i.description} for i in r.items[:50]],
                })

    if residual_result and residual_result.residual_items:
        data["residual_details"] = [
            {
                "path": i.path, "size": i.size, "type": i.residual_type,
                "associated": i.associated_program, "description": i.description,
                "risk": i.risk_level,
            }
            for i in residual_result.residual_items
        ]

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print_success(f"报告已导出: {filepath}")
    except (OSError, IOError) as e:
        print_error(f"导出失败: {e}")
