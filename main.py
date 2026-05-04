"""
CleanCLI - Windows 系统垃圾清理工具 v2.0
主入口模块：命令行参数解析、流程编排
支持：年龄过滤、大小阈值、模拟模式、报告导出、系统信息展示
"""

import argparse
import sys
import os
import time

from cleaner import JunkScanner, clean_items, get_disk_info
from residual import ResidualScanner, clean_residual_item
from ui import (
    print_banner, print_header, print_subheader, print_info,
    print_success, print_warning, print_error, print_progress_bar,
    display_scan_results, display_residual_results, display_system_info,
    prompt_yes_no, prompt_category_select, prompt_residual_select,
    CleanReport, display_clean_report, export_report, format_size, Color,
)


def check_admin() -> bool:
    """检查是否以管理员权限运行"""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False


def _build_junk_scanner(args) -> JunkScanner:
    """根据参数构建扫描器"""
    older = getattr(args, "older_than", 0) or 0
    min_kb = getattr(args, "min_size", 0) or 0
    return JunkScanner(older_than_days=older, min_size_bytes=min_kb * 1024)


def run_info():
    """展示系统信息"""
    disk_info = get_disk_info()
    display_system_info(disk_info)


def run_scan_only(args):
    """仅扫描模式"""
    print_header("系统垃圾扫描")
    print_info("模式", "仅扫描（不清理）")

    disk_info = get_disk_info()
    display_system_info(disk_info, getattr(args, "older_than", 0), getattr(args, "min_size", 0) * 1024)

    print(f"\n  {Color.CYAN}正在扫描系统垃圾文件...{Color.RESET}")
    junk_scanner = _build_junk_scanner(args)
    junk_results = junk_scanner.scan_all()
    display_scan_results(junk_results)

    if prompt_yes_no("是否继续扫描残留文件？", default=True):
        print(f"\n  {Color.CYAN}正在扫描残留文件...{Color.RESET}")
        residual_scanner = ResidualScanner()
        residual_result = residual_scanner.scan_all()
        display_residual_results(residual_result)

    print(f"\n  {Color.GREEN}扫描完成。使用 'cleancli clean' 执行清理操作。{Color.RESET}\n")


def _do_clean_items(items, dry_run: bool, progress_prefix: str = "  清理中"):
    """执行清理并显示进度"""
    if not items:
        return 0, 0, 0

    total = len(items)
    success = 0
    failed = 0
    freed = 0

    for item in items:
        if total > 20:
            print_progress_bar(success + failed, total, prefix=progress_prefix)

        if dry_run:
            success += 1
            freed += item.size
        else:
            s, f, fr = clean_items([item], dry_run=False)
            success += s
            failed += f
            freed += fr

    if total > 20:
        print_progress_bar(total, total, prefix=progress_prefix)

    return success, failed, freed


def run_junk_clean(args):
    """垃圾文件清理模式"""
    dry_run = getattr(args, "dry_run", False)
    auto_select = getattr(args, "auto", False)
    export_path = getattr(args, "export", None)

    mode_str = "（模拟模式）" if dry_run else ""
    print_header(f"系统垃圾清理{mode_str}")

    disk_info = get_disk_info()
    display_system_info(disk_info, getattr(args, "older_than", 0), getattr(args, "min_size", 0) * 1024)

    print(f"\n  {Color.CYAN}正在扫描系统垃圾文件...{Color.RESET}")
    junk_scanner = _build_junk_scanner(args)
    junk_results = junk_scanner.scan_all()
    total_items, total_size = display_scan_results(junk_results)

    if total_items == 0:
        print_success("系统很干净，没有发现垃圾文件！")
        return

    if auto_select:
        selected = [r for r in junk_results if r.items and not r.error]
    else:
        selected = prompt_category_select(junk_results)

    if not selected:
        print_info("提示", "未选择任何清理类别，操作已取消")
        return

    all_items = []
    categories = {}
    for result in selected:
        all_items.extend(result.items)
        categories[result.category] = len(result.items)

    selected_size = sum(item.size for item in all_items)
    print()
    print_subheader("清理确认")
    print_info("待清理项目", f"{Color.YELLOW}{len(all_items)}{Color.RESET} 个")
    print_info("预计释放空间", f"{Color.YELLOW}{format_size(selected_size)}{Color.RESET}")
    if dry_run:
        print_warning("模拟模式 - 不会实际删除文件")

    for cat, count in categories.items():
        print(f"      {Color.DIM}  {cat}: {count} 项{Color.RESET}")

    if not auto_select and not prompt_yes_no("确认执行清理？", default=False):
        print_info("提示", "操作已取消")
        return

    start_time = time.time()
    print(f"\n  {Color.CYAN}{'模拟' if dry_run else '正在'}清理...{Color.RESET}")
    success, failed, freed = clean_items(all_items, dry_run=dry_run)
    elapsed = time.time() - start_time

    report = CleanReport(
        junk_files_cleaned=success,
        junk_space_freed=freed,
        junk_failed=failed,
        categories=categories,
        dry_run=dry_run,
        elapsed_seconds=elapsed,
    )
    display_clean_report(report)

    if export_path:
        export_report(report, export_path, junk_results=junk_results)


def run_residual_clean(args):
    """残留文件清理模式"""
    dry_run = getattr(args, "dry_run", False)
    auto_select = getattr(args, "auto", False)
    export_path = getattr(args, "export", None)

    mode_str = "（模拟模式）" if dry_run else ""
    print_header(f"残留文件清理{mode_str}")

    print(f"  {Color.CYAN}正在扫描残留文件...{Color.RESET}")
    residual_scanner = ResidualScanner()
    residual_result = residual_scanner.scan_all()
    display_residual_results(residual_result)

    if not residual_result.residual_items:
        print_success("系统很干净，没有发现残留文件！")
        return

    if auto_select:
        selected = [item for item in residual_result.residual_items if item.risk_level == "low"]
    else:
        selected = prompt_residual_select(residual_result)

    if not selected:
        print_info("提示", "未选择任何清理项目，操作已取消")
        return

    selected_size = sum(item.size for item in selected)
    print()
    print_subheader("清理确认")
    print_info("待清理项目", f"{Color.YELLOW}{len(selected)}{Color.RESET} 个")
    print_info("预计释放空间", f"{Color.YELLOW}{format_size(selected_size)}{Color.RESET}")
    if dry_run:
        print_warning("模拟模式 - 不会实际删除文件")

    if not auto_select and not prompt_yes_no("确认执行清理？", default=False):
        print_info("提示", "操作已取消")
        return

    start_time = time.time()
    print(f"\n  {Color.CYAN}{'模拟' if dry_run else '正在'}清理残留文件...{Color.RESET}")

    success = 0
    failed = 0
    freed = 0

    for item in selected:
        print_progress_bar(success + failed, len(selected), prefix="  清理中")
        if dry_run:
            success += 1
            freed += item.size
        else:
            if clean_residual_item(item):
                success += 1
                freed += item.size
            else:
                failed += 1

    print_progress_bar(len(selected), len(selected), prefix="  清理中")
    elapsed = time.time() - start_time

    report = CleanReport(
        residual_files_cleaned=success,
        residual_space_freed=freed,
        residual_failed=failed,
        dry_run=dry_run,
        elapsed_seconds=elapsed,
    )
    display_clean_report(report)

    if export_path:
        export_report(report, export_path, residual_result=residual_result)


def run_full_clean(args):
    """完整清理模式（垃圾文件 + 残留文件）"""
    dry_run = getattr(args, "dry_run", False)
    auto_select = getattr(args, "auto", False)
    export_path = getattr(args, "export", None)

    mode_str = "（模拟模式）" if dry_run else ""
    print_header(f"完整系统清理{mode_str}")

    disk_info = get_disk_info()
    display_system_info(disk_info, getattr(args, "older_than", 0), getattr(args, "min_size", 0) * 1024)

    report = CleanReport(dry_run=dry_run)
    junk_results = None
    residual_result = None
    start_time = time.time()

    # 阶段1: 垃圾文件
    print_subheader("阶段 1/2: 系统垃圾文件清理")
    print(f"  {Color.CYAN}正在扫描系统垃圾文件...{Color.RESET}")

    junk_scanner = _build_junk_scanner(args)
    junk_results = junk_scanner.scan_all()
    total_items, total_size = display_scan_results(junk_results)

    if total_items > 0:
        if auto_select:
            selected_junk = [r for r in junk_results if r.items and not r.error]
        else:
            selected_junk = prompt_category_select(junk_results)

        if selected_junk:
            all_junk_items = []
            categories = {}
            for result in selected_junk:
                all_junk_items.extend(result.items)
                categories[result.category] = len(result.items)

            print(f"\n  {Color.CYAN}{'模拟' if dry_run else '正在'}清理垃圾文件...{Color.RESET}")
            success, failed, freed = clean_items(all_junk_items, dry_run=dry_run)
            report.junk_files_cleaned = success
            report.junk_space_freed = freed
            report.junk_failed = failed
            report.categories = categories
            print_success(f"垃圾{'模拟' if dry_run else ''}清理完成: {success} 项, 释放 {format_size(freed)}")

    # 阶段2: 残留文件
    print_subheader("阶段 2/2: 残留文件清理")
    print(f"\n  {Color.CYAN}正在扫描残留文件...{Color.RESET}")

    residual_scanner = ResidualScanner()
    residual_result = residual_scanner.scan_all()
    display_residual_results(residual_result)

    if residual_result.residual_items:
        if auto_select:
            selected_residual = [item for item in residual_result.residual_items if item.risk_level == "low"]
        else:
            selected_residual = prompt_residual_select(residual_result)

        if selected_residual:
            print(f"\n  {Color.CYAN}{'模拟' if dry_run else '正在'}清理残留文件...{Color.RESET}")
            r_success = 0
            r_failed = 0
            r_freed = 0

            for item in selected_residual:
                print_progress_bar(r_success + r_failed, len(selected_residual), prefix="  清理中")
                if dry_run:
                    r_success += 1
                    r_freed += item.size
                else:
                    if clean_residual_item(item):
                        r_success += 1
                        r_freed += item.size
                    else:
                        r_failed += 1

            print_progress_bar(len(selected_residual), len(selected_residual), prefix="  清理中")

            report.residual_files_cleaned = r_success
            report.residual_space_freed = r_freed
            report.residual_failed = r_failed
            print_success(f"残留{'模拟' if dry_run else ''}清理完成: {r_success} 项, 释放 {format_size(r_freed)}")

    report.elapsed_seconds = time.time() - start_time
    display_clean_report(report)

    if export_path:
        export_report(report, export_path, junk_results, residual_result)


def main():
    parser = argparse.ArgumentParser(
        prog="cleancli",
        description="CleanCLI v2.1 - Windows 系统垃圾深度清理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  cleancli                        交互式完整清理
  cleancli scan                   仅扫描，不清理
  cleancli scan --older-than 30   扫描30天前的垃圾文件
  cleancli clean                  清理垃圾文件
  cleancli clean --auto           自动选择所有垃圾文件清理
  cleancli clean --dry-run        模拟清理（不实际删除）
  cleancli clean --export r.json  清理并导出报告
  cleancli residual               扫描并清理残留文件
  cleancli residual --auto        自动清理低风险残留
  cleancli full                   完整清理（垃圾 + 残留）
  cleancli full --auto --dry-run  模拟完整清理
  cleancli info                   显示系统/磁盘信息

注意: 建议以管理员权限运行以获得最佳清理效果
        """,
    )

    # 全局参数
    parser.add_argument("--no-banner", action="store_true", help="不显示横幅")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # info 命令
    subparsers.add_parser("info", help="显示系统和磁盘信息")

    # 公共参数
    def add_common_args(p):
        p.add_argument("--older-than", type=int, default=0,
                       help="仅清理N天前的文件 (默认: 不限)")
        p.add_argument("--min-size", type=int, default=0,
                       help="仅清理大于N KB的文件 (默认: 不限)")
        p.add_argument("--export", type=str, default=None,
                       help="导出清理报告到指定JSON文件")

    # scan 命令
    scan_parser = subparsers.add_parser("scan", help="仅扫描系统垃圾文件（不执行清理）")
    add_common_args(scan_parser)

    # clean 命令
    clean_parser = subparsers.add_parser("clean", help="清理系统垃圾文件")
    clean_parser.add_argument("--auto", action="store_true", help="自动选择所有类别")
    clean_parser.add_argument("--dry-run", action="store_true", help="模拟模式，不实际删除")
    add_common_args(clean_parser)

    # residual 命令
    residual_parser = subparsers.add_parser("residual", help="扫描并清理残留文件")
    residual_parser.add_argument("--auto", action="store_true", help="自动选择低风险项目")
    residual_parser.add_argument("--dry-run", action="store_true", help="模拟模式，不实际删除")
    residual_parser.add_argument("--export", type=str, default=None, help="导出报告到JSON文件")

    # full 命令
    full_parser = subparsers.add_parser("full", help="完整清理（垃圾文件 + 残留文件）")
    full_parser.add_argument("--auto", action="store_true", help="自动选择所有项目")
    full_parser.add_argument("--dry-run", action="store_true", help="模拟模式，不实际删除")
    add_common_args(full_parser)

    args = parser.parse_args()

    if not getattr(args, "no_banner", False):
        print_banner()

    if not check_admin():
        print_warning("当前未以管理员权限运行，部分清理操作可能受限")
        print_info("提示", "建议右键以管理员身份运行本工具")
        print()

    if args.command is None:
        run_full_clean(args)
    elif args.command == "info":
        run_info()
    elif args.command == "scan":
        run_scan_only(args)
    elif args.command == "clean":
        run_junk_clean(args)
    elif args.command == "residual":
        run_residual_clean(args)
    elif args.command == "full":
        run_full_clean(args)


if __name__ == "__main__":
    main()
