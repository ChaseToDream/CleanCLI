"""
CleanCLI - Windows 系统垃圾清理工具 v3.1
交互式主菜单 + CLI子命令双模式
改进：重试删除/只读清除/错误追踪/占比条/错误汇总
"""

import argparse
import sys
import os
import time

from cleancli.cleaner import JunkScanner, clean_items, get_disk_info, get_error_summary
from cleancli.residual import ResidualScanner, clean_residual_item, ResidualScanResult
from cleancli.ui import (
    C, print_banner, print_header, print_section,
    _info_row, _ok, _warn, _err, _blank, _p, Spinner, print_progress,
    display_scan_results, display_residual_results, display_system_info,
    display_error_summary,
    prompt_yes_no, prompt_category_select, prompt_residual_select,
    prompt_main_menu, prompt_scan_options,
    CleanReport, display_clean_report, export_report, fmt_size,
)


def check_admin() -> bool:
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False


def _admin_warning():
    if not check_admin():
        _warn("未以管理员权限运行，部分操作可能受限")
        _info_row("提示", f"{C.DIM}建议右键以管理员身份运行{C.RST}")
        _blank()


def _build_scanner(older: int = 0, min_kb: int = 0) -> JunkScanner:
    return JunkScanner(older_than_days=older, min_size_bytes=min_kb * 1024)


# ── 核心流程 ──────────────────────────────────────────────────

def do_scan(older: int = 0, min_kb: int = 0):
    """执行扫描，返回 (junk_results, residual_result)"""
    spinner = Spinner("正在扫描系统垃圾文件...")
    for _ in range(8):
        spinner.tick()
        time.sleep(0.05)
    junk_scanner = _build_scanner(older, min_kb)
    junk_results = junk_scanner.scan_all()
    spinner.done(f"垃圾扫描完成")

    display_scan_results(junk_results)

    if prompt_yes_no("是否继续扫描残留文件？", default=True):
        spinner = Spinner("正在扫描残留文件...")
        for _ in range(8):
            spinner.tick()
            time.sleep(0.05)
        residual_scanner = ResidualScanner()
        residual_result = residual_scanner.scan_all()
        spinner.done(f"残留扫描完成")
        display_residual_results(residual_result)
    else:
        residual_result = ResidualScanResult()

    return junk_results, residual_result


def do_clean_junk(junk_results, dry_run: bool = False, auto: bool = False,
                  export_path: str = None) -> CleanReport:
    """执行垃圾清理"""
    total_items, total_size = display_scan_results(junk_results)

    if total_items == 0:
        _ok("系统很干净，没有发现垃圾文件！")
        return CleanReport()

    if auto:
        selected = [r for r in junk_results if r.items and not r.error]
    else:
        selected = prompt_category_select(junk_results)

    if not selected:
        _info_row("提示", "未选择任何类别，操作已取消")
        return CleanReport()

    all_items = []
    categories = {}
    for r in selected:
        all_items.extend(r.items)
        categories[r.category] = len(r.items)

    sel_size = sum(i.size for i in all_items)

    # 确认面板
    print_section("清理确认", icon="CFM")
    _info_row("待清理", f"{C.HYEL}{C.B}{len(all_items)}{C.RST} 个")
    _info_row("预计释放", f"{C.HYEL}{C.B}{fmt_size(sel_size)}{C.RST}")
    if dry_run:
        _warn("模拟模式 - 不会实际删除文件")

    if not auto and not prompt_yes_no("确认执行清理？", default=False):
        _info_row("提示", "操作已取消")
        return CleanReport()

    # 执行清理
    start = time.time()
    label = "模拟清理" if dry_run else "正在清理"
    spinner = Spinner(f"{label}中...")
    for _ in range(6):
        spinner.tick()
        time.sleep(0.03)
    success, failed, freed, details = clean_items(all_items, dry_run=dry_run)
    spinner.done(f"{label}完成: {success} 项, 释放 {fmt_size(freed)}")
    elapsed = time.time() - start

    if failed > 0:
        display_error_summary(get_error_summary(details))

    report = CleanReport(
        junk_files_cleaned=success, junk_space_freed=freed,
        junk_failed=failed, categories=categories,
        dry_run=dry_run, elapsed_seconds=elapsed,
    )
    display_clean_report(report)

    if export_path:
        export_report(report, export_path, junk_results=junk_results)

    return report


def do_clean_residual(dry_run: bool = False, auto: bool = False,
                      export_path: str = None) -> CleanReport:
    """执行残留清理"""
    spinner = Spinner("正在扫描残留文件...")
    for _ in range(8):
        spinner.tick()
        time.sleep(0.05)
    residual_scanner = ResidualScanner()
    residual_result = residual_scanner.scan_all()
    spinner.done("残留扫描完成")

    display_residual_results(residual_result)

    if not residual_result.residual_items:
        _ok("系统很干净，没有发现残留文件！")
        return CleanReport()

    if auto:
        selected = [i for i in residual_result.residual_items if i.risk_level == "low"]
    else:
        selected = prompt_residual_select(residual_result)

    if not selected:
        _info_row("提示", "未选择任何项目，操作已取消")
        return CleanReport()

    sel_size = sum(i.size for i in selected)

    print_section("清理确认", icon="CFM")
    _info_row("待清理", f"{C.HYEL}{C.B}{len(selected)}{C.RST} 个")
    _info_row("预计释放", f"{C.HYEL}{C.B}{fmt_size(sel_size)}{C.RST}")
    if dry_run:
        _warn("模拟模式 - 不会实际删除文件")

    if not auto and not prompt_yes_no("确认执行清理？", default=False):
        _info_row("提示", "操作已取消")
        return CleanReport()

    start = time.time()
    label = "模拟清理" if dry_run else "正在清理"
    success = failed = freed = 0

    for item in selected:
        print_progress(success + failed, len(selected), prefix=f"  {label}")
        if dry_run:
            success += 1
            freed += item.size
        else:
            if clean_residual_item(item):
                success += 1
                freed += item.size
            else:
                failed += 1
    print_progress(len(selected), len(selected), prefix=f"  {label}")

    elapsed = time.time() - start
    report = CleanReport(
        residual_files_cleaned=success, residual_space_freed=freed,
        residual_failed=failed, dry_run=dry_run, elapsed_seconds=elapsed,
    )
    display_clean_report(report)

    if export_path:
        export_report(report, export_path, residual_result=residual_result)

    return report


def do_full_clean(older: int = 0, min_kb: int = 0, dry_run: bool = False,
                  auto: bool = False, export_path: str = None):
    """完整清理流程"""
    report = CleanReport(dry_run=dry_run)
    start = time.time()

    # 阶段1
    print_section("阶段 1/2  垃圾文件清理", icon="1/2")

    spinner = Spinner("正在扫描系统垃圾文件...")
    for _ in range(8):
        spinner.tick()
        time.sleep(0.05)
    junk_scanner = _build_scanner(older, min_kb)
    junk_results = junk_scanner.scan_all()
    spinner.done("垃圾扫描完成")

    total_items, _ = display_scan_results(junk_results)

    if total_items > 0:
        if auto:
            selected_junk = [r for r in junk_results if r.items and not r.error]
        else:
            selected_junk = prompt_category_select(junk_results)

        if selected_junk:
            all_items = []
            categories = {}
            for r in selected_junk:
                all_items.extend(r.items)
                categories[r.category] = len(r.items)

            label = "模拟清理" if dry_run else "正在清理"
            spinner = Spinner(f"{label}垃圾文件...")
            for _ in range(6):
                spinner.tick()
                time.sleep(0.03)
            s, f, fr, details = clean_items(all_items, dry_run=dry_run)
            spinner.done(f"垃圾清理完成: {s} 项, 释放 {fmt_size(fr)}")
            if f > 0:
                display_error_summary(get_error_summary(details))
            report.junk_files_cleaned = s
            report.junk_space_freed = fr
            report.junk_failed = f
            report.categories = categories

    # 阶段2
    print_section("阶段 2/2  残留文件清理", icon="2/2")

    spinner = Spinner("正在扫描残留文件...")
    for _ in range(8):
        spinner.tick()
        time.sleep(0.05)
    residual_scanner = ResidualScanner()
    residual_result = residual_scanner.scan_all()
    spinner.done("残留扫描完成")

    display_residual_results(residual_result)

    if residual_result.residual_items:
        if auto:
            sel_res = [i for i in residual_result.residual_items if i.risk_level == "low"]
        else:
            sel_res = prompt_residual_select(residual_result)

        if sel_res:
            label = "模拟清理" if dry_run else "正在清理"
            rs = rf = rfr = 0
            for item in sel_res:
                print_progress(rs + rf, len(sel_res), prefix=f"  {label}")
                if dry_run:
                    rs += 1
                    rfr += item.size
                else:
                    if clean_residual_item(item):
                        rs += 1
                        rfr += item.size
                    else:
                        rf += 1
            print_progress(len(sel_res), len(sel_res), prefix=f"  {label}")
            _ok(f"残留清理完成: {rs} 项, 释放 {fmt_size(rfr)}")
            report.residual_files_cleaned = rs
            report.residual_space_freed = rfr
            report.residual_failed = rf

    report.elapsed_seconds = time.time() - start
    display_clean_report(report)

    if export_path:
        export_report(report, export_path, junk_results, residual_result)


# ── CLI入口 ──────────────────────────────────────────────────

def _add_common_args(p):
    p.add_argument("--older-than", type=int, default=0, help="仅清理N天前的文件")
    p.add_argument("--min-size", type=int, default=0, help="仅清理大于N KB的文件")
    p.add_argument("--export", type=str, default=None, help="导出报告到JSON文件")


def run_cli():
    """命令行子命令模式"""
    parser = argparse.ArgumentParser(
        prog="cleancli",
        description="CleanCLI v3.0 - Windows 系统垃圾深度清理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  cleancli                        交互式主菜单
  cleancli scan                   仅扫描
  cleancli scan --older-than 30   扫描30天前的垃圾
  cleancli clean --auto           自动清理所有垃圾
  cleancli clean --dry-run        模拟清理
  cleancli residual --auto        自动清理低风险残留
  cleancli full --auto            完整自动清理
  cleancli info                   系统信息
        """,
    )
    parser.add_argument("--no-banner", action="store_true", help="不显示横幅")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="系统和磁盘信息")

    sp = subparsers.add_parser("scan", help="仅扫描（不清理）")
    _add_common_args(sp)

    sp = subparsers.add_parser("clean", help="清理垃圾文件")
    sp.add_argument("--auto", action="store_true", help="自动选择所有类别")
    sp.add_argument("--dry-run", action="store_true", help="模拟模式")
    _add_common_args(sp)

    sp = subparsers.add_parser("residual", help="扫描并清理残留文件")
    sp.add_argument("--auto", action="store_true", help="自动选择低风险项")
    sp.add_argument("--dry-run", action="store_true", help="模拟模式")
    sp.add_argument("--export", type=str, default=None, help="导出报告")

    sp = subparsers.add_parser("full", help="完整清理")
    sp.add_argument("--auto", action="store_true", help="自动选择")
    sp.add_argument("--dry-run", action="store_true", help="模拟模式")
    _add_common_args(sp)

    args = parser.parse_args()

    if not args.no_banner:
        print_banner()
    _admin_warning()

    if args.command is None:
        return False  # 进入交互式菜单
    elif args.command == "info":
        display_system_info(get_disk_info())
    elif args.command == "scan":
        do_scan(getattr(args, "older_than", 0), getattr(args, "min_size", 0))
    elif args.command == "clean":
        spinner = Spinner("扫描中...")
        for _ in range(5):
            spinner.tick()
            time.sleep(0.04)
        scanner = _build_scanner(getattr(args, "older_than", 0), getattr(args, "min_size", 0))
        junk_results = scanner.scan_all()
        spinner.done("扫描完成")
        do_clean_junk(junk_results, dry_run=args.dry_run, auto=args.auto, export_path=args.export)
    elif args.command == "residual":
        do_clean_residual(dry_run=args.dry_run, auto=args.auto, export_path=args.export)
    elif args.command == "full":
        do_full_clean(getattr(args, "older_than", 0), getattr(args, "min_size", 0),
                      dry_run=args.dry_run, auto=args.auto, export_path=args.export)
    return True


def run_interactive():
    """交互式主菜单模式"""
    print_banner()
    _admin_warning()

    while True:
        choice = prompt_main_menu()

        if choice == "quit":
            _blank()
            _p(f"  {C.DIM}感谢使用 CleanCLI，再见！{C.RST}")
            _blank()
            break

        elif choice == "info":
            display_system_info(get_disk_info())
            input(f"\n  {C.DIM}按回车返回主菜单...{C.RST}")

        elif choice == "scan":
            opts = prompt_scan_options()
            do_scan(opts["older_than"], opts["min_size"])
            input(f"\n  {C.DIM}按回车返回主菜单...{C.RST}")

        elif choice == "clean":
            opts = prompt_scan_options()
            spinner = Spinner("扫描中...")
            for _ in range(5):
                spinner.tick()
                time.sleep(0.04)
            scanner = _build_scanner(opts["older_than"], opts["min_size"])
            junk_results = scanner.scan_all()
            spinner.done("扫描完成")
            do_clean_junk(junk_results, dry_run=opts["dry_run"],
                          export_path=opts["export"])
            input(f"\n  {C.DIM}按回车返回主菜单...{C.RST}")

        elif choice == "residual":
            opts = prompt_scan_options()
            do_clean_residual(dry_run=opts["dry_run"], export_path=opts["export"])
            input(f"\n  {C.DIM}按回车返回主菜单...{C.RST}")

        elif choice == "full":
            opts = prompt_scan_options()
            do_full_clean(opts["older_than"], opts["min_size"],
                          dry_run=opts["dry_run"], export_path=opts["export"])
            input(f"\n  {C.DIM}按回车返回主菜单...{C.RST}")


def main():
    # 如果有CLI参数则走CLI模式，否则走交互式菜单
    has_cli_args = len(sys.argv) > 1
    if has_cli_args:
        handled = run_cli()
        if handled:
            return
    run_interactive()


if __name__ == "__main__":
    main()
