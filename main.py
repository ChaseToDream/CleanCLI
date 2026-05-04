"""
CleanCLI - Windows 系统垃圾清理工具
主入口模块：命令行参数解析、流程编排
"""

import argparse
import sys
import os

from cleaner import JunkScanner, clean_items, ScanResult
from residual import ResidualScanner, clean_residual_item
from ui import (
    print_banner, print_header, print_subheader, print_info,
    print_success, print_warning, print_error, print_progress_bar,
    display_scan_results, display_residual_results,
    prompt_yes_no, prompt_category_select, prompt_residual_select,
    CleanReport, display_clean_report, format_size, Color,
)


def check_admin():
    """检查是否以管理员权限运行"""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False


def run_scan_only():
    """仅扫描模式"""
    print_header("系统垃圾扫描")
    print_info("模式", "仅扫描（不清理）")
    print()

    # 扫描垃圾文件
    print(f"  {Color.CYAN}正在扫描系统垃圾文件...{Color.RESET}")
    junk_scanner = JunkScanner()
    junk_results = junk_scanner.scan_all()
    display_scan_results(junk_results)

    # 扫描残留文件
    if prompt_yes_no("是否继续扫描残留文件？", default=True):
        print(f"\n  {Color.CYAN}正在扫描残留文件...{Color.RESET}")
        residual_scanner = ResidualScanner()
        residual_result = residual_scanner.scan_all()
        display_residual_results(residual_result)

    print(f"\n  {Color.GREEN}扫描完成。使用 'cleancli --clean' 执行清理操作。{Color.RESET}\n")


def run_junk_clean(auto_select: bool = False):
    """垃圾文件清理模式"""
    print_header("系统垃圾清理")
    print()

    # 扫描
    print(f"  {Color.CYAN}正在扫描系统垃圾文件...{Color.RESET}")
    junk_scanner = JunkScanner()
    junk_results = junk_scanner.scan_all()

    total_items, total_size = display_scan_results(junk_results)

    if total_items == 0:
        print_success("系统很干净，没有发现垃圾文件！")
        return

    # 选择清理类别
    if auto_select:
        selected = [r for r in junk_results if r.items and not r.error]
    else:
        selected = prompt_category_select(junk_results)

    if not selected:
        print_info("提示", "未选择任何清理类别，操作已取消")
        return

    # 汇总待清理项目
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

    for cat, count in categories.items():
        print(f"      {Color.DIM}• {cat}: {count} 项{Color.RESET}")

    if not auto_select and not prompt_yes_no("确认执行清理？", default=False):
        print_info("提示", "操作已取消")
        return

    # 执行清理
    print()
    print(f"  {Color.CYAN}正在清理...{Color.RESET}")

    success, failed, freed = clean_items(all_items)

    report = CleanReport(
        junk_files_cleaned=success,
        junk_space_freed=freed,
        junk_failed=failed,
        categories=categories,
    )

    display_clean_report(report)


def run_residual_clean(auto_select: bool = False):
    """残留文件清理模式"""
    print_header("残留文件清理")
    print()

    print(f"  {Color.CYAN}正在扫描残留文件...{Color.RESET}")
    residual_scanner = ResidualScanner()
    residual_result = residual_scanner.scan_all()

    display_residual_results(residual_result)

    if not residual_result.residual_items:
        print_success("系统很干净，没有发现残留文件！")
        return

    # 选择清理项目
    if auto_select:
        selected = [item for item in residual_result.residual_items if item.risk_level == "low"]
    else:
        selected = prompt_residual_select(residual_result)

    if not selected:
        print_info("提示", "未选择任何清理项目，操作已取消")
        return

    # 汇总
    selected_size = sum(item.size for item in selected)
    print()
    print_subheader("清理确认")
    print_info("待清理项目", f"{Color.YELLOW}{len(selected)}{Color.RESET} 个")
    print_info("预计释放空间", f"{Color.YELLOW}{format_size(selected_size)}{Color.RESET}")

    if not auto_select and not prompt_yes_no("确认执行清理？", default=False):
        print_info("提示", "操作已取消")
        return

    # 执行清理
    print()
    print(f"  {Color.CYAN}正在清理残留文件...{Color.RESET}")

    success = 0
    failed = 0
    freed = 0

    for item in selected:
        print_progress_bar(success + failed, len(selected), prefix="  清理中")
        if clean_residual_item(item):
            success += 1
            freed += item.size
        else:
            failed += 1

    print_progress_bar(len(selected), len(selected), prefix="  清理中")

    report = CleanReport(
        residual_files_cleaned=success,
        residual_space_freed=freed,
        residual_failed=failed,
    )

    display_clean_report(report)


def run_full_clean(auto_select: bool = False):
    """完整清理模式（垃圾文件 + 残留文件）"""
    print_header("完整系统清理")
    print()

    report = CleanReport()

    # 阶段1: 垃圾文件
    print_subheader("阶段 1/2: 系统垃圾文件清理")
    print(f"  {Color.CYAN}正在扫描系统垃圾文件...{Color.RESET}")

    junk_scanner = JunkScanner()
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

            print(f"\n  {Color.CYAN}正在清理垃圾文件...{Color.RESET}")
            success, failed, freed = clean_items(all_junk_items)
            report.junk_files_cleaned = success
            report.junk_space_freed = freed
            report.junk_failed = failed
            report.categories = categories
            print_success(f"垃圾清理完成: {success} 项已清理, 释放 {format_size(freed)}")

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
            print(f"\n  {Color.CYAN}正在清理残留文件...{Color.RESET}")
            r_success = 0
            r_failed = 0
            r_freed = 0

            for item in selected_residual:
                print_progress_bar(r_success + r_failed, len(selected_residual), prefix="  清理中")
                if clean_residual_item(item):
                    r_success += 1
                    r_freed += item.size
                else:
                    r_failed += 1

            print_progress_bar(len(selected_residual), len(selected_residual), prefix="  清理中")

            report.residual_files_cleaned = r_success
            report.residual_space_freed = r_freed
            report.residual_failed = r_failed
            print_success(f"残留清理完成: {r_success} 项已清理, 释放 {format_size(r_freed)}")

    # 总报告
    display_clean_report(report)


def main():
    parser = argparse.ArgumentParser(
        prog="cleancli",
        description="CleanCLI - Windows 系统垃圾清理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  cleancli                  交互式完整清理
  cleancli scan             仅扫描，不清理
  cleancli clean            清理垃圾文件
  cleancli clean --auto     自动选择所有垃圾文件清理
  cleancli residual         扫描并清理残留文件
  cleancli full             完整清理（垃圾 + 残留）

注意: 建议以管理员权限运行以获得最佳清理效果
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan 命令
    subparsers.add_parser("scan", help="仅扫描系统垃圾文件（不执行清理）")

    # clean 命令
    clean_parser = subparsers.add_parser("clean", help="清理系统垃圾文件")
    clean_parser.add_argument("--auto", action="store_true", help="自动选择所有类别")

    # residual 命令
    residual_parser = subparsers.add_parser("residual", help="扫描并清理残留文件")
    residual_parser.add_argument("--auto", action="store_true", help="自动选择低风险项目")

    # full 命令
    full_parser = subparsers.add_parser("full", help="完整清理（垃圾文件 + 残留文件）")
    full_parser.add_argument("--auto", action="store_true", help="自动选择所有项目")

    args = parser.parse_args()

    # 打印横幅
    print_banner()

    # 检查管理员权限
    if not check_admin():
        print_warning("当前未以管理员权限运行，部分清理操作可能受限")
        print_info("提示", "建议右键以管理员身份运行本工具")
        print()

    # 无参数时进入交互式完整清理
    if args.command is None:
        run_full_clean(auto_select=False)
    elif args.command == "scan":
        run_scan_only()
    elif args.command == "clean":
        run_junk_clean(auto_select=args.auto)
    elif args.command == "residual":
        run_residual_clean(auto_select=args.auto)
    elif args.command == "full":
        run_full_clean(auto_select=args.auto)


if __name__ == "__main__":
    main()
